import { useEffect, useRef } from 'react';

const KIND_STYLE = {
  agent: { color: '#4d6a88' },
  sys:   { color: '#243344' },
  error: { color: '#ff4455' },
};

export default function AgentLog({ log }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [log]);

  if (!log || log.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#243344', letterSpacing: '0.1em' }}>
          NO EVENTS
        </span>
      </div>
    );
  }

  const sessionStart = log[0]?.t || Date.now();

  return (
    <div className="log-scroll" style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 5 }}>
      {log.map((entry, i) => {
        const elapsed = ((entry.t - sessionStart) / 1000).toFixed(1);
        const style = KIND_STYLE[entry.kind] || KIND_STYLE.agent;
        return (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <span style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#1e3248', letterSpacing: '0.05em', flexShrink: 0, paddingTop: 1, minWidth: 36 }}>
              +{elapsed}s
            </span>
            <span style={{ fontFamily: "'DM Mono'", fontSize: 9, color: style.color, lineHeight: 1.6, wordBreak: 'break-all' }}>
              {entry.line}
            </span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
