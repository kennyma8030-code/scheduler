import React, { useState } from 'react';

const API_URL = 'http://localhost:8000';

// Color palette
const colors = {
  bg: '#0a0a0f',
  card: '#12121a',
  cardHover: '#1a1a25',
  accent: '#6366f1',
  accentLight: '#818cf8',
  accentDim: '#4f46e5',
  text: '#e2e8f0',
  textMuted: '#94a3b8',
  border: '#1e293b',
  success: '#10b981',
  warning: '#f59e0b',
  dorm: '#22c55e',
  notDorm: '#ef4444',
};

// Styles
const styles = {
  container: {
    minHeight: '100vh',
    background: `linear-gradient(135deg, ${colors.bg} 0%, #0f0f1a 50%, #0a0a12 100%)`,
    width: '100%',
    boxSizing: 'border-box',
    color: colors.text,
    fontFamily: "'Outfit', 'Segoe UI', sans-serif",
    padding: '2rem',
  },
  header: {
    textAlign: 'center',
    marginBottom: '3rem',
  },
  title: {
    fontSize: '3rem',
    fontWeight: '700',
    background: `linear-gradient(135deg, ${colors.accent} 0%, ${colors.accentLight} 100%)`,
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    marginBottom: '0.5rem',
    letterSpacing: '-0.02em',
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: '1.1rem',
    fontWeight: '400',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
    gap: '2rem',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  card: {
    background: colors.card,
    borderRadius: '16px',
    padding: '1.5rem',
    border: `1px solid ${colors.border}`,
    transition: 'all 0.3s ease',
  },
  cardTitle: {
    fontSize: '1.25rem',
    fontWeight: '600',
    marginBottom: '1.5rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  badge: {
    background: colors.accent,
    color: 'white',
    padding: '0.25rem 0.75rem',
    borderRadius: '20px',
    fontSize: '0.75rem',
    fontWeight: '600',
  },
  inputGroup: {
    marginBottom: '1rem',
  },
  label: {
    display: 'block',
    fontSize: '0.85rem',
    color: colors.textMuted,
    marginBottom: '0.5rem',
    fontWeight: '500',
  },
  input: {
    width: '100%',
    padding: '0.75rem 1rem',
    background: colors.bg,
    border: `1px solid ${colors.border}`,
    borderRadius: '8px',
    color: colors.text,
    fontSize: '0.95rem',
    outline: 'none',
    transition: 'border-color 0.2s ease',
    boxSizing: 'border-box',
  },
  inputRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr',
    gap: '0.75rem',
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    cursor: 'pointer',
    fontSize: '0.9rem',
  },
  button: {
    padding: '0.75rem 1.5rem',
    borderRadius: '8px',
    border: 'none',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.9rem',
    transition: 'all 0.2s ease',
  },
  primaryButton: {
    background: `linear-gradient(135deg, ${colors.accent} 0%, ${colors.accentDim} 100%)`,
    color: 'white',
  },
  secondaryButton: {
    background: 'transparent',
    border: `1px solid ${colors.border}`,
    color: colors.textMuted,
  },
  eventList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
    marginTop: '1rem',
    maxHeight: '200px',
    overflowY: 'auto',
  },
  eventItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0.75rem 1rem',
    background: colors.bg,
    borderRadius: '8px',
    fontSize: '0.9rem',
  },
  deleteBtn: {
    background: 'transparent',
    border: 'none',
    color: colors.notDorm,
    cursor: 'pointer',
    fontSize: '1.1rem',
    padding: '0.25rem',
  },
  analyzeButton: {
    width: '100%',
    padding: '1rem',
    fontSize: '1.1rem',
    marginTop: '2rem',
    background: `linear-gradient(135deg, ${colors.accent} 0%, ${colors.accentDim} 100%)`,
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    cursor: 'pointer',
    fontWeight: '700',
    transition: 'all 0.3s ease',
    boxShadow: `0 4px 20px ${colors.accent}40`,
  },
  resultsSection: {
    marginTop: '3rem',
  },
  resultCard: {
    background: colors.card,
    borderRadius: '16px',
    padding: '1.5rem',
    marginBottom: '1.5rem',
    border: `1px solid ${colors.border}`,
  },
  scheduleGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(24, 1fr)',
    gap: '2px',
    marginTop: '1rem',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  hourBlock: {
    height: '40px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.6rem',
    fontWeight: '600',
    position: 'relative',
  },
  timeLabels: {
    display: 'grid',
    gridTemplateColumns: 'repeat(24, 1fr)',
    gap: '2px',
    marginBottom: '0.25rem',
  },
  timeLabel: {
    fontSize: '0.65rem',
    color: colors.textMuted,
    textAlign: 'center',
  },
  legend: {
    display: 'flex',
    gap: '1.5rem',
    marginTop: '1rem',
    flexWrap: 'wrap',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    fontSize: '0.85rem',
    color: colors.textMuted,
  },
  legendDot: {
    width: '12px',
    height: '12px',
    borderRadius: '4px',
  },
  scoreDisplay: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    marginBottom: '1rem',
  },
  scoreBadge: {
    background: `linear-gradient(135deg, ${colors.success} 0%, #059669 100%)`,
    color: 'white',
    padding: '0.5rem 1rem',
    borderRadius: '8px',
    fontWeight: '700',
    fontSize: '1.1rem',
  },
  emptyState: {
    textAlign: 'center',
    padding: '3rem',
    color: colors.textMuted,
  },
};

