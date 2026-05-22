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
    [test] --- constraint routing: missing_220_resistor ---
    [test] Step 3 rerouted OK | text: Step 3 of 3 - Connect a 470-ohm...
    [test] PASSED - constraint routing verified (220-ohm -> 470-ohm)
    [test] --- robustness: malformed input ---
    [test] PASSED - server survives malformed JSON and unknown events
    [test] --- edge cases: out-of-range current_step ---
    [test] PASSED - out-of-range current_step values clamped safely
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
# Constraint routing test
# ---------------------------------------------------------------------------

async def run_constraint_test():
    """Verify constraint routing: missing_220_resistor reroutes Step 3 to 470-ohm.

    Opens a fresh WebSocket session (start_session resets the mock attempt
    counter, so the scripted beat replays cleanly) but passes a non-empty
    user_constraints list. The Step 3 instruction must come back rerouted.
    """
    import websockets

    errors = []
    step3_payload = None

    async with websockets.connect(WS_URL) as ws:
        print("\n[test] --- constraint routing: missing_220_resistor ---")

        # start_session WITH a constraint — the agent should adapt the circuit.
        await ws.send(json.dumps({
            "event": "start_session",
            "circuit_id": CIRCUIT_ID,
            "user_constraints": ["missing_220_resistor"],
        }))
        init = json.loads(await ws.recv())
        _check(init, "session_init", 1, errors)

        # Same scripted beat — the step=2 retry response carries Step 3's instruction.
        frames = [
            (1, "success_advance"),
            (2, "error_short_circuit"),
            (2, "success_advance"),
            (3, "success_advance"),
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
            if resp.get("current_step") == 3:
                step3_payload = resp

    # Core assertion: the rerouted Step 3 instruction must mention 470-ohm.
    if step3_payload is None:
        errors.append("constraint test: never received a Step 3 payload")
    elif "470-ohm" not in step3_payload.get("text", ""):
        errors.append(
            "constraint test: Step 3 text should mention '470-ohm', got: "
            f"{step3_payload.get('text', '')!r}"
        )
    else:
        print(f"[test] Step 3 rerouted OK | text: {step3_payload['text'][:72]}...")

    if errors:
        print(f"\n[test] CONSTRAINT TEST FAILED - {len(errors)} assertion(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("[test] PASSED - constraint routing verified (220-ohm -> 470-ohm)")


# ---------------------------------------------------------------------------
# Robustness test - malformed input must not crash the connection
# ---------------------------------------------------------------------------

async def run_robustness_test():
    """Verify the server survives malformed JSON and unknown events.

    The critical assertion is the LAST one: after two bad messages on a single
    connection, a valid start_session must still succeed - proving the bad
    input degraded gracefully instead of killing the socket.
    """
    import websockets
    from websockets.exceptions import ConnectionClosed

    errors = []

    async def _recv(ws, label):
        """recv() that turns a server-side disconnect into a clear failure."""
        try:
            return json.loads(await ws.recv())
        except ConnectionClosed:
            errors.append(f"{label}: connection was closed by the server")
            return None

    async with websockets.connect(WS_URL) as ws:
        print("\n[test] --- robustness: malformed input ---")

        # 1. malformed JSON (raw text, not a JSON object)
        await ws.send("this is not valid json {{{")
        r1 = await _recv(ws, "malformed JSON")
        if r1 is not None:
            if r1.get("status") != "error_protocol":
                errors.append(
                    "malformed JSON: expected status='error_protocol', "
                    f"got {r1.get('status')!r}")
            for field in ("status", "audio_b64", "image_b64", "text",
                          "agent_log", "current_step", "citation"):
                if field not in r1:
                    errors.append(f"malformed JSON: response missing '{field}'")
            print(f"[test] malformed JSON handled | status={r1.get('status')!r}")

        # 2. well-formed JSON but an unknown event
        await ws.send(json.dumps({"event": "bad_event"}))
        r2 = await _recv(ws, "unknown event")
        if r2 is not None:
            if r2.get("status") != "error_protocol":
                errors.append(
                    "unknown event: expected status='error_protocol', "
                    f"got {r2.get('status')!r}")
            print(f"[test] unknown event handled | status={r2.get('status')!r}")

        # 3. THE KEY ASSERTION - the connection must still be alive
        await ws.send(json.dumps({
            "event": "start_session",
            "circuit_id": CIRCUIT_ID,
            "user_constraints": [],
        }))
        r3 = await _recv(ws, "post-error start_session")
        if r3 is not None:
            if r3.get("status") != "session_init":
                errors.append(
                    "connection did not survive malformed input: expected "
                    f"session_init, got {r3.get('status')!r}")
            else:
                print("[test] connection survived - valid session still works")

    if errors:
        print(f"\n[test] ROBUSTNESS TEST FAILED - {len(errors)} assertion(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("[test] PASSED - server survives malformed JSON and unknown events")


# ---------------------------------------------------------------------------
# Edge-case test - out-of-range current_step must be clamped, not crashed
# ---------------------------------------------------------------------------

async def run_edge_case_test():
    """Verify the agent clamps an out-of-range current_step from the client.

      - step far above the circuit length -> a build-complete response
      - step below 1                       -> snapped to step 1, no crash
    """
    import websockets
    from websockets.exceptions import ConnectionClosed

    errors = []

    async def _recv(ws, label):
        try:
            return json.loads(await ws.recv())
        except ConnectionClosed:
            errors.append(f"{label}: connection was closed by the server")
            return None

    async with websockets.connect(WS_URL) as ws:
        print("\n[test] --- edge cases: out-of-range current_step ---")

        await ws.send(json.dumps({
            "event": "start_session", "circuit_id": CIRCUIT_ID,
            "user_constraints": [],
        }))
        await _recv(ws, "start_session")

        # step far above the circuit length -> build already complete
        await ws.send(json.dumps({
            "event": "frame_eval", "image_b64": "placeholder",
            "current_step": 99, "circuit_id": CIRCUIT_ID,
        }))
        high = await _recv(ws, "high out-of-range step")
        if high is not None:
            if high.get("status") != "success_advance":
                errors.append(
                    f"high step: expected status='success_advance', "
                    f"got {high.get('status')!r}")
            if high.get("current_step") != 4:
                errors.append(
                    f"high step: expected current_step=4 (build complete), "
                    f"got {high.get('current_step')!r}")
            print(f"[test] step=99 handled | status={high.get('status')!r} "
                  f"current_step={high.get('current_step')}")

        # step below 1 -> snapped to step 1, valid payload, no crash
        await ws.send(json.dumps({
            "event": "frame_eval", "image_b64": "placeholder",
            "current_step": 0, "circuit_id": CIRCUIT_ID,
        }))
        low = await _recv(ws, "low out-of-range step")
        if low is not None:
            for field in ("status", "text", "current_step"):
                if field not in low:
                    errors.append(f"low step: response missing '{field}'")
            print(f"[test] step=0 handled | status={low.get('status')!r}")

        # the connection must still be alive after both
        await ws.send(json.dumps({"event": "bad_event"}))
        if await _recv(ws, "post-edge-case") is None:
            errors.append("connection did not survive out-of-range steps")
        else:
            print("[test] connection survived out-of-range steps")

    if errors:
        print(f"\n[test] EDGE CASE TEST FAILED - {len(errors)} assertion(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("[test] PASSED - out-of-range current_step values clamped safely")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def _run_all():
    """Run scripted-beat, constraint-routing, robustness, and edge-case tests."""
    await run_tests()
    await run_constraint_test()
    await run_robustness_test()
    await run_edge_case_test()


if __name__ == "__main__":
    print(f"[server] starting on :{TEST_PORT} (MOCK_MODE={os.environ.get('MOCK_MODE')})")
    _launch_server()
    asyncio.run(_run_all())
