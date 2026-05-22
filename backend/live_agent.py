"""
live_agent.py — Gemini Live API session manager for the Physical IDE.

Replaces the request/response evaluate_frame + generate_next_step pattern
with a single persistent bidirectional Live API session per WebSocket
connection. Gemini sees frames as they arrive (up to 1fps) and streams
back structured verdicts and spoken instructions in real time.

Public interface matches AgentSession so main.py needs no changes:
    session = LiveAssemblySession(circuit_id)
    await session.start()           -> session_init payload
    await session.handle_frame(...) -> verdict payload
    await session.close()           -> cleanup
"""
import asyncio
import base64
import json
import os
import re
import struct

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types

from circuits import get_circuit, get_step, step_count

LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FRAME_TIMEOUT_S = 12.0

_VALID_VERDICTS = {
    "success_advance",
    "error_short_circuit",
    "error_wrong_placement",
    "error_occluded",
}

_SYSTEM_INSTRUCTION = """
You are a real-time hardware assembly safety checker watching a live webcam feed of an Arduino circuit being built step by step.

Your two jobs:
1. Is anything DANGEROUS? (reversed polarity, short circuit, power and ground crossed)
2. Does the assembly MATCH what is expected for the current step?

After each frame you receive, respond with ONLY a valid JSON object — no markdown, no explanation, no code fences:
{"verdict": "...", "instruction": "...", "agent_log": "..."}

verdict must be exactly one of:
  success_advance       — assembly looks correct for this step, safe to proceed
  error_short_circuit   — dangerous connection visible (reversed polarity, VCC shorted to GND)
  error_wrong_placement — something is connected in the wrong place or out of order
  error_occluded        — cannot assess the board (hand in frame, too blurry, too dark)

instruction: one or two plain spoken sentences — what the user should do now
agent_log: one short internal log line e.g. "[Watcher] step 2 verdict=success_advance"

GROUNDING RULE: if you are not confident (below ~70%), return error_occluded.
Never invent components you cannot clearly see.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_image(image_b64: str) -> bytes:
    if image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]
    return base64.b64decode(image_b64)


def _silent_wav(seconds: float = 0.5, rate: int = 8000) -> str:
    n = int(seconds * rate)
    data = b"\x00\x00" * n
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return base64.b64encode(header + data).decode()


_SILENT = _silent_wav()


def _parse_response(text: str, current_step: int) -> dict | None:
    """Extract a verdict JSON from the model's text response."""
    # Strip markdown fences if present
    text = re.sub(r"```[a-z]*\n?", "", text).strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object anywhere in the text
        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    verdict = data.get("verdict", "error_occluded")
    if verdict not in _VALID_VERDICTS:
        verdict = "error_occluded"

    return {
        "verdict": verdict,
        "instruction": data.get("instruction", ""),
        "agent_log": data.get("agent_log", f"[Live] step {current_step} verdict={verdict}"),
    }


def _build_payload(status, instruction, agent_log, current_step, citation=""):
    return {
        "status": status,
        "audio_b64": _SILENT,
        "image_b64": "",
        "text": instruction,
        "agent_log": agent_log,
        "current_step": current_step,
        "citation": citation,
    }


# ---------------------------------------------------------------------------
# Live session
# ---------------------------------------------------------------------------

