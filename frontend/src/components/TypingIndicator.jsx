import './TypingIndicator.css'

export default function TypingIndicator() {
  return (
    <div className="msg-row msg-row-assistant">
      <div className="msg-avatar" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path
            d="M4 12a8 8 0 1116 0M4 12v6a2 2 0 002 2h1v-6H4zm16 0v6a2 2 0 01-2 2h-1v-6h3z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <div className="typing-bubble" aria-label="Assistant is responding">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  )
}
