# The Physical IDE — System Architecture

## The Problem

Hardware assembly errors are invisible until it's too late. A mis-wired connector in a factory costs thousands in rework and millions in recalls. For students, a reversed LED destroys components and discourages learning. In both cases, the failure happens at the moment of wiring — but no tool has ever watched that moment in real time.

**The Physical IDE is a compiler for the physical world.** Just as a software IDE catches syntax errors before you run your code, The Physical IDE catches wiring errors before you power your circuit.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (React)                           │
│                                                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│  │  Webcam     │    │  MediaPipe   │    │   Web Audio API    │  │
│  │  (getUserMedia)│ │  Hands Model │    │  (plays WAV audio) │  │
│  │             │    │  (on-device) │    │                    │  │
│  └──────┬──────┘    └──────┬───────┘    └────────┬───────────┘  │
│         │                  │                     ↑               │
│     JPEG frame         hand-clear event      audio_b64          │
│         │                  │                     │               │
│         └──────────────────▼─────────────────────┘               │
│                      WebSocket Client                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │  wss://  (WebSocket)
                           │  { event: "frame_eval", image_b64, step }
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GOOGLE CLOUD RUN (Gen2)                         │
│                                                                   │
│   FastAPI + uvicorn                                               │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  WebSocket handler (main.py)                             │   │
│   │                                                           │   │
│   │  LiveAssemblySession (live_agent.py)                      │   │
│   │  - decodes JPEG frame                                     │   │
│   │  - builds context: step criteria + wire color rules       │   │
│   │  - opens Gemini Live WebSocket                            │   │
│   └──────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────┘
                              │  wss://  (Gemini Live bidiGenerateContent)
                              │  { image, text context, turn_complete }
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              GEMINI LIVE API (gemini-3.1-flash-live-preview)      │
│                                                                   │
│  Input:  JPEG frame + step context + wire color rules             │
│  Output: AUDIO (24kHz PCM) + output_audio_transcription           │
│                                                                   │
│  The model:                                                       │
│  1. Sees the breadboard (vision)                                  │
│  2. Identifies wire colors and rail positions                     │
│  3. Speaks a verdict + instruction aloud (audio synthesis)        │
│  4. Transcription is parsed for PASS/WRONG/DANGER/UNCLEAR token   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │  PCM audio chunks + transcription text
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLOUD RUN (response path)                       │
│                                                                   │
│  - Concatenate PCM chunks → wrap in WAV header (24kHz, 16-bit)   │
│  - Parse verdict token from transcription (PASS → success_advance)│
│  - Build downstream payload:                                      │
│    { status, audio_b64, text, agent_log, current_step, citation } │
└──────────────────────────────┬──────────────────────────────────┘
                               │  WebSocket response
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (response)                         │
│                                                                   │
│  - Web Audio API decodes WAV + plays spoken verdict               │
│  - Voice circle animates to audio amplitude in real time          │
│  - Instruction panel updates with verdict text                    │
│  - Step counter advances on PASS                                  │
│  - Error state displayed on WRONG/DANGER                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Why This Architecture Is Novel

### 1. One API call does vision + reasoning + speech
Traditional approaches require three separate calls: a vision model for analysis, a text model for instruction generation, and a TTS model for audio. The Gemini Live API collapses all three into a single persistent WebSocket session. The model sees the board, reasons about it, and speaks to the user in one round-trip. This is only possible with Gemini Live's native audio output.

### 2. Edge-triggered scanning via MediaPipe
The Gemini Live API is not polled on a timer. The scan is triggered by MediaPipe Hands detecting that the user's hands have left the camera frame. This is a hardware-aware edge trigger — the agent only evaluates when the board is actually visible and clear. This eliminates wasted API calls and mirrors how a human inspector would work: you check the connection after placing the component, not while your hand is still on it.

### 3. Wire color as a grounding mechanism
Instead of relying on spatial coordinates (which vary by camera angle, lighting, and component placement), the system uses wire color convention as its primary verification signal. Red = positive, black/blue/brown/grey = negative. This color-based approach is:
- **Robust to camera angle** — color is invariant to perspective
- **Standard in electronics** — the color codes are industry convention, not arbitrary
- **Self-grounding** — the model can verify both the wire color AND the rail stripe color independently, then check they match

### 4. Two WebSocket connections, one user experience
The browser maintains one WebSocket to the backend. The backend maintains a separate WebSocket to Gemini Live. The user experiences a seamless conversation with an AI that sees their hardware — but underneath, two persistent connections are running simultaneously, each purpose-built for their role.

### 5. Cloud Run Gen2 for WebSocket affinity
Standard Cloud Run terminates HTTP connections. Gen2 with `--session-affinity` ensures every frame from a given user session hits the same container instance, preserving the assembly state machine across multiple scans. Without session affinity, step 2 of a user's build could land on a different container that has no memory of step 1.

---

## Data Contract (Frontend ↔ Backend)

### Upstream (Browser → Cloud Run)
```json
{ "event": "frame_eval", "image_b64": "data:image/jpeg;base64,...", "current_step": 2, "circuit_id": "servo_control" }
```

### Downstream (Cloud Run → Browser)
```json
{
  "status": "success_advance | error_short_circuit | error_wrong_placement | error_occluded | session_init",
  "audio_b64": "base64-encoded WAV (24kHz 16-bit PCM, no data: prefix)",
  "image_b64": "data:image/...;base64,...",
  "text": "PASS. The red wire is correctly on the positive rail. Now connect the ground wire.",
  "agent_log": "[Watcher] step 1 verdict=success_advance",
  "current_step": 2,
  "citation": "Arduino Uno R3 - power pins reference, p.2"
}
```

---

## Technology Stack

| Layer | Technology | Role |
|---|---|---|
| Vision + Voice AI | Gemini Live API (`gemini-3.1-flash-live-preview`) | Sees board, speaks verdict |
| Tutorial Generation | Gemini 3.5 Flash + Gemini Flash Image | Step planning + Lego diagrams |
| Backend | FastAPI + Python on Cloud Run Gen2 | WebSocket gateway, state machine |
| Edge Detection | MediaPipe Hands (on-device) | Hand-clear trigger, zero latency |
| Audio Playback | Web Audio API | Real-time WAV decode + amplitude analysis |
| Frontend | React + Vite + Chakra Petch/DM Mono | Assembly HUD |
| Hosting | Google Cloud Run (Gen2) | Backend; Firebase Hosting (frontend) |

---

## Industrial QA Application

The same architecture that guides a student assembling a servo circuit also audits a factory worker assembling a wire harness. The verification logic is circuit-agnostic — swap the circuit definition in `circuits.py` for a Boeing wiring diagram and the system enforces aerospace assembly compliance in real time.

Every verdict is logged with timestamp, step, confidence, and outcome — an immutable audit trail that satisfies FAA/ISO manufacturing documentation requirements without any additional tooling.
