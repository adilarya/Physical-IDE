import { useState, useRef, useEffect } from 'react';

/**
 * ChatPanel — slide-out tutorial generator.
 * User describes a circuit goal, the backend streams back a Lego-style
 * step-by-step guide with images.
 */
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

  const WIRE_COLORS = {
    red: 'bg-red-500',
    black: 'bg-slate-900 border border-slate-600',
    brown: 'bg-amber-800',
    green: 'bg-green-500',
    yellow: 'bg-yellow-400',
    orange: 'bg-orange-500',
    none: 'bg-slate-600',
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-950/50"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={
          'fixed top-0 right-0 h-full z-40 flex flex-col bg-slate-900 border-l border-slate-700 shadow-2xl transition-transform duration-300 ' +
          (isOpen ? 'translate-x-0' : 'translate-x-full')
        }
        style={{ width: 420 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <div>
            <h2 className="font-mono text-sm tracking-[0.25em] text-slate-100">CIRCUIT PLANNER</h2>
            <p className="font-mono text-[10px] text-slate-500 mt-0.5">describe your goal → get a wiring guide</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-200 font-mono text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Steps area */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Idle state */}
          {!tutorialState.loading && tutorialState.steps.length === 0 && !tutorialState.error && (
            <div className="h-full flex flex-col items-center justify-center text-center gap-4 opacity-60">
              <div className="text-4xl">⚡</div>
              <p className="font-mono text-xs text-slate-400 leading-relaxed max-w-xs">
                Tell me what you want your breadboard to do and I'll generate a step-by-step wiring guide with diagrams.
              </p>
              <p className="font-mono text-[10px] text-slate-600">
                e.g. "make an LED blink" · "control a servo" · "read a button"
              </p>
            </div>
          )}

          {/* Thinking */}
          {tutorialState.thinking && (
            <div className="flex items-center gap-3 text-orange-400 font-mono text-xs">
              <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
              {tutorialState.thinking}
            </div>
          )}

          {/* Error */}
          {tutorialState.error && (
            <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 font-mono text-xs text-red-300">
              {tutorialState.error}
            </div>
          )}

          {/* Goal banner */}
          {tutorialState.goal && (
            <div className="px-4 py-3 rounded-lg bg-orange-500/10 border border-orange-500/30">
              <span className="font-mono text-[10px] text-orange-400 tracking-widest">GOAL</span>
              <p className="font-mono text-xs text-slate-200 mt-1">{tutorialState.goal}</p>
            </div>
          )}

          {/* Generated steps */}
          {tutorialState.steps.map((s) => (
            <div key={s.step} className="rounded-xl border border-slate-700 bg-slate-800/60 overflow-hidden">
              {/* Step image */}
              {s.image_b64 ? (
                <img
                  src={s.image_b64}
                  alt={s.title}
                  className="w-full object-cover"
                  style={{ maxHeight: 200 }}
                />
              ) : (
                <div className="w-full h-28 bg-slate-800 flex items-center justify-center">
                  <span className="font-mono text-xs text-slate-600">generating diagram...</span>
                </div>
              )}

              {/* Step content */}
              <div className="p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 tracking-widest">
                    STEP {s.step} / {tutorialState.totalSteps}
                  </span>
                  {s.wire_color && s.wire_color !== 'none' && (
                    <span className="flex items-center gap-1.5 font-mono text-[10px] text-slate-400">
                      <span className={`w-2.5 h-2.5 rounded-full ${WIRE_COLORS[s.wire_color] || 'bg-slate-600'}`} />
                      {s.wire_color} wire
                    </span>
                  )}
                </div>
                <p className="font-mono text-xs font-bold text-slate-100 mb-1">{s.title}</p>
                <p className="text-sm text-slate-300 leading-relaxed">{s.instruction}</p>
              </div>
            </div>
          ))}

          {/* Complete banner */}
          {tutorialState.complete && (
            <div className="px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 font-mono text-xs text-emerald-300 text-center">
              Guide complete — follow the steps above, then use the main view to verify your assembly.
            </div>
          )}

          <div ref={stepsEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="px-5 py-4 border-t border-slate-700">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="What do you want to build?"
              disabled={tutorialState.loading}
              className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 font-mono text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-orange-500 disabled:opacity-40"
            />
            <button
              type="submit"
              disabled={!input.trim() || tutorialState.loading}
              className="px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-400 disabled:opacity-40 disabled:cursor-not-allowed font-mono text-xs font-bold text-slate-950"
            >
              {tutorialState.loading ? '...' : 'GO'}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
