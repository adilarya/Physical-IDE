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
        """Return the session_init payload. Live sessions are opened per-frame."""
        self.current_step = 1
        step = get_step(self.circuit_id, 1)
        print(f"[live_agent] Session ready ({LIVE_MODEL})")
        return _build_payload(
            "session_init",
            step["instruction"],
            "[Live] Gemini Live ready. Step 1 ready.",
            1,
            step.get("citation", ""),
        )

    async def handle_frame(self, image_b64: str, current_step: int) -> dict:
        """Open a fresh Live session, evaluate this frame, return verdict payload."""
        self.current_step = current_step
        step = get_step(self.circuit_id, current_step)
        if step is None:
            return _build_payload(
                "success_advance",
                "Assembly complete. All steps verified — great work!",
                "[Live] Build complete.",
                current_step,
            )

        try:
            result = await asyncio.wait_for(
                self._evaluate(image_b64, step, current_step),
                timeout=FRAME_TIMEOUT_S,
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

        return _build_payload(
            verdict,
            result["instruction"] or step.get("instruction", ""),
            result["agent_log"],
            current_step,
            step.get("citation", ""),
        )

    async def close(self):
        pass  # no persistent resources to clean up

    # ------------------------------------------------------------------
    # Internal — one Live session per frame evaluation
    # ------------------------------------------------------------------

    async def _evaluate(self, image_b64: str, step: dict, current_step: int) -> dict:
        """Open a Gemini Live session, send one frame, collect the verdict."""
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        image_bytes = _decode_image(image_b64)
        context = (
            f"Step {current_step}: {step.get('success_criteria', '')}. "
            f"Danger signals: {', '.join(step.get('danger_signals', [])) or 'none'}. "
            "Evaluate this image and give your verdict."
        )

        accumulated = ""
        async with self._client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[
                        types.Part(text=context),
                        types.Part(
                            inline_data=types.Blob(
                                data=image_bytes, mime_type="image/jpeg"
                            )
                        ),
                    ],
                ),
                turn_complete=True,
            )

            async for response in session.receive():
                if response.server_content:
                    if response.server_content.output_transcription:
                        accumulated += response.server_content.output_transcription.text or ""
                    if response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                accumulated += part.text
                    if response.server_content.turn_complete:
                        break

        parsed = _parse_response(accumulated, current_step)
        if parsed is None:
            return {
                "verdict": "error_occluded",
                "instruction": "Could not read the board clearly. Please hold still and try again.",
                "agent_log": f"[Live] Could not parse response: {accumulated[:80]!r}",
            }
        print(f"[live_agent] step={current_step} verdict={parsed['verdict']} raw={accumulated[:60]!r}")
        return parsed
