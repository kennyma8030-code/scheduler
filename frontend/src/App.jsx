import { useState, useEffect } from 'react'

// ── Color palette for event blocks ────────────────────────────────────────────
const PALETTE = [
  '#cdd8f0', '#bfd8c4', '#f0d8c4', '#d8c4f0',
  '#f0c4c8', '#f0e4c0', '#c0e4e4', '#dce8c0',
  '#e0cce8', '#fad8b0', '#b8dce8', '#e8d0b8',
  '#d4e8c0', '#f0cce0', '#c8dcd0', '#e4dcc8',
  '#b8c8e4', '#e8c8d4', '#d0e0b8', '#c8d4e8',
]

const CATEGORY_COLORS = {
  sleep:    '#b8cce8',
  work:     '#f0dca0',
  study:    '#c8e0b0',
  exercise: '#f4b8b0',
  personal: '#dcc8f0',
  social:   '#f0ccb0',
  errands:  '#c8c8c8',
  leisure:  '#b0dcd0',
  other:    '#d8d4ce',
}

function hashColor(name) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (Math.imul(31, h) + name.charCodeAt(i)) | 0
  return PALETTE[Math.abs(h) % PALETTE.length]
}

function eventColor(name, categories) {
  const cat = categories?.[name]
  return cat ? (CATEGORY_COLORS[cat] ?? hashColor(name)) : hashColor(name)
}

function fmtHour(h) {
  if (h === 0 || h === 24) return '12a'
  if (h === 12) return '12p'
  return h < 12 ? `${h}a` : `${h - 12}p`
}

const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const DAY_NAMES  = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function fmtDays(days) {
  if (!days || days.length === 7) return 'Every day'
  const sorted = [...days].sort((a, b) => a - b)
  if (sorted.length === 5 && !sorted.includes(5) && !sorted.includes(6)) return 'Weekdays'
  if (sorted.length === 2 && sorted.includes(5) && sorted.includes(6)) return 'Weekends'
  return sorted.map(d => DAY_LABELS[d]).join(' ')
}

