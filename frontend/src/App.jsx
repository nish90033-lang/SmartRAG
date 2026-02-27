import { useState } from "react"
import axios from "axios"

const API = "https://smartrag-backend.onrender.com"

export default function App() {
  const [page, setPage] = useState("upload")
  const [file, setFile] = useState(null)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [expandedSource, setExpandedSource] = useState(null)

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setUploadStatus(null)
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await axios.post(`${API}/upload`, formData)
      setUploadStatus({ success: true, data: res.data })
    } catch (err) {
      setUploadStatus({ success: false, message: err.response?.data?.detail || "Upload failed." })
    }
    setUploading(false)
  }

  async function handleQuery() {
    if (!question.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const res = await axios.post(`${API}/query`, { question, use_llm: true })
      setResult(res.data)
      setHistory(prev => [{ question, answer: res.data.answer }, ...prev])
    } catch (err) {
      setResult({ answer: "Something went wrong. Is the backend running?", answerable: false, sources: [] })
    }
    setLoading(false)
    setQuestion("")
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
      width: "100%",
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      color: "white",
      padding: "40px 20px"
    }}>
      <div style={{ maxWidth: 820, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{ fontSize: 52, marginBottom: 12 }}>🧠</div>
          <h1 style={{
            margin: 0, fontSize: 42, fontWeight: 800,
            background: "linear-gradient(90deg, #38bdf8, #818cf8, #c084fc)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>
            SmartRAG
          </h1>
          <p style={{ color: "#94a3b8", marginTop: 10, fontSize: 16 }}>
            Upload documents · Ask questions · Get answers with sources
          </p>
          <span style={{
            display: "inline-block", marginTop: 10, fontSize: 12, fontWeight: 600,
            padding: "4px 14px", borderRadius: 99,
            background: "rgba(56,189,248,0.15)", color: "#38bdf8",
            border: "1px solid rgba(56,189,248,0.3)"
          }}>
            ✦ Powered by Groq · Llama 3
          </span>
        </div>

        {/* Nav */}
        <div style={{
          display: "flex", justifyContent: "center", gap: 8, marginBottom: 36,
          background: "rgba(255,255,255,0.05)", borderRadius: 14, padding: 6,
          backdropFilter: "blur(10px)", border: "1px solid rgba(255,255,255,0.1)",
          width: "fit-content", margin: "0 auto 36px"
        }}>
          {[
            { id: "upload", label: "Upload", icon: "📄" },
            { id: "chat", label: "Chat", icon: "💬" },
            { id: "history", label: "History", icon: "🕘" }
          ].map(p => (
            <button key={p.id} onClick={() => setPage(p.id)} style={{
              padding: "10px 28px", borderRadius: 10, border: "none",
              cursor: "pointer", fontWeight: 600, fontSize: 14, transition: "all 0.2s",
              background: page === p.id
                ? "linear-gradient(135deg, #38bdf8, #818cf8)"
                : "transparent",
              color: page === p.id ? "white" : "#94a3b8",
              boxShadow: page === p.id ? "0 4px 15px rgba(56,189,248,0.3)" : "none"
            }}>
              {p.icon} {p.label}
            </button>
          ))}
        </div>

        {/* Upload Page */}
        {page === "upload" && (
          <div style={{
            background: "rgba(255,255,255,0.05)", borderRadius: 20, padding: 40,
            border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(10px)"
          }}>
            <h2 style={{ marginTop: 0, fontSize: 24, fontWeight: 700 }}>Upload a Document</h2>
            <p style={{ color: "#94a3b8", marginBottom: 28 }}>
              Supports PDF files. The document will be chunked, embedded, and indexed for semantic search.
            </p>

            <label style={{
              display: "block", border: "2px dashed rgba(56,189,248,0.4)",
              borderRadius: 14, padding: "36px 20px", textAlign: "center",
              cursor: "pointer", marginBottom: 24, transition: "all 0.2s",
              background: file ? "rgba(56,189,248,0.08)" : "transparent"
            }}>
              <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])}
                style={{ display: "none" }} />
              <div style={{ fontSize: 36, marginBottom: 10 }}>
                {file ? "📄" : "☁️"}
              </div>
              <div style={{ fontWeight: 600, color: file ? "#38bdf8" : "#64748b" }}>
                {file ? file.name : "Click to choose a PDF file"}
              </div>
              {!file && <div style={{ fontSize: 13, color: "#475569", marginTop: 6 }}>or drag and drop</div>}
            </label>

            <button onClick={handleUpload} disabled={!file || uploading} style={{
              width: "100%", padding: "14px", fontSize: 16, fontWeight: 700,
              border: "none", borderRadius: 12, cursor: !file || uploading ? "not-allowed" : "pointer",
              background: !file || uploading
                ? "rgba(255,255,255,0.1)"
                : "linear-gradient(135deg, #38bdf8, #818cf8)",
              color: !file || uploading ? "#475569" : "white",
              boxShadow: !file || uploading ? "none" : "0 4px 20px rgba(56,189,248,0.3)",
              transition: "all 0.2s"
            }}>
              {uploading ? "⏳ Indexing document..." : "🚀 Upload & Index"}
            </button>

            {uploadStatus && (
              <div style={{
                marginTop: 24, padding: 20, borderRadius: 12,
                background: uploadStatus.success ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
                border: `1px solid ${uploadStatus.success ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`
              }}>
                {uploadStatus.success ? (
                  <>
                    <p style={{ margin: 0, color: "#4ade80", fontWeight: 700, fontSize: 16 }}>
                      ✅ Document indexed successfully!
                    </p>
                    <div style={{ display: "flex", gap: 20, marginTop: 12, flexWrap: "wrap" }}>
                      {[
                        { label: "Doc ID", value: uploadStatus.data.doc_id },
                        { label: "Chunks", value: uploadStatus.data.chunk_count },
                        { label: "Trust Score", value: uploadStatus.data.trust_score },
                      ].map(item => (
                        <div key={item.label} style={{
                          background: "rgba(255,255,255,0.05)", borderRadius: 8,
                          padding: "8px 16px", flex: 1, minWidth: 100, textAlign: "center"
                        }}>
                          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>{item.label}</div>
                          <div style={{ fontWeight: 700, color: "#4ade80" }}>{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p style={{ margin: 0, color: "#f87171" }}>❌ {uploadStatus.message}</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Chat Page */}
        {page === "chat" && (
          <div>
            <div style={{
              background: "rgba(255,255,255,0.05)", borderRadius: 20, padding: 32,
              border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(10px)", marginBottom: 24
            }}>
              <h2 style={{ marginTop: 0, fontSize: 22 }}>Ask a Question</h2>
              <p style={{ color: "#94a3b8", marginBottom: 20, fontSize: 14 }}>
                Make sure you've uploaded a document first. Press Enter or click Ask.
              </p>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleQuery()}
                  placeholder="e.g. What are the main findings of this document?"
                  style={{
                    flex: 1, padding: "14px 18px", borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.15)",
                    background: "rgba(255,255,255,0.08)",
                    color: "white", fontSize: 15, outline: "none"
                  }}
                />
                <button onClick={handleQuery} disabled={loading || !question.trim()} style={{
                  padding: "14px 28px", fontWeight: 700, fontSize: 15,
                  background: loading ? "rgba(255,255,255,0.1)" : "linear-gradient(135deg, #38bdf8, #818cf8)",
                  color: loading ? "#475569" : "white", border: "none", borderRadius: 12,
                  cursor: loading ? "not-allowed" : "pointer",
                  boxShadow: loading ? "none" : "0 4px 15px rgba(56,189,248,0.3)"
                }}>
                  {loading ? "⏳" : "Ask →"}
                </button>
              </div>
            </div>

            {loading && (
              <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
                Searching through your documents...
              </div>
            )}

            {result && (
              <div style={{
                background: "rgba(255,255,255,0.05)", borderRadius: 20, padding: 32,
                border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(10px)"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700, padding: "4px 12px", borderRadius: 99,
                    background: result.answerable ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                    color: result.answerable ? "#4ade80" : "#f87171",
                    border: `1px solid ${result.answerable ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`
                  }}>
                    {result.answerable ? "✅ Answered" : "❌ Unanswerable"}
                  </span>
                </div>

                <p style={{ lineHeight: 1.8, fontSize: 15, color: "#e2e8f0", marginBottom: 28 }}>
                  {result.answer}
                </p>

                {result.sources?.length > 0 && (
                  <>
                    <div style={{ borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 24, marginBottom: 16 }}>
                      <p style={{ margin: 0, fontWeight: 700, color: "#818cf8", fontSize: 14 }}>
                        📚 {result.sources.length} Sources Used
                      </p>
                    </div>
                    {result.sources.map((src, i) => (
                      <div key={i} style={{
                        marginBottom: 10, borderRadius: 12,
                        border: "1px solid rgba(255,255,255,0.1)",
                        overflow: "hidden", background: "rgba(255,255,255,0.03)"
                      }}>
                        <div onClick={() => setExpandedSource(expandedSource === i ? null : i)}
                          style={{
                            padding: "12px 18px", cursor: "pointer",
                            display: "flex", justifyContent: "space-between", alignItems: "center"
                          }}>
                          <span style={{ fontWeight: 600, fontSize: 13, color: "#c084fc" }}>
                            📄 {src.doc_id} · Chunk {src.chunk_index}
                          </span>
                          <span style={{ fontSize: 12, color: "#64748b" }}>
                            Relevance: <strong style={{ color: "#38bdf8" }}>{src.relevance_score}</strong>
                            &nbsp;· Trust: <strong style={{ color: "#4ade80" }}>{src.trust_score}</strong>
                            &nbsp;{expandedSource === i ? "▲" : "▼"}
                          </span>
                        </div>
                        {expandedSource === i && (
                          <div style={{
                            padding: "14px 18px", fontSize: 13, color: "#94a3b8",
                            lineHeight: 1.7, borderTop: "1px solid rgba(255,255,255,0.08)"
                          }}>
                            {src.excerpt}
                          </div>
                        )}
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* History Page */}
        {page === "history" && (
          <div>
            <h2 style={{ marginTop: 0 }}>Chat History</h2>
            {history.length === 0 ? (
              <div style={{
                textAlign: "center", padding: 60,
                background: "rgba(255,255,255,0.03)", borderRadius: 20,
                border: "1px solid rgba(255,255,255,0.08)", color: "#475569"
              }}>
                <div style={{ fontSize: 40, marginBottom: 16 }}>💬</div>
                No questions asked yet. Go to Chat to get started.
              </div>
            ) : (
              history.map((item, i) => (
                <div key={i} style={{
                  marginBottom: 16, background: "rgba(255,255,255,0.05)", borderRadius: 14,
                  padding: 22, border: "1px solid rgba(255,255,255,0.1)"
                }}>
                  <p style={{ margin: "0 0 10px", fontWeight: 700, color: "#38bdf8" }}>
                    Q: {item.question}
                  </p>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: 14, lineHeight: 1.7 }}>
                    {item.answer}
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        {/* Footer */}
        <div style={{ textAlign: "center", marginTop: 48, color: "#334155", fontSize: 13 }}>
          SmartRAG · Built with FastAPI + ChromaDB + Sentence Transformers
        </div>
      </div>
    </div>
  )
}