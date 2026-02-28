import { useState, useEffect, useRef, useCallback } from "react"
import axios from "axios"
import "./App.css"

const API = "http://localhost:8000"

export default function App() {
  const [session, setSession]         = useState(null)
  const [page, setPage]               = useState("documents")

  // Auth
  const [email, setEmail]             = useState("")
  const [password, setPassword]       = useState("")
  const [authMode, setAuthMode]       = useState("login")
  const [authError, setAuthError]     = useState("")
  const [authLoading, setAuthLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe]   = useState(false)   // FIX #4: wired up
  const [resetMode, setResetMode]     = useState(false)
  const [resetSent, setResetSent]     = useState(false)

  // Documents
  const [file, setFile]               = useState(null)
  const [uploading, setUploading]     = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [documents, setDocuments]     = useState([])
  const [docsLoading, setDocsLoading] = useState(false)   // FIX #6: loading state
  const [selectedDoc, setSelectedDoc] = useState("")

  // Chat
  const [question, setQuestion]       = useState("")
  const [loading, setLoading]         = useState(false)
  const [result, setResult]           = useState(null)

  // History
  const [history, setHistory]         = useState([])
  const [histLoading, setHistLoading] = useState(false)   // FIX #6: loading state

  // FIX #3: ref to reset file input DOM element
  const fileInputRef = useRef(null)

  // ── Session bootstrap ─────────────────────────────────────────────────────
  useEffect(() => {
    // FIX #2: read from whichever store was used at login
    const token = sessionStorage.getItem("smartrag_token") || localStorage.getItem("smartrag_token")
    const user  = sessionStorage.getItem("smartrag_user")  || localStorage.getItem("smartrag_user")
    if (token && user) {
      try {
        setSession({ access_token: token, user: JSON.parse(user) })
      } catch {
        // FIX #9 (partial): guard against corrupt localStorage value crashing the app
        sessionStorage.removeItem("smartrag_token")
        sessionStorage.removeItem("smartrag_user")
        localStorage.removeItem("smartrag_token")
        localStorage.removeItem("smartrag_user")
      }
    }
  }, [])

  // FIX #3 (useCallback): stable reference so the useEffect dep array is correct
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

  // FIX #3 (useEffect dep): include fetchDocuments in dep array
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

      // FIX #2 + FIX #4: use sessionStorage by default; localStorage only if "remember me"
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

  // FIX #1: handleReset actually calls the API
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

  // ── Documents ─────────────────────────────────────────────────────────────
  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setUploadStatus(null)
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await axios.post(`${API}/upload`, formData, { headers: authHeaders() })
      setUploadStatus({ success: true, data: res.data })
      // FIX #3: clear both state and DOM input after successful upload
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ""
      fetchDocuments()
    } catch (err) {
      setUploadStatus({ success: false, message: err.response?.data?.detail || "Upload failed." })
    } finally {
      setUploading(false)
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────
  async function handleQuery() {
    if (!question.trim() || !selectedDoc) return
    setLoading(true)
    setResult(null)
    try {
      const res = await axios.post(`${API}/query`, {
        question,
        use_llm: true,
        doc_id: String(selectedDoc)  // FIX #5: always send as string
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
                <input
                  type="email"
                  className="field-input"
                  value={email}
                  autoComplete="email"
                  onChange={e => setEmail(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleAuth()}
                />
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
                  {/* FIX #8: toggle sits inside pw-wrap, not auth-input, so centering is correct */}
                  <button type="button" className="pw-toggle" onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? "Hide password" : "Show password"}>
                    {showPassword ? (
                      <svg viewBox="0 0 24 24" fill="none"><path d="M3 3l18 18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/><path d="M10.58 10.58a2 2 0 002.83 2.83" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/><path d="M9.36 5.37A9.8 9.8 0 0112 5c7 0 11 7 11 7a18.6 18.6 0 01-2.64 3.63M6.64 6.64A18.6 18.6 0 001 12s4 7 11 7a9.8 9.8 0 005.64-1.77" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/></svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12Z" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round"/><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.75"/></svg>
                    )}
                  </button>
                </div>
              </div>

              {/* FIX #4: remember me is fully wired */}
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
                    <input
                      type="email"
                      className="field-input"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && handleReset()}
                    />
                  </div>
                  {authError && <div className="auth-error" role="alert">{authError}</div>}
                  {/* FIX #1: button calls real API */}
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
              <p className="page-sub">Upload PDFs to index and query.</p>
            </div>

            <div className="card">
              <p className="card-label">Upload a PDF</p>
              <div className="upload-row">
                {/* FIX #3: ref attached */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  className="file-input"
                  onChange={e => setFile(e.target.files[0] || null)}
                />
                <button
                  className="primary-btn"
                  onClick={handleUpload}
                  disabled={!file || uploading}
                >
                  {uploading ? <span className="spinner" /> : "Upload & Index"}
                </button>
              </div>

              {uploadStatus && (
                <div className={`status-strip ${uploadStatus.success ? "success" : "error"}`}>
                  {uploadStatus.success ? "Document indexed successfully." : uploadStatus.message}
                </div>
              )}
            </div>

            {/* FIX #6: loading + empty states */}
            {docsLoading ? (
              <div className="state-placeholder">Loading documents…</div>
            ) : documents.length === 0 ? (
              <div className="state-placeholder">No documents yet. Upload a PDF above to get started.</div>
            ) : (
              <div className="doc-list">
                {/* FIX #5: key uses doc.doc_id not index */}
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
                <label className="field-label">Document</label>
                {/* FIX #10: select has option colors + focus style */}
                <select
                  className="field-select"
                  value={selectedDoc}
                  onChange={e => setSelectedDoc(String(e.target.value))}  // FIX #5: coerce to string
                >
                  <option value="">Select a document…</option>
                  {/* FIX #5: key uses doc.doc_id */}
                  {documents.map(doc => (
                    <option key={doc.doc_id} value={String(doc.doc_id)}>
                      {doc.filename}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label">Question</label>
                <div className="chat-row">
                  <input
                    className="field-input"
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleQuery()}
                    placeholder="Ask anything about the selected document…"
                  />
                  <button
                    className="primary-btn"
                    onClick={handleQuery}
                    disabled={!question.trim() || !selectedDoc || loading}
                  >
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

                {/* FIX #12: sources section now has styles in CSS */}
                {result.sources?.length > 0 && (
                  <div className="sources">
                    <p className="sources-label">Sources</p>
                    {result.sources.map((src, i) => (
                      // FIX #5: stable key combining doc_id + chunk_index
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

            {/* FIX #6: loading + empty states */}
            {histLoading ? (
              <div className="state-placeholder">Loading history…</div>
            ) : history.length === 0 ? (
              <div className="state-placeholder">No history yet. Ask a question in Chat to get started.</div>
            ) : (
              <div className="history-list">
                {/* FIX #5: key uses item.id */}
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
