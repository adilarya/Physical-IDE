import { useState, useRef, useCallback, useEffect } from 'react';
import { useWebcam } from './hooks/useWebcam';
import { useHandTracker } from './hooks/useHandTracker';
import { useAgentSocket } from './hooks/useAgentSocket';
import ScanOverlay from './components/ScanOverlay';
import InstructionCard from './components/InstructionCard';
import AgentLog from './components/AgentLog';
import ChatPanel from './components/ChatPanel';

const TOTAL_STEPS = 3;

/* ─── Logo ─────────────────────────────────────────────── */
function Logo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <rect x="0.6" y="0.6" width="20.8" height="20.8" stroke="#f97316" strokeWidth="1.2" strokeOpacity="0.35"/>
        <rect x="6" y="6" width="10" height="10" transform="rotate(45 11 11)" fill="none" stroke="#f97316" strokeWidth="1.2"/>
        <circle cx="11" cy="11" r="2" fill="#f97316" className="logo-dot"/>
        <line x1="0" y1="5.5" x2="4" y2="5.5" stroke="#f97316" strokeWidth="0.8" strokeOpacity="0.5"/>
        <line x1="18" y1="16.5" x2="22" y2="16.5" stroke="#f97316" strokeWidth="0.8" strokeOpacity="0.5"/>
      </svg>
      <div>
        <div style={{ fontFamily: "'Chakra Petch'", fontSize: 11, fontWeight: 700, letterSpacing: '0.22em', color: '#e2eeff', lineHeight: 1 }}>THE PHYSICAL IDE</div>
        <div style={{ fontFamily: "'DM Mono'", fontSize: 7.5, letterSpacing: '0.25em', color: '#2d4a6a', marginTop: 2 }}>ASSEMBLY VERIFIER</div>
      </div>
    </div>
  );
}

/* ─── Status label ──────────────────────────────────────── */
const STATUS_MAP = {
  session_init:          ['READY',          '#2d4a6a'],
  success_advance:       ['VERIFIED ✓',     '#10e8a0'],
  error_short_circuit:   ['DANGER',         '#ff4455'],
  error_occluded:        ['BLOCKED',        '#f59e0b'],
  error_wrong_placement: ['WRONG PLACEMENT','#f59e0b'],
  idle:                  ['STANDBY',        '#1e3248'],
};

