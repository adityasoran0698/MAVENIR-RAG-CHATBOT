import SignalIndicator from "./SignalIndicator";
import CitationPills from "./CitationPills";
import "./MessageBubble.css";

export default function MessageBubble({ message }) {
  const {
    role,
    content,
    mode,
    grounded,
    sources,
    flaggedClaims,
    error,
    streaming,
  } = message;

  const isUser = role === "user";

  if (isUser) {
    return (
      <div className="msg-row msg-row-user">
        <div className="msg-bubble msg-bubble-user">{content}</div>
      </div>
    );
  }

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

      <div className="msg-body">
        <div
          className={`msg-bubble msg-bubble-assistant ${
            error ? "msg-bubble-error" : ""
          }`}
        >
          {mode && (
            <div className="msg-meta">
              <SignalIndicator mode={mode} grounded={grounded} />

              <span className="msg-meta-label">
                {mode === "rag"
                  ? grounded
                    ? "grounded in spec"
                    : "partially grounded"
                  : "general knowledge"}
              </span>
            </div>
          )}

          {streaming && !content ? (
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          ) : (
            <p className="msg-text">{content}</p>
          )}

          {flaggedClaims && flaggedClaims.length > 0 && (
            <div className="msg-flagged">
              <span className="msg-flagged-title">Unverified claims</span>

              <ul>
                {flaggedClaims.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          <CitationPills sources={sources} />
        </div>
      </div>
    </div>
  );
}
