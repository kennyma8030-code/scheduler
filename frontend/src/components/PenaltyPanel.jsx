const KIND_LABEL = {
  section: 'per section',
  schedule: 'whole week',
  selection: 'course set',
}

function humanize(type) {
  return type.replaceAll('_', ' ')
}

// Per-result explainability: every constraint the generator ran with, whether
// this schedule satisfies it, and what the misses cost. Also carries the
// warnings for anything that couldn't be applied at all.
export default function PenaltyPanel({ penalties, warnings, stats, applied }) {
  // Penalties only list constraints this schedule violated; everything else in
  // `applied` was satisfied outright.
  const violated = new Map((penalties ?? []).map(p => [p.type, p]))
  const rows = (applied ?? []).map(c => ({ ...c, hit: violated.get(c.type) }))
  // Costly first, then satisfied; hard rules lead their group.
  rows.sort((a, b) => {
    const cost = (b.hit ? b.weight * b.hit.score : 0) - (a.hit ? a.weight * a.hit.score : 0)
    return cost !== 0 ? cost : Number(b.hard) - Number(a.hard)
  })

  // A violated constraint with no matching `applied` entry shouldn't vanish.
  const orphans = (penalties ?? []).filter(
    p => !(applied ?? []).some(c => c.type === p.type)
  )

  return (
    <div className="penalty-panel">
      {rows.length > 0 && (
        <div className="pp-section">
          <h4>Constraints applied ({rows.length})</h4>
          {rows.map((c, i) => (
            <div key={`${c.type}-${i}`} className={`pp-row ${c.hit ? '' : 'met'}`}>
              <span className="pp-type">
                {humanize(c.type)}
                <span className="pp-tags">
                  <span className={`pp-tag ${c.hard ? 'hard' : 'soft'}`}>
                    {c.hard ? 'hard' : `weight ${c.weight}`}
                  </span>
                  <span className="pp-tag kind">{KIND_LABEL[c.kind] ?? c.kind}</span>
                </span>
              </span>
              <div className="pp-bar-track">
                <div
                  className="pp-bar"
                  style={{ width: c.hit ? `${Math.round(c.hit.score * 100)}%` : '0%' }}
                />
              </div>
              <span className="pp-score">
                {c.hit ? `−${Math.round(c.hit.score * 100)}%` : 'met'}
              </span>
            </div>
          ))}
          {orphans.map((p, i) => (
            <div key={`orphan-${i}`} className="pp-row">
              <span className="pp-type">{humanize(p.type)}</span>
              <div className="pp-bar-track">
                <div className="pp-bar" style={{ width: `${Math.round(p.score * 100)}%` }} />
              </div>
              <span className="pp-score">−{Math.round(p.score * 100)}%</span>
            </div>
          ))}
        </div>
      )}

      {rows.length === 0 && !warnings?.length && (
        <div className="dim">No constraints applied — results are ranked on structure alone.</div>
      )}

      {warnings?.length > 0 && (
        <div className="pp-section">
          <h4>Notes</h4>
          {warnings.map((w, i) => <div key={i} className="pp-warning">! {w}</div>)}
        </div>
      )}

      {stats && (
        <div className="pp-stats dim">
          {Number(stats.raw_product ?? 0).toLocaleString()} raw combinations ·{' '}
          {Number(stats.leaves_scored ?? 0).toLocaleString()} scored ·{' '}
          {stats.elapsed_ms} ms{stats.workers > 1 ? ` · ${stats.workers} workers` : ''}
          {stats.truncated ? ' · search truncated by time budget' : ''}
        </div>
      )}
    </div>
  )
}
