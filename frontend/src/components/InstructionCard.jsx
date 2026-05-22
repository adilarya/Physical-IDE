export default function InstructionCard({ image, text, citation, step, total, status }) {
  const complete = step > total;
  const isError = status && status.startsWith('error');
  const isDanger = status === 'error_short_circuit';

  const borderColor = isDanger ? 'rgba(255,68,85,0.3)'
    : isError ? 'rgba(245,158,11,0.2)'
    : complete ? 'rgba(16,232,160,0.2)'
    : '#132030';

  const accentColor = isDanger ? '#ff4455'
    : isError ? '#f59e0b'
    : complete ? '#10e8a0'
    : '#f97316';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 12 }}>

      {/* Image area */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          borderRadius: 2,
          overflow: 'hidden',
          border: `1px solid ${borderColor}`,
          background: '#0d1928',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
        }}
      >
        {image ? (
          <img
            key={image.slice(-32)}
            src={image}
            alt="assembly instruction"
            className="instr-fade"
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, opacity: 0.3 }}>
            {/* Placeholder icon */}
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect x="2" y="2" width="28" height="28" rx="2" stroke="#4d6a88" strokeWidth="1.5" strokeDasharray="4 2"/>
              <circle cx="16" cy="16" r="5" stroke="#4d6a88" strokeWidth="1.5"/>
              <line x1="8" y1="16" x2="11" y2="16" stroke="#4d6a88" strokeWidth="1.5"/>
              <line x1="21" y1="16" x2="24" y2="16" stroke="#4d6a88" strokeWidth="1.5"/>
            </svg>
            <span style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#4d6a88', letterSpacing: '0.1em' }}>
              {status === 'session_init' || !status ? 'AWAITING FIRST SCAN' : 'NO DIAGRAM'}
            </span>
          </div>
        )}

        {/* Error / danger overlay badge */}
        {isError && (
          <div style={{
            position: 'absolute',
            top: 8,
            left: 8,
            padding: '3px 8px',
            background: isDanger ? 'rgba(255,68,85,0.9)' : 'rgba(245,158,11,0.85)',
            fontFamily: "'Chakra Petch'",
            fontSize: 9,
            fontWeight: 600,
            letterSpacing: '0.2em',
            color: '#fff',
            borderRadius: 1,
          }}>
            {isDanger ? '⚠ DANGER' : '⚠ ' + status.replace('error_', '').replace(/_/g, ' ').toUpperCase()}
          </div>
        )}

        {/* Step progress bar at bottom */}
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, background: '#132030' }}>
          <div style={{
            height: '100%',
            width: `${Math.min((Math.min(step, total) / total) * 100, 100)}%`,
            background: accentColor,
            transition: 'width 0.5s ease, background 0.3s ease',
          }} />
        </div>
      </div>

      {/* Text */}
      <div style={{ flexShrink: 0 }}>
        <p
          key={text}
          className="instr-fade"
          style={{
            fontFamily: "'Chakra Petch'",
            fontSize: 13,
            fontWeight: 400,
            lineHeight: 1.65,
            color: isError ? (isDanger ? '#ff7a86' : '#f6c05a') : '#c8ddf0',
            margin: 0,
          }}
        >
          {text}
        </p>

        {citation && (
          <p style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#243344', letterSpacing: '0.06em', marginTop: 6 }}>
            SRC / {citation}
          </p>
        )}

        {complete && (
          <div style={{
            marginTop: 10,
            padding: '8px 12px',
            background: 'rgba(16,232,160,0.08)',
            border: '1px solid rgba(16,232,160,0.2)',
            borderRadius: 2,
            fontFamily: "'Chakra Petch'",
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.2em',
            color: '#10e8a0',
            textAlign: 'center',
          }}>
            ✓ BUILD COMPLETE — ALL STEPS VERIFIED
          </div>
        )}
      </div>
    </div>
  );
}