// Helper to format hour
const formatHour = (hour) => {
  if (hour === 0) return '12a';
  if (hour === 12) return '12p';
  if (hour < 12) return `${hour}a`;
  return `${hour - 12}p`;
};

// Event colors
const eventColors = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
  '#06b6d4', '#3b82f6', '#f43f5e', '#84cc16', '#a855f7',
];

const getEventColor = (eventName, events) => {
  const index = events.findIndex(e => e === eventName);
  return eventColors[index % eventColors.length];
};

// Components
const EventForm = ({ type, onAdd }) => {
  const isFixed = type === 'fixed';
  const [name, setName] = useState('');
  const [start, setStart] = useState('');
  const [finish, setFinish] = useState('');
  const [duration, setDuration] = useState('');
  const [inDorm, setInDorm] = useState(false);

  const handleSubmit = () => {
    if (!name) return;
    
    if (isFixed) {
      if (start === '' || finish === '') return;
      onAdd({
        name,
        start: parseInt(start),
        finish: parseInt(finish),
        in_dorm: inDorm,
      });
    } else {
      if (duration === '') return;
      onAdd({
        name,
        duration: parseInt(duration),
        in_dorm: inDorm,
      });
    }
    
    setName('');
    setStart('');
    setFinish('');
    setDuration('');
    setInDorm(false);
  };

  return (
    <div>
      <div style={styles.inputGroup}>
        <label style={styles.label}>Event Name</label>
        <input
          style={styles.input}
          placeholder="e.g., Math Class"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      
      {isFixed ? (
        <div style={styles.inputRow}>
          <div>
            <label style={styles.label}>Start Hour (0-23)</label>
            <input
              style={styles.input}
              type="number"
              min="0"
              max="23"
              placeholder="9"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div>
            <label style={styles.label}>End Hour (0-23)</label>
            <input
              style={styles.input}
              type="number"
              min="0"
              max="24"
              placeholder="11"
              value={finish}
              onChange={(e) => setFinish(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: '0.5rem' }}>
            <label style={styles.checkbox}>
              <input
                type="checkbox"
                checked={inDorm}
                onChange={(e) => setInDorm(e.target.checked)}
              />
              In Dorm
            </label>
          </div>
        </div>
      ) : (
        <div style={styles.inputRow}>
          <div>
            <label style={styles.label}>Duration (hours)</label>
            <input
              style={styles.input}
              type="number"
              min="1"
              max="12"
              placeholder="2"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: '0.5rem' }}>
            <label style={styles.checkbox}>
              <input
                type="checkbox"
                checked={inDorm}
                onChange={(e) => setInDorm(e.target.checked)}
              />
              In Dorm
            </label>
          </div>
          <div></div>
        </div>
      )}
      
      <button
        style={{ ...styles.button, ...styles.primaryButton, marginTop: '1rem' }}
        onClick={handleSubmit}
      >
        Add {isFixed ? 'Fixed' : 'Flexible'} Event
      </button>
    </div>
  );
};

