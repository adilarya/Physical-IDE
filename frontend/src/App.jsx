import { useState, useRef, useCallback, useEffect } from 'react';
import { useWebcam } from './hooks/useWebcam';
import { useHandTracker } from './hooks/useHandTracker';
import { useAgentSocket } from './hooks/useAgentSocket';
import ScanOverlay from './components/ScanOverlay';
import InstructionCard from './components/InstructionCard';
import AgentLog from './components/AgentLog';
import ChatPanel from './components/ChatPanel';

const TOTAL_STEPS = 3;

/* ─── Logo ──────────────────────────────────────────────────────────────── */
function Logo() {
  return (
    <div className="flex items-center gap-3">
      {/* Mark: circuit node symbol */}
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Outer ring */}
        <rect x="1" y="1" width="26" height="26" rx="2" stroke="#f97316" strokeWidth="1.2" strokeOpacity="0.4"/>
        {/* Inner square rotated 45° */}
        <rect x="8" y="8" width="12" height="12" rx="1" transform="rotate(45 14 14)" fill="none" stroke="#f97316" strokeWidth="1.2"/>
        {/* Center dot */}
        <circle cx="14" cy="14" r="2.5" fill="#f97316" className="logo-dot"/>
        {/* Corner traces */}
        <line x1="1" y1="7" x2="6" y2="7" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
        <line x1="22" y1="21" x2="27" y2="21" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
        <line x1="7" y1="1" x2="7" y2="6" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
        <line x1="21" y1="22" x2="21" y2="27" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
      </svg>
      {/* Wordmark */}
      <div>
        <div style={{ fontFamily: "'Chakra Petch', sans-serif", fontSize: 15, fontWeight: 700, letterSpacing: '0.22em', color: '#c8ddf0' }}>
          PREFLIGHT
        </div>
        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 8, letterSpacing: '0.3em', color: '#4d6a88', marginTop: 1 }}>
          PHYSICAL IDE
        </div>
      </div>
    </div>
  );
}