// ── Landing ───────────────────────────────────────────────────────────────────
function Landing({ onStart }) {
  return (
    <div className="landing">
      <nav className="top-nav">
        <span className="wordmark">sync.</span>
        <button className="btn-outline" onClick={() => onStart('daily')}>Open app</button>
      </nav>

      <section className="hero">
        <div className="hero-inner">
          <p className="eyebrow">Roommate scheduling</p>
          <h1 className="hero-title">
            Schedules that<br />work for both.
          </h1>
          <p className="hero-sub">
            Enter your events, describe what matters to you in plain language,
            and get ranked schedule combinations built around your preferences.
          </p>
          <div className="hero-actions">
            <button className="btn-primary lg" onClick={() => onStart('daily')}>Daily schedule</button>
            <button className="btn-outline lg" onClick={() => onStart('weekly')}>Weekly schedule</button>
          </div>
        </div>
      </section>

      <div className="steps">
        {[
          ['01', 'Add schedules', 'Enter fixed commitments and flexible activities for each roommate.'],
          ['02', 'Describe preferences', 'Write naturally what matters. The AI parses and applies constraints.'],
          ['03', 'Browse results', 'Get ranked schedule combinations that satisfy your constraints.'],
        ].map(([num, title, desc]) => (
          <div key={num} className="step">
            <span className="step-num">{num}</span>
            <h3 className="step-title">{title}</h3>
            <p className="step-desc">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── RoommateForm ──────────────────────────────────────────────────────────────
function blankFixed()    { return { name: '', start: 8,  finish: 10, in_dorm: false } }
function blankFlexible() { return { name: '', duration: 2, in_dorm: false } }

function RoommateForm({ label, data, onChange }) {
  const [tab,  setTab]  = useState('fixed')
  const [form, setForm] = useState(blankFixed())

  function switchTab(t) {
    setTab(t)
    setForm(t === 'fixed' ? blankFixed() : blankFlexible())
  }

  function add() {
    if (!form.name.trim()) return
    const ev = { ...form, name: form.name.trim() }
    if (tab === 'fixed') {
      onChange({ ...data, fixed: [...data.fixed, ev] })
    } else {
      onChange({ ...data, flexible: [...data.flexible, ev] })
    }
    setForm(tab === 'fixed' ? blankFixed() : blankFlexible())
  }

  function removeFixed(i)    { onChange({ ...data, fixed:    data.fixed.filter((_, j) => j !== i) }) }
  function removeFlexible(i) { onChange({ ...data, flexible: data.flexible.filter((_, j) => j !== i) }) }

  return (
    <div className={`roommate-card ${label.toLowerCase()}`}>
      <div className="card-head">
        <span className="card-badge">{label}</span>
        <input
          className="name-input"
          placeholder="Roommate name"
          value={data.name}
          onChange={e => onChange({ ...data, name: e.target.value })}
        />
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'fixed'    ? 'on' : ''}`} onClick={() => switchTab('fixed')}>Fixed</button>
        <button className={`tab ${tab === 'flexible' ? 'on' : ''}`} onClick={() => switchTab('flexible')}>Flexible</button>
      </div>

      <div className="add-form">
        <input
          className="field"
          placeholder="Event name"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          onKeyDown={e => e.key === 'Enter' && add()}
        />
        <div className="inline-row">
          {tab === 'fixed' ? (
            <>
              <div className="lbl-field">
                <label>Start</label>
                <input type="number" className="field sm" min={0} max={23}
                  value={form.start === '' ? '' : form.start}
                  onChange={e => setForm({ ...form, start: e.target.value === '' ? '' : +e.target.value })}
                  onBlur={() => setForm(f => ({ ...f, start: f.start === '' ? 0 : f.start }))} />
              </div>
              <div className="lbl-field">
                <label>End</label>
                <input type="number" className="field sm" min={1} max={24}
                  value={form.finish === '' ? '' : form.finish}
                  onChange={e => setForm({ ...form, finish: e.target.value === '' ? '' : +e.target.value })}
                  onBlur={() => setForm(f => ({ ...f, finish: f.finish === '' ? 0 : f.finish }))} />
              </div>
            </>
          ) : (
            <div className="lbl-field">
              <label>Duration (hrs)</label>
              <input type="number" className="field sm" min={1} max={12}
                value={form.duration}
                onChange={e => setForm({ ...form, duration: +e.target.value })} />
            </div>
          )}
          <label className="dorm-check">
            <input type="checkbox" checked={form.in_dorm}
              onChange={e => setForm({ ...form, in_dorm: e.target.checked })} />
            In dorm
          </label>
          <button className="btn-add" onClick={add}>Add</button>
        </div>
      </div>

      <div className="ev-list">
        {data.fixed.length === 0 && data.flexible.length === 0 ? (
          <p className="ev-empty">No events added yet.</p>
        ) : (
          <>
            {data.fixed.map((ev, i) => (
              <div key={`f${i}`} className="ev-row">
                <span className="ev-dot" style={{ background: hashColor(ev.name) }} />
                <span className="ev-name">{ev.name}</span>
                <span className="ev-meta">{fmtHour(ev.start)}-{fmtHour(ev.finish)}</span>
                <button className="ev-del" onClick={() => removeFixed(i)}>x</button>
              </div>
            ))}
            {data.flexible.map((ev, i) => (
              <div key={`fl${i}`} className="ev-row">
                <span className="ev-dot" style={{ background: hashColor(ev.name) }} />
                <span className="ev-name">{ev.name}</span>
                <span className="ev-meta">{ev.duration}h flex</span>
                <button className="ev-del" onClick={() => removeFlexible(i)}>x</button>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

// ── DayPicker ─────────────────────────────────────────────────────────────────
function DayPicker({ days, onChange }) {
  function toggle(d) {
    if (days.includes(d)) {
      if (days.length === 1) return
      onChange(days.filter(x => x !== d))
    } else {
      onChange([...days, d].sort((a, b) => a - b))
    }
  }
  return (
    <div className="day-picker">
      <div className="day-btns">
        {DAY_LABELS.map((lbl, d) => (
          <button key={d} type="button" className={`day-btn ${days.includes(d) ? 'on' : ''}`} onClick={() => toggle(d)}>
            {lbl}
          </button>
        ))}
      </div>
      <div className="day-presets">
        <button type="button" className="day-preset" onClick={() => onChange([0,1,2,3,4,5,6])}>All</button>
        <button type="button" className="day-preset" onClick={() => onChange([0,1,2,3,4])}>Wkdays</button>
        <button type="button" className="day-preset" onClick={() => onChange([5,6])}>Wkend</button>
      </div>
    </div>
  )
}

// ── WeeklyRoommateForm ────────────────────────────────────────────────────────
function blankWeeklyFixed()    { return { name: '', start: 8,  finish: 10, in_dorm: false, days: [0,1,2,3,4,5,6] } }
function blankWeeklyFlexible() { return { name: '', duration: 2, in_dorm: false, days: [0,1,2,3,4,5,6] } }

function WeeklyRoommateForm({ label, data, onChange }) {
  const [tab,  setTab]  = useState('fixed')
  const [form, setForm] = useState(blankWeeklyFixed())

  function switchTab(t) {
    setTab(t)
    setForm(t === 'fixed' ? blankWeeklyFixed() : blankWeeklyFlexible())
  }

  function add() {
    if (!form.name.trim()) return
    const ev = { ...form, name: form.name.trim() }
    if (tab === 'fixed') {
      onChange({ ...data, fixed: [...data.fixed, ev] })
    } else {
      onChange({ ...data, flexible: [...data.flexible, ev] })
    }
    setForm(tab === 'fixed' ? blankWeeklyFixed() : blankWeeklyFlexible())
  }

  function removeFixed(i)    { onChange({ ...data, fixed:    data.fixed.filter((_, j) => j !== i) }) }
  function removeFlexible(i) { onChange({ ...data, flexible: data.flexible.filter((_, j) => j !== i) }) }

  return (
    <div className={`roommate-card ${label.toLowerCase()}`}>
      <div className="card-head">
        <span className="card-badge">{label}</span>
        <input
          className="name-input"
          placeholder="Roommate name"
          value={data.name}
          onChange={e => onChange({ ...data, name: e.target.value })}
        />
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'fixed'    ? 'on' : ''}`} onClick={() => switchTab('fixed')}>Fixed</button>
        <button className={`tab ${tab === 'flexible' ? 'on' : ''}`} onClick={() => switchTab('flexible')}>Flexible</button>
      </div>

      <div className="add-form">
        <input
          className="field"
          placeholder="Event name"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
          onKeyDown={e => e.key === 'Enter' && add()}
        />
        <div className="inline-row">
          {tab === 'fixed' ? (
            <>
              <div className="lbl-field">
                <label>Start</label>
                <input type="number" className="field sm" min={0} max={23}
                  value={form.start === '' ? '' : form.start}
                  onChange={e => setForm({ ...form, start: e.target.value === '' ? '' : +e.target.value })}
                  onBlur={() => setForm(f => ({ ...f, start: f.start === '' ? 0 : f.start }))} />
              </div>
              <div className="lbl-field">
                <label>End</label>
                <input type="number" className="field sm" min={1} max={24}
                  value={form.finish === '' ? '' : form.finish}
                  onChange={e => setForm({ ...form, finish: e.target.value === '' ? '' : +e.target.value })}
                  onBlur={() => setForm(f => ({ ...f, finish: f.finish === '' ? 0 : f.finish }))} />
              </div>
            </>
          ) : (
            <div className="lbl-field">
              <label>Duration (hrs)</label>
              <input type="number" className="field sm" min={1} max={12}
                value={form.duration}
                onChange={e => setForm({ ...form, duration: +e.target.value })} />
            </div>
          )}
          <label className="dorm-check">
            <input type="checkbox" checked={form.in_dorm}
              onChange={e => setForm({ ...form, in_dorm: e.target.checked })} />
            In dorm
          </label>
          <button className="btn-add" onClick={add}>Add</button>
        </div>
        <DayPicker days={form.days} onChange={days => setForm({ ...form, days })} />
      </div>

      <div className="ev-list">
        {data.fixed.length === 0 && data.flexible.length === 0 ? (
          <p className="ev-empty">No events added yet.</p>
        ) : (
          <>
            {data.fixed.map((ev, i) => (
              <div key={`f${i}`} className="ev-row">
                <span className="ev-dot" style={{ background: hashColor(ev.name) }} />
                <span className="ev-name">{ev.name}</span>
                <span className="ev-meta">{fmtHour(ev.start)}-{fmtHour(ev.finish)} · {fmtDays(ev.days)}</span>
                <button className="ev-del" onClick={() => removeFixed(i)}>x</button>
              </div>
            ))}
            {data.flexible.map((ev, i) => (
              <div key={`fl${i}`} className="ev-row">
                <span className="ev-dot" style={{ background: hashColor(ev.name) }} />
                <span className="ev-name">{ev.name}</span>
                <span className="ev-meta">{ev.duration}h flex · {fmtDays(ev.days)}</span>
                <button className="ev-del" onClick={() => removeFlexible(i)}>x</button>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

// ── Timeline ──────────────────────────────────────────────────────────────────
const HOUR_H = 24

function Timeline({ blocks, name, startHour, endHour, hh = HOUR_H, categories }) {
  const totalH = (endHour - startHour) * hh
  const hours = []
  for (let h = startHour; h <= endHour; h++) hours.push(h)

  return (
    <div className="timeline-v">
      <p className="tl-v-header">{name}</p>
      <div className="tl-v-wrap">
        <div className="tl-v-times" style={{ height: totalH }}>
          {hours.map(h => (
            <span
              key={h}
              className="tl-v-hour-label"
              style={{ top: (h - startHour) * hh }}
            >
              {fmtHour(h)}
            </span>
          ))}
        </div>
        <div className="tl-v-col" style={{ height: totalH }}>
          {hours.slice(1).map(h => (
            <div
              key={h}
              className="tl-v-rule"
              style={{ top: (h - startHour) * hh }}
            />
          ))}
          {blocks.map((b, i) => {
            const dur = b.finish - b.start
            const segClass = dur < 0.75 ? 'tl-v-seg xs' : dur < 1.25 ? 'tl-v-seg sm' : 'tl-v-seg'
            return (
              <div
                key={i}
                className={segClass}
                style={{
                  top:    (b.start  - startHour) * hh + 3,
                  height: (b.finish - b.start)   * hh - 6,
                  background: eventColor(b.event, categories),
                  animationDelay: `${i * 0.08}s`,
                }}
              >
                <span className="tl-v-seg-name">{b.event}</span>
                {dur >= 1.25 && <span className="tl-v-seg-time">{fmtHour(b.start)}–{fmtHour(b.finish)}</span>}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── ScheduleCarousel ──────────────────────────────────────────────────────────
// Overhead inside fullscreen card (px): padding(44) + header(64) + tl-name(24) + nav(62) + card-gap(60)
const FS_OVERHEAD = 254

function CarouselContent({ result, idx, total, nameA, nameB, onPrev, onNext, fullscreen, onToggleFullscreen, rankLabel, categories }) {
  const startHour = 0
  const endHour   = 24
  const hh = fullscreen
    ? Math.max(16, Math.floor((window.innerHeight - FS_OVERHEAD) / 24))
    : HOUR_H

  useEffect(() => {
    if (!fullscreen) return
    function onKey(e) {
      if (e.key === 'ArrowLeft')  onPrev()
      if (e.key === 'ArrowRight') onNext()
      if (e.key === 'Escape')     onToggleFullscreen()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [fullscreen, onPrev, onNext, onToggleFullscreen])

  return (
    <>
      <button className="carousel-fullscreen-btn" onClick={onToggleFullscreen} title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
        {fullscreen ? '⤡' : '⤢'}
      </button>
      <div className="carousel-header">
        <span className="carousel-rank">{rankLabel ?? `#${idx + 1}`}</span>
        <span className="carousel-of">{rankLabel ? '' : `of ${total}`}</span>
        <span className="carousel-score-center">
          {result.score.toFixed(1)}<span className="result-unit">pts</span>
        </span>
      </div>
      <div className="schedules-grid">
        <Timeline blocks={result.roommate_a} name={nameA} startHour={startHour} endHour={endHour} hh={hh} categories={categories} />
        <Timeline blocks={result.roommate_b} name={nameB} startHour={startHour} endHour={endHour} hh={hh} categories={categories} />
      </div>
      <div className="carousel-nav">
        <button className="carousel-arrow" onClick={onPrev} disabled={idx === 0}>‹</button>
        <button className="carousel-arrow" onClick={onNext} disabled={idx === total - 1}>›</button>
      </div>
    </>
  )
}

function ScheduleCarousel({ results, nameA, nameB, categories }) {
  const [idx, setIdx] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const total = results.length
  const result = results[idx]
  const onPrev = () => setIdx(i => Math.max(0, i - 1))
  const onNext = () => setIdx(i => Math.min(total - 1, i + 1))
  const onToggleFullscreen = () => setFullscreen(f => !f)

  const sharedProps = { result, idx, total, nameA, nameB, onPrev, onNext, fullscreen, onToggleFullscreen, categories }

  return (
    <>
      <div className="carousel">
        <CarouselContent {...sharedProps} />
      </div>
      {fullscreen && (
        <div className="carousel-overlay" onClick={e => { if (e.target === e.currentTarget) setFullscreen(false) }}>
          <div className="carousel-fs">
            <CarouselContent {...sharedProps} />
          </div>
        </div>
      )}
    </>
  )
}

// ── Scheduler ─────────────────────────────────────────────────────────────────
function Scheduler({ onBack, onResults, rA, setRA, rB, setRB, prefs, setPrefs }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function submit() {
    setLoading(true)
    setError(null)
    const t0 = performance.now()
    try {
      const body = {
        roommate_a: {
          roommate_name:   rA.name || 'Roommate A',
          fixed_events:    rA.fixed.map(({ name, start, finish, in_dorm }) => ({ name, start, finish, in_dorm })),
          flexible_events: rA.flexible.map(({ name, duration, in_dorm }) => ({ name, duration, in_dorm })),
        },
        roommate_b: {
          roommate_name:   rB.name || 'Roommate B',
          fixed_events:    rB.fixed.map(({ name, start, finish, in_dorm }) => ({ name, start, finish, in_dorm })),
          flexible_events: rB.flexible.map(({ name, duration, in_dorm }) => ({ name, duration, in_dorm })),
        },
      }
      const url = `http://localhost:8000/analyze/day?text=${encodeURIComponent(prefs)}`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      const elapsed = (performance.now() - t0) / 1000
      onResults(data.results, rA.name || 'Roommate A', rB.name || 'Roommate B', data.stats, elapsed, data.constraints, data.categories)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-nav">
        <button className="btn-back" onClick={onBack}>Back</button>
        <span className="wordmark">sync.</span>
      </div>

      <div className="page-intro">
        <h2 className="page-title">Build schedules</h2>
        <p className="page-sub">Add events for each roommate, then describe your preferences below.</p>
      </div>

      <div className="roommates">
        <RoommateForm label="A" data={rA} onChange={setRA} />
        <RoommateForm label="B" data={rB} onChange={setRB} />
      </div>

      <div className="prefs-section">
        <p className="prefs-label">Preferences</p>
        <p className="prefs-hint">Write naturally. The AI will parse and apply constraints.</p>
        <textarea
          className="prefs-area"
          rows={5}
          placeholder="e.g. I need my gym before noon. Blake's gaming should never overlap with my nap. It would be nice if we are not both home at the same time."
          value={prefs}
          onChange={e => setPrefs(e.target.value)}
        />
      </div>

      {error && <div className="error-box">{error}</div>}

      <button className="btn-primary lg" onClick={submit} disabled={loading}>
        {loading
          ? <span className="btn-loading"><span className="btn-spinner" />Analyzing…</span>
          : 'Find schedules'}
      </button>
    </div>
  )
}

// ── WeeklyScheduler ───────────────────────────────────────────────────────────
function WeeklyScheduler({ onBack, onResults, rA, setRA, rB, setRB, prefs, setPrefs }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function submit() {
    setLoading(true)
    setError(null)
    try {
      const body = {
        roommate_a: {
          roommate_name:   rA.name || 'Roommate A',
          fixed_events:    rA.fixed.map(({ name, start, finish, in_dorm, days }) => ({ name, start, finish, in_dorm, days })),
          flexible_events: rA.flexible.map(({ name, duration, in_dorm, days }) => ({ name, duration, in_dorm, days })),
        },
        roommate_b: {
          roommate_name:   rB.name || 'Roommate B',
          fixed_events:    rB.fixed.map(({ name, start, finish, in_dorm, days }) => ({ name, start, finish, in_dorm, days })),
          flexible_events: rB.flexible.map(({ name, duration, in_dorm, days }) => ({ name, duration, in_dorm, days })),
        },
      }
      const url = `http://localhost:8000/analyze/week?text=${encodeURIComponent(prefs)}`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      onResults(data.results, rA.name || 'Roommate A', rB.name || 'Roommate B', data.constraints, data.categories)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-nav">
        <button className="btn-back" onClick={onBack}>Back</button>
        <span className="wordmark">sync.</span>
      </div>

      <div className="page-intro">
        <h2 className="page-title">Build weekly schedules</h2>
        <p className="page-sub">Add events for each roommate. Each event can repeat on specific days of the week.</p>
      </div>

      <div className="roommates">
        <WeeklyRoommateForm label="A" data={rA} onChange={setRA} />
        <WeeklyRoommateForm label="B" data={rB} onChange={setRB} />
      </div>

      <div className="prefs-section">
        <p className="prefs-label">Preferences</p>
        <p className="prefs-hint">Write naturally. The AI will parse and apply constraints.</p>
        <textarea
          className="prefs-area"
          rows={5}
          placeholder="e.g. I need my gym before noon. Blake's gaming should never overlap with my nap. It would be nice if we are not both home at the same time."
          value={prefs}
          onChange={e => setPrefs(e.target.value)}
        />
      </div>

      {error && <div className="error-box">{error}</div>}

      <button className="btn-primary lg" onClick={submit} disabled={loading}>
        {loading
          ? <span className="btn-loading"><span className="btn-spinner" />Analyzing…</span>
          : 'Find schedules'}
      </button>
    </div>
  )
}

// ── Analytics ─────────────────────────────────────────────────────────────────
function PipeStep({ label, value, accent }) {
  return (
    <div className={`pipe-step ${accent ? 'accent' : ''}`}>
      <span className="pipe-value">{value}</span>
      <span className="pipe-label">{label}</span>
    </div>
  )
}

function PipeArrow({ delta }) {
  const hasDelta = delta > 0
  return (
    <div className="pipe-arrow">
      {hasDelta && <span className="pipe-delta">−{delta.toLocaleString()}</span>}
      <span className="pipe-chevron">›</span>
    </div>
  )
}

function ScoreBar({ min, max, mean, median, stdev }) {
  const p = v => `${Math.max(0, Math.min(100, v)).toFixed(2)}%`
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ left: p(min), width: p(max - min) }} />
        <div className="score-bar-pin mean" style={{ left: p(mean) }} title={`Mean: ${mean.toFixed(1)}`} />
        <div className="score-bar-pin median" style={{ left: p(median) }} title={`Median: ${median.toFixed(1)}`} />
      </div>
      <div className="score-bar-ends">
        <span>{min.toFixed(1)}</span>
        <span>{max.toFixed(1)}</span>
      </div>
      <div className="score-bar-legend">
        <span><span className="score-swatch mean" />mean {mean.toFixed(1)}</span>
        <span><span className="score-swatch median" />median {median.toFixed(1)}</span>
        <span>σ {stdev.toFixed(1)}</span>
      </div>
    </div>
  )
}

function Analytics({ stats, elapsed, resultCount }) {
  if (!stats) return null
  const totalRaw  = stats.schedules_a * stats.schedules_b
  const hardPruned = totalRaw - stats.valid_pairs
  const crossPruned = stats.valid_pairs - stats.passing_pairs
  const hasScores = stats.score_min != null

  return (
    <div className="analytics">
      <p className="analytics-title">Run analytics</p>

      <div className="pipeline">
        <PipeStep label="raw pairs" value={totalRaw.toLocaleString()} />
        <PipeArrow delta={hardPruned} />
        <PipeStep label="valid pairs" value={stats.valid_pairs.toLocaleString()} />
        <PipeArrow delta={crossPruned} />
        <PipeStep label="passing" value={stats.passing_pairs.toLocaleString()} accent />
        <PipeArrow delta={0} />
        <PipeStep label="returned" value={resultCount} />
      </div>

      <div className="analytics-lower">
        {hasScores && (
          <div className="analytics-panel">
            <p className="analytics-panel-title">Score distribution</p>
            <ScoreBar
              min={stats.score_min} max={stats.score_max}
              mean={stats.score_mean} median={stats.score_median}
              stdev={stats.score_stdev}
            />
          </div>
        )}
        <div className="analytics-panel">
          <p className="analytics-panel-title">Performance</p>
          <p className="perf-time">{elapsed != null ? `${elapsed.toFixed(2)}s` : '—'}</p>
          <p className="perf-sublabel">total load time</p>
          <p className="perf-gen">{stats.schedules_a.toLocaleString()} A  ×  {stats.schedules_b.toLocaleString()} B schedules</p>
        </div>
      </div>
    </div>
  )
}

// ── Results ───────────────────────────────────────────────────────────────────
function Results({ results, nameA, nameB, stats, elapsed, constraints, categories, onReset }) {
  const sorted = [...results].sort((a, b) => b.score - a.score)
  const [tab, setTab] = useState('schedules')

  return (
    <div className="page results-page">
      <div className="page-nav">
        <button className="btn-back" onClick={onReset}>← Back</button>
        <span className="wordmark">sync.</span>
      </div>

      <div className="page-intro">
        <h2 className="page-title">Results</h2>
        <p className="page-sub">
          {sorted.length === 0
            ? 'No valid combinations found. Try relaxing some hard constraints.'
            : `${sorted.length} combinations found, ranked by score.`}
        </p>
      </div>

      <div className="result-tabs">
        {[['schedules', 'Schedules'], ['analytics', 'Analytics'], ['constraints', 'AI constraints']].map(([key, label]) => (
          <button key={key} className={`result-tab ${tab === key ? 'on' : ''}`} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'schedules' && (
        sorted.length === 0
          ? <p className="empty-state">No valid combinations found.</p>
          : <ScheduleCarousel results={sorted} nameA={nameA} nameB={nameB} categories={categories} />
      )}

      {tab === 'analytics' && (
        <Analytics stats={stats} elapsed={elapsed} resultCount={sorted.length} />
      )}

      {tab === 'constraints' && (
        <div className="constraints-panel">
          <p className="constraints-meta">
            {constraints?.length ?? 0} constraint{constraints?.length !== 1 ? 's' : ''} extracted by the AI parser
          </p>
          <pre className="constraints-json">{JSON.stringify(constraints ?? [], null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

// ── WeeklyResults ─────────────────────────────────────────────────────────────
function WeeklyResults({ results, nameA, nameB, constraints, categories, onReset }) {
  const [day,        setDay]        = useState(0)
  const [tab,        setTab]        = useState('schedules')
  const [fullscreen, setFullscreen] = useState(false)

  const dayResult = results[day] || { results: [], stats: null }
  const sorted    = [...(dayResult.results || [])].sort((a, b) => b.score - a.score)
  const result    = sorted[0] || null

  const onPrev            = () => setDay(d => Math.max(0, d - 1))
  const onNext            = () => setDay(d => Math.min(6, d + 1))
  const onToggleFullscreen = () => setFullscreen(f => !f)

  const carouselProps = result ? {
    result,
    idx: day, total: 7,
    rankLabel: DAY_NAMES[day],
    nameA, nameB,
    onPrev, onNext,
    fullscreen, onToggleFullscreen,
    categories,
  } : null

  return (
    <div className="page results-page">
      <div className="page-nav">
        <button className="btn-back" onClick={onReset}>← Back</button>
        <span className="wordmark">sync.</span>
      </div>

      <div className="page-intro">
        <h2 className="page-title">Weekly results</h2>
        <p className="page-sub">Use the arrows to browse each day's best schedule.</p>
      </div>

      <div className="result-tabs">
        {[['schedules', 'Schedules'], ['analytics', 'Analytics'], ['constraints', 'AI constraints']].map(([key, label]) => (
          <button key={key} className={`result-tab ${tab === key ? 'on' : ''}`} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'schedules' && (
        carouselProps
          ? <>
              <div className="carousel">
                <CarouselContent {...carouselProps} />
              </div>
              {fullscreen && (
                <div className="carousel-overlay" onClick={e => { if (e.target === e.currentTarget) setFullscreen(false) }}>
                  <div className="carousel-fs">
                    <CarouselContent {...carouselProps} />
                  </div>
                </div>
              )}
            </>
          : <p className="empty-state">No valid combinations for {DAY_NAMES[day]}.</p>
      )}

      {tab === 'analytics' && (
        <Analytics stats={dayResult.stats} elapsed={null} resultCount={sorted.length} />
      )}

      {tab === 'constraints' && (
        <div className="constraints-panel">
          <p className="constraints-meta">
            {constraints?.length ?? 0} constraint{constraints?.length !== 1 ? 's' : ''} extracted by the AI parser
          </p>
          <pre className="constraints-json">{JSON.stringify(constraints ?? [], null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [view,        setView]        = useState('landing')

  // Daily state
  const [results,     setResults]     = useState(null)
  const [nameA,       setNameA]       = useState('Roommate A')
  const [nameB,       setNameB]       = useState('Roommate B')
  const [stats,       setStats]       = useState(null)
  const [elapsed,     setElapsed]     = useState(null)
  const [constraints, setConstraints] = useState([])
  const [categories,  setCategories]  = useState({})
  const [rA,    setRA]    = useState({ name: '', fixed: [], flexible: [] })
  const [rB,    setRB]    = useState({ name: '', fixed: [], flexible: [] })
  const [prefs, setPrefs] = useState('')

  // Weekly state
  const [wResults,     setWResults]     = useState(null)
  const [wNameA,       setWNameA]       = useState('Roommate A')
  const [wNameB,       setWNameB]       = useState('Roommate B')
  const [wConstraints, setWConstraints] = useState([])
  const [wCategories,  setWCategories]  = useState({})
  const [wrA,    setWRA]    = useState({ name: '', fixed: [], flexible: [] })
  const [wrB,    setWRB]    = useState({ name: '', fixed: [], flexible: [] })
  const [wPrefs, setWPrefs] = useState('')

  function handleStart(mode) {
    setView(mode === 'weekly' ? 'weekly-scheduler' : 'scheduler')
  }

  function handleResults(res, a, b, st, el, cj, cats) {
    setResults(res)
    setNameA(a)
    setNameB(b)
    setStats(st)
    setElapsed(el)
    setConstraints(cj ?? [])
    setCategories(cats ?? {})
    setView('results')
  }

  function handleWeeklyResults(res, a, b, cj, cats) {
    setWResults(res)
    setWNameA(a)
    setWNameB(b)
    setWConstraints(cj ?? [])
    setWCategories(cats ?? {})
    setView('weekly-results')
  }

  if (view === 'landing') return <Landing onStart={handleStart} />

  if (view === 'scheduler') return (
    <Scheduler
      onBack={() => setView('landing')}
      onResults={handleResults}
      rA={rA} setRA={setRA}
      rB={rB} setRB={setRB}
      prefs={prefs} setPrefs={setPrefs}
    />
  )

  if (view === 'results') return (
    <Results
      results={results} nameA={nameA} nameB={nameB}
      stats={stats} elapsed={elapsed} constraints={constraints} categories={categories}
      onReset={() => setView('scheduler')}
    />
  )

  if (view === 'weekly-scheduler') return (
    <WeeklyScheduler
      onBack={() => setView('landing')}
      onResults={handleWeeklyResults}
      rA={wrA} setRA={setWRA}
      rB={wrB} setRB={setWRB}
      prefs={wPrefs} setPrefs={setWPrefs}
    />
  )

  if (view === 'weekly-results') return (
    <WeeklyResults
      results={wResults} nameA={wNameA} nameB={wNameB}
      constraints={wConstraints} categories={wCategories}
      onReset={() => setView('weekly-scheduler')}
    />
  )
}
