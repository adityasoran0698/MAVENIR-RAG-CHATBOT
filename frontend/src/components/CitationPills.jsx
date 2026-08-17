import './CitationPills.css'

export default function CitationPills({ sources }) {
  if (!sources || sources.length === 0) return null

  return (
    <div className="citation-pills">
      {sources.map((src) => (
        <span key={src} className="citation-pill">
          <svg width="10" height="12" viewBox="0 0 24 28" fill="none" aria-hidden="true">
            <path
              d="M4 2h16v24l-8-5-8 5V2z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
            />
          </svg>
          {src}
        </span>
      ))}
    </div>
  )
}
