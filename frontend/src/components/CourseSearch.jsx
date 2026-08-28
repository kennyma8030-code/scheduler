import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { fmtCredits } from '../lib'

// Debounced typeahead over /api/courses/search.
export default function CourseSearch({ termKey, onPick, placeholder }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)
  const boxRef = useRef(null)

  useEffect(() => {
    function onDocClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  function onChange(value) {
    setQuery(value)
    clearTimeout(timer.current)
    if (value.trim().length < 2) { setResults([]); setOpen(false); return }
    timer.current = setTimeout(async () => {
      setBusy(true)
      try {
        const rows = await api.searchCourses(termKey, value.trim())
        setResults(rows)
        setOpen(true)
      } catch { setResults([]) }
      setBusy(false)
    }, 200)
  }

  function pick(row) {
    onPick(row)
    setQuery('')
    setResults([])
    setOpen(false)
  }

  return (
    <div className="course-search" ref={boxRef}>
      <input
        className="field"
        value={query}
        placeholder={placeholder ?? 'Search courses — "data structures", "01:198:112", "cs"…'}
        onChange={e => onChange(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
      />
      {busy && <span className="cs-busy">…</span>}
      {open && results.length > 0 && (
        <div className="cs-dropdown">
          {results.map(row => (
            <button
              key={`${row.course_string}|${row.supplement}`}
              className="cs-row"
              onClick={() => pick(row)}
            >
              <span className="cs-course">{row.course_string}{row.supplement ? ` (${row.supplement})` : ''}</span>
              <span className="cs-title">{row.title}</span>
              <span className="cs-meta">
                {fmtCredits(row.credits)} cr · {row.open_section_count}/{row.section_count} open
                {row.core_codes.length > 0 && ` · ${row.core_codes.join(' ')}`}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
