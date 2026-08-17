import PdfUpload from './PdfUpload'
import './Sidebar.css'

export default function Sidebar({ documents, chunkCount, onUpload, onNewChat }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 12a8 8 0 1116 0M4 12v6a2 2 0 002 2h1v-6H4zm16 0v6a2 2 0 01-2 2h-1v-6h3z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <div className="sidebar-title">3GPP assistant</div>
          <div className="sidebar-subtitle">RAG-grounded spec Q&amp;A</div>
        </div>
      </div>

      <button className="sidebar-new-chat" onClick={onNewChat}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
          <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        New conversation
      </button>

      <div className="sidebar-section">
        <div className="sidebar-section-title">Knowledge base</div>

        <PdfUpload onUploadComplete={onUpload} />

        {documents.length > 0 ? (
          <ul className="kb-doc-list">
            {documents.map((d) => (
              <li key={d} className="kb-doc-item">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M6 2h9l5 5v15H6V2z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                  <path d="M15 2v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                </svg>
                <span className="kb-doc-name">{d}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="kb-hint">Upload a 3GPP spec PDF to get grounded, cited answers.</p>
        )}

        {documents.length > 0 && (
          <div className="kb-status kb-status-active">
            <span className="kb-dot kb-dot-active" />
            {chunkCount} clauses indexed
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-legend">
          <div className="legend-row">
            <span className="legend-dot legend-dot-teal" />
            Grounded in spec
          </div>
          <div className="legend-row">
            <span className="legend-dot legend-dot-muted" />
            General knowledge
          </div>
        </div>
      </div>
    </aside>
  )
}
