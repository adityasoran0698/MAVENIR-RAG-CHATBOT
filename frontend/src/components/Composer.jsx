import { useState, useRef, useEffect } from 'react'
import './Composer.css'

export default function Composer({ onSend, disabled, indexed }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [value])

  const handleSubmit = (e) => {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-box">
        <textarea
          ref={textareaRef}
          className="composer-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            indexed
              ? 'Ask about a 3GPP procedure, clause, or parameter…'
              : 'Ask anything — index a spec on the left for grounded, cited answers'
          }
          rows={1}
          disabled={disabled}
        />
        <button
          type="submit"
          className="composer-send"
          disabled={disabled || !value.trim()}
          aria-label="Send message"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 12l16-8-6 8 6 8-16-8z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
      <div className="composer-hint">Enter to send · Shift+Enter for new line</div>
    </form>
  )
}
