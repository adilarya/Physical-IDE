# ADIL — Backend & Agent Orchestration
**Role:** FastAPI server, WebSocket pipeline, Antigravity state machine, model routing, Cloud Run deployment.
**Stack:** Python, FastAPI, uvicorn, google-genai SDK, Cloud Run

---

## How to Run Your Part Independently

You do not need the frontend running. You do not need a Gemini API key for development.

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Start the server (MOCK_MODE=true by default — no API keys needed)
python main.py
# Server binds on :8080

# In a separate terminal, run the full test harness:
python test_ws.py
# Expected: PASSED — all 5 payloads received and validated
```

To test with real Gemini calls:
```bash
cp .env.example .env
# Edit .env: set MOCK_MODE=false and GEMINI_API_KEY=your_key
python main.py
python test_ws.py
```

---

## Files You Own

```
backend/
  main.py           ← FastAPI app, WebSocket endpoint, CORS, routing
  agent.py          ← AgentSession, Watcher sub-agent, Planner sub-agent
  circuits.py       ← hardcoded circuit definitions (step data)
  gemini_client.py  ← Vertex AI / google-genai wrapper (interface to Eshwar's work)
  requirements.txt
  Dockerfile
  deploy.sh
  .env.example
  test_ws.py        ← your standalone test harness
```

You share `gemini_client.py` as an interface with Eshwar — you own the file structure and the mock, Eshwar owns the real implementation inside `_real_evaluate_frame` and `_real_generate_*`. Do not break the public function signatures.

---

## The Locked WebSocket Contract

This is the single most important thing you own. Both Athif and Eshwar depend on it. **Do not change field names or types without telling both of them.**

### Frontend → Backend

```json
// Sent once on connect
{
  "event": "start_session",
  "circuit_id": "temperature_alarm",
  "user_constraints": []
}

// Sent on every hand-clear or force capture
{
  "event": "frame_eval",
  "image_b64": "data:image/jpeg;base64,...",
  "current_step": 2,
  "circuit_id": "temperature_alarm"
}
```

### Backend → Frontend (every response)

```json
{
  "status": "session_init | success_advance | error_short_circuit | error_occluded | error_wrong_placement | error_protocol",
  "audio_b64": "base64-encoded WAV string (no data: prefix)",
  "image_b64": "data:image/...;base64,... (full data URI with prefix)",
  "text": "Human-readable instruction or correction",
  "agent_log": "[Watcher] ... [Planner] ...",
  "current_step": 3,
  "citation": "Source reference string or empty string"
}
```

Rules:
- Every field must always be present, even if empty string
- `audio_b64` has no `data:` prefix — the frontend's `decodeAudioData()` call strips it
- `image_b64` always has the `data:` prefix
- `current_step` greater than the total step count (3) signals build complete
- `citation` can be an empty string — never `null`
- `error_protocol` is emitted only by `main.py` for malformed input or unknown events — never by the agent/Watcher

---

## What You Need to Build

### 1. AgentSession State Machine (`agent.py`)

The `AgentSession` class is the core of your work. It owns:
- Which step the user is currently on (`current_step`)
- Orchestrating Watcher → Planner for every frame
- Deciding when to advance vs. send a correction

**Current implementation is functional for the mock.** For the real demo you need to validate and harden:

- `start()` — emits the `session_init` payload for Step 1. Currently calls `reset_mock_state()` — ensure this stays even in real mode so repeated demo runs replay correctly.
- `handle_frame(image_b64, current_step)` — runs Watcher, then Planner based on verdict:
  - `success_advance` → increment step, call Planner for the next step, return `success_advance` payload
  - Any `error_*` → stay on current step, call Planner with `correction=True` context, return error payload
  - When `next_step > step_count` → call Planner with `complete=True`, return `success_advance` payload with `current_step = 4`

**Edge cases to handle:**
- `frame_eval` arriving before `start_session` (already handled — `AgentSession` is created on first `frame_eval` if session is `None`)
- Client sending a `current_step` that is out of range — clamp it, do not crash
- `get_step()` returning `None` for an out-of-range index — handle gracefully in `handle_frame`

### 2. Constraint Routing Logic

This is the "Physical IDE" differentiator for the demo. When `user_constraints` is non-empty in the `start_session` message, the agent should adapt the circuit steps.

`user_constraints` is currently accepted but ignored. For the demo, implement at minimum:

**Missing component constraint:**
- If `"missing_220_resistor"` is in `user_constraints`, substitute a 470-ohm resistor in Step 3 and update the instruction text to reflect the substitution
- The circuit still works — the LED is dimmer but safe

**Implementation:**
- `circuits.py` — add a `get_circuit_with_constraints(circuit_id, constraints)` function that returns a modified step list
- `agent.py` — pass `user_constraints` into this function at session start and store the adapted circuit

This is what makes the demo story compelling: "even if you're missing a component, the agent reroutes."

### 3. WebSocket Server Hardening (`main.py`)

The current `main.py` is functional. Harden it for a live demo:

- **Unknown event handling** — already returns an error payload. Verify it never crashes the connection.
- **Malformed JSON** — wrap `json.loads()` in a try/except and send an error payload rather than crashing.
- **Disconnect cleanup** — `WebSocketDisconnect` is caught. Make sure any in-flight async tasks are cancelled on disconnect.
- **CORS** — currently `allow_origins=["*"]`. Before the demo, lock this to the frontend's actual origin (or keep wildcard if origin is unknown at demo time — acceptable for a hackathon).

### 4. Cloud Run Deployment (`deploy.sh` / `Dockerfile`)

The `Dockerfile` and `deploy.sh` already exist. Your job is to make sure a deploy actually works end-to-end.

```bash
# Local Docker test (do this before submitting):
docker build -t physical-ide-backend .
docker run -p 8080:8080 -e MOCK_MODE=true physical-ide-backend
python test_ws.py  # should still PASS against the Docker container
```

**`deploy.sh` checklist:**
- Sets the correct GCP project ID
- Passes `MOCK_MODE`, `GEMINI_API_KEY`, and `GEMINI_STRATEGY` as Cloud Run env vars via `--set-env-vars`
- Uses `--allow-unauthenticated` (demo endpoint is public)
- Uses `--port 8080` to match the Dockerfile `EXPOSE`
- After deploy, runs the WebSocket test against the Cloud Run URL to confirm it is live

### 5. Multi-Circuit Support (Stretch)

`circuits.py` currently has one circuit: `temperature_alarm`. If time allows, add a second circuit (e.g. `led_blink`) so the demo can show the system is general-purpose, not one-trick. The frontend sends `circuit_id` — the backend already uses it. Just add the entry to `CIRCUITS` in `circuits.py`.

---

## Interface with Eshwar (Vision Pipeline)

You call two functions from `gemini_client.py`. **Do not change these signatures:**

```python
# Called by Watcher.run()
result = await evaluate_frame(image_b64, current_step, expected_state)
# Returns: {"verdict": str, "confidence": float, "detected_components": list, "reasoning": str}

# Called by Planner.run()
result = await generate_next_step(step_index, context)
# Returns: {"audio_b64": str, "image_b64": str, "text": str, "agent_log": str}
```

`MOCK_MODE=true` (default) means both functions return hardcoded responses — no coordination with Eshwar needed during development. When Eshwar's real implementations are ready, flip `MOCK_MODE=false` and they drop in behind the same interface.

---

## Testing Your Work

**Primary test:** `python test_ws.py` — this validates the full contract end-to-end.

**Manual test via wscat or websocat:**
```bash
# Install wscat: npm install -g wscat
wscat -c ws://localhost:8080/ws/agent

# Paste these one at a time:
{"event":"start_session","circuit_id":"temperature_alarm","user_constraints":[]}
{"event":"frame_eval","image_b64":"placeholder","current_step":1,"circuit_id":"temperature_alarm"}
{"event":"frame_eval","image_b64":"placeholder","current_step":2,"circuit_id":"temperature_alarm"}
{"event":"frame_eval","image_b64":"placeholder","current_step":2,"circuit_id":"temperature_alarm"}
{"event":"frame_eval","image_b64":"placeholder","current_step":3,"circuit_id":"temperature_alarm"}
```

**Test constraint routing:**
```json
{"event":"start_session","circuit_id":"temperature_alarm","user_constraints":["missing_220_resistor"]}
```
Step 3 instruction should mention 470-ohm instead of 220-ohm.

**Test unknown event:**
```json
{"event":"bad_event"}
```
Should return an `error_protocol` payload, not crash the connection.

---

## Definition of Done

- [ ] `python test_ws.py` passes against the local server
- [ ] `python test_ws.py` passes against the Docker container
- [ ] Constraint routing: `missing_220_resistor` produces a Step 3 with 470-ohm substitution
- [ ] Malformed JSON does not crash the WebSocket connection
- [ ] `deploy.sh` deploys to Cloud Run successfully
- [ ] `python test_ws.py WS_URL=wss://your-cloud-run-url/ws/agent` passes against the deployed instance
- [ ] `MOCK_MODE=false` + real Gemini key produces valid payloads (all contract fields present)
