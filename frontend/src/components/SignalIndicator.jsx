import './SignalIndicator.css'

// Visual metaphor: grounded answers show full signal bars (like a real
// network connection), ungrounded/plain-chat answers show a single dim bar.
// This ties the hallucination-reduction thesis directly to the telecom
// domain instead of using a generic checkmark/badge.
export default function SignalIndicator({ mode, grounded }) {
  const strength = mode === 'rag' && grounded ? 4 : mode === 'rag' ? 2 : 1
  const label =
    mode === 'plain'
      ? 'No document indexed — general knowledge'
      : grounded
      ? 'Grounded in indexed specification'
      : 'Partially grounded — see flagged claims'

  return (
    <div className="signal" title={label} role="img" aria-label={label}>
      {[1, 2, 3, 4].map((bar) => (
        <span
          key={bar}
          className={`signal-bar ${bar <= strength ? 'signal-bar-active' : ''} ${
            mode === 'rag' && grounded ? 'signal-bar-pulse' : ''
          }`}
          style={{ height: `${bar * 3 + 3}px`, animationDelay: `${bar * 80}ms` }}
        />
      ))}
    </div>
  )
}
