from flask import Flask, request, jsonify, send_from_directory
import os
import tempfile
from sentence_transformers import SentenceTransformer, CrossEncoder
import faiss
import pickle
import pymupdf
from langchain.text_splitter import CharacterTextSplitter
import numpy as np
from groq import Groq
from dotenv import load_dotenv

app = Flask(__name__,static_folder='build')

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set")

# Create data directory if it doesn't exist
DATA_DIR = 'backend'
os.makedirs(DATA_DIR, exist_ok=True)

# Paths for FAISS index and metadata
FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'faiss_index.bin')
METADATA_PATH = os.path.join(DATA_DIR, 'metadata.pkl')

# Load models once at startup
try:
    embed_model = SentenceTransformer('all-minilm-l6-v2')
    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
except Exception as e:
    print(f"Error loading models: {e}")
    raise

# In-memory storage for previous responses
previous_responses = []

def extract_split_text(pdf_path):
    """Extract text from PDF and split into chunks."""
    try:
        doc = pymupdf.open(pdf_path)
        text = [page.get_text("text") for page in doc]
        doc.close()  # Properly close the document
        
        if not any(text):
            return None, "No text extracted! The PDF may be image-based."
        full_text = "\n\n".join(text)
    except Exception as e:
        return None, f"Error opening PDF: {e}"

    try:
        text_splitter = CharacterTextSplitter(
            separator="\n\n",
            chunk_size=200,
            chunk_overlap=10
        )
        docs = text_splitter.create_documents([full_text])
        return docs, "Successfully extracted text from all pages."
    except Exception as e:
        return None, f"Error splitting text: {e}"

def store_embeddings_in_faiss(docs):
    """Generate embeddings and store in FAISS."""
    try:
        text_chunks = [doc.page_content for doc in docs]
        embeddings = embed_model.encode(text_chunks, convert_to_numpy=True)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        d = embeddings.shape[1]
        index = faiss.IndexFlatIP(d)
        index.add(embeddings)
        faiss.write_index(index, FAISS_INDEX_PATH)

        with open(METADATA_PATH, "wb") as f:
            pickle.dump(text_chunks, f)
        return True, "Successfully stored embeddings"
    except Exception as e:
        return False, f"Error storing embeddings: {e}"

def multi_hop_search_rerank_and_answer(query, faiss_index_path=FAISS_INDEX_PATH, metadata_path=METADATA_PATH,top_k=5):
    

    if not os.path.exists(faiss_index_path) or not os.path.exists(metadata_path):
        return "Please upload a PDF first."

    try:
        
        index = faiss.read_index(faiss_index_path)
        with open(metadata_path, "rb") as f:
            text_chunks = pickle.load(f)

        def retrieve_context(input_query):
            
            query_embedding = embed_model.encode([input_query], convert_to_numpy=True)
            query_embedding = query_embedding / np.linalg.norm(query_embedding)

            distances, indices = index.search(query_embedding, top_k)
            retrieved_chunks = [text_chunks[idx] for idx in indices[0]]

            
            rerank_pairs = [[input_query, chunk] for chunk in retrieved_chunks]
            scores = reranker.predict(rerank_pairs)

           
            ranked_results = sorted(zip(retrieved_chunks, scores), key=lambda x: x[1], reverse=True)
            top_chunks = [chunk for chunk, _ in ranked_results[:5]]  # Take top 3

          
            return "\n\n".join(top_chunks)

        initial_context = retrieve_context(query)

        client = Groq(api_key=GROQ_API_KEY)

        followup_prompt = (
            "Based on the following context extracted from a document, generate a clarifying query "
            "or specify additional details needed to answer the user's question more completely.\n\n"
            f"Context: {initial_context}\n\n"
            f"User Query: {query}\n\n"
            "Clarifying Query:"
        )

        followup_response = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[
                {"role": "system", "content": "You are an AI assistant that generates clarifying queries to enhance information retrieval."},
                {"role": "user", "content": followup_prompt}
            ],
        )
        followup_query = followup_response.choices[0].message.content.strip()

        additional_context = retrieve_context(followup_query)

        combined_context = initial_context + "\n\n" + additional_context

        system_prompt = (
            "You are an AI assistant answering questions based on a PDF document. "
            "Use the provided text context to generate an accurate response. "
            "Generate a long elaborated answer with respect to context so that the user understands it better. "
            "If the answer is not in the context, say 'I couldn't find an answer in the document.'"
        )

        # Final answer generation using the combined context
        final_response = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {combined_context}\n\nUser Query: {query}"}
            ],
        )

        # Return the generated answer
        answer = final_response.choices[0].message.content
        previous_responses.append({'query': query, 'answer': answer})
        return answer

    except Exception as e:
        return f"Error processing query: {str(e)}"

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    """Handle PDF upload and processing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    try:
        # Use a temporary file for storage
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            pdf_path = temp_file.name
        
        # Process the PDF
        docs, message = extract_split_text(pdf_path)
        
        # Clean up the temporary file
        os.unlink(pdf_path)
        
        if docs is None:
            return jsonify({'error': message}), 400
        
        success, msg = store_embeddings_in_faiss(docs)
        if not success:
            return jsonify({'error': msg}), 500
        
        return jsonify({'message': 'PDF processed successfully', 'details': message}), 200
    
    except Exception as e:
        return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500

@app.route('/ask', methods=['POST'])
def ask():
    """Handle user query and return response."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        query = data.get('query')
        if not query or not isinstance(query, str) or query.strip() == '':
            return jsonify({'error': 'No valid query provided'}), 400
        
        answer = search_rerank_and_answer(query)
        return jsonify({
            'success': True,
            'answer': answer,
            'previous_responses': previous_responses
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error processing request: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join('build', path)):
        return send_from_directory('build', path)
    else:
        return send_from_directory('build', 'index.html')

# This should be at the end of your file
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
