"use client"

// App.js
import { useState } from "react"
import { FaCloudUploadAlt, FaPaperPlane, FaTrash, FaFileAlt, FaRobot, FaHistory } from "react-icons/fa"
import "./App.css"

function App() {
  const [file, setFile] = useState(null)
  const [query, setQuery] = useState("")
  const [answer, setAnswer] = useState("")
  const [previousResponses, setPreviousResponses] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState("")
  const [error, setError] = useState("")
  const [pdfUploaded, setPdfUploaded] = useState(false)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile && selectedFile.type === "application/pdf") {
      setFile(selectedFile)
      setError("")
    } else if (selectedFile) {
      setError("Please select a PDF file")
      setFile(null)
    }
  }

  const handleFileUpload = async () => {
    if (!file) {
      setError("Please select a file first")
      return
    }

    setLoading(true)
    setUploadStatus("Uploading PDF...")
    setError("")

    const formData = new FormData()
    formData.append("file", file)

    try {
      const response = await fetch("/upload_pdf", {
        method: "POST",
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || "Failed to upload PDF")
      }

      setUploadStatus("PDF processed successfully!")
      setPdfUploaded(true)
      setFile(null)
    } catch (err) {
      setError(err.message || "Error uploading PDF")
      setUploadStatus("")
    } finally {
      setLoading(false)
    }
  }

  const handleQuerySubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) {
      setError("Please enter a query")
      return
    }

    if (!pdfUploaded) {
      setError("Please upload a PDF first")
      return
    }

    setLoading(true)
    setError("")

    try {
      const response = await fetch("/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || "Failed to get answer")
      }

      setAnswer(data.answer)
      setPreviousResponses(data.previous_responses || [])
    } catch (err) {
      setError(err.message || "Error getting answer")
    } finally {
      setLoading(false)
    }
  }

  const clearConversation = () => {
    setAnswer("")
    setPreviousResponses([])
    setQuery("")
  }

  // Custom loading spinner component with improved animation
  const LoadingSpinner = () => (
    <div className="flex items-center justify-center">
      <svg
        className="spinner"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
          strokeOpacity="0.2"
        />
        <path
          d="M12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )

  return (
    <div className="app-container">
      <header>
        <h1>PDF Query Assistant</h1>
        <p>Upload a PDF and ask questions about its content</p>
      </header>

      <main>
        <section className="upload-section">
          <h2>
            <FaFileAlt /> Upload Your PDF
          </h2>
          <div className="upload-container">
            <label className="file-input-label">
              <input type="file" onChange={handleFileChange} className="file-input" accept=".pdf" disabled={loading} />
              <div className={`upload-box ${!file && !loading ? "pulse" : ""}`}>
                <FaCloudUploadAlt size={48} />
                <p>{file ? file.name : "Choose PDF file or drag & drop here"}</p>
              </div>
            </label>
            <button onClick={handleFileUpload} disabled={!file || loading} className="upload-button">
              {loading ? (
                <LoadingSpinner />
              ) : (
                <>
                  <FaCloudUploadAlt /> Upload PDF
                </>
              )}
            </button>
          </div>
          {uploadStatus && <p className="status-message success">{uploadStatus}</p>}
        </section>

        <section className="query-section glass-effect">
          <h2>
            <FaRobot /> Ask Questions About Your PDF
          </h2>
          <form onSubmit={handleQuerySubmit} className="query-form">
            <div className="input-container">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a question about the PDF content..."
                disabled={loading || !pdfUploaded}
                className="query-input"
              />
              <button type="submit" disabled={loading || !pdfUploaded} className="submit-button">
                {loading ? <LoadingSpinner /> : <FaPaperPlane />}
              </button>
            </div>
          </form>

          {error && <p className="error-message">{error}</p>}

          {answer && (
            <div className="response-container">
              <div className="response-header">
                <h3>Answer</h3>
                <button onClick={clearConversation} className="clear-button">
                  <FaTrash /> Clear
                </button>
              </div>
              <div className="current-response">
                <p className="query-text">
                  <strong>Q:</strong> {query}
                </p>
                <p className="answer-text">
                  <strong>A:</strong> {answer}
                </p>
              </div>
            </div>
          )}
        </section>

        {previousResponses.length > 1 && (
          <section className="history-section">
            <h2>
              <FaHistory /> Previous Questions & Answers
            </h2>
            <div className="history-container">
              {previousResponses.slice(0, -1).map((item, index) => (
                <div key={index} className="history-item">
                  <p className="query-text">
                    <strong>Q:</strong> {item.query}
                  </p>
                  <p className="answer-text">
                    <strong>A:</strong> {item.answer}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default App

