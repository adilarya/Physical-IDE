# Project PreFlight — Technical Stack
**The Physical IDE** | Google I/O 2026 Hackathon

---

## Google Technologies

### AI & Models
| Technology | Role |
|---|---|
| **Gemini Live API** (`gemini-3.1-flash-live-preview`) | Core vision engine. Receives JPEG frames from the webcam, evaluates physical assembly state in real time, and returns a spoken verdict + audio response. The model is audio-native — it sees the board and speaks directly to the user. |
| **Gemini 3.5 Flash** (`gemini-3.5-flash`) | Planner model. Generates step-by-step assembly instructions, correction messages, and interleaved text output. |

### Infrastructure
| Technology | Role |
|---|---|
| **Google Cloud Run (Gen2)** | Hosts the FastAPI backend. Configured with `--min-instances 1` (zero cold start), `--cpu-boost`, and `--session-affinity` to ensure the WebSocket session stays on the same container. |
| **Google Cloud Logging** | Audit trail for every assembly verification event — verdict, confidence, and step logged to the cloud for compliance use cases. |

### Frontend & Edge
| Technology | Role |
|---|---|
| **MediaPipe Hands** (Google) | Runs on-device in the browser. Detects when hands leave the camera frame and triggers the assembly scan — no server round-trip for the detection step. |

---

## Other Notable Technologies

### Backend
| Technology | Role |
|---|---|
| **Python 3.13** | Primary backend language |
| **FastAPI** | WebSocket gateway — handles real-time bidirectional communication between the browser and the Gemini Live session |
| **uvicorn** | ASGI server, runs the FastAPI app on Cloud Run |
| **google-genai SDK** | Official Python client for Gemini Live API and generative model calls |
| **asyncio** | Manages concurrent WebSocket connections and async Gemini API calls |

### Frontend
| Technology | Role |
|---|---|
| **React 18** | UI framework — webcam feed, instruction card, agent log, scan overlay |
| **Vite** | Dev server and bundler |
| **TailwindCSS** | Styling — dark mission-control aesthetic |
| **Web Audio API** | Plays the audio returned from Gemini Live directly in the browser (no audio library needed) |
| **WebSocket API** | Native browser WebSocket — streams frames to the backend, receives verdict payloads |
| **getUserMedia** | Browser webcam access — captures JPEG frames for Gemini evaluation |

---

## Architecture in One Sentence

> A React frontend captures webcam frames via MediaPipe hand-exit detection, streams them over WebSocket to a FastAPI backend on Cloud Run, which opens a Gemini Live API session per frame to get a real-time spoken verdict and WAV audio response, then sends the verdict + audio back to the browser where Web Audio API plays it instantly.

---

## Key Numbers for the Pitch
- **Audio latency:** ~5-8s from hands-out to spoken verdict (Gemini Live session open + inference)
- **Frame resolution:** JPEG, captured at browser native resolution
- **Audio format:** 24kHz 16-bit PCM from Gemini Live, wrapped in WAV, played via Web Audio API
- **Mock mode:** Full end-to-end demo runs with zero API calls (`MOCK_MODE=true`) — no keys needed for development or fallback
- **WebSocket contract:** 7-field JSON payload — `status`, `audio_b64`, `image_b64`, `text`, `agent_log`, `current_step`, `citation`