/* ─── Main ──────────────────────────────────────────────── */
export default function App() {
  const [started, setStarted] = useState(false);
  const [videoWidth, setVideoWidth] = useState(340);
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

  const sendTutorialGoal = useCallback((goal) => {
    setTutorialState({ loading: true, thinking: '', goal, steps: [], totalSteps: 0, complete: false, error: '' });
    socket.sendTutorial(goal);
  }, [socket]);

  useEffect(() => {
    const ev = socket.tutorialEvent;
    if (!ev) return;
    if (ev.event === 'tutorial_thinking') setTutorialState(p => ({ ...p, thinking: ev.text }));
    else if (ev.event === 'tutorial_start') setTutorialState(p => ({ ...p, thinking: '', totalSteps: ev.total_steps, goal: ev.goal }));
    else if (ev.event === 'tutorial_step') setTutorialState(p => ({ ...p, steps: [...p.steps, ev] }));
    else if (ev.event === 'tutorial_complete') setTutorialState(p => ({ ...p, loading: false, complete: true, thinking: '' }));
    else if (ev.event === 'tutorial_error') setTutorialState(p => ({ ...p, loading: false, error: ev.text, thinking: '' }));
  }, [socket.tutorialEvent]);

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
      setVideoWidth(Math.min(Math.max(dragStartWidth.current + e.clientX - dragStartX.current, 200), 680));
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

  /* ── Start screen ── */
  if (!started) {
    return (
      <div style={{ height: '100%', display: 'flex', background: '#060c16', position: 'relative', overflow: 'hidden' }}>
        {/* Left orange bar */}
        <div style={{ width: 3, background: 'linear-gradient(180deg, transparent, #f97316 30%, #f97316 70%, transparent)', flexShrink: 0 }} />

        {/* Left info column */}
        <div style={{ width: 320, flexShrink: 0, padding: '48px 40px', display: 'flex', flexDirection: 'column', justifyContent: 'center', borderRight: '1px solid #0f1f30' }}>
          <Logo />
          <div style={{ marginTop: 48 }}>
            <div style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#1e3248', letterSpacing: '0.2em', marginBottom: 16 }}>01 / SYSTEM</div>
            <div style={{ fontFamily: "'Chakra Petch'", fontSize: 22, fontWeight: 700, color: '#e2eeff', lineHeight: 1.3, letterSpacing: '0.04em' }}>
              Real-time<br/>hardware assembly<br/>verification.
            </div>
          </div>
          <div style={{ marginTop: 40, fontFamily: "'DM Mono'", fontSize: 10, color: '#2d4a6a', lineHeight: 2, letterSpacing: '0.04em' }}>
            — Gemini Live API vision<br/>
            — spoken verdict + audio<br/>
            — wire color safety rules<br/>
            — lego-style circuit guides
          </div>
        </div>

        {/* Right: large boot area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 40, padding: 60 }}>
          {/* Big logo mark */}
          <svg width="120" height="120" viewBox="0 0 22 22" fill="none" className="boot-in">
            <rect x="0.6" y="0.6" width="20.8" height="20.8" stroke="#f97316" strokeWidth="0.6" strokeOpacity="0.25"/>
            <rect x="6" y="6" width="10" height="10" transform="rotate(45 11 11)" fill="none" stroke="#f97316" strokeWidth="0.8"/>
            <circle cx="11" cy="11" r="2" fill="#f97316" className="logo-dot"/>
            <line x1="0" y1="5.5" x2="4" y2="5.5" stroke="#f97316" strokeWidth="0.6" strokeOpacity="0.5"/>
            <line x1="18" y1="16.5" x2="22" y2="16.5" stroke="#f97316" strokeWidth="0.6" strokeOpacity="0.5"/>
            <line x1="5.5" y1="0" x2="5.5" y2="4" stroke="#f97316" strokeWidth="0.6" strokeOpacity="0.5"/>
            <line x1="16.5" y1="18" x2="16.5" y2="22" stroke="#f97316" strokeWidth="0.6" strokeOpacity="0.5"/>
          </svg>

          <div className="boot-in-2" style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#1e3248', letterSpacing: '0.25em', marginBottom: 12 }}>GOOGLE I/O 2026</div>
            <div style={{ fontFamily: "'Chakra Petch'", fontSize: 11, color: '#2d4a6a', letterSpacing: '0.2em' }}>
              THE PHYSICAL IDE · GEMINI LIVE · AUDIO
            </div>
          </div>

          <button
            onClick={() => setStarted(true)}
            className="boot-in-3"
            style={{
              fontFamily: "'Chakra Petch'",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.35em',
              padding: '16px 52px',
              background: '#f97316',
              color: '#060c16',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            INITIALIZE SESSION
          </button>
        </div>

        {/* Bottom bar */}
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, #f97316, transparent 60%)' }} />
      </div>
    );
  }

  /* ── Main view ── */
  const [statusLabel, statusColor] = STATUS_MAP[socket.status] || STATUS_MAP.idle;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#060c16' }}>
      <ChatPanel isOpen={chatOpen} onClose={() => setChatOpen(false)} sendMessage={sendTutorialGoal} tutorialState={tutorialState} />

      {/* ── Header ── */}
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', borderBottom: '1px solid #0f1f30', gap: 20 }}>
        {/* Orange left tick */}
        <div style={{ width: 3, height: 20, background: '#f97316', flexShrink: 0 }} />
        <Logo />

        {/* Divider */}
        <div style={{ width: 1, height: 20, background: '#0f1f30', flexShrink: 0 }} />

        {/* Step */}
        <div style={{ fontFamily: "'DM Mono'", fontSize: 9, color: '#1e3248', letterSpacing: '0.12em' }}>
          {socket.currentStep > TOTAL_STEPS
            ? <span style={{ color: '#10e8a0' }}>COMPLETE</span>
            : <>STEP <span style={{ color: '#c8ddf0' }}>{Math.min(socket.currentStep, TOTAL_STEPS)}</span>/{TOTAL_STEPS}</>}
        </div>

        {/* Status */}
        <div style={{ fontFamily: "'Chakra Petch'", fontSize: 9, fontWeight: 600, letterSpacing: '0.2em', color: statusColor }}>
          {statusLabel}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Connection */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: "'DM Mono'", fontSize: 8, letterSpacing: '0.12em', color: socket.connected ? '#10e8a0' : '#ff4455' }}>
            <span className={socket.connected ? 'pulse-dot' : ''} style={{ display: 'block', width: 5, height: 5, borderRadius: '50%', background: socket.connected ? '#10e8a0' : '#ff4455' }} />
            {socket.connected ? 'LIVE' : 'OFFLINE'}
          </div>

          {/* Planner toggle */}
          <button
            onClick={() => setChatOpen(o => !o)}
            style={{
              fontFamily: "'Chakra Petch'",
              fontSize: 8,
              fontWeight: 600,
              letterSpacing: '0.25em',
              padding: '5px 14px',
              background: chatOpen ? '#f97316' : 'transparent',
              color: chatOpen ? '#060c16' : '#f97316',
              border: '1px solid rgba(249,115,22,0.4)',
              cursor: 'pointer',
            }}
          >
            ⚡ PLANNER
          </button>
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

        {/* 01 LIVE FEED */}
        <div style={{ width: videoWidth, flexShrink: 0, display: 'flex', flexDirection: 'column', borderRight: '1px solid #0f1f30' }}>
          {/* Panel label bar */}
          <div style={{ height: 32, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 10, borderBottom: '1px solid #0f1f30', background: '#07101a' }}>
            <span style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#f97316', letterSpacing: '0.15em', opacity: 0.6 }}>01</span>
            <span style={{ fontFamily: "'Chakra Petch'", fontSize: 8, fontWeight: 500, letterSpacing: '0.3em', color: '#1e3248' }}>LIVE FEED</span>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 5 }}>
              <span className={handsInFrame ? 'pulse-dot' : ''} style={{ display: 'block', width: 4, height: 4, borderRadius: '50%', background: handsInFrame ? '#f59e0b' : '#10e8a0' }} />
              <span style={{ fontFamily: "'DM Mono'", fontSize: 7, color: handsInFrame ? '#f59e0b' : '#10e8a0', letterSpacing: '0.1em' }}>
                {handsInFrame ? 'HANDS' : 'CLEAR'}
              </span>
            </div>
          </div>

          {/* Camera — raw, no card */}
          <div style={{ flex: 1, position: 'relative', background: '#000', overflow: 'hidden', minHeight: 0 }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
            <ScanOverlay active={socket.scanning} />
            {webcamError && (
              <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '6px 10px', background: 'rgba(255,68,85,0.9)', fontFamily: "'DM Mono'", fontSize: 8, color: '#fff' }}>
                {webcamError}
              </div>
            )}
          </div>

          {/* Capture controls */}
          <div style={{ flexShrink: 0, padding: '10px 14px', borderTop: '1px solid #0f1f30', background: '#07101a', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button
              onClick={forceCapture}
              disabled={!socket.connected || socket.scanning}
              style={{
                fontFamily: "'Chakra Petch'",
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: '0.3em',
                padding: '10px 0',
                width: '100%',
                background: socket.scanning ? 'transparent' : '#f97316',
                color: socket.scanning ? '#f97316' : '#060c16',
                border: socket.scanning ? '1px solid rgba(249,115,22,0.3)' : 'none',
                cursor: socket.connected && !socket.scanning ? 'pointer' : 'not-allowed',
                opacity: !socket.connected ? 0.3 : 1,
              }}
            >
              {socket.scanning ? 'SCANNING...' : 'FORCE CAPTURE'}
            </button>
            <div style={{ fontFamily: "'DM Mono'", fontSize: 7.5, color: '#1e3248', textAlign: 'center', letterSpacing: '0.05em' }}>
              {trackerReady ? 'remove hands to trigger scan' : 'loading hand tracker...'}
            </div>
          </div>
        </div>

        {/* Drag handle */}
        <div
          onMouseDown={onDragMouseDown}
          style={{ width: 4, flexShrink: 0, cursor: 'col-resize', background: '#07101a', position: 'relative' }}
        >
          <div
            style={{ position: 'absolute', inset: 0, transition: 'background 0.15s' }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(249,115,22,0.2)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          />
        </div>

        {/* 02 INSTRUCTION */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, borderRight: '1px solid #0f1f30' }}>
          <div style={{ height: 32, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 20px', gap: 10, borderBottom: '1px solid #0f1f30', background: '#07101a' }}>
            <span style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#f97316', letterSpacing: '0.15em', opacity: 0.6 }}>02</span>
            <span style={{ fontFamily: "'Chakra Petch'", fontSize: 8, fontWeight: 500, letterSpacing: '0.3em', color: '#1e3248' }}>INSTRUCTION</span>
          </div>
          <div style={{ flex: 1, padding: '16px 20px', minHeight: 0 }}>
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

        {/* 03 AGENT LOG */}
        <div style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: 32, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 10, borderBottom: '1px solid #0f1f30', background: '#07101a' }}>
            <span style={{ fontFamily: "'DM Mono'", fontSize: 8, color: '#f97316', letterSpacing: '0.15em', opacity: 0.6 }}>03</span>
            <span style={{ fontFamily: "'Chakra Petch'", fontSize: 8, fontWeight: 500, letterSpacing: '0.3em', color: '#1e3248' }}>AGENT LOG</span>
            <span style={{ marginLeft: 'auto', fontFamily: "'DM Mono'", fontSize: 7, color: '#1e3248' }}>{socket.log.length} EVT</span>
          </div>
          <div style={{ flex: 1, padding: '10px 14px', minHeight: 0 }}>
            <AgentLog log={socket.log} />
          </div>
        </div>

      </div>

      {/* ── Bottom status bar ── */}
      <div style={{ height: 24, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 16px', gap: 20, borderTop: '1px solid #0f1f30', background: '#07101a' }}>
        <div style={{ fontFamily: "'DM Mono'", fontSize: 7.5, color: '#1e3248', letterSpacing: '0.12em' }}>
          GEMINI LIVE API · gemini-3.1-flash-live-preview · CLOUD RUN GEN2
        </div>
        <div style={{ marginLeft: 'auto', fontFamily: "'DM Mono'", fontSize: 7.5, color: '#1e3248', letterSpacing: '0.1em' }}>
          GOOGLE I/O 2026
        </div>
      </div>
    </div>
  );
}
