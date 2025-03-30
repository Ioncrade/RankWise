# RankWise

A Retrieval-Augmented Generation (RAG) application that allows users to upload PDF documents and ask questions about their content. The application extracts text from PDFs, creates embeddings for efficient search, and uses an LLM to generate accurate answers based on the document's content.

![PDF Query Assistant Screenshot](https://via.placeholder.com/800x450)

## Features

- 📄 PDF upload and processing
- 🔍 Semantic search using FAISS vector database
- 🤖 Natural language question answering with Groq's LLM
- 📊 Response history tracking
- 💻 Clean, responsive user interface

## Architecture

This application consists of two main components:

1. **Flask Backend**: Handles PDF processing, vector search, and LLM integration
2. **React Frontend**: Provides an intuitive user interface

### Technical Stack

- **Backend**:
  - Flask (Python web framework)
  - Sentence-Transformers (for text embeddings)
  - FAISS (for vector search)
  - PyMuPDF (for PDF text extraction)
  - Groq API (for LLM capabilities)

- **Frontend**:
  - React (JavaScript library)
  - React Icons (for UI elements)
  - CSS3 (for styling)

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 14+
- npm 6+
- Groq API key

### Installation

#### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pdf-query-assistant.git
   cd pdf-query-assistant
   ```

2. Set up a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the backend directory with your Groq API key:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

#### Frontend Setup

1. Install frontend dependencies:
   ```bash
   cd ../frontend
   npm install
   ```

### Development Mode

1. Start the Flask backend (from the backend directory):
   ```bash
   python app.py
   ```
   This will start the Flask server at http://localhost:5000

2. In a separate terminal, start the React frontend (from the frontend directory):
   ```bash
   npm start
   ```
   This will start the React development server at http://localhost:3000

3. Open your browser and navigate to http://localhost:3000

### Production Deployment

1. Build the React frontend:
   ```bash
   cd frontend
   npm run build
   ```

2. Copy the build directory to your backend directory:
   ```bash
   cp -r build ../backend/
   ```

3. Run the Flask application:
   ```bash
   cd ../backend
   python app.py
   ```

4. Access the application at http://localhost:5000

## Usage Guide

1. **Upload a PDF**:
   - Click on the upload area or drag and drop a PDF file
   - Click the "Upload PDF" button
   - Wait for processing to complete

2. **Ask Questions**:
   - Type your question about the PDF content in the input field
   - Click the send button or press Enter
   - View the AI-generated answer

3. **Review History**:
   - Scroll down to see previous questions and answers
   - Click "Clear" to reset the conversation

## How It Works

1. **PDF Processing Pipeline**:
   - Text extraction from PDF
   - Chunking text into smaller segments
   - Generating embeddings for each text chunk
   - Storing embeddings in a FAISS vector database

2. **Query Processing**:
   - Embedding the user query
   - Semantic search in the vector database
   - Reranking search results
   - Constructing context from top results
   - Generating an answer using Groq's LLM

## Project Structure

```
pdf-query-assistant/
├── backend/
│   ├── app.py              # Main Flask application
│   ├── requirements.txt    # Python dependencies
│   └── .env                # Environment variables
├── frontend/
│   ├── public/             # Static assets
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── App.css         # Application styles
│   │   └── index.js        # React entry point
│   ├── package.json        # Node.js dependencies
│   └── README.md           # Frontend documentation
└── README.md               # Main project documentation
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- [Sentence-Transformers](https://www.sbert.net/) for the embedding models
- [FAISS](https://github.com/facebookresearch/faiss) for efficient similarity search
- [Groq](https://groq.com/) for the LLM API
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) for PDF processing
- [React](https://reactjs.org/) for the frontend framework