const EventList = ({ events, type, onDelete }) => {
  if (events.length === 0) return null;
  
  return (
    <div style={styles.eventList}>
      {events.map((event, index) => (
        <div key={index} style={styles.eventItem}>
          <span>
            <strong>{event.name}</strong>
            {type === 'fixed' 
              ? ` • ${formatHour(event.start)} - ${formatHour(event.finish)}`
              : ` • ${event.duration}h`
            }
            {event.in_dorm && <span style={{ color: colors.dorm }}> • 🏠</span>}
          </span>
          <button style={styles.deleteBtn} onClick={() => onDelete(index)}>×</button>
        </div>
      ))}
    </div>
  );
};

const RoommateCard = ({ name, roommate, setRoommate }) => {
  const addFixedEvent = (event) => {
    setRoommate({
      ...roommate,
      fixed_events: [...roommate.fixed_events, event],
    });
  };

  const addFlexibleEvent = (event) => {
    setRoommate({
      ...roommate,
      flexible_events: [...roommate.flexible_events, event],
    });
  };

  const deleteFixedEvent = (index) => {
    setRoommate({
      ...roommate,
      fixed_events: roommate.fixed_events.filter((_, i) => i !== index),
    });
  };

  const deleteFlexibleEvent = (index) => {
    setRoommate({
      ...roommate,
      flexible_events: roommate.flexible_events.filter((_, i) => i !== index),
    });
  };

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>
        <span style={{ fontSize: '1.5rem' }}>👤</span>
        <input
          style={{ ...styles.input, fontSize: '1.1rem', fontWeight: '600', width: 'auto', flex: 1 }}
          value={roommate.roommate_name}
          onChange={(e) => setRoommate({ ...roommate, roommate_name: e.target.value })}
          placeholder="Roommate Name"
        />
      </div>

      <div style={{ marginBottom: '2rem' }}>
        <h4 style={{ color: colors.accentLight, marginBottom: '1rem', fontSize: '0.95rem', fontWeight: '600' }}>
          📌 Fixed Events
          <span style={{ ...styles.badge, marginLeft: '0.75rem' }}>
            {roommate.fixed_events.length}
          </span>
        </h4>
        <EventForm type="fixed" onAdd={addFixedEvent} />
        <EventList events={roommate.fixed_events} type="fixed" onDelete={deleteFixedEvent} />
      </div>

      <div>
        <h4 style={{ color: colors.accentLight, marginBottom: '1rem', fontSize: '0.95rem', fontWeight: '600' }}>
          🔄 Flexible Events
          <span style={{ ...styles.badge, marginLeft: '0.75rem' }}>
            {roommate.flexible_events.length}
          </span>
        </h4>
        <EventForm type="flexible" onAdd={addFlexibleEvent} />
        <EventList events={roommate.flexible_events} type="flexible" onDelete={deleteFlexibleEvent} />
      </div>
    </div>
  );
};

