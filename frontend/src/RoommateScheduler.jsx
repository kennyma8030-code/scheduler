import React, { useState } from 'react';

const API_URL = 'http://localhost:8000';

const c = {
  bg: '#0a0a0a',
  surface: '#111111',
  elevated: '#1c1c1c',
  border: '#252525',
  borderFocus: '#4a4a4a',
  text: '#f5f5f5',
  muted: '#6b6b6b',
  subtle: '#333333',
  positive: '#22c55e',
  negative: '#ef4444',
  tag: '#1e1e1e',
  tagBorder: '#2e2e2e',
};

const eventPalette = [
  '#6366f1', '#8b5cf6', '#3b82f6', '#06b6d4',
  '#10b981', '#f59e0b', '#f43f5e', '#84cc16',
  '#a855f7', '#ec4899',
];

const getEventColor = (name, allNames) => {
  const i = allNames.indexOf(name);
  return eventPalette[i % eventPalette.length];
};

const formatHour = (h) => {
  if (h === 0) return '12a';
  if (h === 12) return '12p';
  return h < 12 ? `${h}a` : `${h - 12}p`;
};

// ─── EventForm ────────────────────────────────────────────────────────────────

const EventForm = ({ type, onAdd }) => {
  const isFixed = type === 'fixed';
  const [name, setName] = useState('');
  const [start, setStart] = useState('');
  const [finish, setFinish] = useState('');
  const [duration, setDuration] = useState('');
  const [inDorm, setInDorm] = useState(false);

  const submit = () => {
    if (!name) return;
    if (isFixed) {
      if (start === '' || finish === '') return;
      onAdd({ name, start: parseInt(start), finish: parseInt(finish), in_dorm: inDorm });
    } else {
      if (duration === '') return;
      onAdd({ name, duration: parseInt(duration), in_dorm: inDorm });
    }
    setName(''); setStart(''); setFinish(''); setDuration(''); setInDorm(false);
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    background: c.bg,
    border: `1px solid ${c.border}`,
    borderRadius: '6px',
    color: c.text,
    fontSize: '13px',
    outline: 'none',
    fontFamily: 'inherit',
    transition: 'border-color 0.15s',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '11px',
    fontWeight: '500',
    color: c.muted,
    marginBottom: '5px',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div>
        <label style={labelStyle}>Name</label>
        <input
          style={inputStyle}
          placeholder="e.g. Math Class"
          value={name}
          onChange={e => setName(e.target.value)}
          onFocus={e => (e.target.style.borderColor = c.borderFocus)}
          onBlur={e => (e.target.style.borderColor = c.border)}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isFixed ? '1fr 1fr auto' : '1fr auto', gap: '10px', alignItems: 'end' }}>
        {isFixed ? (
          <>
            <div>
              <label style={labelStyle}>Start (0–23)</label>
              <input style={inputStyle} type="number" min="0" max="23" placeholder="9"
                value={start} onChange={e => setStart(e.target.value)}
                onFocus={e => (e.target.style.borderColor = c.borderFocus)}
                onBlur={e => (e.target.style.borderColor = c.border)}
              />
            </div>
            <div>
              <label style={labelStyle}>End (0–23)</label>
              <input style={inputStyle} type="number" min="0" max="24" placeholder="11"
                value={finish} onChange={e => setFinish(e.target.value)}
                onFocus={e => (e.target.style.borderColor = c.borderFocus)}
                onBlur={e => (e.target.style.borderColor = c.border)}
              />
            </div>
          </>
        ) : (
          <div>
            <label style={labelStyle}>Duration (hrs)</label>
            <input style={inputStyle} type="number" min="1" max="12" placeholder="2"
              value={duration} onChange={e => setDuration(e.target.value)}
              onFocus={e => (e.target.style.borderColor = c.borderFocus)}
              onBlur={e => (e.target.style.borderColor = c.border)}
            />
          </div>
        )}
        <div style={{ paddingBottom: '1px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={inDorm}
              onChange={e => setInDorm(e.target.checked)}
              style={{ accentColor: c.positive, width: '14px', height: '14px' }}
            />
            <span style={{ fontSize: '12px', color: c.muted, fontWeight: '500' }}>In dorm</span>
          </label>
        </div>
      </div>

      <button
        onClick={submit}
        style={{
          alignSelf: 'flex-start',
          padding: '7px 14px',
          background: c.elevated,
          border: `1px solid ${c.border}`,
          borderRadius: '6px',
          color: c.text,
          fontSize: '12px',
          fontWeight: '500',
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'background 0.15s, border-color 0.15s',
        }}
        onMouseEnter={e => { e.target.style.background = c.subtle; e.target.style.borderColor = c.borderFocus; }}
        onMouseLeave={e => { e.target.style.background = c.elevated; e.target.style.borderColor = c.border; }}
      >
        Add event
      </button>
    </div>
  );
};

// ─── EventList ────────────────────────────────────────────────────────────────

