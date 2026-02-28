import { useState, useEffect } from "react"
import axios from "axios"
import { createClient } from "@supabase/supabase-js"

const API = "https://smartrag-backend.onrender.com"
const supabase = createClient(
  "https://nnlbggpbudktmzagigcj.supabase.co",
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ubGJnZ3BidWRrdG16YWdpZ2NqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIyNjUyODYsImV4cCI6MjA4Nzg0MTI4Nn0.KRoz705J6yRHTOaigg69iWlBVuUXyglVSJz0aAi3Yi4"
)

export default function App() {
  const [session, setSession] = useState(null)
  const [page, setPage] = useState("documents")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [authMode, setAuthMode] = useState("login")
  const [authError, setAuthError] = useState("")
  const [authLoading, setAuthLoading] = useState(false)

  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedDoc, setSelectedDoc] = useState(null)

  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [expandedSource, setExpandedSource] = useState(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => setSession(session))
    supabase.auth.onAuthStateChange((_event, session) => setSession(session))
  }, [])

  useEffect(() => {
    if (session) fetchDocuments()
  }, [session])

  const authHeaders = () => ({
    Authorization: `Bearer ${session?.access_token}`
  })

  async function fetchDocuments() {
    try {
      const res = await axios.get(`${API}/documents`, { headers: authHeaders() })
      setDocuments(res.data.documents || [])
    } catch (e) {
      console.error(e)
    }
  }

  async function fetchHistory() {
    try {
      const res = await axios.get(`${API}/history`, { headers: authHeaders() })
      setHistory(res.data.history || [])
    } catch (e) {
      console.error(e)
    }
  }

  async function handleAuth() {
    setAuthLoading(true)
    setAuthError("")
    try {
      if (authMode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) setAuthError(error.message)
      } else {
        const { error } = await supabase.auth.signUp({ email, password })
        if (error) setAuthError(error.message)
        else setAuthError("Check your email to confirm your account!")
      }
    } catch (e) {
      setAuthError("Something went wrong.")
    }
    setAuthLoading(false)
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setUploadStatus(null)
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await axios.post(`${API}/upload`, formData, { headers: authHeaders() })
      setUploadStatus({ success: true, data: res.data })
      fetchDocuments()
    } catch (err) {
      setUploadStatus({ success: false, message: err.response?.data?.detail || "Upload failed." })
    }
    setUploading(false)
  }

  async function handleQuery() {
    if (!question.trim() || !selectedDoc) return
    setLoading(true)
    setResult(null)
    try {
      const res = await axios.post(`${API}/query`, {
        question,
        use_llm: true,
        doc_id: selectedDoc
      }, { headers: authHeaders() })
      setResult(res.data)
    } catch (err) {
      setResult({ answer: "Something went wrong.", answerable: false, sources: [] })
    }
    setLoading(false)
    setQuestion("")
  }

  // Auth Screen
  if (!session) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
        fontFamily: "'Segoe UI', system-ui, sans-serif"
      }}>
        <div style={{
          width: 420, background: "rgba(255,255,255,0.05)", borderRadius: 20,
          padding: 40, border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(10px)"
        }}>
          <div style={{ textAlign: "center", marginBottom: 32 }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>🧠</div>
            <h1 style={{
              margin: 0, fontSize: 32, fontWeight: 800,
              background: "linear-gradient(90deg, #38bdf8, #818cf8)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
            }}>SmartRAG</h1>
            <p style={{ color: "#94a3b8", marginTop: 8, fontSize: 14 }}>
              AI-powered document intelligence
            </p>
          </div>

          <div style={{ display: "flex", marginBottom: 24, background: "rgba(255,255,255,0.05)", borderRadius: 10, padding: 4 }}>
            {["login", "signup"].map(mode => (
              <button key={mode} onClick={() => setAuthMode(mode)} style={{
                flex: 1, padding: "8px", border: "none", borderRadius: 8, cursor: "pointer",
                fontWeight: 600, fontSize: 14,
                background: authMode === mode ? "linear-gradient(135deg, #38bdf8, #818cf8)" : "transparent",
                color: authMode === mode ? "white" : "#94a3b8"
              }}>
                {mode === "login" ? "Sign In" : "Sign Up"}
              </button>
            ))}
          </div>

          <input
            type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)}
            style={{
              width: "100%", padding: "12px 16px", marginBottom: 12, borderRadius: 10,
              border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.08)",
              color: "white", fontSize: 14, outline: "none", boxSizing: "border-box"
            }}
          />
          <input
            type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAuth()}
            style={{
              width: "100%", padding: "12px 16px", marginBottom: 20, borderRadius: 10,
              border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.08)",
              color: "white", fontSize: 14, outline: "none", boxSizing: "border-box"
            }}
          />

          {authError && (
            <div style={{
              marginBottom: 16, padding: 12, borderRadius: 8, fontSize: 13,
              background: authError.includes("Check") ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
              color: authError.includes("Check") ? "#4ade80" : "#f87171",
              border: `1px solid ${authError.includes("Check") ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`
            }}>
              {authError}
            </div>
          )}

          <button onClick={handleAuth} disabled={authLoading} style={{
            width: "100%", padding: "13px", fontWeight: 700, fontSize: 15,
            background: "linear-gradient(135deg, #38bdf8, #818cf8)",
            color: "white", border: "none", borderRadius: 10, cursor: "pointer",
            boxShadow: "0 4px 20px rgba(56,189,248,0.3)"
          }}>
            {authLoading ? "Please wait..." : authMode === "login" ? "Sign In →" : "Create Account →"}
          </button>
        </div>
      </div>
    )
  }

  // Main App
  return (
    <div style={{
      minHeight: "100vh", display: "flex",
      background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
      fontFamily: "'Segoe UI', system-ui, sans-serif", color: "white"
    }}>
      {/* Sidebar */}
      <div style={{
        width: 240, background: "rgba(0,0,0,0.3)", borderRight: "1px solid rgba(255,255,255,0.08)",
        padding: "24px 16px", display: "flex", flexDirection: "column"
      }}>
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 24, marginBottom: 4 }}>🧠</div>
          <h2 style={{
            margin: 0, fontSize: 20, fontWeight: 800,
            background: "linear-gradient(90deg, #38bdf8, #818cf8)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>SmartRAG</h2>
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "#475569" }}>Document Intelligence</p>
        </div>

        {[
          { id: "documents", icon: "📄", label: "Documents" },
          { id: "chat", icon: "💬", label: "Chat" },
          { id: "history", icon: "🕘", label: "History" },
        ].map(item => (
          <button key={item.id} onClick={() => { setPage(item.id); if (item.id === "history") fetchHistory() }} style={{
            display: "flex", alignItems: "center", gap: 10, width: "100%",
            padding: "11px 14px", marginBottom: 4, borderRadius: 10, border: "none",
            cursor: "pointer", fontWeight: 600, fontSize: 14, textAlign: "left",
            background: page === item.id ? "linear-gradient(135deg, rgba(56,189,248,0.2), rgba(129,140,248,0.2))" : "transparent",
            color: page === item.id ? "#38bdf8" : "#64748b",
            borderLeft: page === item.id ? "2px solid #38bdf8" : "2px solid transparent"
          }}>
            <span>{item.icon}</span> {item.label}
          </button>
        ))}

        <div style={{ marginTop: "auto" }}>
          <div style={{
            padding: "10px 14px", borderRadius: 10,
            background: "rgba(255,255,255,0.05)", marginBottom: 8
          }}>
            <p style={{ margin: 0, fontSize: 11, color: "#475569" }}>Signed in as</p>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "#94a3b8", wordBreak: "break-all" }}>
              {session.user.email}
            </p>
          </div>
          <button onClick={() => supabase.auth.signOut()} style={{
            width: "100%", padding: "9px", borderRadius: 10, border: "1px solid rgba(239,68,68,0.3)",
            background: "rgba(239,68,68,0.1)", color: "#f87171", cursor: "pointer",
            fontWeight: 600, fontSize: 13
          }}>
            Sign Out
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, padding: 32, overflowY: "auto" }}>

        {/* Documents Page */}
        {page === "documents" && (
          <div>
            <h2 style={{ marginTop: 0, fontSize: 24, fontWeight: 700 }}>My Documents</h2>
            <p style={{ color: "#64748b", marginBottom: 28 }}>Upload PDFs to index them for question answering.</p>

            {/* Upload Card */}
            <div style={{
              background: "rgba(255,255,255,0.04)", borderRadius: 16, padding: 28,
              border: "1px solid rgba(255,255,255,0.08)", marginBottom: 28
            }}>
              <h3 style={{ marginTop: 0, fontSize: 16, color: "#94a3b8" }}>Upload New Document</h3>
              <label style={{
                display: "block", border: "2px dashed rgba(56,189,248,0.3)", borderRadius: 12,
                padding: "28px 20px", textAlign: "center", cursor: "pointer", marginBottom: 16,
                background: file ? "rgba(56,189,248,0.06)" : "transparent"
              }}>
                <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])} style={{ display: "none" }} />
                <div style={{ fontSize: 28, marginBottom: 8 }}>{file ? "📄" : "☁️"}</div>
                <div style={{ fontWeight: 600, color: file ? "#38bdf8" : "#475569", fontSize: 14 }}>
                  {file ? file.name : "Click to choose a PDF"}
                </div>
              </label>
              <button onClick={handleUpload} disabled={!file || uploading} style={{
                width: "100%", padding: "12px", fontWeight: 700, fontSize: 14,
                border: "none", borderRadius: 10, cursor: !file || uploading ? "not-allowed" : "pointer",
                background: !file || uploading ? "rgba(255,255,255,0.05)" : "linear-gradient(135deg, #38bdf8, #818cf8)",
                color: !file || uploading ? "#475569" : "white"
              }}>
                {uploading ? "⏳ Indexing..." : "🚀 Upload & Index"}
              </button>

              {uploadStatus && (
                <div style={{
                  marginTop: 16, padding: 16, borderRadius: 10,
                  background: uploadStatus.success ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                  border: `1px solid ${uploadStatus.success ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`
                }}>
                  {uploadStatus.success ? (
                    <div>
                      <p style={{ margin: "0 0 10px", color: "#4ade80", fontWeight: 700 }}>✅ Indexed successfully!</p>
                      <div style={{ display: "flex", gap: 12 }}>
                        {[
                          { label: "Doc ID", value: uploadStatus.data.doc_id },
                          { label: "Chunks", value: uploadStatus.data.chunk_count },
                          { label: "Trust", value: `${uploadStatus.data.trust_score}%` }
                        ].map(item => (
                          <div key={item.label} style={{
                            flex: 1, textAlign: "center", padding: "8px",
                            background: "rgba(255,255,255,0.04)", borderRadius: 8
                          }}>
                            <div style={{ fontSize: 11, color: "#475569" }}>{item.label}</div>
                            <div style={{ fontWeight: 700, color: "#4ade80", fontSize: 14 }}>{item.value}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p style={{ margin: 0, color: "#f87171" }}>❌ {uploadStatus.message}</p>
                  )}
                </div>
              )}
            </div>

            {/* Documents List */}
            <h3 style={{ fontSize: 16, color: "#94a3b8", marginBottom: 14 }}>
              Uploaded Documents ({documents.length})
            </h3>
            {documents.length === 0 ? (
              <div style={{
                textAlign: "center", padding: 40, borderRadius: 16,
                background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)",
                color: "#475569"
              }}>
                <div style={{ fontSize: 32, marginBottom: 10 }}>📭</div>
                No documents yet. Upload your first PDF above.
              </div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {documents.map((doc, i) => (
                  <div key={i} style={{
                    padding: "16px 20px", borderRadius: 12,
                    background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                    display: "flex", justifyContent: "space-between", alignItems: "center"
                  }}>
                    <div>
                      <p style={{ margin: 0, fontWeight: 600, fontSize: 14, color: "#e2e8f0" }}>
                        📄 {doc.filename}
                      </p>
                      <p style={{ margin: "4px 0 0", fontSize: 12, color: "#475569" }}>
                        {doc.chunk_count} chunks · Uploaded {new Date(doc.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{
                        fontSize: 12, fontWeight: 700, padding: "3px 10px", borderRadius: 99,
                        background: "rgba(56,189,248,0.1)", color: "#38bdf8"
                      }}>
                        Trust: {doc.trust_score}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Chat Page */}
        {page === "chat" && (
          <div>
            <h2 style={{ marginTop: 0, fontSize: 24, fontWeight: 700 }}>Chat</h2>
            <p style={{ color: "#64748b", marginBottom: 24 }}>Select a document and ask a question.</p>

            {/* Document Selector */}
            <div style={{
              background: "rgba(255,255,255,0.04)", borderRadius: 14, padding: 20,
              border: "1px solid rgba(255,255,255,0.08)", marginBottom: 20
            }}>
              <label style={{ fontSize: 13, color: "#94a3b8", fontWeight: 600, display: "block", marginBottom: 10 }}>
                Select Document to Query
              </label>
              {documents.length === 0 ? (
                <p style={{ color: "#475569", fontSize: 13, margin: 0 }}>
                  No documents uploaded yet. Go to Documents tab first.
                </p>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {documents.map((doc, i) => (
                    <button key={i} onClick={() => setSelectedDoc(doc.doc_id)} style={{
                      padding: "8px 16px", borderRadius: 8, border: "none", cursor: "pointer",
                      fontWeight: 600, fontSize: 13,
                      background: selectedDoc === doc.doc_id
                        ? "linear-gradient(135deg, #38bdf8, #818cf8)"
                        : "rgba(255,255,255,0.07)",
                      color: selectedDoc === doc.doc_id ? "white" : "#94a3b8"
                    }}>
                      📄 {doc.filename}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Question Input */}
            <div style={{
              background: "rgba(255,255,255,0.04)", borderRadius: 14, padding: 20,
              border: "1px solid rgba(255,255,255,0.08)", marginBottom: 20
            }}>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleQuery()}
                  placeholder={selectedDoc ? "Ask a question about this document..." : "Select a document first..."}
                  disabled={!selectedDoc}
                  style={{
                    flex: 1, padding: "12px 16px", borderRadius: 10,
                    border: "1px solid rgba(255,255,255,0.12)",
                    background: "rgba(255,255,255,0.06)",
                    color: "white", fontSize: 14, outline: "none"
                  }}
                />
                <button onClick={handleQuery} disabled={loading || !question.trim() || !selectedDoc} style={{
                  padding: "12px 24px", fontWeight: 700, fontSize: 14,
                  background: loading || !selectedDoc ? "rgba(255,255,255,0.05)" : "linear-gradient(135deg, #38bdf8, #818cf8)",
                  color: loading || !selectedDoc ? "#475569" : "white",
                  border: "none", borderRadius: 10, cursor: "pointer"
                }}>
                  {loading ? "⏳" : "Ask →"}
                </button>
              </div>
            </div>

            {/* Result */}
            {result && (
              <div style={{
                background: "rgba(255,255,255,0.04)", borderRadius: 14, padding: 24,
                border: "1px solid rgba(255,255,255,0.08)"
              }}>
                <span style={{
                  display: "inline-block", marginBottom: 16, fontSize: 12, fontWeight: 700,
                  padding: "3px 12px", borderRadius: 99,
                  background: result.answerable ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
                  color: result.answerable ? "#4ade80" : "#f87171",
                  border: `1px solid ${result.answerable ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`
                }}>
                  {result.answerable ? "✅ Answered" : "❌ Unanswerable"}
                </span>

                <p style={{ lineHeight: 1.8, fontSize: 15, color: "#e2e8f0", marginBottom: 24 }}>
                  {result.answer}
                </p>

                {result.sources?.length > 0 && (
                  <>
                    <p style={{ fontWeight: 700, color: "#818cf8", fontSize: 13, marginBottom: 10 }}>
                      📚 {result.sources.length} Sources Used
                    </p>
                    {result.sources.map((src, i) => (
                      <div key={i} style={{
                        marginBottom: 8, borderRadius: 10,
                        border: "1px solid rgba(255,255,255,0.08)",
                        overflow: "hidden"
                      }}>
                        <div onClick={() => setExpandedSource(expandedSource === i ? null : i)}
                          style={{
                            padding: "10px 16px", cursor: "pointer",
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            background: "rgba(255,255,255,0.03)"
                          }}>
                          <span style={{ fontWeight: 600, fontSize: 13, color: "#c084fc" }}>
                            📄 {src.doc_id} · Chunk {src.chunk_index}
                          </span>
                          <span style={{ fontSize: 12, color: "#64748b" }}>
                            Relevance: <strong style={{ color: "#38bdf8" }}>{src.relevance_score}</strong>
                            &nbsp;· Trust: <strong style={{ color: "#4ade80" }}>{src.trust_score}%</strong>
                            &nbsp;{expandedSource === i ? "▲" : "▼"}
                          </span>
                        </div>
                        {expandedSource === i && (
                          <div style={{
                            padding: "12px 16px", fontSize: 13, color: "#94a3b8",
                            lineHeight: 1.7, borderTop: "1px solid rgba(255,255,255,0.06)"
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
            <h2 style={{ marginTop: 0, fontSize: 24, fontWeight: 700 }}>Chat History</h2>
            {history.length === 0 ? (
              <div style={{
                textAlign: "center", padding: 60, borderRadius: 16,
                background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)",
                color: "#475569"
              }}>
                <div style={{ fontSize: 36, marginBottom: 12 }}>💬</div>
                No chat history yet.
              </div>
            ) : (
              history.map((item, i) => (
                <div key={i} style={{
                  marginBottom: 12, background: "rgba(255,255,255,0.04)", borderRadius: 12,
                  padding: 20, border: "1px solid rgba(255,255,255,0.08)"
                }}>
                  <p style={{ margin: "0 0 8px", fontWeight: 700, color: "#38bdf8", fontSize: 14 }}>
                    Q: {item.question}
                  </p>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: 13, lineHeight: 1.7 }}>
                    {item.answer}
                  </p>
                  <p style={{ margin: "8px 0 0", fontSize: 11, color: "#334155" }}>
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}