class LiveAssemblySession:
    """
    One instance per WebSocket connection. Opens a persistent Gemini Live
    session and streams frames into it, collecting verdict responses.
    """

    def __init__(self, circuit_id: str):
        self.circuit_id = circuit_id
        self.circuit = get_circuit(circuit_id)
        self.current_step = 1

        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._frame_queue: asyncio.Queue = asyncio.Queue()
        self._result_queue: asyncio.Queue = asyncio.Queue()
        self._live_task: asyncio.Task | None = None
        self._ready = asyncio.Event()

    # ------------------------------------------------------------------
    # Public interface (same as AgentSession)
    # ------------------------------------------------------------------

    async def start(self) -> dict:
        """Open the Live session and return the session_init payload."""
        self._live_task = asyncio.create_task(self._run())
        # Wait until the Live connection is established (or fail fast)
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=8.0)
        except asyncio.TimeoutError:
            raise RuntimeError("Gemini Live session failed to connect within 8s")

        self.current_step = 1
        step = get_step(self.circuit_id, 1)
        return _build_payload(
            "session_init",
            step["instruction"],
            "[Live] Gemini Live session connected. Step 1 ready.",
            1,
            step.get("citation", ""),
        )

    async def handle_frame(self, image_b64: str, current_step: int) -> dict:
        """Send a frame to the Live session and return the verdict payload."""
        self.current_step = current_step
        step = get_step(self.circuit_id, current_step)
        if step is None:
            # Past the last step — build complete
            return _build_payload(
                "success_advance",
                "Assembly complete. All steps verified.",
                "[Live] Build complete.",
                current_step,
            )

        await self._frame_queue.put({
            "image_b64": image_b64,
            "step": current_step,
            "success_criteria": step.get("success_criteria", ""),
            "danger_signals": step.get("danger_signals", []),
            "instruction": step.get("instruction", ""),
            "citation": step.get("citation", ""),
        })

        try:
            result = await asyncio.wait_for(
                self._result_queue.get(), timeout=FRAME_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            return _build_payload(
                "error_occluded",
                "No response from the vision model — please hold still and try again.",
                "[Live] Frame evaluation timed out.",
                current_step,
            )

        verdict = result["verdict"]

        if verdict == "success_advance":
            next_step = current_step + 1
            if next_step > step_count(self.circuit_id):
                self.current_step = next_step
                return _build_payload(
                    "success_advance",
                    "Assembly complete. All steps verified — great work!",
                    "[Live] Build complete. All steps passed.",
                    next_step,
                )
            next_step_data = get_step(self.circuit_id, next_step)
            self.current_step = next_step
            return _build_payload(
                "success_advance",
                next_step_data["instruction"],
                result["agent_log"],
                next_step,
                next_step_data.get("citation", ""),
            )

        # Error verdict — stay on current step, surface the correction
        return _build_payload(
            verdict,
            result["instruction"] or step.get("instruction", ""),
            result["agent_log"],
            current_step,
            step.get("citation", ""),
        )

    async def close(self):
        if self._live_task:
            self._live_task.cancel()
            try:
                await self._live_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Internal — persistent Live session background task
    # ------------------------------------------------------------------

    async def _run(self):
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        try:
            async with self._client.aio.live.connect(
                model=LIVE_MODEL, config=config
            ) as session:
                self._ready.set()
                print(f"[live_agent] Gemini Live connected ({LIVE_MODEL})")

                # Run sender and receiver concurrently for the lifetime of
                # this WebSocket connection.
                await asyncio.gather(
                    self._sender(session),
                    self._receiver(session),
                )

        except asyncio.CancelledError:
            print("[live_agent] Live session closed (WebSocket disconnected)")
        except Exception as e:
            print(f"[live_agent] Live session error: {e!r}")
            self._ready.set()  # unblock start() so it can raise

    async def _sender(self, session):
        """Read frames from the queue and stream them to Gemini Live."""
        while True:
            frame_data = await self._frame_queue.get()

            context = (
                f"Step {frame_data['step']}: {frame_data['success_criteria']}. "
                f"Danger signals to watch for: {', '.join(frame_data['danger_signals']) or 'none'}."
            )
            await session.send_realtime_input(text=context)

            image_bytes = _decode_image(frame_data["image_b64"])
            await session.send_realtime_input(
                video=types.Blob(data=image_bytes, mime_type="image/jpeg")
            )

    async def _receiver(self, session):
        """Collect streamed text responses and put parsed verdicts in the result queue."""
        accumulated = ""
        async for response in session.receive():
            if response.server_content:
                if response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.text:
                            accumulated += part.text

                if response.server_content.turn_complete:
                    parsed = _parse_response(accumulated, self.current_step)
                    if parsed is None:
                        # Could not parse — return occluded so the demo never stalls
                        parsed = {
                            "verdict": "error_occluded",
                            "instruction": "Could not read the board clearly. Please hold still and try again.",
                            "agent_log": f"[Live] Failed to parse model response: {accumulated[:80]!r}",
                        }
                    await self._result_queue.put(parsed)
                    accumulated = ""