const EventList = ({ events, type, onDelete }) => {
  if (!events.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '10px' }}>
      {events.map((ev, i) => (
        <div key={i} style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 10px',
          background: c.tag,
          border: `1px solid ${c.tagBorder}`,
          borderRadius: '6px',
          fontSize: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: c.text }}>
            <span style={{ fontWeight: '500' }}>{ev.name}</span>
            <span style={{ color: c.muted }}>
              {type === 'fixed'
                ? `${formatHour(ev.start)} – ${formatHour(ev.finish)}`
                : `${ev.duration}h`}
            </span>
            {ev.in_dorm && (
              <span style={{
                fontSize: '10px',
                fontWeight: '600',
                color: c.positive,
                border: `1px solid ${c.positive}40`,
                borderRadius: '4px',
                padding: '1px 5px',
                letterSpacing: '0.04em',
              }}>
                IN DORM
              </span>
            )}
          </div>
          <button
            onClick={() => onDelete(i)}
            style={{
              background: 'none',
              border: 'none',
              color: c.muted,
              cursor: 'pointer',
              fontSize: '16px',
              lineHeight: 1,
              padding: '0 2px',
              display: 'flex',
              alignItems: 'center',
            }}
            onMouseEnter={e => (e.target.style.color = c.negative)}
            onMouseLeave={e => (e.target.style.color = c.muted)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};

// ─── SectionHeader ────────────────────────────────────────────────────────────

const SectionHeader = ({ title, count }) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '12px',
  }}>
    <span style={{
      fontSize: '11px',
      fontWeight: '600',
      color: c.muted,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
    }}>
      {title}
    </span>
    <span style={{
      fontSize: '10px',
      fontWeight: '600',
      color: c.muted,
      background: c.elevated,
      border: `1px solid ${c.border}`,
      borderRadius: '10px',
      padding: '1px 7px',
    }}>
      {count}
    </span>
  </div>
);

// ─── RoommateCard ─────────────────────────────────────────────────────────────

const RoommateCard = ({ roommate, setRoommate }) => {
  const addFixed = (ev) => setRoommate({ ...roommate, fixed_events: [...roommate.fixed_events, ev] });
  const addFlexible = (ev) => setRoommate({ ...roommate, flexible_events: [...roommate.flexible_events, ev] });
  const delFixed = (i) => setRoommate({ ...roommate, fixed_events: roommate.fixed_events.filter((_, j) => j !== i) });
  const delFlexible = (i) => setRoommate({ ...roommate, flexible_events: roommate.flexible_events.filter((_, j) => j !== i) });

  return (
    <div style={{
      background: c.surface,
      border: `1px solid ${c.border}`,
      borderRadius: '10px',
      padding: '20px',
    }}>
      <input
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          borderBottom: `1px solid ${c.border}`,
          color: c.text,
          fontSize: '16px',
          fontWeight: '600',
          fontFamily: 'inherit',
          outline: 'none',
          paddingBottom: '12px',
          marginBottom: '20px',
          letterSpacing: '-0.01em',
        }}
        value={roommate.roommate_name}
        onChange={e => setRoommate({ ...roommate, roommate_name: e.target.value })}
        placeholder="Name"
        onFocus={e => (e.target.style.borderBottomColor = c.borderFocus)}
        onBlur={e => (e.target.style.borderBottomColor = c.border)}
      />

      <div style={{ marginBottom: '24px' }}>
        <SectionHeader title="Fixed Events" count={roommate.fixed_events.length} />
        <EventForm type="fixed" onAdd={addFixed} />
        <EventList events={roommate.fixed_events} type="fixed" onDelete={delFixed} />
      </div>

      <div>
        <SectionHeader title="Flexible Events" count={roommate.flexible_events.length} />
        <EventForm type="flexible" onAdd={addFlexible} />
        <EventList events={roommate.flexible_events} type="flexible" onDelete={delFlexible} />
      </div>
    </div>
  );
};

// ─── ScheduleVisualization ────────────────────────────────────────────────────

