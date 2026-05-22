"""
test_ws.py — ADIL's standalone backend test harness.

Starts the FastAPI server in a background thread, then drives it through the
full scripted demo beat over a real WebSocket connection. No frontend needed.
No Gemini API key needed (MOCK_MODE=true is the default).

Usage:
    cd backend
    python test_ws.py

Expected output:
    [server] starting on :8099 (test port)
    [test] connected
    [test] session_init  | text: Step 1 of 3 - Power rail...
    [test] step=1 status=success_advance | text: Step 2 of 3 - The LED...
    [test] step=2 status=error_short_circuit | text: SAFETY STOP...
    [test] step=2 status=success_advance | text: Step 3 of 3 - Current...
    [test] step=3 status=success_advance | text: Assembly complete...
    [test] PASSED - all 5 payloads received and validated
"""
import asyncio
import json
import os
import sys
import threading
import time

# Force mock mode for the isolated test - never hit real Gemini.
os.environ.setdefault("MOCK_MODE", "true")

TEST_PORT = 8099
WS_URL = f"ws://localhost:{TEST_PORT}/ws/agent"
CIRCUIT_ID = "temperature_alarm"

# ---------------------------------------------------------------------------
# Server bootstrap (runs in a daemon thread so the script auto-exits when done)
# ---------------------------------------------------------------------------

def _start_server():
    import uvicorn
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=TEST_PORT, log_level="warning")


def _launch_server():
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    # Give uvicorn a moment to bind.
    time.sleep(1.5)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

async def run_tests():
    try:
        import websockets
    except ImportError:
        print("[test] ERROR: 'websockets' not installed. Run: pip install websockets")
        sys.exit(1)

    errors = []

    async with websockets.connect(WS_URL) as ws:
        print(f"[test] connected to {WS_URL}")

        # 1. start_session
        await ws.send(json.dumps({
            "event": "start_session",
            "circuit_id": CIRCUIT_ID,
            "user_constraints": [],
        }))
        init = json.loads(await ws.recv())
        _check(init, "session_init", 1, errors)
        print(f"[test] session_init  | text: {init['text'][:60]}...")

        # 2-5. frame_eval sequence matching the scripted beat
        frames = [
            (1, "success_advance"),
            (2, "error_short_circuit"),  # first attempt on step 2 -> short circuit
            (2, "success_advance"),      # retry step 2 -> passes
            (3, "success_advance"),      # step 3 -> build complete
        ]

        for step, expected_status in frames:
            await ws.send(json.dumps({
                "event": "frame_eval",
                "image_b64": "data:image/jpeg;base64,/9j/placeholder==",
                "current_step": step,
                "circuit_id": CIRCUIT_ID,
            }))
            resp = json.loads(await ws.recv())
            _check(resp, expected_status, step, errors)
            print(f"[test] step={step} status={resp['status']} | text: {resp['text'][:60]}...")

    if errors:
        print(f"\n[test] FAILED — {len(errors)} assertion(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n[test] PASSED — all 5 payloads received and validated")


def _check(payload, expected_status, expected_step, errors):
    """Validate the locked downstream contract fields."""
    for field in ("status", "audio_b64", "image_b64", "text", "agent_log", "current_step", "citation"):
        if field not in payload:
            errors.append(f"missing field '{field}' in payload for step={expected_step}")

    if payload.get("status") != expected_status:
        errors.append(
            f"step={expected_step}: expected status={expected_status!r}, "
            f"got {payload.get('status')!r}"
        )

    if not payload.get("text"):
        errors.append(f"step={expected_step}: 'text' field is empty")

    if not payload.get("audio_b64"):
        errors.append(f"step={expected_step}: 'audio_b64' field is empty")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[server] starting on :{TEST_PORT} (MOCK_MODE={os.environ.get('MOCK_MODE')})")
    _launch_server()
    asyncio.run(run_tests())
