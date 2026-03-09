import { useState, useEffect, useRef, useCallback } from "react"
import axios from "axios"
import "./App.css"

const API = "https://smartrag.onrender.com"

export default function App() {
  const [session, setSession]           = useState(null)
  const [page, setPage]                 = useState("documents")

  // Auth
  const [email, setEmail]               = useState("")
  const [password, setPassword]         = useState("")
  const [authMode, setAuthMode]         = useState("login")
  const [authError, setAuthError]       = useState("")
  const [authLoading, setAuthLoading]   = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe]     = useState(false)
  const [resetMode, setResetMode]       = useState(false)
  const [resetSent, setResetSent]       = useState(false)

  // Documents
  const [file, setFile]                 = useState(null)
  const [uploading, setUploading]       = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [documents, setDocuments]       = useState([])
  const [docsLoading, setDocsLoading]   = useState(false)

  // Text upload
  const [uploadMode, setUploadMode]         = useState("pdf")   // "pdf" | "text"
  const [textInput, setTextInput]           = useState("")
  const [textDocName, setTextDocName]       = useState("")
  const [textUploading, setTextUploading]   = useState(false)

  // Multi-doc selection
  const [selectedDocs, setSelectedDocs] = useState([])

  // Chat
  const [question, setQuestion]         = useState("")
  const [loading, setLoading]           = useState(false)
  const [result, setResult]             = useState(null)

  // History
  const [history, setHistory]           = useState([])
  const [histLoading, setHistLoading]   = useState(false)

  const fileInputRef = useRef(null)

  // ── Session bootstrap ─────────────────────────────────────────────────────
  useEffect(() => {
    const token = sessionStorage.getItem("smartrag_token") || localStorage.getItem("smartrag_token")
    const user  = sessionStorage.getItem("smartrag_user")  || localStorage.getItem("smartrag_user")
    if (token && user) {
      try {
        setSession({ access_token: token, user: JSON.parse(user) })
      } catch {
        sessionStorage.removeItem("smartrag_token")
        sessionStorage.removeItem("smartrag_user")
        localStorage.removeItem("smartrag_token")
        localStorage.removeItem("smartrag_user")
      }
    }
  }, [])

  const fetchDocuments = useCallback(async () => {
    setDocsLoading(true)
    try {
      const res = await axios.get(`${API}/documents`, { headers: authHeaders() })
      setDocuments(res.data.documents || [])
    } catch (e) {
      console.error(e)
    } finally {
      setDocsLoading(false)
    }
  }, [session]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (session) fetchDocuments()
  }, [session, fetchDocuments])

  const authHeaders = () => ({
    Authorization: `Bearer ${session?.access_token}`
  })

  // ── Auth ──────────────────────────────────────────────────────────────────
  async function handleAuth() {
    setAuthLoading(true)
    setAuthError("")
    try {
      const endpoint = authMode === "login" ? "/auth/login" : "/auth/signup"
      const res = await axios.post(`${API}${endpoint}`, { email, password })
      const store = rememberMe ? localStorage : sessionStorage
      store.setItem("smartrag_token", res.data.token)
      store.setItem("smartrag_user",  JSON.stringify(res.data.user))
      setSession({ access_token: res.data.token, user: res.data.user })
    } catch (err) {
      setAuthError(err.response?.data?.detail || "Authentication failed. Please try again.")
    } finally {
      setAuthLoading(false)
    }
  }

  async function handleReset() {
    setAuthLoading(true)
    setAuthError("")
    try {
      await axios.post(`${API}/auth/reset`, { email })
      setResetSent(true)
    } catch (err) {
      setAuthError(err.response?.data?.detail || "Could not send reset email. Please try again.")
    } finally {
      setAuthLoading(false)
    }
  }

  function handleSignOut() {
    sessionStorage.removeItem("smartrag_token")
    sessionStorage.removeItem("smartrag_user")
    localStorage.removeItem("smartrag_token")
    localStorage.removeItem("smartrag_user")
    setSession(null)
  }

  // ── Documents — PDF upload ────────────────────────────────────────────────
  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setUploadStatus(null)
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await axios.post(`${API}/upload`, formData, { headers: authHeaders() })
      setUploadStatus({ success: true, message: `Document indexed — ${res.data.chunk_count} chunks, trust ${res.data.trust_score}%` })
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ""
      fetchDocuments()
    } catch (err) {
      setUploadStatus({ success: false, message: err.response?.data?.detail || "Upload failed." })
    } finally {
      setUploading(false)
    }
  }

  // ── Documents — Text upload ───────────────────────────────────────────────
  async function handleTextUpload() {
    if (!textInput.trim()) return
    setTextUploading(true)
    setUploadStatus(null)
    try {
      const res = await axios.post(
        `${API}/upload-text`,
        {
          text:     textInput.trim(),
          doc_name: textDocName.trim() || "Untitled Text Document",
        },
        { headers: authHeaders() }
      )
      setUploadStatus({
        success: true,
        message: `✓ "${res.data.doc_name}" indexed — ${res.data.chunk_count} chunks, trust ${res.data.trust_score}%`,
      })
      setTextInput("")
      setTextDocName("")
      fetchDocuments()
    } catch (err) {
      setUploadStatus({
        success: false,
        message: err.response?.data?.detail || "Text upload failed.",
      })
    } finally {
      setTextUploading(false)
    }
  }

  // ── Multi-doc selection helpers ───────────────────────────────────────────
  function toggleDoc(docId) {
    setSelectedDocs(prev =>
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    )
  }
  function selectAllDocs() { setSelectedDocs(documents.map(d => d.doc_id)) }
  function clearAllDocs()  { setSelectedDocs([]) }

  // ── Chat ──────────────────────────────────────────────────────────────────
  async function handleQuery() {
    if (!question.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const res = await axios.post(`${API}/query`, {
        question,
        use_llm: true,
        doc_ids: selectedDocs.length > 0 ? selectedDocs : null,
      }, { headers: authHeaders() })
      setResult(res.data)
    } catch (err) {
      setResult({ answer: "Something went wrong. Please try again.", answerable: false, sources: [] })
    } finally {
      setLoading(false)
      setQuestion("")
    }
  }

  // ── History ───────────────────────────────────────────────────────────────
  async function fetchHistory() {
    setHistLoading(true)
    try {
      const res = await axios.get(`${API}/history`, { headers: authHeaders() })
      setHistory(res.data.history || [])
    } catch (e) {
      console.error(e)
    } finally {
      setHistLoading(false)
    }
  }

  // ── Auth Screen ───────────────────────────────────────────────────────────
  if (!session) {
    return (
      <div className="auth-page">
        <div className="auth-panel">

          <div className="auth-brand">
            <svg className="auth-logo" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5Z" stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round"/>
              <path d="M2 17l10 5 10-5"            stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round"/>
              <path d="M2 12l10 5 10-5"            stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round"/>
            </svg>
            <h1 className="auth-wordmark">SmartRAG</h1>
            <p className="auth-tagline">Secure document intelligence</p>
          </div>

          {!resetMode ? (
            <>
              <div className="tab-row">
                <button className={`tab-btn ${authMode === "login"  ? "active" : ""}`} onClick={() => { setAuthMode("login");  setAuthError("") }}>Sign In</button>
                <button className={`tab-btn ${authMode === "signup" ? "active" : ""}`} onClick={() => { setAuthMode("signup"); setAuthError("") }}>Create Account</button>
              </div>

              <div className="field-group">
                <label className="field-label">Email address</label>
                <input type="email" className="field-input" value={email} autoComplete="email"
                  onChange={e => setEmail(e.target.value)} onKeyDown={e => e.key === "Enter" && handleAuth()} />
              </div>

              <div className="field-group">
                <label className="field-label">Password</label>
                <div className="pw-wrap">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="field-input"
                    value={password}
                    autoComplete={authMode === "login" ? "current-password" : "new-password"}
                    onChange={e => setPassword(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleAuth()}
                  />
                  <button type="button" className="pw-toggle" onClick={() => setShowPassword(v => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}>
                    {showPassword ? (
                      <svg viewBox="0 0 24 24" fill="none"><path d="M3 3l18 18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/><path d="M10.58 10.58a2 2 0 002.83 2.83" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/><path d="M9.36 5.37A9.8 9.8 0 0112 5c7 0 11 7 11 7a18.6 18.6 0 01-2.64 3.63M6.64 6.64A18.6 18.6 0 001 12s4 7 11 7a9.8 9.8 0 005.64-1.77" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/></svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12Z" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round"/><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.75"/></svg>
                    )}
                  </button>
                </div>
              </div>

              <label className="checkbox-row">
                <input type="checkbox" className="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)} />
                <span className="checkbox-label">Remember me for 30 days</span>
              </label>

              {authError && <div className="auth-error" role="alert">{authError}</div>}

              <button className="primary-btn full-width" onClick={handleAuth} disabled={authLoading || !email || !password}>
                {authLoading ? <span className="spinner" /> : authMode === "login" ? "Sign In" : "Create Account"}
              </button>

              {authMode === "login" && (
                <button className="link-btn" onClick={() => { setResetMode(true); setAuthError("") }}>
                  Forgot your password?
                </button>
              )}
            </>
          ) : (
            <>
              <div className="reset-header">
                <h2 className="reset-title">Reset password</h2>
                <p className="reset-sub">We'll send a reset link to your email address.</p>
              </div>

              {!resetSent ? (
                <>
                  <div className="field-group">
                    <label className="field-label">Email address</label>
                    <input type="email" className="field-input" value={email}
                      onChange={e => setEmail(e.target.value)} onKeyDown={e => e.key === "Enter" && handleReset()} />
                  </div>
                  {authError && <div className="auth-error" role="alert">{authError}</div>}
                  <button className="primary-btn full-width" onClick={handleReset} disabled={authLoading || !email}>
                    {authLoading ? <span className="spinner" /> : "Send reset link"}
                  </button>
                </>
              ) : (
                <div className="info-box">
                  Check your inbox — a reset link has been sent to <strong>{email}</strong>.
                </div>
              )}

              <button className="link-btn" onClick={() => { setResetMode(false); setResetSent(false); setAuthError("") }}>
                ← Back to sign in
              </button>
            </>
          )}
        </div>
      </div>
    )
  }

  // ── Main App ──────────────────────────────────────────────────────────────
  return (
    <div className="app-layout">

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5Z" stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round"/>
            <path d="M2 17l10 5 10-5"            stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round"/>
            <path d="M2 12l10 5 10-5"            stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round"/>
          </svg>
          <span>SmartRAG</span>
        </div>

        <nav className="sidebar-nav">
          {[
            { id: "documents", label: "Documents" },
            { id: "chat",      label: "Chat"      },
            { id: "history",   label: "History"   },
          ].map(item => (
            <button
              key={item.id}
              className={`nav-link ${page === item.id ? "active" : ""}`}
              onClick={() => {
                setPage(item.id)
                if (item.id === "history") fetchHistory()
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-pill">
            <span className="user-avatar">{session.user.email[0].toUpperCase()}</span>
            <span className="user-email">{session.user.email}</span>
          </div>
          <button className="signout-btn" onClick={handleSignOut}>Sign out</button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">

        {/* ── Documents ── */}
        {page === "documents" && (
          <section>
            <div className="page-header">
              <h2 className="page-title">Documents</h2>
              <p className="page-sub">Upload PDFs or paste text to index and query.</p>
            </div>

            <div className="card">
              <p className="card-label">Upload Document</p>

              {/* PDF / Text mode toggle */}
              <div className="tab-row" style={{ marginBottom: "16px" }}>
                <button
                  className={`tab-btn ${uploadMode === "pdf" ? "active" : ""}`}
                  onClick={() => { setUploadMode("pdf"); setUploadStatus(null) }}
                >
                  📄 PDF File
                </button>
                <button
                  className={`tab-btn ${uploadMode === "text" ? "active" : ""}`}
                  onClick={() => { setUploadMode("text"); setUploadStatus(null) }}
                >
                  ✏️ Paste Text
                </button>
              </div>

              {uploadMode === "pdf" ? (
                <div className="upload-row">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    className="file-input"
                    onChange={e => setFile(e.target.files[0] || null)}
                  />
                  <button className="primary-btn" onClick={handleUpload} disabled={!file || uploading}>
                    {uploading ? <><span className="spinner" /> Indexing…</> : "Upload & Index"}
                  </button>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <input
                    className="field-input"
                    placeholder="Document name (optional)"
                    value={textDocName}
                    onChange={e => setTextDocName(e.target.value)}
                  />
                  <textarea
                    className="field-input"
                    placeholder="Paste any text here — notes, articles, code, lecture content…"
                    value={textInput}
                    onChange={e => setTextInput(e.target.value)}
                    rows={8}
                    style={{ resize: "vertical", fontFamily: "var(--font-mono)", fontSize: "13px" }}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "11px", color: "var(--slate-400)", fontFamily: "var(--font-mono)" }}>
                      {textInput.trim().split(/\s+/).filter(Boolean).length} words
                    </span>
                    <button
                      className="primary-btn"
                      onClick={handleTextUpload}
                      disabled={!textInput.trim() || textUploading}
                    >
                      {textUploading ? <><span className="spinner" /> Indexing…</> : "Index Text"}
                    </button>
                  </div>
                </div>
              )}

              {uploadStatus && (
                <div className={`status-strip ${uploadStatus.success ? "success" : "error"}`}>
                  {uploadStatus.message}
                </div>
              )}
            </div>

            {docsLoading ? (
              <div className="state-placeholder">Loading documents…</div>
            ) : documents.length === 0 ? (
              <div className="state-placeholder">No documents yet. Upload a PDF or paste text above to get started.</div>
            ) : (
              <div className="doc-list">
                {documents.map(doc => (
                  <div key={doc.doc_id} className="doc-row">
                    <div>
                      <div className="doc-name">{doc.filename}</div>
                      <div className="doc-meta">
                        {doc.chunk_count} chunks · {new Date(doc.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <span className="badge">{doc.trust_score}% trust</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ── Chat ── */}
        {page === "chat" && (
          <section>
            <div className="page-header">
              <h2 className="page-title">Chat</h2>
              <p className="page-sub">Ask questions about your indexed documents.</p>
            </div>

            <div className="card">
              <div className="field-group">
                <div className="doc-select-header">
                  <label className="field-label">
                    Documents
                    <span className="doc-select-count">
                      {selectedDocs.length === 0
                        ? "— searching all"
                        : `${selectedDocs.length} of ${documents.length} selected`}
                    </span>
                  </label>
                  <div className="doc-select-actions">
                    <button className="link-btn small" onClick={selectAllDocs}>Select all</button>
                    <span className="doc-select-divider">·</span>
                    <button className="link-btn small" onClick={clearAllDocs}>Clear</button>
                  </div>
                </div>

                <div className="doc-checkbox-list">
                  {documents.length === 0 ? (
                    <div className="state-placeholder">No documents uploaded yet.</div>
                  ) : (
                    documents.map(doc => (
                      <label
                        key={doc.doc_id}
                        className={`doc-checkbox-row ${selectedDocs.includes(doc.doc_id) ? "checked" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedDocs.includes(doc.doc_id)}
                          onChange={() => toggleDoc(doc.doc_id)}
                        />
                        <div className="doc-checkbox-info">
                          <span className="doc-checkbox-name">{doc.filename}</span>
                          <span className="doc-checkbox-meta">{doc.chunk_count} chunks</span>
                        </div>
                        <span className="badge">{doc.trust_score}% trust</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Question</label>
                <div className="chat-row">
                  <input
                    className="field-input"
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleQuery()}
                    placeholder={
                      selectedDocs.length === 0
                        ? "Ask anything across all documents…"
                        : `Ask anything across ${selectedDocs.length} selected document${selectedDocs.length > 1 ? "s" : ""}…`
                    }
                  />
                  <button className="primary-btn" onClick={handleQuery} disabled={!question.trim() || loading}>
                    {loading ? <span className="spinner" /> : "Ask"}
                  </button>
                </div>
              </div>
            </div>

            {result && (
              <div className="card result-card">
                <span className={`badge ${result.answerable ? "success" : "muted"}`}>
                  {result.answerable ? "Answered" : "Unanswerable"}
                </span>
                <p className="answer-text">{result.answer}</p>

                {result.sources?.length > 0 && (
                  <div className="sources">
                    <p className="sources-label">Sources</p>
                    {result.sources.map((src) => (
                      <div key={`${src.doc_id}-${src.chunk_index}`} className="source-card">
                        <div className="source-header">
                          <span>{src.doc_id}</span>
                          <span>Chunk {src.chunk_index}</span>
                        </div>
                        <div className="source-meta">
                          Relevance {src.relevance_score}% · Trust {src.trust_score}%
                        </div>
                        <p className="source-excerpt">{src.excerpt}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* ── History ── */}
        {page === "history" && (
          <section>
            <div className="page-header">
              <h2 className="page-title">History</h2>
              <p className="page-sub">Your past queries and answers.</p>
            </div>

            {histLoading ? (
              <div className="state-placeholder">Loading history…</div>
            ) : history.length === 0 ? (
              <div className="state-placeholder">No history yet. Ask a question in Chat to get started.</div>
            ) : (
              <div className="history-list">
                {history.map(item => (
                  <div key={item.id} className="history-card">
                    <p className="history-question">{item.question}</p>
                    <p className="history-answer">{item.answer}</p>
                    <span className="history-date">{new Date(item.created_at).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

      </main>
    </div>
  )
}