const ScheduleVisualization = ({ blocks, label, allEventNames }) => {
  const hourMap = {};
  blocks.forEach(b => {
    for (let h = b.start; h < b.finish; h++) hourMap[h] = b;
  });

  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ fontSize: '11px', fontWeight: '600', color: c.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>
        {label}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: '2px', marginBottom: '4px' }}>
        {Array.from({ length: 24 }, (_, i) => (
          <div key={i} style={{ fontSize: '9px', color: c.muted, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}>
            {i % 3 === 0 ? formatHour(i) : ''}
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: '2px', borderRadius: '5px', overflow: 'hidden' }}>
        {Array.from({ length: 24 }, (_, hour) => {
          const block = hourMap[hour];
          const bg = block ? getEventColor(block.event, allEventNames) : c.elevated;
          return (
            <div
              key={hour}
              title={block ? `${block.event} (${formatHour(block.start)}–${formatHour(block.finish)})${block.in_dorm ? ' · In Dorm' : ''}` : 'Free'}
              style={{
                height: '32px',
                background: bg,
                opacity: block ? 1 : 0.25,
                borderBottom: block?.in_dorm ? `3px solid ${c.positive}` : '3px solid transparent',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
              }}
            >
              {block && block.start === hour && (
                <span style={{
                  position: 'absolute',
                  left: '3px',
                  fontSize: '9px',
                  fontWeight: '600',
                  color: 'rgba(0,0,0,0.75)',
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                }}>
                  {block.event}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── ResultCard ───────────────────────────────────────────────────────────────

const ResultCard = ({ result, index, allEventNames }) => (
  <div style={{
    background: c.surface,
    border: `1px solid ${c.border}`,
    borderRadius: '10px',
    padding: '20px',
    marginBottom: '12px',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
      <span style={{ fontSize: '13px', fontWeight: '600', color: c.text }}>
        Option {index + 1}
      </span>
      <span style={{
        fontSize: '12px',
        fontWeight: '600',
        color: result.score === 0 ? c.positive : c.muted,
        background: c.elevated,
        border: `1px solid ${c.border}`,
        borderRadius: '6px',
        padding: '4px 10px',
      }}>
        {result.score}h overlap in dorm
      </span>
    </div>

    <ScheduleVisualization blocks={result.roommate_a} label="Roommate A" allEventNames={allEventNames} />
    <ScheduleVisualization blocks={result.roommate_b} label="Roommate B" allEventNames={allEventNames} />

    <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
        <div style={{ width: '10px', height: '3px', background: c.positive, borderRadius: '2px' }} />
        <span style={{ fontSize: '11px', color: c.muted }}>Green border = in dorm</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
        <div style={{ width: '10px', height: '10px', background: c.elevated, borderRadius: '2px', opacity: 0.4 }} />
        <span style={{ fontSize: '11px', color: c.muted }}>Dim = free</span>
      </div>
    </div>
  </div>
);

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function RoommateScheduler() {
  const [roommateA, setRoommateA] = useState({ roommate_name: 'Roommate A', fixed_events: [], flexible_events: [] });
  const [roommateB, setRoommateB] = useState({ roommate_name: 'Roommate B', fixed_events: [], flexible_events: [] });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roommate_a: roommateA, roommate_b: roommateB }),
      });
      if (!res.ok) throw new Error('Failed to analyze schedules');
      const data = await res.json();
      setResults(data.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const allEventNames = [
    ...roommateA.fixed_events, ...roommateA.flexible_events,
    ...roommateB.fixed_events, ...roommateB.flexible_events,
  ].map(e => e.name).filter((v, i, a) => a.indexOf(v) === i);

  return (
    <div style={{ minHeight: '100vh', background: c.bg, color: c.text, fontFamily: 'Inter, sans-serif', padding: '40px 24px' }}>

      {/* Header */}
      <header style={{ maxWidth: '900px', margin: '0 auto 40px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '700', letterSpacing: '-0.03em', color: c.text, marginBottom: '6px' }}>
          Schedule Optimizer
        </h1>
        <p style={{ fontSize: '13px', color: c.muted, fontWeight: '400' }}>
          Find arrangements that minimize time both roommates spend in the dorm together.
        </p>
      </header>

      {/* Roommate Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '16px', maxWidth: '900px', margin: '0 auto' }}>
        <RoommateCard roommate={roommateA} setRoommate={setRoommateA} />
        <RoommateCard roommate={roommateB} setRoommate={setRoommateB} />
      </div>

      {/* Analyze Button */}
      <div style={{ maxWidth: '900px', margin: '24px auto 0' }}>
        <button
          onClick={analyze}
          disabled={loading}
          style={{
            width: '100%',
            padding: '13px',
            background: loading ? c.elevated : c.text,
            color: loading ? c.muted : c.bg,
            border: 'none',
            borderRadius: '8px',
            fontSize: '14px',
            fontWeight: '600',
            fontFamily: 'inherit',
            cursor: loading ? 'not-allowed' : 'pointer',
            letterSpacing: '-0.01em',
            transition: 'background 0.15s, color 0.15s',
          }}
          onMouseEnter={e => { if (!loading) e.target.style.background = '#d4d4d4'; }}
          onMouseLeave={e => { if (!loading) e.target.style.background = c.text; }}
        >
          {loading ? 'Analyzing...' : 'Analyze Schedules'}
        </button>

        {error && (
          <div style={{
            marginTop: '12px',
            padding: '12px 14px',
            background: `${c.negative}18`,
            border: `1px solid ${c.negative}40`,
            borderRadius: '7px',
            color: c.negative,
            fontSize: '13px',
          }}>
            {error} — make sure the server is running on {API_URL}
          </div>
        )}
      </div>

      {/* Results */}
      {results && (
        <div style={{ maxWidth: '900px', margin: '40px auto 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: '600', color: c.text, letterSpacing: '-0.01em' }}>
              Results
            </h2>
            <span style={{ fontSize: '11px', color: c.muted, background: c.elevated, border: `1px solid ${c.border}`, borderRadius: '10px', padding: '1px 8px', fontWeight: '500' }}>
              {results.length} options
            </span>
          </div>

          {results.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: c.muted, fontSize: '13px' }}>
              No valid combinations found. Try adjusting the events.
            </div>
          ) : (
            results.map((result, i) => (
              <ResultCard key={i} result={result} index={i} allEventNames={allEventNames} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
