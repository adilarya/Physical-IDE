import { useEffect, useRef } from 'react';

const KIND_COLOR = {
  sys: 'text-sky-400',
  agent: 'text-emerald-300',
  error: 'text-red-400',
};

function fmtTime(t) {
  return new Date(t).toTimeString().slice(0, 8);
}

/**
 * AgentLog - the right panel. Terminal-style scrolling log of agent events,
 * colored by kind, auto-scrolling to the newest line.
 */
export default function AgentLog({ log }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [log]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-xs tracking-widest text-slate-400">
          AGENT LOG
        </span>
        <span className="font-mono text-xs text-slate-600">
          {log.length} events
        </span>
      </div>

      <div className="log-scroll flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-black/60 p-3 font-mono text-xs leading-relaxed">
        {log.length === 0 && (
          <div className="text-slate-700">[ waiting for agent events ]</div>
        )}
        {log.map((e, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-slate-700 shrink-0">{fmtTime(e.t)}</span>
            <span className={KIND_COLOR[e.kind] || 'text-slate-300'}>
              {e.line}
            </span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
