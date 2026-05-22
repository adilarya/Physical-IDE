import { useEffect, useRef, useState, useCallback } from 'react';
import { useMockAgentSocket } from './useMockAgentSocket';

// Single env-var swap to point at Cloud Run - see frontend/.env.example.
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws/agent';
const CIRCUIT_ID = 'servo_control';

// VITE_MOCK_SOCKET=true → play the scripted beat in-browser, no backend needed.
// Athif: add this to frontend/.env to work without the backend running.
export function useAgentSocket(enabled) {
  const mockMode = import.meta.env.VITE_MOCK_SOCKET === 'true';
  const mock = useMockAgentSocket(mockMode && enabled);
  const real = useRealAgentSocket(!mockMode && enabled);
  return mockMode ? mock : real;
}

// The original implementation is renamed to useRealAgentSocket below.
// Nothing else in the codebase needs to change.

// If the backend never answers a frame, drop the scan overlay anyway.
const SCAN_TIMEOUT_MS = 35000;

/**
 * useAgentSocket(enabled)
 *  - connects on enable, sends start_session, auto-reconnects
 *  - sendFrame(imageB64): uploads a frame_eval for the current step
 *  - downstream payloads: drive instruction state, append log, auto-play audio
 */
function useRealAgentSocket(enabled) {
  const [connected, setConnected] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [status, setStatus] = useState('idle');
  const [currentStep, setCurrentStep] = useState(1);
  const [instructionText, setInstructionText] = useState('Waiting for session...');
  const [instructionImage, setInstructionImage] = useState(null);
  const [citation, setCitation] = useState('');
  const [log, setLog] = useState([]);
  const [tutorialEvent, setTutorialEvent] = useState(null);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const scanTimerRef = useRef(null);
  const stepRef = useRef(1); // mirror so sendFrame always reads the latest step

  useEffect(() => {
    stepRef.current = currentStep;
  }, [currentStep]);

  const appendLog = useCallback((line, kind = 'agent') => {
    setLog((prev) => [...prev, { t: Date.now(), line, kind }].slice(-120));
  }, []);

  // ----- audio (Web Audio API) ---------------------------------------------
  function ensureAudioCtx() {
    if (!audioCtxRef.current) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      audioCtxRef.current = new Ctx();
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }

  async function playAudio(b64) {
    if (!b64) return;
    try {
      const ctx = ensureAudioCtx();
      const clean = b64.includes(',') ? b64.split(',')[1] : b64;
      const bytes = Uint8Array.from(atob(clean), (c) => c.charCodeAt(0));
      const buffer = await ctx.decodeAudioData(bytes.buffer);
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(ctx.destination);
      src.start();
    } catch (e) {
      console.warn('[useAgentSocket] audio playback failed', e);
    }
  }

  // ----- downstream payload handling ---------------------------------------
  function handlePayload(msg) {
    if (scanTimerRef.current) {
      clearTimeout(scanTimerRef.current);
      scanTimerRef.current = null;
    }
    setScanning(false);

    if (msg.status) setStatus(msg.status);
    if (typeof msg.current_step === 'number') setCurrentStep(msg.current_step);
    if (msg.text) setInstructionText(msg.text);
    if (msg.image_b64) setInstructionImage(msg.image_b64);
    setCitation(msg.citation || '');

    if (msg.agent_log) {
      const kind = msg.status && msg.status.startsWith('error') ? 'error' : 'agent';
      appendLog(msg.agent_log, kind);
    }
    playAudio(msg.audio_b64);
  }

  // ----- connection lifecycle ----------------------------------------------
  useEffect(() => {
    if (!enabled) return;
    ensureAudioCtx(); // created inside the user gesture that set enabled=true

    let ws = null;
    let retryTimer = null;
    let closedByUs = false;

    function connect() {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        appendLog('socket connected -> ' + WS_URL, 'sys');
        ws.send(
          JSON.stringify({
            event: 'start_session',
            circuit_id: CIRCUIT_ID,
            user_constraints: [],
          })
        );
      };

      ws.onmessage = (ev) => {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        // Tutorial events are handled separately from the main payload
        if (msg.event && msg.event.startsWith('tutorial_')) {
          setTutorialEvent({ ...msg, _ts: Date.now() });
          return;
        }
        handlePayload(msg);
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs) {
          appendLog('socket closed - retrying in 2s', 'sys');
          retryTimer = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => appendLog('socket error', 'sys');
    }

    connect();

    return () => {
      closedByUs = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (scanTimerRef.current) clearTimeout(scanTimerRef.current);
      if (ws) ws.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // ----- upstream: send tutorial goal -------------------------------------
  const sendTutorial = useCallback((goal) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ event: 'generate_tutorial', goal }));
  }, []);

  // ----- upstream: send a captured frame -----------------------------------
  const sendFrame = useCallback(
    (imageB64) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        appendLog('cannot send frame - socket not open', 'sys');
        return;
      }
      setScanning(true);
      appendLog(`frame captured -> evaluating step ${stepRef.current}`, 'sys');

      ws.send(
        JSON.stringify({
          event: 'frame_eval',
          image_b64: imageB64,
          current_step: stepRef.current,
          circuit_id: CIRCUIT_ID,
        })
      );

      if (scanTimerRef.current) clearTimeout(scanTimerRef.current);
      scanTimerRef.current = setTimeout(() => {
        scanTimerRef.current = null;
        setScanning(false);
        appendLog('scan timed out - no response from agent', 'sys');
      }, SCAN_TIMEOUT_MS);
    },
    [appendLog]
  );

  return {
    connected,
    scanning,
    status,
    currentStep,
    instructionText,
    instructionImage,
    citation,
    log,
    sendFrame,
    sendTutorial,
    tutorialEvent,
  };
}
