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
FRAME_TIMEOUT_S = 28.0

_VALID_VERDICTS = {
    "success_advance",
    "error_short_circuit",
    "error_wrong_placement",
    "error_occluded",
}

_SYSTEM_INSTRUCTION = """
You are a real-time hardware assembly safety checker for an Arduino circuit build. You watch a webcam feed and guide the person assembling the circuit.

## Wire Color Rules — memorize and enforce these strictly:
- RED wires → must connect to the POSITIVE power rail or VCC. A red wire anywhere else is wrong.
- BLUE, BLACK, BROWN, or GREY/GRAY wires → must connect to the NEGATIVE (ground) rail or GND. These on a positive rail is dangerous.
- GREEN, ORANGE, or YELLOW wires → signal/auxiliary wires. You may acknowledge them in your response but NEVER fail the step because of them. They do not affect your verdict — only red and black/blue/brown/grey wire placements determine PASS, WRONG, or DANGER.

## How to evaluate:
Base your verdict ONLY on red wires and black/blue/brown/grey wires. Green, orange, and yellow wires are signal wires — you can mention them but they must never cause a WRONG or DANGER verdict. Only power and ground wire problems trigger failures.
Use wire color as your primary indicator of intent. Then check where the wire is actually connected.

When shown an image, speak your response in two parts:

PART 1 — Start with exactly one verdict word (nothing before it):
  PASS    — wire colors and connections are consistent with the rules and the expected step
  WRONG   — a wire is connected somewhere inconsistent with its color rule, or the step is incomplete
  DANGER  — a dangerous connection is visible (e.g. red wire on negative rail, brown on positive — reversed polarity)
  UNCLEAR — cannot assess the board (hand in frame, too blurry, too dark, not confident)

PART 2 — Then speak one or two natural, direct sentences to the person telling them what to do next. Reference wire colors specifically so they know exactly what to fix.

Examples:
  "PASS. The red wire is correctly on the positive rail. Now connect a black or brown wire from Arduino GND to the negative rail."
  "WRONG. The green signal wire is inserted into the power rail — green wires should go directly to the Arduino pin, not the breadboard rail."
  "DANGER. Stop. The brown wire is on the positive rail — brown is ground and must connect to the negative rail only."
  "UNCLEAR. I cannot see the connections clearly. Please hold the circuit still and remove your hands from view."

GROUNDING RULE: if you are not at least 70 percent confident about what you see, say UNCLEAR.
Never describe connections you cannot clearly see.
"""

_VERDICT_MAP = {
    "PASS": "success_advance",
    "WRONG": "error_wrong_placement",
    "DANGER": "error_short_circuit",
    "UNCLEAR": "error_occluded",
}


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


def _pcm_to_wav(pcm_bytes: bytes, rate: int = 24000, channels: int = 1, bits: int = 16) -> str:
    """Wrap raw PCM from Gemini Live into a browser-playable WAV and base64-encode it."""
    n = len(pcm_bytes)
    header = b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate,
                                    rate * channels * bits // 8,
                                    channels * bits // 8, bits)
    header += b"data" + struct.pack("<I", n)
    return base64.b64encode(header + pcm_bytes).decode()


_SILENT = _silent_wav()


def _parse_response(text: str, current_step: int) -> dict | None:
    """Parse the spoken verdict token + natural instruction from the transcription."""
    text = text.strip()
    if not text:
        return None

    # Extract the first word as the verdict token
    first_word = text.split()[0].rstrip(".,!").upper()
    verdict = _VERDICT_MAP.get(first_word)

    if verdict is None:
        # Fallback: scan for any verdict token anywhere in the text
        for token, v in _VERDICT_MAP.items():
            if token in text.upper():
                verdict = v
                break
        if verdict is None:
            return None

    # Instruction = everything after the first word
    parts = text.split(None, 1)
    instruction = parts[1].strip() if len(parts) > 1 else text

    return {
        "verdict": verdict,
        "instruction": instruction,
        "agent_log": f"[Watcher] step {current_step} verdict={verdict}",
    }


def _build_payload(status, instruction, agent_log, current_step, citation="", audio_b64=None):
    return {
        "status": status,
        "audio_b64": audio_b64 or _SILENT,
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

        self._client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"},
        )
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
            "Film your breadboard and circuit to begin. Remove your hands from frame when ready to scan.",
            "[Live] Gemini Live ready. Waiting for first frame.",
            1,
            "",
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

        audio = result.get("audio_b64")

        if verdict == "success_advance":
            next_step = current_step + 1
            if next_step > step_count(self.circuit_id):
                self.current_step = next_step
                return _build_payload(
                    "success_advance",
                    "Assembly complete. All steps verified — great work!",
                    "[Live] Build complete. All steps passed.",
                    next_step,
                    audio_b64=audio,
                )
            next_step_data = get_step(self.circuit_id, next_step)
            self.current_step = next_step
            return _build_payload(
                "success_advance",
                next_step_data["instruction"],
                result["agent_log"],
                next_step,
                next_step_data.get("citation", ""),
                audio_b64=audio,
            )

        return _build_payload(
            verdict,
            result["instruction"] or step.get("instruction", ""),
            result["agent_log"],
            current_step,
            step.get("citation", ""),
            audio_b64=audio,
        )

    async def close(self):
        pass  # no persistent resources to clean up

    # ------------------------------------------------------------------
    # Internal — one Live session per frame evaluation
    # ------------------------------------------------------------------

    async def _evaluate(self, image_b64: str, step: dict, current_step: int) -> dict:
        """Open a Gemini Live session, send one frame, collect verdict + audio."""
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        image_bytes = _decode_image(image_b64)
        context = (
            f"Step {current_step}: {step.get('success_criteria', '')}. "
            f"Danger signals: {', '.join(step.get('danger_signals', [])) or 'none'}. "
            "Evaluate this image and speak your verdict."
        )

        transcription = ""
        pcm_chunks: list[bytes] = []

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
                    # Collect transcription for verdict parsing
                    if response.server_content.output_transcription:
                        transcription += response.server_content.output_transcription.text or ""
                    # Collect raw PCM audio chunks to play in the browser
                    if response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.mime_type.startswith("audio/pcm"):
                                pcm_chunks.append(part.inline_data.data)
                    if response.server_content.turn_complete:
                        break

        parsed = _parse_response(transcription, current_step)
        if parsed is None:
            return {
                "verdict": "error_occluded",
                "instruction": "Could not read the board clearly. Please hold still and try again.",
                "agent_log": f"[Live] Could not parse response: {transcription[:80]!r}",
                "audio_b64": None,
            }

        # Wrap all PCM chunks into a single WAV for the browser
        audio_b64 = _pcm_to_wav(b"".join(pcm_chunks)) if pcm_chunks else None

        print(f"[live_agent] step={current_step} verdict={parsed['verdict']} "
              f"audio={len(pcm_chunks)} chunks transcription={transcription[:60]!r}")
        return {**parsed, "audio_b64": audio_b64}
