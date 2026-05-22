# Mock Mode

**The whole project runs end-to-end with zero Gemini API calls by default.**
This lets the frontend dev test the full interaction loop in minute one, and
lets the backend dev swap in real Gemini calls behind the same interface when
ready — with no contract changes.

Controlled by one env var: `MOCK_MODE` (default **`true`**).

```bash
MOCK_MODE=true     # default — canned responses, no key needed
MOCK_MODE=false    # real google-genai calls (needs GEMINI_API_KEY)
```

---

## What is faked

`gemini_client.py` is the only file that branches on `MOCK_MODE`. Everything
above it (`agent.py`, `main.py`, the entire frontend) is identical in both modes.

| Function | Mock behavior |
|---|---|
| `evaluate_frame(image_b64, current_step, expected_state)` | Returns a hardcoded verdict based on `current_step`. **Ignores the image.** |
| `generate_next_step(step_index, context)` | Returns a pre-canned `{audio_b64, image_b64, text, agent_log}`. |

- **Image** — an inline SVG breadboard sketch (data URI), one per step, with the
  active component highlighted in orange. No network, no files.
- **Audio** — a 1-second silent 16-bit PCM WAV, base64-encoded at runtime.
  Valid enough for `decodeAudioData()` on the frontend; you will hear silence.

---

## The scripted demo beat

The mock `evaluate_frame` is deliberately scripted so the demo's **safety
interrupt** lands every time:

```
Step 1  -> success_advance        (advance to Step 2)
Step 2  -> error_short_circuit    (FIRST attempt — agent interrupts)
Step 2  -> success_advance        (retry — advance to Step 3)
Step 3  -> success_advance        (advance to "build complete")
```

So in the demo: build step 1, hands out -> verified. Build step 2, hands out ->
the agent **interrupts with a short-circuit correction**. Fix it, hands out ->
verified. The per-step attempt counter resets on every `start_session`, so you
can re-run the demo back to back.

> Mock attempt tracking is process-global, keyed by step index — fine for a
> single-session demo, not multi-session safe. `# TODO` noted in code.

---

## The locked API contract

### Frontend -> Backend

`start_session` (sent once, on connect):
```json
{ "event": "start_session", "circuit_id": "temperature_alarm", "user_constraints": [] }
```

`frame_eval` (sent on every hand-clear):
```json
{ "event": "frame_eval", "image_b64": "data:image/jpeg;base64,...",
  "current_step": 2, "circuit_id": "temperature_alarm" }
```

### Backend -> Frontend (interleaved payload)

```json
{
  "status": "success_advance | error_short_circuit | error_occluded | error_wrong_placement | session_init",
  "audio_b64": "base64-wav-or-mp3 (no data: prefix)",
  "image_b64": "data:image/...;base64,...",
  "text": "Step 3: Connect the 220-ohm resistor from row 11 to the ground rail.",
  "agent_log": "[Watcher] ... [Planner] ...",
  "current_step": 3,
  "citation": "Resistor color codes - 220 ohm band reference, p.4"
}
```

`current_step` greater than the step count means the build is complete.

---

## Testing each half alone

**Backend only** — no frontend, no key:
```bash
cd backend && python main.py
# then, from another shell:
python - <<'PY'
import asyncio, json, websockets
async def go():
    async with websockets.connect("ws://localhost:8080/ws/agent") as ws:
        await ws.send(json.dumps({"event":"start_session","circuit_id":"temperature_alarm","user_constraints":[]}))
        print("init:", json.loads(await ws.recv())["text"])
        for step in (1, 2, 2, 3):
            await ws.send(json.dumps({"event":"frame_eval","image_b64":"x","current_step":step,"circuit_id":"temperature_alarm"}))
            r = json.loads(await ws.recv())
            print(step, "->", r["status"], "|", r["text"][:60])
asyncio.run(go())
PY
```

**Frontend only** — point it at any backend (mock or real) via `VITE_WS_URL`,
or just run the mock backend above. The UI does not care which mode the backend
is in.

---

## Flipping to real Gemini

1. `pip install -r requirements.txt` (already includes `google-genai`).
2. Set `MOCK_MODE=false` and `GEMINI_API_KEY=...` in `backend/.env`.
3. Pick `GEMINI_STRATEGY` (`parallel` is the safer default; `single_pass` is the
   optimistic one-call path).
4. No code edits. No frontend changes. The contract is identical.
