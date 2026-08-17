import "./EmptyState.css";

const SUGGESTIONS = [
  "What is a network slice?",
  "Explain the role of the AMF",
  "What is the difference between AMF and SMF?",
  "Describe the PDU session establishment procedure",
];

export default function EmptyState({ indexed, onSuggestion }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
          <path
            d="M4 12a8 8 0 1116 0M4 12v6a2 2 0 002 2h1v-6H4zm16 0v6a2 2 0 01-2 2h-1v-6h3z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <h1 className="empty-title">Your 3GPP Standards RAG Assistant</h1>

      <p className="empty-subtitle">
        {indexed
          ? "Get grounded, citation-backed answers from Telecom 3GPP specifications with minimal hallucinations."
          : "Upload a 3GPP specification to get grounded, citation-backed answers with minimal hallucinations."}
      </p>

      <div className="empty-suggestions">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            className="suggestion-chip"
            onClick={() => onSuggestion(s)}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
