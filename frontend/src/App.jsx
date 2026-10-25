
import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const ROLES = [
  { id: "admin", title: "Administrator", description: "Monitor security and document activity." },
  { id: "owner", title: "Document Owner", description: "Upload and share your documents." },
  { id: "viewer", title: "Viewer", description: "Access documents shared with you." },
];


const ICONS = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6",
  share: "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v14",
  shield: "M12 3l8 3v6c0 4.5-3.2 8.3-8 9-4.8-.7-8-4.5-8-9V6z M9 12l2 2 4-4",
  lock: "M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  key: "M15 7a4 4 0 1 1-3.5 6L4 20.5V17h3v-3h3l1.5-1.5A4 4 0 0 1 15 7z",
  ban: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.6 5.6l12.8 12.8",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  arrow: "M5 12h14M13 6l6 6-6 6",
  download: "M12 3v12M7 10l5 5 5-5M4 21h16",
  refresh: "M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  check: "M5 13l4 4L19 7",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
};

function Icon({ name, size = 18 }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

function resultTone(result = "") {
  const r = String(result).toLowerCase();
  if (/(denied|fail|forbid|reject|error|block)/.test(r)) return "danger";
  if (/(success|allow|ok|granted|valid)/.test(r)) return "success";
  return "neutral";
}

function fileKind(doc) {
  const name = doc.filename || doc.original_filename || "";
  const ext = name.includes(".") ? name.split(".").pop().toUpperCase().slice(0, 4) : "";
  return ext || (doc.content_type || "FILE").split("/").pop().toUpperCase().slice(0, 4);
}

async function apiRequest(path, token, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  const data = options.raw
    ? null
    : await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data?.detail || `Request failed (${response.status}).`);
  }

  return options.raw ? response : data;
}

