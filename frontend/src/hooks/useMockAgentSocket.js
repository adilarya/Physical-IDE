/**
 * useMockAgentSocket — zero-backend drop-in for useAgentSocket.
 *
 * Plays the scripted demo beat entirely in-browser:
 *   session_init  -> Step 1 instruction
 *   sendFrame()   step 1 -> success_advance -> Step 2
 *   sendFrame()   step 2 first call -> error_short_circuit (correction)
 *   sendFrame()   step 2 retry      -> success_advance    -> Step 3
 *   sendFrame()   step 3 -> success_advance -> build complete
 *
 * Enable by adding  VITE_MOCK_SOCKET=true  to frontend/.env
 * The exported hook signature is identical to useAgentSocket so App.jsx
 * needs no changes.
 */
import { useState, useRef, useCallback, useEffect } from 'react';

const RESPONSE_DELAY_MS = 900;

const STEPS = {
  1: {
    text: 'Step 1 of 3 — Power rail. Take a red jumper wire and connect the Arduino\'s 5V pin to the positive (+) rail on the breadboard.',
    citation: 'Arduino Uno R3 - power pins reference, p.2',
    agent_log: '[Planner] Generated Step 1 (power rail). Mock mode.',
  },
  2: {
    text: 'Step 2 of 3 — The LED. Place the LED across the center gap. Longer leg (anode) in row 10, shorter leg (cathode) in row 11.',
    citation: 'LED polarity guide - anode vs cathode, p.1',
    agent_log: '[Planner] Generated Step 2 (LED placement). Mock mode.',
  },
  3: {
    text: 'Step 3 of 3 — Current-limiting resistor. Bridge a 220-ohm resistor from row 11 to the blue ground rail.',
    citation: 'Resistor color codes - 220 ohm band reference, p.4',
    agent_log: '[Planner] Generated Step 3 (220 ohm resistor). Mock mode.',
  },
  done: {
    text: 'Assembly complete. All three steps verified — your temperature alarm circuit is wired correctly. Power the Arduino to test it.',
    citation: '',
    agent_log: '[Planner] Build complete. 3/3 steps verified. Mock mode.',
  },
};

const SHORT_CIRCUIT_CORRECTION = {
  text: 'SAFETY STOP. The LED legs are bridging the positive rail directly — that is a short circuit and will damage the component. Pull the short leg (cathode) out of the positive rail and move it to row 11.',
  citation: '',
  agent_log: '[Watcher] SHORT CIRCUIT on +5V rail. [Planner] SAFETY INTERRUPT — correction issued.',
};

export function useMockAgentSocket(enabled) {
  const [connected, setConnected]           = useState(false);
  const [scanning, setScanning]             = useState(false);
  const [status, setStatus]                 = useState('idle');
  const [currentStep, setCurrentStep]       = useState(1);
  const [instructionText, setInstructionText] = useState('Waiting for session...');
  const [instructionImage, setInstructionImage] = useState(null);
  const [citation, setCitation]             = useState('');
  const [log, setLog]                       = useState([]);

  const stepRef      = useRef(1);
  const attemptsRef  = useRef({});

  useEffect(() => { stepRef.current = currentStep; }, [currentStep]);

  const appendLog = useCallback((line, kind = 'agent') => {
    setLog(prev => [...prev, { t: Date.now(), line, kind }].slice(-120));
  }, []);

  function applyStep(stepKey, statusVal) {
    const s = STEPS[stepKey] || STEPS.done;
    setStatus(statusVal);
    setInstructionText(s.text);
    setCitation(s.citation);
    if (typeof stepKey === 'number') setCurrentStep(stepKey);
    appendLog(s.agent_log);
  }

  useEffect(() => {
    if (!enabled) return;
    attemptsRef.current = {};

    const t = setTimeout(() => {
      setConnected(true);
      appendLog('mock socket connected (no backend needed)', 'sys');
      applyStep(1, 'session_init');
    }, 500);

    return () => {
      clearTimeout(t);
      setConnected(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  const sendFrame = useCallback((imageB64) => {
    const step = stepRef.current;
    setScanning(true);
    appendLog(`frame captured -> evaluating step ${step}`, 'sys');

    setTimeout(() => {
      setScanning(false);
      attemptsRef.current[step] = (attemptsRef.current[step] || 0) + 1;
      const attempt = attemptsRef.current[step];

      // Scripted beat: step 2 first attempt always short-circuits.
      if (step === 2 && attempt === 1) {
        setStatus('error_short_circuit');
        setInstructionText(SHORT_CIRCUIT_CORRECTION.text);
        setCitation(SHORT_CIRCUIT_CORRECTION.citation);
        appendLog(SHORT_CIRCUIT_CORRECTION.agent_log, 'error');
        return;
      }

      const nextStep = step + 1;
      if (nextStep > 3) {
        applyStep('done', 'success_advance');
        setCurrentStep(4);
      } else {
        applyStep(nextStep, 'success_advance');
      }
    }, RESPONSE_DELAY_MS);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appendLog]);

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
  };
}
