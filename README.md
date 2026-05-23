# The Physical IDE

**A real-time hardware assembly verification agent powered by Gemini Live API.**

Built at Google I/O 2026 Hackathon.

---

## Team

| Name | Role | Email |
|---|---|---|
| **Eshwar Rajasekar** | Vision AI & Data | eshwar.rajasekar@gmail.com |
| **Adil Arya** | Backend & Agent Orchestration | mr.adil.arya@gmail.com |
| **Athif Shaffy** | Frontend & Real-Time UX | athif.shaffy@gmail.com |

---

## What It Does

The Physical IDE is a compiler for the real world. Just as a software IDE catches syntax errors before you run your code, The Physical IDE catches wiring errors before you power your circuit.

Point a webcam at a breadboard. Remove your hands. Gemini Live API sees the board, evaluates the assembly, and speaks a verdict and instruction aloud — all in a single round-trip. No polling. No text boxes. A real-time AI that sees your hardware and talks back.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design, data flow, and explanation of why each design decision was made.

---

## Tech Stack

- **Gemini Live API** (`gemini-3.1-flash-live-preview`) — vision + verdict + audio in one WebSocket call
- **Google Cloud Run Gen2** — WebSocket-capable backend with session affinity
- **MediaPipe Hands** — on-device hand detection, triggers scans at the right moment
- **FastAPI** — WebSocket gateway and state machine
- **React + Web Audio API** — real-time audio playback with amplitude visualization

---

## Running Locally

```bash
# Backend
cd backend
cp .env.example .env          # add your GEMINI_API_KEY
pip install -r requirements.txt
python main.py                 # runs on :8080

# Frontend
cd frontend
npm install
npm run dev                    # runs on :5173
```

Set `MOCK_MODE=true` in `backend/.env` to run with zero API calls.

---

## Deploying to Cloud Run

```bash
cd backend
GCP_PROJECT_ID=your-project GEMINI_API_KEY=your-key bash deploy.sh
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full deployment guide.