function AdminDashboard({ token, onLogout }) {
  const [assistantOpen, setAssistantOpen] = useState(false);
const [assistantQuestion, setAssistantQuestion] = useState("");
const [assistantLoading, setAssistantLoading] = useState(false);

const [assistantMessages, setAssistantMessages] = useState([
  {
    role: "assistant",
    content:
      "Hi! I can explain TrustVault dashboard metrics, user statuses, document activity, and audit events. I only answer questions about this admin dashboard.",
  },
]);
  const [tab, setTab] = useState("Overview");
  const [users, setUsers] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [owner, setOwner] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const headers = { Authorization: `Bearer ${token}` };

  
async function askDashboardAssistant(event) {
  event.preventDefault();

  const question = assistantQuestion.trim();
  if (!question || assistantLoading) return;

  setAssistantQuestion("");
  setAssistantMessages((messages) => [
    ...messages,
    { role: "user", content: question },
  ]);
  setAssistantLoading(true);

  try {
    const response = await fetch(`${API_URL}/admin/assistant`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Unable to get an AI response."
      );
    }

    setAssistantMessages((messages) => [
      ...messages,
      { role: "assistant", content: data.answer },
    ]);
  } catch (error) {
    setAssistantMessages((messages) => [
      ...messages,
      {
        role: "assistant",
        content:
          error.message ||
          "AI assistant unavailable. Check that Ollama is running.",
      },
    ]);
  } finally {
    setAssistantLoading(false);
  }
}

  async function request(path, options = {}) {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: { ...headers, ...options.headers },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return data;
  }

  async function loadUsers() {
    const data = await request("/admin/users");
    setUsers(Array.isArray(data) ? data : data.users || []);
  }

  async function loadDocuments() {
    const data = await request("/admin/documents");
    setDocuments(Array.isArray(data) ? data : data.documents || []);
  }

  async function loadDashboard() {
    const params = new URLSearchParams({ limit: "100", offset: "0" });
    if (search.trim()) params.set("search_name", search.trim());
    if (owner.trim()) params.set("owner", owner.trim());
    if (category.trim()) params.set("category", category.trim());
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    setDashboard(await request(`/admin/dashboard?${params}`));
  }

  async function refreshAll() {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      await Promise.all([loadUsers(), loadDocuments(), loadDashboard()]);
    } catch (err) {
      setError(err.message || "Unable to load admin data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshAll();
  }, [token]);

  async function toggleUser(user) {
    const action = user.is_active ? "disable" : "enable";
    if (
      user.is_active &&
      !window.confirm(`Disable the account for ${user.email}?`)
    ) return;

    setLoading(true);
    setError("");
    setNotice("");
    try {
      await request(`/admin/users/${user.id}/${action}`, {
        method: "PATCH",
      });
      setNotice(`Account ${action === "disable" ? "disabled" : "enabled"} successfully.`);
      await loadUsers();
    } catch (err) {
      setError(err.message || "Unable to update user.");
    } finally {
      setLoading(false);
    }
  }

  async function deleteDocument(doc) {
    const name = doc.original_filename || doc.filename || `Document ${doc.id}`;
    if (!window.confirm(`Delete "${name}"? This action cannot be undone from this screen.`)) {
      return;
    }

    setLoading(true);
    setError("");
    setNotice("");
    try {
      await request(`/admin/documents/${doc.id}`, { method: "DELETE" });
      setNotice(`Delete request completed for "${name}".`);
      await Promise.all([loadDocuments(), loadDashboard()]);
    } catch (err) {
      setError(err.message || "Unable to delete document.");
    } finally {
      setLoading(false);
    }
  }

  async function verifyHashChain() {
    setLoading(true);
    setError("");
    setVerification(null);
    try {
      setVerification(await request("/admin/audit/verify"));
    } catch (err) {
      setError(err.message || "Hash-chain verification failed.");
    } finally {
      setLoading(false);
    }
  }

  const summary = dashboard?.summary || {};
  const events = dashboard?.events || [];

  const nav = ["Overview", "Manage Users", "Documents", "Activity & Audit"];

  function sizeLabel(bytes) {
    if (bytes == null) return "—";
    const value = Number(bytes);
    if (!Number.isFinite(value)) return "—";
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(2)} MB`;
  }

  return (
    <main className="dashboard-shell admin-shell">
      <aside className="dashboard-sidebar">
        <div className="brand dashboard-brand">
          <span className="brand-icon">T</span> TrustVault
        </div>
        <p className="sidebar-label">ADMINISTRATION</p>

        {nav.map((item) => (
          <button
            type="button"
            key={item}
            className={`sidebar-link ${tab === item ? "active" : ""}`}
            onClick={() => setTab(item)}
          >
            {item === "Overview" ? "▦" :
             item === "Manage Users" ? "♙" :
             item === "Documents" ? "▤" : "◷"}{" "}
            {item}
          </button>
        ))}

        <div className="sidebar-bottom">
          <div className="sidebar-security">
            <span>✦</span>
            <div>
              <strong>Protected workspace</strong>
              <small>Administrator access</small>
            </div>
          </div>
          <button type="button" className="logout-button" onClick={onLogout}>
            ↪ Sign out
          </button>
        </div>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-topbar">
          <div>
            <p className="eyebrow">TRUSTVAULT SECURITY</p>
            <h2>{tab}</h2>
          </div>
          <button
            type="button"
            className="primary-small"
            onClick={refreshAll}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh data"}
          </button>
        </header>

        {error && <p className="login-message" role="alert">{error}</p>}
        {notice && <p className="account-note" role="status">{notice}</p>}

        {tab === "Overview" && (
          <>
            <section className="welcome-banner">
              <div>
                <p className="eyebrow">ADMINISTRATOR WORKSPACE</p>
                <h1>Security at a glance.</h1>
                <p>Manage accounts, documents, permissions, and audit integrity.</p>
              </div>
              <div className="welcome-symbol">✧</div>
            </section>

            <section className="admin-metrics">
              <article className="admin-metric">
                <span>Total users</span>
                <strong>{users.length}</strong>
              </article>
              <article className="admin-metric">
                <span>Active users</span>
                <strong>{users.filter((u) => u.is_active).length}</strong>
              </article>
              <article className="admin-metric">
                <span>Total documents</span>
                <strong>{summary.total_documents ?? documents.length}</strong>
              </article>
              <article className="admin-metric">
                <span>Audit activities</span>
                <strong>{summary.recent_activities ?? dashboard?.total_filtered ?? events.length}</strong>
              </article>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>Administrator actions</h3>
                  <p>Choose a section to manage TrustVault.</p>
                </div>
              </div>
              <div className="admin-filter-actions">
                {nav.slice(1).map((item) => (
                  <button
                    type="button"
                    className="primary-small"
                    key={item}
                    onClick={() => setTab(item)}
                  >
                    Open {item}
                  </button>
                ))}
              </div>
            </section>
          </>
        )}

        {tab === "Manage Users" && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h3>User management</h3>
                <p>Review account roles and disable or re-enable accounts.</p>
              </div>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>ID</th><th>Email</th><th>Role</th>
                    <th>Status</th><th>Created</th><th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.id}</td>
                      <td>{user.email}</td>
                      <td>{user.role?.value || user.role || "—"}</td>
                      <td>
                        <span className="role-pill">
                          {user.is_active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td>
                        {user.created_at
                          ? new Date(user.created_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td>
                        {user.role?.value === "admin" || user.role === "admin" ? (
                          <span>Protected admin</span>
                        ) : (
                          <button
                            type="button"
                            className="primary-small"
                            disabled={loading}
                            onClick={() => toggleUser(user)}
                          >
                            {user.is_active ? "Disable" : "Enable"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!users.length && <p>No users returned by the API.</p>}
            </div>
          </section>
        )}

        {tab === "Documents" && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h3>All documents</h3>
                <p>Metadata for documents across user accounts.</p>
              </div>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>ID</th><th>Filename</th><th>Owner</th>
                    <th>Size</th><th>Content type</th><th>Uploaded</th><th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id}>
                      <td>{doc.id}</td>
                      <td>{doc.original_filename || doc.filename || "—"}</td>
                      <td>
                        {doc.owner_email || doc.owner?.email ||
                         doc.owner_id || "—"}
                      </td>
                      <td>{sizeLabel(doc.size_bytes ?? doc.size)}</td>
                      <td>{doc.content_type || "—"}</td>
                      <td>
                        {doc.created_at
                          ? new Date(doc.created_at).toLocaleString()
                          : "—"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="primary-small"
                          disabled={loading}
                          onClick={() => deleteDocument(doc)}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!documents.length && <p>No documents returned by the API.</p>}
            </div>
          </section>
        )}

        {tab === "Activity & Audit" && (
          <>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>Filter activity</h3>
                  <p>Search document and permission-related audit events.</p>
                </div>
              </div>
              <form
                className="admin-filters"
                onSubmit={(e) => {
                  e.preventDefault();
                  setLoading(true);
                  setError("");
                  loadDashboard()
                    .catch((err) => setError(err.message))
                    .finally(() => setLoading(false));
                }}
              >
                <label>Document name
                  <input value={search} onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search filename" />
                </label>
                <label>Owner email
                  <input value={owner} onChange={(e) => setOwner(e.target.value)}
                    placeholder="owner@example.com" />
                </label>
                <label>Category / MIME type
                  <input value={category} onChange={(e) => setCategory(e.target.value)}
                    placeholder="application/pdf" />
                </label>
                <label>From
                  <input type="date" value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)} />
                </label>
                <label>To
                  <input type="date" value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)} />
                </label>
                <div className="admin-filter-actions">
                  <button type="submit" className="primary-small" disabled={loading}>
                    Apply filters
                  </button>
                  <button type="button" className="secondary-button" onClick={() => {
                    setSearch(""); setOwner(""); setCategory("");
                    setDateFrom(""); setDateTo("");
                    setLoading(true);
                    setError("");
                    const params = new URLSearchParams({ limit: "100", offset: "0" });
                    request(`/admin/dashboard?${params}`)
                      .then(setDashboard)
                      .catch((err) => setError(err.message))
                      .finally(() => setLoading(false));
                  }}>
                    Clear
                  </button>
                </div>
              </form>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>Activity and permission-change logs</h3>
                  <p>{dashboard?.total_filtered ?? events.length} matching events</p>
                </div>
                <button
                  type="button"
                  className="primary-small"
                  onClick={verifyHashChain}
                  disabled={loading}
                >
                  Verify hash chain
                </button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Date / Time</th><th>Document</th><th>Owner</th>
                      <th>Action</th><th>Result</th><th>Actor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.id}>
                        <td>{event.occurred_at
                          ? new Date(event.occurred_at).toLocaleString() : "—"}</td>
                        <td>{event.document_name ||
                          (event.document_id ? `Document ${event.document_id}` : "—")}</td>
                        <td>{event.owner_email || "—"}</td>
                        <td>{event.action || "—"}</td>
                        <td>{event.result || "—"}</td>
                        <td>{event.actor_user_id ?? "System"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!events.length && <p>No audit events match these filters.</p>}
              </div>
              {verification && (
                <div className="account-note" role="status">
                  <strong>Hash-chain verification result</strong>
                  <pre className="admin-json">
                    {JSON.stringify(verification, null, 2)}
                  </pre>
                </div>
              )}
            </section>
          </>
        )}

        <footer className="dashboard-footer">
          <span>TrustVault · Secure document workspace</span>
          <span>Administrator dashboard</span>
        </footer>
      </section>
      
{assistantOpen && (
  <section className="tv-ai-panel" aria-label="TrustVault AI Assistant">
    <header className="tv-ai-header">
      <div>
        <strong>TrustVault AI Assistant</strong>
        <small>Admin dashboard only</small>
      </div>
      <button
        type="button"
        onClick={() => setAssistantOpen(false)}
        aria-label="Close assistant"
      >
        ×
      </button>
    </header>

    <div className="tv-ai-messages" aria-live="polite">
      {assistantMessages.map((message, index) => (
        <div
          key={index}
          className={`tv-ai-message ${message.role}`}
        >
          {message.content}
        </div>
      ))}

      {assistantLoading && (
        <p>Analyzing dashboard data…</p>
      )}
    </div>

    <form className="tv-ai-form" onSubmit={askDashboardAssistant}>
      <input
        value={assistantQuestion}
        onChange={(event) => setAssistantQuestion(event.target.value)}
        placeholder="Ask about dashboard activity…"
        maxLength={500}
      />
      <button type="submit" disabled={assistantLoading}>
        Send
      </button>
    </form>
  </section>
)}

<button
  type="button"
  className="tv-ai-launcher"
  onClick={() => setAssistantOpen((open) => !open)}
>
  ✦ AI Assistant
</button>

    </main>
  );
}

function App() {
  const [selectedRole, setSelectedRole] = useState("owner");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [session, setSession] = useState(null);
  const [activePage, setActivePage] = useState("Overview");

  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState("");
  const [viewingDocument, setViewingDocument] = useState(null);
  const [viewerUrl, setViewerUrl] = useState("");
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerError, setViewerError] = useState("");

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");

  const [shareDocumentId, setShareDocumentId] = useState("");
  const [shareUserId, setShareUserId] = useState("");
  const [sharePermissions, setSharePermissions] = useState(["view"]);
  const [sharing, setSharing] = useState(false);
  const [shareMessage, setShareMessage] = useState("");

  const [revokeDocumentId, setRevokeDocumentId] = useState("");
  const [revokeUserId, setRevokeUserId] = useState("");
  const [revokeMessage, setRevokeMessage] = useState("");

  useEffect(() => {
    if (!session?.token || session.user.role === "admin") {
      setDocuments([]);
      return;
    }

    const controller = new AbortController();

    async function loadDocuments() {
      setDocumentsLoading(true);
      setDocumentsError("");

      try {
        const response = await fetch(`${API_URL}/documents`, {
          headers: { Authorization: `Bearer ${session.token}` },
          signal: controller.signal,
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(data.detail || "Unable to load documents.");
        }

        setDocuments(Array.isArray(data.documents) ? data.documents : []);
      } catch (err) {
        if (err.name !== "AbortError") setDocumentsError(err.message);
      } finally {
        if (!controller.signal.aborted) setDocumentsLoading(false);
      }
    }

    loadDocuments();
    return () => controller.abort();
  }, [session?.token, session?.user?.role]);

  async function refreshDocuments() {
    if (!session?.token) return;
    setDocumentsLoading(true);
    setDocumentsError("");

    try {
      const data = await apiRequest("/documents", session.token);
      setDocuments(Array.isArray(data.documents) ? data.documents : []);
    } catch (err) {
      setDocumentsError(err.message);
    } finally {
      setDocumentsLoading(false);
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      const data = await apiRequest("/auth/login", null, {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!data.access_token || !data.user?.role) {
        throw new Error("The server returned an incomplete login response.");
      }

      if (data.user.role !== selectedRole) {
        try {
          await apiRequest("/auth/logout", data.access_token, {
            method: "POST",
          });
        } catch {
          // Show the role mismatch even if logout fails.
        }
        throw new Error(
          `Your account role is ${data.user.role}. Select that role and try again.`
        );
      }

      const newSession = { token: data.access_token, user: data.user };
      setSession(newSession);
      setPassword("");
      setActivePage(data.user.role === "admin" ? "Admin Dashboard" : "Overview");
    } catch (err) {
      setMessage(err.message || "Unable to connect to TrustVault.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    return () => {
      if (viewerUrl) URL.revokeObjectURL(viewerUrl);
    };
  }, [viewerUrl]);

  async function handleLogout() {
    if (session?.token) {
      try {
        await apiRequest("/auth/logout", session.token, { method: "POST" });
      } catch {
        // Clear the local session even if the server cannot be reached.
      }
    }

    setSession(null);
    setPassword("");
    setSelectedRole("owner");
    setActivePage("Overview");
    setMessage("");
    setDocuments([]);
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadMessage("Choose a file before uploading.");
      return;
    }

    setUploading(true);
    setUploadMessage("");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      await apiRequest("/documents/upload", session.token, {
        method: "POST",
        body: formData,
      });

      setUploadMessage("Document uploaded successfully.");
      setSelectedFile(null);
      const input = document.getElementById("document-file");
      if (input) input.value = "";
      await refreshDocuments();
    } catch (err) {
      setUploadMessage(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleView(doc) {
    setViewerLoading(true);
    setViewerError("");
    setViewingDocument(doc);
    if (viewerUrl) URL.revokeObjectURL(viewerUrl);
    setViewerUrl("");

    try {
      const response = await fetch(`${API_URL}/documents/${doc.id}/view`, {
        headers: { Authorization: `Bearer ${session.token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Unable to open document (${response.status}).`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setViewerUrl(url);
    } catch (err) {
      setViewerError(err.message || "Unable to open this document.");
    } finally {
      setViewerLoading(false);
    }
  }

  function closeViewer() {
    if (viewerUrl) URL.revokeObjectURL(viewerUrl);
    setViewerUrl("");
    setViewingDocument(null);
    setViewerError("");
  }

  async function handleDownload(doc) {
    setDocumentsError("");

    try {
      const response = await apiRequest(
        `/documents/${doc.id}/download`,
        session.token,
        { raw: true }
      );

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download =
        doc.filename || doc.original_filename || `document-${doc.id}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setDocumentsError(err.message);
    }
  }

  async function handleShare(event) {
    event.preventDefault();

    if (!shareDocumentId || !shareUserId) {
      setShareMessage("Select a document and enter a registered user ID.");
      return;
    }

    if (!Number.isInteger(Number(shareUserId)) || Number(shareUserId) < 1) {
      setShareMessage("Enter a valid numeric user ID.");
      return;
    }

    if (sharePermissions.length === 0) {
      setShareMessage("Select at least one permission.");
      return;
    }

    setSharing(true);
    setShareMessage("");

    try {
      await apiRequest(
        `/documents/${shareDocumentId}/grants`,
        session.token,
        {
          method: "POST",
          body: JSON.stringify({
            user_id: Number(shareUserId),
            permissions: sharePermissions,
          }),
        }
      );

      setShareMessage("Document permissions saved successfully.");
      setShareUserId("");
    } catch (err) {
      setShareMessage(err.message);
    } finally {
      setSharing(false);
    }
  }

  async function handleRevoke(event) {
    event.preventDefault();

    if (!revokeDocumentId || !revokeUserId) {
      setRevokeMessage("Select a document and enter the user's ID.");
      return;
    }

    setRevokeMessage("");

    try {
      await apiRequest(
        `/documents/${revokeDocumentId}/grants/${revokeUserId}`,
        session.token,
        { method: "DELETE" }
      );
      setRevokeMessage("Document access revoked successfully.");
      setRevokeUserId("");
    } catch (err) {
      setRevokeMessage(err.message);
    }
  }

  if (session?.user?.role === "admin") {
    return (
      <AdminDashboard token={session.token} onLogout={handleLogout} />
    );
  }

  if (session) {
    const isOwner = session.user.role === "owner";
    const navigation = [
      ["Overview", "grid"],
      ["Documents", "file"],
      ...(isOwner ? [["Secure Sharing", "share"], ["Revoke Access", "ban"]] : []),
    ];

    return (
      <main className="dashboard-shell">
        <aside className="dashboard-sidebar">
          <button
            className="brand dashboard-brand"
            onClick={() => setActivePage("Overview")}
          >
            <span className="brand-icon">T</span> TrustVault
          </button>

          <p className="sidebar-label">WORKSPACE</p>

          {navigation.map(([page, icon]) => (
            <button
              key={page}
              className={`sidebar-link ${activePage === page ? "active" : ""}`}
              onClick={() => setActivePage(page)}
            >
              <Icon name={icon} /> {page}
            </button>
          ))}

          <div className="sidebar-bottom">
            <div className="sidebar-security">
              <span className="sidebar-security-icon"><Icon name="shield" /></span>
              <div>
                <strong>Protected workspace</strong>
                <small>Authenticated account</small>
              </div>
            </div>
            <button className="logout-button" onClick={handleLogout}>
              <Icon name="logout" /> Sign out
            </button>
          </div>
        </aside>

        <section className="dashboard-main">
          <header className="dashboard-topbar">
            <div>
              <p className="eyebrow">SECURE DOCUMENT WORKSPACE</p>
              <h2>{activePage}</h2>
            </div>
            <div className="user-chip">
              <span className="avatar">
                {(session.user.email || "U")[0].toUpperCase()}
              </span>
              <div>
                <strong>{session.user.email}</strong>
                <small>{session.user.role}</small>
              </div>
            </div>
          </header>

          {activePage === "Overview" && (
            <>
              <section className="welcome-banner">
                <div>
                  <p className="eyebrow">YOUR PRIVATE SPACE</p>
                  <h1>Welcome back.</h1>
                  <p>Your documents and permissions, in one secure place.</p>
                </div>
                <div className="welcome-symbol"><Icon name="lock" size={34} /></div>
              </section>

              <section className="stats-grid">
                <article className="stat-card">
                  <span className="stat-icon"><Icon name="file" size={20} /></span>
                  <p>Available documents</p>
                  <h3>{documentsLoading ? "…" : documents.length}</h3>
                </article>
                <article className="stat-card">
                  <span className="stat-icon"><Icon name="share" size={20} /></span>
                  <p>Account role</p>
                  <h3 className="cap">{session.user.role}</h3>
                </article>
                <article className="stat-card">
                  <span className="stat-icon"><Icon name="check" size={20} /></span>
                  <p>Session status</p>
                  <h3>Active</h3>
                </article>
              </section>

              <section className="panel">
                <h3>Quick actions</h3>
                <p>Manage your available documents and permissions.</p>
                <button className="action-row" onClick={() => setActivePage("Documents")}>
                  <span className="action-icon"><Icon name="file" /></span>
                  <span><strong>Browse documents</strong><small>View available files</small></span>
                  <span className="action-arrow"><Icon name="arrow" size={18} /></span>
                </button>
                <button className="action-row" onClick={() => setActivePage("Secure Sharing")}>
                  <span className="action-icon"><Icon name="share" /></span>
                  <span><strong>Secure sharing</strong><small>Manage document access</small></span>
                  <span className="action-arrow"><Icon name="arrow" size={18} /></span>
                </button>
              </section>
            </>
          )}

          {activePage === "Documents" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h3>Your documents</h3>
                  <p>Documents available to your account.</p>
                </div>
                <button className="primary-small" onClick={refreshDocuments} disabled={documentsLoading}>
                  <Icon name="refresh" size={16} /> {documentsLoading ? "Refreshing..." : "Refresh"}
                </button>
              </div>

              {isOwner && (
                <form className="upload-form" onSubmit={handleUpload}>
                  <label htmlFor="document-file">Upload a document</label>
                  <input
                    id="document-file"
                    type="file"
                    onChange={(e) => {
                      setSelectedFile(e.target.files?.[0] || null);
                      setUploadMessage("");
                    }}
                    required
                  />
                  <button className="primary-small" disabled={uploading || !selectedFile}>
                    <Icon name="upload" size={16} /> {uploading ? "Uploading..." : "Upload document"}
                  </button>
                  {uploadMessage && <p role="status">{uploadMessage}</p>}
                </form>
              )}

              {documentsError && <p className="login-message" role="alert">{documentsError}</p>}
              {documentsLoading && <p className="loading-text">Loading documents…</p>}

              {!documentsLoading && !documentsError && documents.length === 0 && (
                <div className="empty-state"><Icon name="file" size={28} /><strong>No documents yet</strong><p>Documents available to your account will appear here.</p></div>
              )}

              <div className="document-list">
                {documents.map((doc) => (
                  <article className="account-row" key={doc.id}>
                    <span className="file-badge">{fileKind(doc)}</span>
                    <div className="doc-meta">
                      <strong>{doc.filename || doc.original_filename || `Document ${doc.id}`}</strong>
                      <p>{doc.content_type || "Unknown file type"}</p>
                      <small>
                        {typeof doc.size_bytes === "number"
                          ? `${(doc.size_bytes / 1024).toFixed(1)} KB`
                          : ""}
                      </small>
                    </div>
                    <div className="document-actions">
                      <button className="primary-small" onClick={() => handleView(doc)}>
                        <Icon name="eye" size={16} /> View / Read
                      </button>
                      {(doc.permissions || []).includes("download") && (
                        <button className="secondary-button" onClick={() => handleDownload(doc)}>
                          <Icon name="download" size={16} /> Download
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {isOwner && activePage === "Secure Sharing" && (
            <section className="panel">
              <h3>Secure document sharing</h3>
              <p>Share a document with a registered user.</p>

              {!isOwner ? (
                <p>Only document owners can grant or revoke sharing permissions.</p>
              ) : (
                <>
                  <form className="upload-form" onSubmit={handleShare}>
                    <label htmlFor="share-document">Document</label>
                    <select
                      id="share-document"
                      value={shareDocumentId}
                      onChange={(e) => setShareDocumentId(e.target.value)}
                      required
                    >
                      <option value="">Select a document</option>
                      {documents.map((doc) => (
                        <option key={doc.id} value={doc.id}>
                          {doc.filename || doc.original_filename || `Document ${doc.id}`}
                        </option>
                      ))}
                    </select>

                    <label htmlFor="share-user-id">Registered user ID</label>
                    <input
                      id="share-user-id"
                      type="number"
                      min="1"
                      value={shareUserId}
                      onChange={(e) => setShareUserId(e.target.value)}
                      placeholder="Enter user ID"
                      required
                    />

                    <p>Access level</p>
                    <label className="permission-option">
                      <input
                        type="radio"
                        name="share-access-level"
                        checked={sharePermissions.length === 1 && sharePermissions.includes("view")}
                        onChange={() => setSharePermissions(["view"])}
                      />
                      <span>
                        <strong>View only</strong>
                        <small>Viewer can read the document inside TrustVault.</small>
                      </span>
                    </label>
                    <label className="permission-option">
                      <input
                        type="radio"
                        name="share-access-level"
                        checked={sharePermissions.includes("view") && sharePermissions.includes("download")}
                        onChange={() => setSharePermissions(["view", "download"])}
                      />
                      <span>
                        <strong>View + Download</strong>
                        <small>Viewer can read the document and download a copy.</small>
                      </span>
                    </label>

                    <button className="primary-small" disabled={sharing || documents.length === 0}>
                      {sharing ? "Sharing..." : "Share document"}
                    </button>
                    {shareMessage && <p role="status">{shareMessage}</p>}
                  </form>

                </>
              )}
            </section>
          )}

          {isOwner && activePage === "Revoke Access" && (
            <section className="panel">
              <h3>Revoke document access</h3>
              <p>Remove a viewer's permission to access one of your documents.</p>
              <form className="upload-form" onSubmit={handleRevoke}>
                <label htmlFor="revoke-document">Document</label>
                <select
                  id="revoke-document"
                  value={revokeDocumentId}
                  onChange={(e) => setRevokeDocumentId(e.target.value)}
                  required
                >
                  <option value="">Select a document</option>
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.filename || doc.original_filename || `Document ${doc.id}`}
                    </option>
                  ))}
                </select>

                <label htmlFor="revoke-user-id">Viewer user ID</label>
                <input
                  id="revoke-user-id"
                  type="number"
                  min="1"
                  value={revokeUserId}
                  onChange={(e) => setRevokeUserId(e.target.value)}
                  placeholder="Enter registered user ID"
                  required
                />

                <button className="primary-small" disabled={!revokeDocumentId || !revokeUserId}>
                  Revoke access
                </button>
                {revokeMessage && <p role="status">{revokeMessage}</p>}
              </form>
            </section>
          )}

          {viewingDocument && (
            <div className="trustvault-viewer-backdrop" role="dialog" aria-modal="true" aria-label="Document reader">
              <section className="trustvault-viewer">
                <header className="trustvault-viewer-header">
                  <div>
                    <p className="eyebrow">SECURE DOCUMENT READER</p>
                    <h2>{viewingDocument.filename || viewingDocument.original_filename || "Document"}</h2>
                    <p className="muted">View-only access · Downloads are controlled by your permissions</p>
                  </div>
                  <button type="button" className="secondary-button" onClick={closeViewer}>Close reader</button>
                </header>
                <div className="trustvault-viewer-content">
                  {viewerLoading && <p className="loading-text">Opening document securely…</p>}
                  {viewerError && <p className="login-message" role="alert">{viewerError}</p>}
                  {!viewerLoading && !viewerError && viewerUrl && (
                    <>
                      {/^image\//i.test(viewingDocument.content_type || "") ? (
                        <div className="trustvault-image-stage">
                          <img src={viewerUrl} alt={viewingDocument.filename || "Shared document"} />
                        </div>
                      ) : (
                        <iframe
                          className="trustvault-document-frame"
                          src={
                            viewingDocument.content_type === "application/pdf"
                              ? `${viewerUrl}#toolbar=0&navpanes=0&scrollbar=1`
                              : viewerUrl
                          }
                          title={viewingDocument.filename || "Shared document"}
                          referrerPolicy="no-referrer"
                        />
                      )}
                      <div className="trustvault-watermark" aria-hidden="true">
                        {session?.user?.email} · TRUSTVAULT · VIEW ONLY
                      </div>
                    </>
                  )}
                </div>
                <p className="trustvault-security-note">
                  This reader does not provide a download control for view-only access. Screenshots and external recording cannot be reliably blocked by a browser.
                </p>
              </section>
            </div>
          )}

          <footer className="dashboard-footer">
            <span>TrustVault · Secure document workspace</span>
            <span>Access is enforced by the backend</span>
          </footer>
        </section>
      </main>
    );
  }

  return (
    <main className="app">
      <nav className="navbar">
        <a className="brand" href="/">
          <span className="brand-icon">T</span> TrustVault
        </a>
        <span className="status">● Secure document workspace</span>
      </nav>

      <section className="login-layout">
        <div className="intro">
          <p className="eyebrow">YOUR FILES. YOUR CONTROL.</p>
          <h1>Security starts<br />with <span>trust.</span></h1>
          <p className="description">
            A secure space for private documents, controlled sharing, and accountable access.
          </p>
          <div className="security-note">
            <span>✦</span>
            <div>
              <strong>Access with accountability</strong>
              <p>Permissions and document activity are enforced by the server.</p>
            </div>
          </div>
        </div>

        <section className="login-card">
          <p className="eyebrow">WELCOME BACK</p>
          <h2>Sign in to TrustVault</h2>
          <p className="muted">Choose your account role to continue.</p>

          <div className="role-list">
            {ROLES.map((role) => (
              <button
                type="button"
                key={role.id}
                className={`role-option ${selectedRole === role.id ? "selected" : ""}`}
                onClick={() => setSelectedRole(role.id)}
                aria-pressed={selectedRole === role.id}
              >
                
                  
                
                <span className="role-copy">
                  <strong>{role.title}</strong>
                  <small>{role.description}</small>
                </span>
                <span className="radio">{selectedRole === role.id ? "●" : "○"}</span>
              </button>
            ))}
          </div>

          <form onSubmit={handleLogin}>
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />

            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />

            <button className="submit-button" type="submit" disabled={loading}>
              {loading ? "Signing in..." : "Sign in securely →"}
            </button>
          </form>

          {message && <p className="login-message" role="alert">{message}</p>}

          <p className="fine-print">
            Selecting a role does not grant permissions. TrustVault verifies
            your account and access rights on the server.
          </p>
        </section>
      </section>
    </main>
  );
}

export default App;