/* ─── Status badge ──────────────────────────────────────────────────────── */
const STATUS_CONFIG = {
  session_init:         { label: 'READY',         color: '#4d6a88',   bg: 'rgba(77,106,136,0.12)' },
  success_advance:      { label: 'VERIFIED',       color: '#10e8a0',   bg: 'rgba(16,232,160,0.1)'  },
  error_short_circuit:  { label: 'SHORT CIRCUIT',  color: '#ff4455',   bg: 'rgba(255,68,85,0.12)'  },
  error_occluded:       { label: 'VIEW BLOCKED',   color: '#f59e0b',   bg: 'rgba(245,158,11,0.12)' },
  error_wrong_placement:{ label: 'WRONG PLACEMENT',color: '#f59e0b',   bg: 'rgba(245,158,11,0.12)' },
  idle:                 { label: 'STANDBY',        color: '#243344',   bg: 'rgba(36,51,68,0.2)'    },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
  return (
    <div className="status-badge" style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}33` }}>
      {cfg.label}
    </div>
  );
}

/* ─── Panel header ──────────────────────────────────────────────────────── */
function PanelLabel({ num, title, children }) {
  return (
    <div className="panel-label">
      <span className="panel-num">{num} /</span>
      <span className="panel-title">{title}</span>
      <div className="ml-auto flex items-center gap-2">{children}</div>
    </div>
  );
}

/* ─── Main App ──────────────────────────────────────────────────────────── */
export default function App() {
  const [started, setStarted] = useState(false);
  const [videoWidth, setVideoWidth] = useState(360);
  const [chatOpen, setChatOpen] = useState(false);
  const [tutorialState, setTutorialState] = useState({
    loading: false, thinking: '', goal: '', steps: [],
    totalSteps: 0, complete: false, error: '',
  });

  const dragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);

  const { videoRef, error: webcamError, captureFrame } = useWebcam(started);
  const socket = useAgentSocket(started);

  const socketRef = useRef(socket);
  socketRef.current = socket;

  const onHandClear = useCallback(() => {
    const s = socketRef.current;
    if (!s.connected || s.scanning) return;
    s.sendFrame(captureFrame());
  }, [captureFrame]);

  const { handsInFrame, trackerReady } = useHandTracker(videoRef, started, onHandClear);

  const forceCapture = () => {
    if (!socket.connected || socket.scanning) return;
    socket.sendFrame(captureFrame());
  };

  // Tutorial goal sender
  const sendTutorialGoal = useCallback((goal) => {
    setTutorialState({ loading: true, thinking: '', goal, steps: [], totalSteps: 0, complete: false, error: '' });
    socket.sendTutorial(goal);
  }, [socket]);

  // Handle tutorial streaming events
  useEffect(() => {
    const ev = socket.tutorialEvent;
    if (!ev) return;
    if (ev.event === 'tutorial_thinking') {
      setTutorialState(p => ({ ...p, thinking: ev.text }));
    } else if (ev.event === 'tutorial_start') {
      setTutorialState(p => ({ ...p, thinking: '', totalSteps: ev.total_steps, goal: ev.goal }));
    } else if (ev.event === 'tutorial_step') {
      setTutorialState(p => ({ ...p, steps: [...p.steps, ev] }));
    } else if (ev.event === 'tutorial_complete') {
      setTutorialState(p => ({ ...p, loading: false, complete: true, thinking: '' }));
    } else if (ev.event === 'tutorial_error') {
      setTutorialState(p => ({ ...p, loading: false, error: ev.text, thinking: '' }));
    }
  }, [socket.tutorialEvent]);

  // Drag resize
  const onDragMouseDown = useCallback((e) => {
    dragging.current = true;
    dragStartX.current = e.clientX;
    dragStartWidth.current = videoWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [videoWidth]);

  useEffect(() => {
    const onMove = (e) => {
      if (!dragging.current) return;
      const next = Math.min(Math.max(dragStartWidth.current + e.clientX - dragStartX.current, 200), 700);
      setVideoWidth(next);
    };
    const onUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  /* ─── Start Screen ─────────────────────────────────────────────────────── */
  if (!started) {
    return (
      <div className="h-full flex flex-col items-center justify-center" style={{ background: '#060c16' }}>
        {/* Decorative lines */}
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, #f97316, transparent)' }} />
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, #f97316, transparent)' }} />

        <div className="flex flex-col items-center gap-8 boot-in" style={{ maxWidth: 440, textAlign: 'center' }}>
          {/* Logo large */}
          <div className="flex flex-col items-center gap-4 boot-in">
            <svg width="64" height="64" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="1" width="26" height="26" rx="2" stroke="#f97316" strokeWidth="1.2" strokeOpacity="0.4"/>
              <rect x="8" y="8" width="12" height="12" rx="1" transform="rotate(45 14 14)" fill="none" stroke="#f97316" strokeWidth="1.5"/>
              <circle cx="14" cy="14" r="2.5" fill="#f97316" className="logo-dot"/>
              <line x1="1" y1="7" x2="6" y2="7" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
              <line x1="22" y1="21" x2="27" y2="21" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
              <line x1="7" y1="1" x2="7" y2="6" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
              <line x1="21" y1="22" x2="21" y2="27" stroke="#f97316" strokeWidth="1" strokeOpacity="0.5"/>
            </svg>
            <div>
              <div style={{ fontFamily: "'Chakra Petch'", fontSize: 28, fontWeight: 700, letterSpacing: '0.28em', color: '#c8ddf0' }}>PREFLIGHT</div>
              <div style={{ fontFamily: "'DM Mono'", fontSize: 10, letterSpacing: '0.35em', color: '#4d6a88', marginTop: 4 }}>PHYSICAL IDE — ASSEMBLY VERIFIER</div>
            </div>
          </div>

          {/* Divider */}
          <div className="boot-in-2" style={{ width: '100%', height: 1, background: 'linear-gradient(90deg, transparent, #1e3248, transparent)' }} />

          {/* Description */}
          <p className="boot-in-2" style={{ fontFamily: "'DM Mono'", fontSize: 11, color: '#4d6a88', lineHeight: 1.8, letterSpacing: '0.04em' }}>
            Real-time hardware assembly verification.<br/>
            Point your camera at the breadboard — the agent<br/>
            watches, speaks, and catches wiring errors live.
          </p>

          {/* CTA */}
          <button
            onClick={() => setStarted(true)}
            className="boot-in-3"
            style={{
              fontFamily: "'Chakra Petch'",
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: '0.3em',
              padding: '14px 40px',
              background: '#f97316',
              color: '#060c16',
              border: 'none',
              borderRadius: 1,
              cursor: 'pointer',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            INITIALIZE SESSION
          </button>

          <p className="boot-in-4" style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#243344', letterSpacing: '0.1em' }}>
            grants camera access · connects to gemini live api · enables audio
          </p>
        </div>
      </div>
    );
  }

  /* ─── Main View ────────────────────────────────────────────────────────── */
  return (
    <div className="h-full flex flex-col" style={{ background: '#060c16', padding: '10px 12px', gap: 10 }}>

      <ChatPanel
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        sendMessage={sendTutorialGoal}
        tutorialState={tutorialState}
      />

      {/* ── Top bar ── */}
      <header style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0, paddingBottom: 10, borderBottom: '1px solid #132030' }}>
        <Logo />

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Step counter */}
          <div style={{ fontFamily: "'DM Mono'", fontSize: 10, color: '#4d6a88', letterSpacing: '0.1em' }}>
            {socket.currentStep > TOTAL_STEPS
              ? <span style={{ color: '#10e8a0' }}>BUILD COMPLETE</span>
              : <span>STEP <span style={{ color: '#c8ddf0' }}>{Math.min(socket.currentStep, TOTAL_STEPS)}</span> / {TOTAL_STEPS}</span>
            }
          </div>

          {/* Status badge */}
          <StatusBadge status={socket.status} />

          {/* Connection */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: "'DM Mono'", fontSize: 9, letterSpacing: '0.15em' }}>
            <span
              className={socket.connected ? 'pulse-dot' : ''}
              style={{ display: 'block', width: 6, height: 6, borderRadius: '50%', background: socket.connected ? '#10e8a0' : '#ff4455' }}
            />
            <span style={{ color: socket.connected ? '#10e8a0' : '#ff4455' }}>
              {socket.connected ? 'AGENT ONLINE' : 'OFFLINE'}
            </span>
          </div>

          {/* Circuit planner button */}
          <button
            onClick={() => setChatOpen(o => !o)}
            title="Circuit Planner"
            style={{
              fontFamily: "'Chakra Petch'",
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: '0.2em',
              padding: '5px 12px',
              background: chatOpen ? 'rgba(249,115,22,0.15)' : 'transparent',
              color: '#f97316',
              border: '1px solid rgba(249,115,22,0.3)',
              borderRadius: 1,
              cursor: 'pointer',
            }}
          >
            ⚡ PLANNER
          </button>
        </div>
      </header>

      {/* ── Three-panel body ── */}
      <div style={{ flex: 1, display: 'flex', gap: 0, minHeight: 0 }}>

        {/* 01 / LIVE FEED */}
        <div className="panel-card" style={{ width: videoWidth, flexShrink: 0, display: 'flex', flexDirection: 'column', padding: '14px 14px 10px', minHeight: 0 }}>
          <PanelLabel num="01" title="LIVE FEED">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: "'DM Mono'", fontSize: 9, letterSpacing: '0.12em' }}>
              <span
                className={handsInFrame ? 'pulse-dot' : ''}
                style={{ display: 'block', width: 5, height: 5, borderRadius: '50%', background: handsInFrame ? '#f59e0b' : '#10e8a0' }}
              />
              <span style={{ color: handsInFrame ? '#f59e0b' : '#10e8a0' }}>
                {handsInFrame ? 'HANDS IN FRAME' : 'CLEAR'}
              </span>
            </div>
          </PanelLabel>

          {/* Camera feed */}
          <div style={{ flex: 1, position: 'relative', borderRadius: 2, overflow: 'hidden', background: '#000', border: '1px solid #132030', minHeight: 0 }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
            <ScanOverlay active={socket.scanning} />

            {webcamError && (
              <div style={{ position: 'absolute', bottom: 8, left: 8, right: 8, padding: '4px 8px', background: 'rgba(255,68,85,0.85)', fontFamily: "'DM Mono'", fontSize: 9, color: '#fff', borderRadius: 1 }}>
                {webcamError}
              </div>
            )}
          </div>

          {/* Controls */}
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button
              onClick={forceCapture}
              disabled={!socket.connected || socket.scanning}
              style={{
                fontFamily: "'Chakra Petch'",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.25em',
                padding: '9px 0',
                width: '100%',
                background: socket.scanning ? 'rgba(249,115,22,0.1)' : '#f97316',
                color: socket.scanning ? '#f97316' : '#060c16',
                border: socket.scanning ? '1px solid rgba(249,115,22,0.4)' : 'none',
                borderRadius: 1,
                cursor: socket.connected && !socket.scanning ? 'pointer' : 'not-allowed',
                opacity: !socket.connected ? 0.35 : 1,
              }}
            >
              {socket.scanning ? 'SCANNING...' : 'FORCE CAPTURE'}
            </button>
            <div style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#243344', letterSpacing: '0.06em', textAlign: 'center' }}>
              {trackerReady ? 'remove hands from frame to trigger scan' : 'loading hand-tracking model...'}
            </div>
          </div>
        </div>

        {/* Drag handle */}
        <div
          onMouseDown={onDragMouseDown}
          style={{ width: 16, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'col-resize' }}
          className="group"
        >
          <div style={{ width: 1, height: '100%', background: '#132030', transition: 'background 0.15s' }}
               onMouseEnter={e => e.target.style.background = '#f97316'}
               onMouseLeave={e => e.target.style.background = '#132030'}
          />
        </div>

        {/* 02 / INSTRUCTION */}
        <div className="panel-card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '14px 14px 14px', minHeight: 0, minWidth: 0 }}>
          <PanelLabel num="02" title="INSTRUCTION" />
          <div style={{ flex: 1, minHeight: 0 }}>
            <InstructionCard
              image={socket.instructionImage}
              text={socket.instructionText}
              citation={socket.citation}
              step={socket.currentStep}
              total={TOTAL_STEPS}
              status={socket.status}
            />
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: 16, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: 1, height: '100%', background: '#132030' }} />
        </div>

        {/* 03 / AGENT LOG */}
        <div className="panel-card" style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', padding: '14px 14px 14px', minHeight: 0 }}>
          <PanelLabel num="03" title="AGENT LOG" />
          <div style={{ flex: 1, minHeight: 0 }}>
            <AgentLog log={socket.log} />
          </div>
        </div>

      </div>
    </div>
  );
}
