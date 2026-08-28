import { useEffect, useState } from 'react'
import { api } from '../api'
import ThemeToggle from '../components/ThemeToggle'

export default function Landing({ onStart }) {
  const [terms, setTerms] = useState([])
  const [termKey, setTermKey] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.terms()
      .then(rows => {
        setTerms(rows)
        if (rows.length) setTermKey(rows[0].key)
      })
      .catch(e => setError(String(e.message ?? e)))
  }, [])

  return (
    <div className="landing">
      <nav className="top-nav">
        <span className="wordmark">sked.</span>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <ThemeToggle />
          <button className="btn-outline" onClick={() => onStart('saved')}>Saved</button>
        </div>
      </nav>

      <section className="hero">
        <div className="hero-inner">
          <p className="eyebrow">Rutgers course scheduling</p>
          <h1 className="hero-title">Your semester,<br />solved.</h1>
          <p className="hero-sub">
            Pick your courses, lock the sections you already know, describe what
            matters in plain language — and get ranked, conflict-free schedules
            with WebReg indexes ready to go.
          </p>
          <div className="hero-actions">
            {terms.length > 0 ? (
              <>
                <select
                  className="field term-picker"
                  value={termKey}
                  onChange={e => setTermKey(e.target.value)}
                >
                  {terms.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
                </select>
                <button className="btn-primary lg" onClick={() => onStart('builder', termKey)}>
                  Build my schedule
                </button>
              </>
            ) : (
              <p className="dim">
                {error
                  ? `Backend unreachable: ${error}`
                  : 'No terms synced yet — run: python -m backend.class_scheduler.sync 2026 fall NB'}
              </p>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
