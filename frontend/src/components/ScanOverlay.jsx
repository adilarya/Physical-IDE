/**
 * ScanOverlay - the "Deep-Scan" branding overlay shown over the webcam feed
 * during the 1-3s processing window. Intentionally NOT a spinner: a sweeping
 * orange measurement grid, a scan band, AR fiducial markers, and component
 * recognition reticles. All animation lives in index.css.
 */
export default function ScanOverlay({ active }) {
  if (!active) return null;

  const corners = ['top-3 left-3', 'top-3 right-3', 'bottom-3 left-3', 'bottom-3 right-3'];

  return (
    <div className="scan-root absolute inset-0 z-20 overflow-hidden pointer-events-none">
      {/* darkening tint */}
      <div className="absolute inset-0 bg-slate-950/45" />

      {/* moving measurement grid */}
      <div className="scan-grid absolute inset-0" />

      {/* vertical sweep band */}
      <div className="absolute inset-x-0 h-1/2 scan-sweep" />

      {/* corner AR fiducial markers */}
      {corners.map((pos, i) => (
        <div
          key={i}
          className={`fiducial absolute ${pos} w-9 h-9 border-2 border-orange-400`}
          style={{ animationDelay: `${i * 0.15}s` }}
        >
          <div className="absolute inset-1.5 border border-orange-400/60" />
          <div className="absolute left-1/2 top-1/2 w-1.5 h-1.5 -translate-x-1/2 -translate-y-1/2 bg-orange-400" />
        </div>
      ))}

      {/* component-recognition reticles */}
      <div className="reticle absolute left-[27%] top-[38%] w-16 h-16">
        <div className="reticle-spin w-full h-full rounded-full border border-orange-400/40 border-t-orange-400" />
        <div className="absolute left-1/2 top-1/2 w-1.5 h-1.5 -translate-x-1/2 -translate-y-1/2 bg-orange-400" />
      </div>
      <div
        className="reticle absolute left-[63%] top-[56%] w-12 h-12"
        style={{ animationDelay: '0.5s' }}
      >
        <div className="w-full h-full border border-orange-300/70" />
        <div className="absolute left-1/2 top-0 h-full w-px bg-orange-300/50" />
        <div className="absolute top-1/2 left-0 w-full h-px bg-orange-300/50" />
      </div>

      {/* status readout */}
      <div className="absolute left-1/2 bottom-6 -translate-x-1/2 text-center">
        <div className="font-mono text-sm tracking-[0.4em] text-orange-400">
          DEEP-SCAN
        </div>
        <div className="font-mono text-xs tracking-[0.25em] text-orange-200/80 mt-1">
          ANALYZING BOARD STATE
          <span className="dot1">.</span>
          <span className="dot2">.</span>
          <span className="dot3">.</span>
        </div>
      </div>
    </div>
  );
}
