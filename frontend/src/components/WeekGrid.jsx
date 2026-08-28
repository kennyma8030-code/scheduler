import { useState } from 'react'
import { DAY_NAMES, campusColor, campusLabel, fmtTime } from '../lib'

// The centerpiece: a Mon–Fri (plus weekend when used) grid, 5-minute-precise
// block positioning, colored by campus. `week` is 7 arrays of
// {start, end, course_string, index, campus_code, mode} in minutes.
export default function WeekGrid({ week, asyncCourses = [] }) {
  const [popover, setPopover] = useState(null) // {day, blockIdx}

  const usedDays = week.map((blocks, d) => ({ d, blocks })).filter(
    ({ d, blocks }) => d < 5 || blocks.length > 0
  )
  const allBlocks = week.flat()
  const earliest = Math.min(8 * 60, ...allBlocks.map(b => b.start))
  const latest = Math.max(18 * 60, ...allBlocks.map(b => b.end))
  const top = Math.floor(earliest / 60) * 60
  const bottom = Math.ceil(latest / 60) * 60
  const span = bottom - top
  const hours = []
  for (let h = top; h <= bottom; h += 60) hours.push(h)

  return (
    <div className="weekgrid-wrap">
      <div className="weekgrid" style={{ '--cols': usedDays.length }}>
        <div className="wg-axis">
          {hours.map(h => (
            <span key={h} className="wg-hour" style={{ top: `${((h - top) / span) * 100}%` }}>
              {fmtTime(h)}
            </span>
          ))}
        </div>
        {usedDays.map(({ d, blocks }) => (
          <div key={d} className="wg-day">
            <div className="wg-day-head">{DAY_NAMES[d]}</div>
            <div className="wg-day-col">
              {hours.map(h => (
                <div key={h} className="wg-gridline" style={{ top: `${((h - top) / span) * 100}%` }} />
              ))}
              {blocks.map((b, i) => (
                <div
                  key={`${b.index}-${i}`}
                  className="wg-block"
                  style={{
                    top: `${((b.start - top) / span) * 100}%`,
                    height: `${((b.end - b.start) / span) * 100}%`,
                    background: campusColor(b.campus_code),
                  }}
                  onClick={() => setPopover(popover?.day === d && popover?.i === i ? null : { day: d, i })}
                >
                  <span className="wg-block-course">{b.course_string}</span>
                  <span className="wg-block-time">{fmtTime(b.start)}–{fmtTime(b.end)}</span>
                  {popover?.day === d && popover?.i === i && (
                    <div className="wg-popover" onClick={e => e.stopPropagation()}>
                      <strong>{b.course_string}</strong> {b.mode}
                      <div>{fmtTime(b.start)}–{fmtTime(b.end)} · {campusLabel(b.campus_code)}</div>
                      <div className="wg-popover-index">index {b.index}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {asyncCourses.length > 0 && (
        <div className="wg-async-strip">
          <span className="wg-async-label">online / asynchronous:</span>
          {asyncCourses.map(c => (
            <span key={c.index} className="wg-async-chip">
              {c.course_string} <span className="dim">idx {c.index}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
