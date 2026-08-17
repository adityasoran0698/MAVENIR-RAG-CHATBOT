import { useRef, useState } from 'react'
import './PdfUpload.css'

const STAGES = [
  { key: 'uploading', label: 'Uploading document' },
  { key: 'chunking', label: 'Chunking by clause' },
  { key: 'embedding', label: 'Generating embeddings' },
  { key: 'storing', label: 'Storing in vector index' },
]

export default function PdfUpload({ onUploadComplete, disabled }) {
  const inputRef = useRef(null)
  const [status, setStatus] = useState('idle') // idle | working | done | error
  const [progress, setProgress] = useState(0)
  const [stageIndex, setStageIndex] = useState(0)
  const [fileName, setFileName] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = '' // allow re-selecting the same file later

    setFileName(file.name)
    setStatus('working')
    setStageIndex(0)
    setProgress(0)
    setErrorMsg('')

    try {
      const resultPromise = onUploadComplete(file, (pct) => {
        setProgress(pct)
        if (pct >= 100) {
          setStageIndex(1)
        }
      })

      // Step through the remaining stages on a steady cadence for UX, but
      // never let this outlive the real request - it's cleared as soon as
      // the backend actually responds (see below), so a fast response
      // still ends on the correct final stage instead of a stale label.
      let i = 1
      const interval = setInterval(() => {
        i = Math.min(i + 1, STAGES.length - 1)
        setStageIndex(i)
      }, 700)

      await resultPromise
      clearInterval(interval)
      setStageIndex(STAGES.length - 1)
      setStatus('done')
      setTimeout(() => setStatus('idle'), 2200)
    } catch (err) {
      setStatus('error')
      setErrorMsg(err.message || 'Upload failed')
    }
  }

  return (
    <div className="pdf-upload">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        disabled={disabled || status === 'working'}
        className="pdf-upload-input"
        id="pdf-upload-input"
      />
      <label
        htmlFor="pdf-upload-input"
        className={`pdf-upload-dropzone ${status === 'working' ? 'pdf-upload-working' : ''} ${
          disabled ? 'pdf-upload-disabled' : ''
        }`}
      >
        {status === 'idle' && (
          <>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 3v12m0-12l-4 4m4-4l4 4M5 17v2a2 2 0 002 2h10a2 2 0 002-2v-2"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>Upload a spec PDF</span>
          </>
        )}

        {status === 'working' && (
          <div className="pdf-upload-progress">
            <div className="pdf-upload-progress-header">
              <span className="pdf-upload-filename">{fileName}</span>
              {stageIndex === 0 && <span className="pdf-upload-pct">{progress}%</span>}
            </div>
            <div className="pdf-upload-bar-track">
              <div
                className="pdf-upload-bar-fill"
                style={{
                  width: stageIndex === 0 ? `${progress}%` : '100%',
                }}
              />
            </div>
            <span className="pdf-upload-stage">{STAGES[stageIndex].label}…</span>
          </div>
        )}

        {status === 'done' && (
          <div className="pdf-upload-done">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>{fileName} indexed</span>
          </div>
        )}

        {status === 'error' && (
          <div className="pdf-upload-error">
            <span>{errorMsg}</span>
            <span className="pdf-upload-retry">Click to retry</span>
          </div>
        )}
      </label>
    </div>
  )
}
