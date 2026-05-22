"""
test_vision.py — ESHWAR's standalone vision pipeline test harness.

Tests evaluate_frame() and generate_next_step() directly — no server, no
frontend, no WebSocket needed. Works in both mock and real Gemini mode.

Usage (mock, no keys needed):
    cd backend
    python test_vision.py

Usage (real Gemini, optional real image):
    MOCK_MODE=false GEMINI_API_KEY=... python test_vision.py
    MOCK_MODE=false GEMINI_API_KEY=... python test_vision.py --image path/to/board.jpg

What it tests:
    1. evaluate_frame() returns a valid verdict for each step (mock) or for a
       real image (MOCK_MODE=false with --image).
    2. generate_next_step() returns all required fields for steps 1-3 and "done".
    3. generate_next_step() returns a valid correction payload for each error type.
    4. The verdict is always one of the four valid values.
    5. audio_b64 is a non-empty string (silent WAV in mock, real audio otherwise).
    6. image_b64 starts with "data:" (inline SVG/PNG — the browser can render it).
"""
import asyncio
import base64
import os
import sys
import argparse

os.environ.setdefault("MOCK_MODE", "true")

VALID_VERDICTS = {
    "success_advance",
    "error_short_circuit",
    "error_occluded",
    "error_wrong_placement",
}

VALID_STATUSES = VALID_VERDICTS  # same set used as status in the downstream payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_image(path):
    """Load a real image from disk and return it as a base64 data URI."""
    with open(path, "rb") as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def _blank_frame():
    """1x1 white JPEG as a minimal placeholder image."""
    # Minimal valid JPEG (1x1 white pixel)
    b64 = (
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
        "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJ"
        "CQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/"
        "EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAA"
        "AAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AJAA/9k="
    )
    return "data:image/jpeg;base64," + b64


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

async def test_evaluate_frame(image_b64, errors):
    from gemini_client import evaluate_frame
    from circuits import get_step

    print("\n── evaluate_frame() ──────────────────────────────")
    for step in (1, 2, 3):
        s = get_step("temperature_alarm", step)
        result = await evaluate_frame(image_b64, step, s["success_criteria"])
        verdict = result.get("verdict")
        conf = result.get("confidence", 0)
        detected = result.get("detected_components", [])
        reasoning = result.get("reasoning", "")

        ok = verdict in VALID_VERDICTS
        flag = "OK" if ok else "FAIL"
        print(f"  [{flag}] step={step} verdict={verdict!r} conf={conf:.2f} "
              f"components={detected} reasoning={reasoning[:60]!r}")

        if not ok:
            errors.append(f"evaluate_frame step={step}: invalid verdict {verdict!r}")
        for field in ("verdict", "confidence", "detected_components", "reasoning"):
            if field not in result:
                errors.append(f"evaluate_frame step={step}: missing field '{field}'")


async def test_generate_next_step(errors):
    from gemini_client import generate_next_step

    print("\n── generate_next_step() — normal steps ───────────")
    for step_key in (1, 2, 3, "done"):
        ctx = {"fresh": True} if step_key != "done" else {"complete": True}
        result = await generate_next_step(step_key, ctx)
        _check_planner_output(result, f"step={step_key}", errors)
        print(f"  [OK] step={step_key!r} text={result.get('text','')[:60]!r}")

    print("\n── generate_next_step() — corrections ────────────")
    for verdict in ("error_short_circuit", "error_occluded", "error_wrong_placement"):
        ctx = {"correction": True, "verdict": verdict, "step": {}, "watcher": {}}
        result = await generate_next_step(2, ctx)
        _check_planner_output(result, f"correction/{verdict}", errors)
        print(f"  [OK] {verdict} text={result.get('text','')[:60]!r}")


def _check_planner_output(result, label, errors):
    for field in ("audio_b64", "image_b64", "text", "agent_log"):
        if not result.get(field):
            errors.append(f"generate_next_step {label}: missing or empty field '{field}'")

    img = result.get("image_b64", "")
    if img and not img.startswith("data:"):
        errors.append(f"generate_next_step {label}: image_b64 must be a data URI (starts with 'data:')")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main(image_path):
    mock_mode = os.environ.get("MOCK_MODE", "true").lower() == "true"
    print(f"MOCK_MODE={mock_mode}  |  image={'--image arg' if image_path else 'blank placeholder'}")

    if image_path:
        image_b64 = _load_image(image_path)
        print(f"Loaded real image: {image_path} ({len(image_b64)} chars)")
    else:
        image_b64 = _blank_frame()
        print("Using blank placeholder frame (1x1 white JPEG)")

    errors = []

    await test_evaluate_frame(image_b64, errors)
    await test_generate_next_step(errors)

    print("\n" + "─" * 52)
    if errors:
        print(f"FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("PASSED — all vision pipeline outputs validated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vision pipeline test harness")
    parser.add_argument("--image", metavar="PATH", default=None,
                        help="Optional: path to a real board image (.jpg/.png) "
                             "to pass to evaluate_frame (MOCK_MODE=false only)")
    args = parser.parse_args()
    asyncio.run(main(args.image))
