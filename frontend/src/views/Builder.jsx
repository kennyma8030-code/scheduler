import { useEffect, useState } from 'react'
import { api } from '../api'
import CourseSearch from '../components/CourseSearch'
import RequirementList from '../components/RequirementList'
import ThemeToggle from '../components/ThemeToggle'

const EXAMPLE_CHIPS = [
  'no 8ams', 'keep Fridays free', 'compact days, no long gaps',
  'leave time for lunch', 'done by 4pm', 'keep me off Busch if possible',
]

let nextId = 1

export default function Builder({ termKey, onBack, onResults }) {
  const [requirements, setRequirements] = useState([])
  const [coreCodes, setCoreCodes] = useState([])
  const [showCorePicker, setShowCorePicker] = useState(false)
  const [preferences, setPreferences] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.coreCodes(termKey).then(setCoreCodes).catch(() => {})
  }, [termKey])

  function addCourse(row) {
    const exists = requirements.some(
      r => r.kind === 'course'
        && r.course.course_string === row.course_string
        && r.course.supplement === row.supplement
    )
    if (exists) return
    setRequirements([...requirements, {
      id: nextId++, kind: 'course', course: row, lockedIndex: null,
    }])
  }

  function addCore(code, description) {
    setRequirements([...requirements, {
      id: nextId++, kind: 'core', core_code: code, description,
    }])
    setShowCorePicker(false)
  }

  function toPayload() {
    return requirements.map(r => {
      if (r.kind === 'core') return { kind: 'core', core_code: r.core_code }
      if (r.lockedIndex) {
        return {
          kind: 'section',
          course_string: r.course.course_string,
          supplement: r.course.supplement,
          index: r.lockedIndex,
        }
      }
      return {
        kind: 'course',
        course_string: r.course.course_string,
        supplement: r.course.supplement,
      }
    })
  }

  async function generate() {
    setBusy(true)
    setError('')
    try {
      const out = await api.generate({
        term_key: termKey,
        requirements: toPayload(),
        preferences_text: preferences,
      })
      onResults(out, { termKey, requirements: toPayload(), preferences })
    } catch (e) {
      setError(String(e.message ?? e))
    }
    setBusy(false)
  }

  return (
    <div className="page">
      <nav className="page-nav">
        <button className="btn-back" onClick={onBack}>← Back</button>
        <span className="wordmark">sked.</span>
        <ThemeToggle />
      </nav>

      <div className="page-intro">
        <h2 className="page-title">Build {termKey}</h2>
        <p className="page-sub">
          Add courses, lock what you already know, and let the generator fill
          the rest. Fully flexible searches take longer — that's expected.
        </p>
      </div>

      <div className="builder-grid">
        <div className="builder-left">
          <CourseSearch termKey={termKey} onPick={addCourse} />
          <div className="builder-actions-row">
            <button className="btn-outline sm" onClick={() => setShowCorePicker(!showCorePicker)}>
              + core requirement
            </button>
          </div>
          {showCorePicker && (
            <div className="core-picker">
              {coreCodes.map(c => (
                <button key={c.code} className="core-row" onClick={() => addCore(c.code, c.description)}>
                  <span className="core-code">{c.code}</span>
                  <span className="core-desc">{c.description}</span>
                  <span className="dim">{c.course_count} courses</span>
                </button>
              ))}
            </div>
          )}
          <RequirementList
            termKey={termKey}
            requirements={requirements}
            onChange={setRequirements}
          />
        </div>

        <div className="builder-right">
          <h3 className="prefs-title">Preferences</h3>
          <textarea
            className="prefs-box"
            value={preferences}
            placeholder="Write naturally — the AI turns this into weighted constraints. e.g. &quot;No classes before 10, keep Fridays light, I really want Professor Centeno for data structures, and give me a lunch break.&quot;"
            onChange={e => setPreferences(e.target.value)}
          />
          <div className="prefs-chips">
            {EXAMPLE_CHIPS.map(chip => (
              <button
                key={chip}
                className="prefs-chip"
                onClick={() => setPreferences(p => (p ? `${p.replace(/[.\s]*$/, '')}. ${chip}` : chip))}
              >
                {chip}
              </button>
            ))}
          </div>
          {error && <div className="error-box">{error}</div>}
          <button
            className="btn-primary lg generate-btn"
            disabled={busy || requirements.length === 0}
            onClick={generate}
          >
            {busy ? 'Generating…' : 'Generate schedules'}
          </button>
        </div>
      </div>
    </div>
  )
}
