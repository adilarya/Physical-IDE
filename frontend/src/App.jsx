import { useState, useRef, useCallback, useEffect } from 'react';
import { useWebcam } from './hooks/useWebcam';
import { useHandTracker } from './hooks/useHandTracker';
import { useAgentSocket } from './hooks/useAgentSocket';
import ScanOverlay from './components/ScanOverlay';
import InstructionCard from './components/InstructionCard';
import AgentLog from './components/AgentLog';
import ChatPanel from './components/ChatPanel';

const TOTAL_STEPS = 3;

export default function App() {
  // `started` gates the camera/socket/audio behind a real user gesture
  // (required for getUserMedia + AudioContext autoplay policies).
  const [started, setStarted] = useState(false);
  const [videoWidth, setVideoWidth] = useState(380);
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

  // Tutorial: send goal to backend and handle streaming steps
  const sendTutorialGoal = useCallback((goal) => {
    setTutorialState({ loading: true, thinking: '', goal, steps: [], totalSteps: 0, complete: false, error: '' });
    socket.sendTutorial(goal);
  }, [socket]);

  // Handle tutorial events streamed from the backend
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

  // Drag-to-resize the video panel
  const onDragHandleMouseDown = useCallback((e) => {
    dragging.current = true;
    dragStartX.current = e.clientX;
    dragStartWidth.current = videoWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [videoWidth]);

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!dragging.current) return;
      const delta = e.clientX - dragStartX.current;
      const next = Math.min(Math.max(dragStartWidth.current + delta, 220), 720);
      setVideoWidth(next);
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  if (!started) {
    return <StartScreen onStart={() => setStarted(true)} />;
  }

  return (
    <div className="h-full flex flex-col p-4 gap-4">
      <ChatPanel
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        sendMessage={sendTutorialGoal}
        tutorialState={tutorialState}
      />

      {/* Chat icon — bottom right */}
      <button
        onClick={() => setChatOpen(o => !o)}
        title="Circuit Planner"
        className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-orange-500 hover:bg-orange-400 shadow-lg flex items-center justify-center text-slate-950 text-xl transition-transform hover:scale-110"
      >
        ⚡
      </button>

      <Header
        connected={socket.connected}
        step={socket.currentStep}
        total={TOTAL_STEPS}
        status={socket.status}
      />

      <div className="flex-1 flex gap-0 min-h-0">
        {/* LEFT - live webcam feed + Deep-Scan overlay */}
        <section className="flex flex-col gap-3 min-h-0 shrink-0" style={{ width: videoWidth }}>
          <span className="font-mono text-xs tracking-widest text-slate-400">
            LIVE FEED
          </span>
          <div className="relative flex-1 rounded-xl overflow-hidden border border-slate-800 bg-black">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />
            <ScanOverlay active={socket.scanning} />

            <div className="absolute top-3 left-3 flex items-center gap-2 px-2 py-1 rounded bg-slate-950/80 font-mono text-xs">
              <span
                className={
                  'w-2 h-2 rounded-full ' +
                  (handsInFrame ? 'bg-amber-400 pulse-dot' : 'bg-emerald-400')
                }
              />
              {handsInFrame ? 'HANDS IN FRAME' : 'FRAME CLEAR'}
            </div>

            {webcamError && (
              <div className="absolute bottom-3 left-3 right-3 px-2 py-1 rounded bg-red-500/80 font-mono text-xs">
                camera: {webcamError} - using placeholder frames
              </div>
            )}
          </div>

          <button
            onClick={forceCapture}
            disabled={!socket.connected || socket.scanning}
            className="w-full py-2 rounded-lg bg-orange-500 hover:bg-orange-400 disabled:opacity-40 disabled:cursor-not-allowed font-mono text-xs tracking-[0.2em] font-bold text-slate-950"
          >
            FORCE CAPTURE
          </button>

          <p className="font-mono text-[10px] text-slate-600">
            {trackerReady
              ? 'hand-tracking active - pull hands out of frame to trigger a scan'
              : 'loading hand-tracking model...'}
          </p>
        </section>

        {/* DRAG HANDLE */}
        <div
          onMouseDown={onDragHandleMouseDown}
          className="w-2 mx-2 shrink-0 flex items-center justify-center cursor-col-resize group"
        >
          <div className="w-px h-full bg-slate-700 group-hover:bg-orange-500 transition-colors" />
        </div>

        {/* CENTER - current instruction */}
        <section className="flex-1 rounded-xl border border-slate-800 bg-slate-900/40 p-4 min-h-0 min-w-0">
          <InstructionCard
            image={socket.instructionImage}
            text={socket.instructionText}
            citation={socket.citation}
            step={socket.currentStep}
            total={TOTAL_STEPS}
            status={socket.status}
          />
        </section>

        {/* DRAG HANDLE */}
        <div
          className="w-2 mx-2 shrink-0 flex items-center justify-center cursor-col-resize group"
        >
          <div className="w-px h-full bg-slate-700" />
        </div>

        {/* RIGHT - agent log */}
        <section className="w-72 shrink-0 rounded-xl border border-slate-800 bg-slate-900/40 p-4 min-h-0">
          <AgentLog log={socket.log} />
        </section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

const STATUS_META = {
  session_init: ['SESSION READY', 'bg-sky-500/20 text-sky-300'],
  success_advance: ['STEP VERIFIED', 'bg-emerald-500/20 text-emerald-300'],
  error_short_circuit: ['SHORT CIRCUIT', 'bg-red-500/25 text-red-300'],
  error_occluded: ['VIEW BLOCKED', 'bg-amber-500/20 text-amber-300'],
  error_wrong_placement: ['WRONG PLACEMENT', 'bg-amber-500/20 text-amber-300'],
  idle: ['STANDBY', 'bg-slate-700/40 text-slate-400'],
};

function StatusPill({ status }) {
  const [label, cls] = STATUS_META[status] || STATUS_META.idle;
  return <span className={'px-2 py-1 rounded ' + cls}>{label}</span>;
}

function Header({ connected, step, total, status }) {
  const complete = step > total;
  return (
    <header className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-orange-500 flex items-center justify-center font-black text-slate-950">
          PI
        </div>
        <div>
          <h1 className="font-mono text-sm tracking-[0.35em] text-slate-100">
            THE PHYSICAL IDE
          </h1>
          <p className="font-mono text-[10px] tracking-[0.25em] text-slate-500">
            DYNAMIC SCHEMATIC MENTOR
          </p>
        </div>
      </div>

      <div className="flex items-center gap-5 font-mono text-xs">
        <span className="text-slate-400">
          {complete ? 'BUILD COMPLETE' : `STEP ${Math.min(step, total)} / ${total}`}
        </span>
        <StatusPill status={status} />
        <span className="flex items-center gap-2">
          <span
            className={
              'w-2 h-2 rounded-full ' +
              (connected ? 'bg-emerald-400 pulse-dot' : 'bg-red-500')
            }
          />
          {connected ? 'AGENT ONLINE' : 'OFFLINE'}
        </span>
      </div>
    </header>
  );
}

function StartScreen({ onStart }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-8 p-8 text-center">
      <div>
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-orange-500 flex items-center justify-center font-black text-2xl text-slate-950">
          PI
        </div>
        <h1 className="font-mono text-2xl tracking-[0.35em] text-slate-100">
          THE PHYSICAL IDE
        </h1>
        <p className="font-mono text-xs tracking-[0.3em] text-orange-400 mt-2">
          DEEP-SCAN ASSEMBLY MENTOR
        </p>
      </div>

      <p className="max-w-md text-sm text-slate-400 leading-relaxed">
        Build the Temperature Alarm circuit under your webcam. Take your hands
        out of frame after each step - the agent scans the board, verifies your
        wiring, and narrates the next move.
      </p>

      <button
        onClick={onStart}
        className="px-8 py-4 rounded-xl bg-orange-500 hover:bg-orange-400 font-mono text-sm tracking-[0.25em] font-bold text-slate-950"
      >
        INITIALIZE SESSION
      </button>

      <p className="font-mono text-[10px] text-slate-600">
        grants camera access · connects to agent socket · enables audio
      </p>
    </div>
  );
}
