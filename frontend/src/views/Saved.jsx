import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import WeekGrid from '../components/WeekGrid'
import SectionCard from '../components/SectionCard'
import ThemeToggle from '../components/ThemeToggle'

export default function Saved({ onBack }) {
  const [rows, setRows] = useState([])
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.saved().then(setRows).catch(e => setError(String(e.message ?? e)))
  }, [])

  async function open(id) {
    setDetail(await api.loadSaved(id))
  }

  const week = useMemo(() => {
    if (!detail) return null
    const days = [[], [], [], [], [], [], []]
    for (const sel of detail.selections) {
      for (const m of sel.section.meetings) {
        if (m.day === null || m.start === null) continue
        days[m.day].push({
          start: m.start, end: m.end, index: sel.section.index,
          course_string: sel.course_string, campus_code: m.campus_code, mode: m.mode,
        })
      }
    }
    for (const day of days) day.sort((a, b) => a.start - b.start)
    return days
  }, [detail])

  const asyncCourses = useMemo(() => {
    if (!detail) return []
    return detail.selections
      .filter(sel => !sel.section.meetings.some(m => m.day !== null && m.start !== null))
      .map(sel => ({ course_string: sel.course_string, index: sel.section.index }))
  }, [detail])

  return (
    <div className="page results-page">
      <nav className="page-nav">
        <button className="btn-back" onClick={() => (detail ? setDetail(null) : onBack())}>
          ← Back
        </button>
        <span className="wordmark">sked.</span>
        <ThemeToggle />
      </nav>

      {!detail && (
        <>
          <div className="page-intro">
            <h2 className="page-title">Saved schedules</h2>
          </div>
          {error && <div className="error-box">{error}</div>}
          {rows.length === 0 && !error && <p className="dim">Nothing saved yet.</p>}
          <div className="saved-list">
            {rows.map(r => (
              <button key={r.id} className="saved-row" onClick={() => open(r.id)}>
                <span className="saved-name">{r.name || `schedule #${r.id}`}</span>
                <span className="dim">{r.term_key} · score {r.score ?? '—'} · {r.indexes.length} sections</span>
                <span className="dim">{new Date(r.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {detail && (
        <>
          <div className="page-intro">
            <h2 className="page-title">{detail.name || `schedule #${detail.id}`}</h2>
            <p className="page-sub">{detail.term_key}
              {detail.score !== null && ` · score ${detail.score}`}</p>
          </div>
          {detail.stale_indexes.length > 0 && (
            <div className="error-box">
              These indexes no longer exist after a catalog re-sync:{' '}
              {detail.stale_indexes.join(', ')} — regenerate to replace them.
            </div>
          )}
          <WeekGrid week={week} asyncCourses={asyncCourses} />
          <div className="section-cards">
            {detail.selections.map(sel => (
              <SectionCard key={sel.section.index} selection={sel} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
