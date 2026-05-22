# The Physical IDE — Dynamic Schematic Mentor

**Team:** Eshwar Rajasekar · Athif Shaffy · Adil Arya

A hands-free, vision-anchored AI agent for hardware assembly. The user builds an
Arduino circuit on a breadboard under a webcam. Whenever their hands leave the
frame, the browser captures a frame and streams it over a WebSocket to a Cloud
Run backend. Two ADK-style sub-agents take over: a **Watcher** evaluates the
physical board against the expected step (catching short circuits and
mis-placements), and a **Planner** generates the next step as an interleaved
payload of audio narration + an isometric "Lego-style" instruction image + a
text log. The result is a physical IDE — schematic guidance that reacts to what
you actually built, not what you were supposed to build.

---

## Quick start (mock mode — zero API keys, ~10 min to a live demo)

Both halves run end-to-end with **no Gemini key** by default. See
[`MOCK_MODE.md`](MOCK_MODE.md) for what is faked and how the scripted demo beat
works.

### Backend

```bash
cd physical-ide/backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py                      # serves ws://localhost:8080/ws/agent
```

### Frontend

```bash
cd physical-ide/frontend
npm install
npm run dev                         # http://localhost:5173
```

Open the page, click **INITIALIZE SESSION**, grant camera access. Pull your
hands out of frame to trigger a scan — or use the **FORCE CAPTURE** button if
hand-tracking is flaky on demo hardware.

---

## Going live (real Gemini)

Switching to real inference is a **single env-var change, no code edits**:

```bash
# backend/.env
MOCK_MODE=false
GEMINI_API_KEY=<your-key>
GEMINI_STRATEGY=parallel            # or: single_pass
```

`gemini_client.py` exposes a stable interface; the mock and the two real
strategies sit behind it. If a real call fails it falls back to mock output so
the demo never hard-crashes.

---

## Architecture

```
+------------------------------------------------------------------+
|  BROWSER  (React + Vite)                                          |
|  +----------+   +--------------+   +--------------------+          |
|  | Webcam   |   | MediaPipe    |   | Web Audio + <img>  |          |
|  | feed     |-->| Hands        |   | render + AgentLog  |          |
|  +----------+   +------+-------+   +---------^----------+          |
|                        | onHandClear        |                     |
|                  +-----v--------------------+-----+                |
|                  | useAgentSocket  (WebSocket)    |                |
|                  +---------------+----------------+                |
+----------------------------------|--------------------------------+
                                   |  wss://<cloud-run>/ws/agent
                        frame_eval v ^ interleaved payload
+----------------------------------|--------------------------------+
|  CLOUD RUN  (FastAPI)            |                                 |
|  +-------------------------------v-----------------------------+   |
|  | main.py        /ws/agent  WebSocket gateway                 |   |
|  +-------------------------------+-----------------------------+   |
|  | agent.py       AgentSession state machine                   |   |
|  |    +-----------+            +-----------+                    |   |
|  |    |  Watcher  |  -------->  |  Planner  |                    |   |
|  |    +-----+-----+            +-----+-----+                    |   |
|  +----------|------------------------|------------------------+   |
|  +----------v------------------------v------------------------+   |
|  | gemini_client.py   MOCK_MODE  <-->  google-genai            |   |
|  |   evaluate_frame()        single_pass | parallel strategies  |   |
|  |   generate_next_step()                                       |   |
|  +--------------------------------------------------------------+   |
+--------------------------------------------------------------------+
```

## Google APIs used

- **Gemini API** (`google-genai` SDK) — vision frame evaluation (the Watcher).
- **Gemini multimodal generation** — interleaved TEXT + IMAGE + AUDIO
  (`single_pass` strategy), or **Imagen 3** image generation + **Gemini TTS**
  stitched in parallel (`parallel` strategy).
- **Google Cloud Run** — serverless WebSocket backend host.
- **MediaPipe Tasks Vision** (`HandLandmarker`) — in-browser hand tracking that
  decides when the work area is clear.

## Repo layout

```
physical-ide/
  backend/      FastAPI + ADK-style agent + Gemini wrapper
  frontend/     React + Vite mission-control UI
  README.md     this file
  MOCK_MODE.md  how to run end-to-end with mocks
```

## Locked API contract

WebSocket: `wss://<cloud-run-url>/ws/agent`. Do not deviate — frontend and
backend are built against it independently. Full message shapes are documented
in [`MOCK_MODE.md`](MOCK_MODE.md) and enforced by `agent.py::_payload`.
