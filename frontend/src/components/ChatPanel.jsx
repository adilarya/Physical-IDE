import { useState, useRef, useEffect } from 'react';

const WIRE_DOT = {
  red:    '#ef4444',
  black:  '#64748b',
  brown:  '#92400e',
  green:  '#22c55e',
  yellow: '#eab308',
  orange: '#FF5722',
  none:   '#243344',
};

export default function ChatPanel({ isOpen, onClose, sendMessage, tutorialState }) {
  const [input, setInput] = useState('');
  const stepsEndRef = useRef(null);

  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [tutorialState.steps]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const goal = input.trim();
    if (!goal || tutorialState.loading) return;
    sendMessage(goal);
    setInput('');
  };

  const panelStyle = {
    position: 'fixed',
    top: 0,
    right: 0,
    height: '100%',
    width: 420,
    zIndex: 40,
    display: 'flex',
    flexDirection: 'column',
    background: '#09111e',
    borderLeft: '1px solid #1e3248',
    boxShadow: '-20px 0 60px rgba(0,0,0,0.6)',
    transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
    transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
  };

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          style={{ position: 'fixed', inset: 0, zIndex: 30, background: 'rgba(6,12,22,0.6)' }}
        />
      )}

      <div style={panelStyle}>
        {/* Orange top accent */}
        <div style={{ height: 1, background: 'linear-gradient(90deg, #FF5722, rgba(255,87,34,0.1), transparent)', flexShrink: 0 }} />

        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #132030', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontFamily: "'Chakra Petch'", fontSize: 11, fontWeight: 600, letterSpacing: '0.28em', color: '#c8ddf0' }}>
              CIRCUIT PLANNER
            </div>
            <div style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#4d6a88', marginTop: 3, letterSpacing: '0.1em' }}>
              describe your goal → get a wiring guide
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ fontFamily: "'DM Mono'", fontSize: 12, color: '#243344', background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        {/* Content area */}
        <div className="log-scroll" style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Idle */}
          {!tutorialState.loading && tutorialState.steps.length === 0 && !tutorialState.error && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, opacity: 0.5, textAlign: 'center', padding: '40px 20px' }}>
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <rect x="2" y="2" width="36" height="36" rx="2" stroke="#4d6a88" strokeWidth="1.2" strokeDasharray="5 3"/>
                <circle cx="20" cy="20" r="7" stroke="#4d6a88" strokeWidth="1.2"/>
                <line x1="6" y1="20" x2="13" y2="20" stroke="#4d6a88" strokeWidth="1.2"/>
                <line x1="27" y1="20" x2="34" y2="20" stroke="#4d6a88" strokeWidth="1.2"/>
                <line x1="20" y1="6" x2="20" y2="13" stroke="#4d6a88" strokeWidth="1.2"/>
                <line x1="20" y1="27" x2="20" y2="34" stroke="#4d6a88" strokeWidth="1.2"/>
              </svg>
              <div>
                <div style={{ fontFamily: "'Chakra Petch'", fontSize: 10, letterSpacing: '0.2em', color: '#4d6a88', marginBottom: 8 }}>READY TO PLAN</div>
                <div style={{ fontFamily: "'DM Mono'", fontSize: 10, color: '#243344', lineHeight: 1.8 }}>
                  e.g. "make an LED blink"<br/>
                  "control a servo motor"<br/>
                  "read a button press"
                </div>
              </div>
            </div>
          )}

          {/* Thinking */}
          {tutorialState.thinking && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="pulse-dot" style={{ display: 'block', width: 6, height: 6, borderRadius: '50%', background: '#FF5722', flexShrink: 0 }} />
              <span style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#FF5722', letterSpacing: '0.08em' }}>{tutorialState.thinking}</span>
            </div>
          )}

          {/* Error */}
          {tutorialState.error && (
            <div style={{ padding: '10px 12px', background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.2)', borderRadius: 2, fontFamily: "'DM Mono'", fontSize: 9, color: '#ff7a86', letterSpacing: '0.05em' }}>
              {tutorialState.error}
            </div>
          )}

          {/* Goal banner */}
          {tutorialState.goal && tutorialState.steps.length === 0 && !tutorialState.error && (
            <div style={{ padding: '10px 12px', background: 'rgba(255,87,34,0.06)', border: '1px solid rgba(255,87,34,0.15)', borderRadius: 2 }}>
              <div style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#FF5722', letterSpacing: '0.2em', marginBottom: 4 }}>GOAL</div>
              <div style={{ fontFamily: "'Chakra Petch'", fontSize: 11, color: '#c8ddf0' }}>{tutorialState.goal}</div>
            </div>
          )}

          {/* Steps */}
          {tutorialState.steps.map((s, idx) => (
            <div
              key={s.step}
              className="step-appear"
              style={{
                animationDelay: `${idx * 0.05}s`,
                borderRadius: 2,
                border: '1px solid #132030',
                background: '#0d1928',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              {/* Orange top accent */}
              <div style={{ height: 1, background: 'linear-gradient(90deg, #FF5722, rgba(255,87,34,0.05), transparent)' }} />

              {/* Image */}
              {s.image_b64 ? (
                <img
                  src={s.image_b64}
                  alt={s.title}
                  style={{ width: '100%', maxHeight: 160, objectFit: 'cover', display: 'block' }}
                />
              ) : (
                <div style={{ width: '100%', height: 80, background: '#07101a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span className="pulse-dot" style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#243344', letterSpacing: '0.1em' }}>GENERATING DIAGRAM</span>
                </div>
              )}

              {/* Content */}
              <div style={{ padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#FF5722', letterSpacing: '0.2em' }}>
                    {String(s.step).padStart(2, '0')} / {String(tutorialState.totalSteps).padStart(2, '0')}
                  </span>
                  {s.wire_color && s.wire_color !== 'none' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ display: 'block', width: 8, height: 8, borderRadius: '50%', background: WIRE_DOT[s.wire_color] || '#243344', flexShrink: 0 }} />
                      <span style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#4d6a88' }}>{s.wire_color}</span>
                    </div>
                  )}
                </div>
                <div style={{ fontFamily: "'Chakra Petch'", fontSize: 11, fontWeight: 600, color: '#c8ddf0', marginBottom: 4 }}>{s.title}</div>
                <div style={{ fontFamily: "'DM Mono'", fontSize: 10, color: '#4d6a88', lineHeight: 1.7 }}>{s.instruction}</div>
              </div>
            </div>
          ))}

          {/* Complete */}
          {tutorialState.complete && (
            <div style={{ padding: '10px 14px', background: 'rgba(16,232,160,0.06)', border: '1px solid rgba(16,232,160,0.15)', borderRadius: 2, textAlign: 'center' }}>
              <div style={{ fontFamily: "'Chakra Petch'", fontSize: 10, fontWeight: 600, color: '#10e8a0', letterSpacing: '0.2em' }}>✓ GUIDE COMPLETE</div>
              <div style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#4d6a88', marginTop: 4 }}>follow the steps above, then verify in the main view</div>
            </div>
          )}

          <div ref={stepsEndRef} />
        </div>

        {/* Input */}
        <div style={{ padding: '14px 20px', borderTop: '1px solid #132030', flexShrink: 0 }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="What do you want to build?"
              disabled={tutorialState.loading}
              style={{
                flex: 1,
                fontFamily: "'DM Mono'",
                fontSize: 11,
                padding: '9px 12px',
                background: '#07101a',
                border: '1px solid #1e3248',
                borderRadius: 1,
                color: '#c8ddf0',
                outline: 'none',
                opacity: tutorialState.loading ? 0.4 : 1,
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || tutorialState.loading}
              style={{
                fontFamily: "'Chakra Petch'",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.2em',
                padding: '9px 16px',
                background: (!input.trim() || tutorialState.loading) ? 'transparent' : '#FF5722',
                color: (!input.trim() || tutorialState.loading) ? '#243344' : '#060c16',
                border: '1px solid',
                borderColor: (!input.trim() || tutorialState.loading) ? '#243344' : '#FF5722',
                borderRadius: 1,
                cursor: (!input.trim() || tutorialState.loading) ? 'not-allowed' : 'pointer',
              }}
            >
              {tutorialState.loading ? '...' : 'GO'}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}
