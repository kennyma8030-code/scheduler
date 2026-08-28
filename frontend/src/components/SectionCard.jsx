import { useState } from 'react'
import { DAY_NAMES, campusLabel, fmtCredits, fmtTime } from '../lib'

// One selected section in a result: the WebReg index (click to copy),
// instructors, meetings, open badge, final exam.
export default function SectionCard({ selection, openIndexes }) {
  const [copied, setCopied] = useState(false)
  const s = selection.section
  const isOpen = openIndexes ? openIndexes.has(s.index) : s.open

  function copyIndex() {
    navigator.clipboard?.writeText(s.index)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  const timed = s.meetings.filter(m => m.day !== null && m.start !== null)

  return (
    <div className="section-card">
      <div className="sc-head">
        <span className="sc-course">{selection.course_string}</span>
        <span className="sc-title">{selection.title}</span>
        <span className={`badge ${isOpen ? 'open' : 'closed'}`}>{isOpen ? 'open' : 'closed'}</span>
        {s.honors && <span className="badge honors">honors</span>}
      </div>
      <div className="sc-body">
        <button className="sc-index" onClick={copyIndex} title="Copy for WebReg">
          {copied ? 'copied!' : `index ${s.index}`}
        </button>
        <span className="sc-meta">
          {fmtCredits(selection.credits)} cr
          {s.instructors.length > 0 && ` · ${s.instructors.join(', ')}`}
        </span>
      </div>
      <div className="sc-meetings">
        {timed.length === 0 && <span className="dim">asynchronous — no scheduled meetings</span>}
        {timed.map((m, i) => (
          <span key={i} className="sc-meeting">
            {DAY_NAMES[m.day]} {fmtTime(m.start)}–{fmtTime(m.end)}
            <span className="dim"> {m.mode} · {campusLabel(m.campus_code)}</span>
          </span>
        ))}
      </div>
      {s.final_exam && <div className="sc-final dim">final: {s.final_exam}</div>}
    </div>
  )
}
