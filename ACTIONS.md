# ACTIONS.md — Claude Agent Log
A running record of every action taken by Claude in this session, in order.

---

## Session Start

**Context loaded:** Read `agent_context.md`, all backend and frontend source files, `MOCK_MODE.md`, `README.md`, `.gitignore`.

---

## Actions Taken

### 1. Pulled latest from remote
- Ran `git pull` — already up to date, no conflicts.

### 2. Read and committed `agent_context.md`
- User added `agent_context.md` describing the Physical IDE project: vision-anchored safety agent, EdTech wedge, industrial QA pivot, FastAPI/Antigravity/Vertex AI architecture.
- Committed and pushed to `main`.

### 3. Proposed 3-person team split
- Suggested Frontend/UX, Backend/Orchestration, and Vision AI/Compliance as the three roles.
- User confirmed and named: **Athif** (Frontend), **Adil** (Backend), **Eshwar** (Vision AI).

### 4. Added team roles to `agent_context.md`
- Added Section 5 with detailed responsibilities for Athif, Adil, and Eshwar.
- Committed and pushed to `main`.

### 5. Created independent dev scaffolding (3 files)
- **`frontend/src/hooks/useMockAgentSocket.js`** — in-browser scripted demo hook for Athif. Plays the full 5-step beat (session_init → error_short_circuit → corrections → build complete) with zero backend dependency.
- **`frontend/src/hooks/useAgentSocket.js`** — modified to export a unified `useAgentSocket` hook that branches on `VITE_MOCK_SOCKET=true` to use the mock, otherwise uses the real WebSocket. Original implementation renamed to `useRealAgentSocket`.
- **`backend/test_ws.py`** — Adil's standalone backend test. Spins up FastAPI on port 8099, drives the full WebSocket flow through 5 payloads, validates every field in the locked contract.
- **`backend/test_vision.py`** — Eshwar's standalone vision pipeline test. Calls `evaluate_frame` and `generate_next_step` directly for all steps and all correction types. Supports `--image` flag for real board photos.
- Updated `frontend/.env.example` to document `VITE_MOCK_SOCKET`.
- Committed and pushed to `main`.

### 6. Created full technical spec documents (3 files)
- **`ATHIF.md`** — frontend spec: how to run in mock mode, all 5 UI states with visual treatment, InstructionCard spec, ScanOverlay, AgentLog, layout requirements, manual test table, definition-of-done checklist.
- **`ADIL.md`** — backend spec: full locked WebSocket contract, AgentSession state machine requirements, constraint routing (missing component substitution), server hardening, Docker + Cloud Run deployment checklist, definition-of-done.
- **`ESHWAR.md`** — vision spec: exact function signatures, Gemini model breakdown (Flash/Imagen/TTS), WAV wrapping bug and fix, fiducial marker system with OpenCV ArUco code, digital twin spatial schema, audit trail logging format, 4 test scenarios, definition-of-done.
- Committed and pushed to `main`.

### 7. Created and updated `.env` files
- **`backend/.env`** — created with all keys (gitignored): `MOCK_MODE`, `GEMINI_API_KEY`, `GEMINI_STRATEGY`, model overrides, `GCP_PROJECT_ID`, `GCP_REGION`, `GOOGLE_APPLICATION_CREDENTIALS`, `PORT`, `FIRESTORE_AUDIT_COLLECTION`.
- **`backend/.env.example`** — rewritten with all keys and descriptions including new GCP and Firestore keys.
- **`frontend/.env`** — created with `VITE_WS_URL` and `VITE_MOCK_SOCKET` (gitignored).
- **`frontend/.env.example`** — updated and cleaned up.
- Confirmed `.gitignore` already covered both `.env` files — no changes needed.
- Committed and pushed `.env.example` files to `main`. `.env` files correctly not committed.

### 8. Fixed `test_vision.py` dotenv loading order
- **Problem:** `os.environ.setdefault("MOCK_MODE", "true")` was running before `load_dotenv()` in `gemini_client.py`, so the `.env` file's `MOCK_MODE=false` was being ignored.
- **Fix:** Added `load_dotenv()` call at the top of `test_vision.py` before the `setdefault` call, so `.env` values take precedence.

### 9. Installed `google-genai` SDK
- `pip install google-genai` installed to wrong Python (3.12 site-packages).
- Active interpreter was Python 3.13 (Anaconda).
- Used `pip3.13 install google-genai` — installed successfully, import verified.

### 10. Confirmed real Gemini connection working
- Ran `python test_vision.py` with `MOCK_MODE=false` and real `GEMINI_API_KEY`.
- `evaluate_frame`: Gemini API reached but returned `400 INVALID_ARGUMENT` for the 1x1 blank placeholder JPEG — expected, as it's too small to process. Falls back to mock safely.
- `generate_next_step`: **Real Gemini output confirmed** — text, corrections, and done state all returned live generated content (not mock strings).
- Overall test: `PASSED`.
- **Next step for Eshwar:** test `evaluate_frame` with a real breadboard photo using `--image`.

---

## Pending / Next Actions

- [ ] Eshwar: run `python test_vision.py --image board.jpg` with a real breadboard photo
- [ ] Eshwar: tune `_SYSTEM_EVAL` prompt in `gemini_client.py` for accurate verdict classification
- [ ] Eshwar: fix WAV wrapping for TTS audio (raw PCM → valid WAV header)
- [ ] Adil: implement constraint routing for `missing_220_resistor`
- [ ] Adil: test `test_ws.py` against Docker container
- [ ] Adil: run `deploy.sh` to Cloud Run
- [ ] Athif: build out all 5 status state visual treatments in the UI
- [ ] Athif: implement ScanOverlay animation and InstructionCard image display
