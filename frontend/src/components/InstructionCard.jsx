/**
 * InstructionCard - the center panel. Shows the current Lego-style instruction
 * image, the text caption, the source citation, and a step badge. Image + text
 * fade in on every change (keyed by content).
 */
export default function InstructionCard({
  image,
  text,
  citation,
  step,
  total,
  status,
}) {
  const complete = step > total;
  const isError = status && status.startsWith('error');

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-xs tracking-widest text-slate-400">
          INSTRUCTION
        </span>
        <span
          className={
            'font-mono text-xs px-2 py-1 rounded ' +
            (complete
              ? 'bg-emerald-500/20 text-emerald-300'
              : 'bg-orange-500/20 text-orange-300')
          }
        >
          {complete ? 'BUILD COMPLETE' : `STEP ${Math.min(step, total)} / ${total}`}
        </span>
      </div>

      <div className="relative flex-1 rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden flex items-center justify-center">
        {image ? (
          <img
            key={image.slice(-32)}
            src={image}
            alt="assembly instruction"
            className="instr-fade max-h-full max-w-full object-contain"
          />
        ) : (
          <span className="text-slate-600 font-mono text-sm">
            awaiting first instruction...
          </span>
        )}

        {isError && (
          <div className="absolute top-3 left-3 px-2 py-1 rounded bg-red-500/90 text-white font-mono text-xs tracking-wider">
            ALERT: {status.replace('error_', '').replace(/_/g, ' ').toUpperCase()}
          </div>
        )}
      </div>

      <p
        key={text}
        className={
          'instr-fade mt-4 leading-relaxed ' +
          (isError ? 'text-red-200' : 'text-slate-100')
        }
      >
        {text}
      </p>

      {citation && (
        <p className="mt-2 font-mono text-xs text-slate-500">
          source: {citation}
        </p>
      )}
    </div>
  );
}