const ScheduleVisualization = ({ blocks, label, allEventNames }) => {
  // Build hour map
  const hourMap = {};
  blocks.forEach(block => {
    for (let h = block.start; h < block.finish; h++) {
      hourMap[h] = block;
    }
  });

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: colors.textMuted }}>{label}</div>
      <div style={styles.timeLabels}>
        {Array.from({ length: 24 }, (_, i) => (
          <div key={i} style={styles.timeLabel}>{formatHour(i)}</div>
        ))}
      </div>
      <div style={styles.scheduleGrid}>
        {Array.from({ length: 24 }, (_, hour) => {
          const block = hourMap[hour];
          const isEmpty = !block;
          const bgColor = isEmpty 
            ? colors.bg 
            : getEventColor(block.event, allEventNames);
          const borderColor = block?.in_dorm ? colors.dorm : 'transparent';
          
          return (
            <div
              key={hour}
              style={{
                ...styles.hourBlock,
                background: bgColor,
                borderBottom: `3px solid ${borderColor}`,
                opacity: isEmpty ? 0.3 : 1,
              }}
              title={block ? `${block.event} (${formatHour(block.start)}-${formatHour(block.finish)})${block.in_dorm ? ' - In Dorm' : ''}` : 'Free'}
            >
              {block && block.start === hour && (
                <span style={{ 
                  position: 'absolute', 
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: `${(block.finish - block.start) * 100}%`,
                  padding: '0 2px',
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

const ResultCard = ({ result, index, allEventNames }) => {
  return (
    <div style={styles.resultCard}>
      <div style={styles.scoreDisplay}>
        <span style={{ fontSize: '1.1rem', fontWeight: '600' }}>Option #{index + 1}</span>
        <div style={styles.scoreBadge}>
          {result.score} hrs together in dorm
        </div>
      </div>
      
      <ScheduleVisualization 
        blocks={result.roommate_a} 
        label="Roommate A" 
        allEventNames={allEventNames}
      />
      <ScheduleVisualization 
        blocks={result.roommate_b} 
        label="Roommate B" 
        allEventNames={allEventNames}
      />
      
      <div style={styles.legend}>
        <div style={styles.legendItem}>
          <div style={{ ...styles.legendDot, background: colors.dorm }}></div>
          <span>Green border = In Dorm</span>
        </div>
        <div style={styles.legendItem}>
          <div style={{ ...styles.legendDot, background: colors.bg, opacity: 0.3 }}></div>
          <span>Empty = Free time</span>
        </div>
      </div>
    </div>
  );
};

export default function RoommateScheduler() {
  const [roommateA, setRoommateA] = useState({
    roommate_name: 'Roommate A',
    fixed_events: [],
    flexible_events: [],
  });
  
  const [roommateB, setRoommateB] = useState({
    roommate_name: 'Roommate B',
    fixed_events: [],
    flexible_events: [],
  });
  
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          roommate_a: roommateA,
          roommate_b: roommateB,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to analyze schedules');
      }
      
      const data = await response.json();
      setResults(data.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Collect all event names for consistent coloring
  const allEventNames = [
    ...roommateA.fixed_events.map(e => e.name),
    ...roommateA.flexible_events.map(e => e.name),
    ...roommateB.fixed_events.map(e => e.name),
    ...roommateB.flexible_events.map(e => e.name),
  ].filter((v, i, a) => a.indexOf(v) === i);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>Roommate Schedule Optimizer</h1>
        <p style={styles.subtitle}>
          Find the best schedule combinations to minimize your time together
        </p>
      </header>

      <div style={styles.grid}>
        <RoommateCard
          name="A"
          roommate={roommateA}
          setRoommate={setRoommateA}
        />
        <RoommateCard
          name="B"
          roommate={roommateB}
          setRoommate={setRoommateB}
        />
      </div>

      <div style={{ maxWidth: '600px', margin: '0 auto' }}>
        <button
          style={{
            ...styles.analyzeButton,
            opacity: loading ? 0.7 : 1,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
          onClick={analyze}
          disabled={loading}
        >
          {loading ? '⏳ Analyzing...' : '✨ Find Best Schedules'}
        </button>
        
        {error && (
          <div style={{ 
            marginTop: '1rem', 
            padding: '1rem', 
            background: `${colors.notDorm}20`, 
            borderRadius: '8px',
            color: colors.notDorm,
            textAlign: 'center',
          }}>
            {error}. Make sure your FastAPI server is running on {API_URL}
          </div>
        )}
      </div>

      {results && (
        <div style={styles.resultsSection}>
          <h2 style={{ ...styles.title, fontSize: '2rem', textAlign: 'center', marginBottom: '2rem' }}>
            Top {results.length} Schedule Combinations
          </h2>
          
          {results.length === 0 ? (
            <div style={styles.emptyState}>
              No valid schedule combinations found. Try adjusting the events.
            </div>
          ) : (
            results.map((result, index) => (
              <ResultCard 
                key={index} 
                result={result} 
                index={index}
                allEventNames={allEventNames}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}