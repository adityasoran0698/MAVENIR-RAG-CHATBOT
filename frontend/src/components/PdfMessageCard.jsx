import './PdfMessageCard.css'

export default function PdfMessageCard({ filename, numChunks }) {
  return (
    <div className="msg-row msg-row-assistant">
      <div className="pdf-card">
        <div className="pdf-card-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M6 2h9l5 5v15H6V2z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
            <path d="M15 2v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="pdf-card-info">
          <span className="pdf-card-name">{filename}</span>
          <span className="pdf-card-meta">{numChunks} clauses indexed · ready to query</span>
        </div>
        <div className="pdf-card-badge">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
            <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
    </div>
  )
}
