import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import WeekGrid from '../components/WeekGrid'
import SectionCard from '../components/SectionCard'
import PenaltyPanel from '../components/PenaltyPanel'
import ThemeToggle from '../components/ThemeToggle'

// Results are grouped as course combinations, each with section variants
// inside. Open badges refresh live every 30 seconds.
export default function Results({ output, request, onBack }) {
  const combos = output.course_combos ?? []
  const [comboIdx, setComboIdx] = useState(0)
  const [variantIdx, setVariantIdx] = useState(0)
  const [openIndexes, setOpenIndexes] = useState(null)
  const [savedId, setSavedId] = useState(null)

  useEffect(() => {
    let alive = true
    async function poll() {
      try {
        const status = await api.openStatus(request.termKey)
        if (alive) setOpenIndexes(new Set(status.open_indexes))
      } catch { /* keep the last known state */ }
    }
    poll()
    const timer = setInterval(poll, 30_000)
    return () => { alive = false; clearInterval(timer) }
  }, [request.termKey])

  const combo = combos[comboIdx]
  const result = combo?.results[Math.min(variantIdx, (combo?.results.length ?? 1) - 1)]

  const asyncCourses = useMemo(() => {
    if (!result) return []
    return result.selections
      .filter(sel => !sel.section.meetings.some(m => m.day !== null && m.start !== null))
      .map(sel => ({ course_string: sel.course_string, index: sel.section.index }))
  }, [result])

  async function save() {
    const saved = await api.save({
      term_key: request.termKey,
      name: combo.courses.join(', '),
      indexes: result.indexes,
      requirements: request.requirements,
      preferences_text: request.preferences,
      constraints_json: output.constraints ?? [],
      score: result.score,
    })
    setSavedId(saved.id)
  }

  if (output.infeasible) {
    return (
      <div className="page results-page">
        <nav className="page-nav">
          <button className="btn-back" onClick={onBack}>← Adjust</button>
          <span className="wordmark">sked.</span>
          <ThemeToggle />
        </nav>
        <div className="infeasible-box">
          <h2>No schedule is possible</h2>
          <p>
            {output.infeasible.group
              ? <>The requirement <strong>{output.infeasible.group}</strong>: {output.infeasible.reason}</>
              : output.infeasible.reason}
          </p>
          <button className="btn-primary" onClick={onBack}>Adjust requirements</button>
        </div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="page results-page">
        <nav className="page-nav">
          <button className="btn-back" onClick={onBack}>← Adjust</button>
          <span className="wordmark">sked.</span>
          <ThemeToggle />
        </nav>
        <div className="infeasible-box">
          <h2>No valid combinations found</h2>
          <p>Every section pairing hit a conflict or a hard constraint. Try
          loosening a hard preference or unlocking a section.</p>
          <PenaltyPanel warnings={output.warnings} stats={output.stats} />
          <button className="btn-primary" onClick={onBack}>Adjust requirements</button>
        </div>
      </div>
    )
  }

  return (
    <div className="page results-page">
      <nav className="page-nav">
        <button className="btn-back" onClick={onBack}>← Adjust</button>
        <span className="wordmark">sked.</span>
        <ThemeToggle />
      </nav>

      {combos.length > 1 && (
        <div className="combo-tabs">
          {combos.map((c, i) => (
            <button
              key={i}
              className={`combo-tab ${i === comboIdx ? 'on' : ''}`}
              onClick={() => { setComboIdx(i); setVariantIdx(0) }}
            >
              <span className="combo-score">{c.results[0].score}</span>
              <span className="combo-courses">{c.courses.join(' · ')}</span>
            </button>
          ))}
        </div>
      )}

      <div className="result-head">
        <div>
          <span className="result-score">{result.score}</span>
          <span className="result-meta">
            {result.credits_assumed ? '≈' : ''}{result.credits_total} credits ·
            indexes {result.indexes.join(', ')}
          </span>
        </div>
        <div className="result-head-actions">
          {combo.results.length > 1 && (
            <span className="variant-nav">
              <button
                className="btn-outline sm"
                disabled={variantIdx === 0}
                onClick={() => setVariantIdx(variantIdx - 1)}
              >‹</button>
              <span className="dim"> variant {variantIdx + 1}/{combo.results.length} </span>
              <button
                className="btn-outline sm"
                disabled={variantIdx >= combo.results.length - 1}
                onClick={() => setVariantIdx(variantIdx + 1)}
              >›</button>
            </span>
          )}
          <button className="btn-primary" onClick={save} disabled={savedId !== null}>
            {savedId !== null ? 'Saved ✓' : 'Save schedule'}
          </button>
        </div>
      </div>

      <WeekGrid week={result.week} asyncCourses={asyncCourses} />

      <div className="section-cards">
        {result.selections.map(sel => (
          <SectionCard key={sel.section.index} selection={sel} openIndexes={openIndexes} />
        ))}
      </div>

      <PenaltyPanel
        penalties={result.penalties}
        warnings={output.warnings}
        stats={output.stats}
      />
    </div>
  )
}
