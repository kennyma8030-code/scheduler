import { useState } from 'react'
import { api } from '../api'
import { DAY_NAMES, campusLabel, fmtCredits, fmtTime } from '../lib'

// The requirement chips, and the lock-level control on each: an exact section
// (skeleton), any section of the course, or a flexible core group. Tighter
// locks mean a faster, more focused generation run.

function describeMeetings(meetings) {
  const timed = meetings.filter(m => m.day !== null && m.start !== null)
  if (!timed.length) return 'asynchronous'
  return timed
    .map(m => `${DAY_NAMES[m.day]} ${fmtTime(m.start)}–${fmtTime(m.end)} ${campusLabel(m.campus_code)}`)
    .join(' · ')
}

function SectionPicker({ termKey, req, onLock }) {
  const [sections, setSections] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      const detail = await api.courseDetail(termKey, req.course.course_string, req.course.supplement)
      setSections(detail.sections)
    } catch (e) { setError(String(e.message ?? e)) }
  }
  if (sections === null) {
    load()
    return <div className="sp-loading">{error || 'loading sections…'}</div>
  }
  return (
    <div className="section-picker">
      <button
        className={`sp-row ${!req.lockedIndex ? 'on' : ''}`}
        onClick={() => onLock(null)}
      >
        <span className="sp-index">any</span>
        <span className="sp-meta">let the generator choose ({sections.length} sections)</span>
      </button>
      {sections.map(s => (
        <button
          key={s.index}
          className={`sp-row ${req.lockedIndex === s.index ? 'on' : ''} ${s.open ? '' : 'closed'}`}
          onClick={() => onLock(s.index)}
        >
          <span className="sp-index">{s.index}</span>
          <span className={`badge ${s.open ? 'open' : 'closed'}`}>{s.open ? 'open' : 'closed'}</span>
          <span className="sp-meta">
            {describeMeetings(s.meetings)}
            {s.instructors.length > 0 && ` — ${s.instructors.join(', ')}`}
          </span>
        </button>
      ))}
    </div>
  )
}

export default function RequirementList({ termKey, requirements, onChange }) {
  const [expanded, setExpanded] = useState(null)

  function update(id, patch) {
    onChange(requirements.map(r => (r.id === id ? { ...r, ...patch } : r)))
  }
  function remove(id) {
    onChange(requirements.filter(r => r.id !== id))
    if (expanded === id) setExpanded(null)
  }

  const creditTotal = requirements.reduce(
    (sum, r) => sum + (r.kind === 'course' ? (r.course.credits ?? 3) : 3), 0
  )

  return (
    <div className="req-list">
      {requirements.length === 0 && (
        <p className="req-empty">Add the courses you're taking. Lock exact sections
        where you know them — the tighter the locks, the faster the search.</p>
      )}
      {requirements.map(req => (
        <div key={req.id} className="req-chip-wrap">
          <div className="req-chip">
            {req.kind === 'course' ? (
              <>
                <span className="req-course">{req.course.course_string}</span>
                <span className="req-title">{req.course.title}</span>
                <span className="req-credits">{fmtCredits(req.course.credits)} cr</span>
                <button
                  className={`req-lock ${req.lockedIndex ? 'locked' : ''}`}
                  title="Lock level"
                  onClick={() => setExpanded(expanded === req.id ? null : req.id)}
                >
                  {req.lockedIndex ? `idx ${req.lockedIndex}` : 'any section'} ▾
                </button>
              </>
            ) : (
              <>
                <span className="req-course core">core {req.core_code}</span>
                <span className="req-title">{req.description}</span>
                <span className="req-flexible">generator picks the course</span>
              </>
            )}
            <button className="req-remove" onClick={() => remove(req.id)} title="Remove">×</button>
          </div>
          {expanded === req.id && req.kind === 'course' && (
            <SectionPicker
              termKey={termKey}
              req={req}
              onLock={index => { update(req.id, { lockedIndex: index }); setExpanded(null) }}
            />
          )}
        </div>
      ))}
      {requirements.length > 0 && (
        <div className="req-total">≈ {creditTotal} credits · {requirements.length} requirement{requirements.length === 1 ? '' : 's'}</div>
      )}
    </div>
  )
}
