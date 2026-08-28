// Per-result explainability: which soft constraints this schedule pays for,
// plus generation warnings (dropped constraints, caps).
export default function PenaltyPanel({ penalties, warnings, stats }) {
  const hasContent = penalties?.length || warnings?.length
  return (
    <div className="penalty-panel">
      {penalties?.length > 0 && (
        <div className="pp-section">
          <h4>Trade-offs in this schedule</h4>
          {penalties.map((p, i) => (
            <div key={i} className="pp-row">
              <span className="pp-type">{p.type.replaceAll('_', ' ')}</span>
              <div className="pp-bar-track">
                <div className="pp-bar" style={{ width: `${Math.round(p.score * 100)}%` }} />
              </div>
              <span className="pp-score">{Math.round(p.score * 100)}%</span>
            </div>
          ))}
        </div>
      )}
      {warnings?.length > 0 && (
        <div className="pp-section">
          <h4>Notes</h4>
          {warnings.map((w, i) => <div key={i} className="pp-warning">! {w}</div>)}
        </div>
      )}
      {!hasContent && <div className="dim">No trade-offs — every preference is satisfied.</div>}
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
