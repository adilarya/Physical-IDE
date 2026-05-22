"""
gemini_client.py - wrapper around the google-genai SDK with a full mock fallback.

TODO: verify SDK surface at 11:30, choose strategy by 12:00
      Unverified: single-pass TEXT+IMAGE+AUDIO modalities, Imagen model id,
      Gemini TTS audio container (likely raw PCM -> needs WAV wrapping).

PUBLIC INTERFACE (stable - agent.py depends on this, do NOT change signatures):

    async evaluate_frame(image_b64, current_step, expected_state) -> dict
        -> {"verdict", "confidence", "detected_components", "reasoning"}
           verdict is one of:
             success_advance | error_short_circuit
             error_occluded  | error_wrong_placement

    async generate_next_step(step_index, context) -> dict
        -> {"audio_b64", "image_b64", "text", "agent_log"}

MOCK_MODE=true  (default) : zero API calls, deterministic canned responses.
MOCK_MODE=false           : real google-genai calls; strategy via GEMINI_STRATEGY.
                            Real failures fall back to mock so the demo survives.
"""
import os
import json
import base64
import struct
import asyncio

try:  # optional - lets local dev use a backend/.env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
GEMINI_STRATEGY = os.getenv("GEMINI_STRATEGY", "parallel")   # single_pass | parallel
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_VALID_VERDICTS = {
    "success_advance", "error_short_circuit",
    "error_occluded", "error_wrong_placement",
}

# The image-generation style string. These keywords MUST appear verbatim in the
# real Imagen / Gemini image prompt - do not paraphrase.
_IMAGE_STYLE = (
    "isometric vector art, Lego-style assembly instruction, flat background, "
    "clean lines, top-down perspective, minimal shading, "
    "single component highlighted in orange"
)


# ===========================================================================
#  PUBLIC INTERFACE
# ===========================================================================

async def evaluate_frame(image_b64, current_step, expected_state):
    """WATCHER backend: is the physical board in the expected state?"""
    if MOCK_MODE:
        return _mock_evaluate(current_step)
    try:
        return await _real_evaluate_frame(image_b64, current_step, expected_state)
    except Exception as e:  # noqa: BLE001 - demo must never hard-crash
        print(f"[gemini_client] real evaluation failed ({e!r}) - falling back to mock")
        return _mock_evaluate(current_step)


async def generate_next_step(step_index, context):
    """PLANNER backend: produce the next interleaved (text+image+audio) turn."""
    if MOCK_MODE:
        return _mock_generate(step_index, context)
    try:
        if GEMINI_STRATEGY == "single_pass":
            return await _real_generate_single_pass(step_index, context)
        return await _real_generate_parallel(step_index, context)
    except Exception as e:  # noqa: BLE001 - demo must never hard-crash
        print(f"[gemini_client] real generation failed ({e!r}) - falling back to mock")
        return _mock_generate(step_index, context)


def reset_mock_state():
    """Called on start_session so repeated demo runs replay the scripted beat."""
    _mock_attempts.clear()


# ===========================================================================
#  MOCK IMPLEMENTATION
# ===========================================================================

# Process-global per-step attempt counter.
# TODO: not multi-session safe - fine for a single-session demo only.
_mock_attempts = {}


def _mock_evaluate(current_step):
    n = _mock_attempts.get(current_step, 0)
    _mock_attempts[current_step] = n + 1

    # Scripted demo beat: step 2 first attempt = short circuit, retry = success.
    if current_step == 2 and n == 0:
        return {
            "verdict": "error_short_circuit",
            "confidence": 0.92,
            "detected_components": ["led_cathode_in_positive_rail"],
            "reasoning": "LED cathode detected in the +5V rail - a direct short "
                         "across the supply.",
        }
    return {
        "verdict": "success_advance",
        "confidence": 0.96,
        "detected_components": [f"step_{current_step}_components_ok"],
        "reasoning": "Physical board state matches the expected configuration.",
    }


def _mock_generate(step_index, context):
    if context.get("correction"):
        verdict = context.get("verdict", "error_wrong_placement")
        c = _CORRECTIONS.get(verdict, _CORRECTIONS["error_wrong_placement"])
        label = verdict.replace("error_", "").replace("_", " ").upper()
        return {
            "audio_b64": _SILENT_WAV,
            "image_b64": _mock_image("warning", "CORRECTION REQUIRED", label),
            "text": c["text"],
            "agent_log": c["log"],
        }
    s = _STEPS.get(step_index, _DONE_STEP)
    return {
        "audio_b64": _SILENT_WAV,
        "image_b64": _mock_image(s["kind"], s["label"], s["caption"]),
        "text": s["text"],
        "agent_log": s["log"],
    }


# --- canned step content ----------------------------------------------------

_STEPS = {
    1: dict(
        kind="wire", label="STEP 1 / 3  -  POWER RAIL",
        caption="Red jumper:  Arduino 5V  ->  breadboard (+) rail",
        text="Step 1 of 3 - Power rail. Take a red jumper wire and connect the "
             "Arduino 5V pin to the positive rail of the breadboard. This powers "
             "the entire circuit.",
        log="[Planner] Generated Step 1 (5V power rail). Modalities: text+image+audio.",
    ),
    2: dict(
        kind="wire", label="STEP 2 / 3  -  GROUND RAIL",
        caption="Black jumper:  Arduino GND  ->  breadboard (-) rail",
        text="Step 2 of 3 - Ground rail. Take a black jumper wire and connect the "
             "Arduino GND pin to the negative rail of the breadboard. This completes "
             "the power circuit.",
        log="[Planner] Generated Step 2 (GND rail).",
    ),
    3: dict(
        kind="resistor", label="STEP 3 / 3  -  SERVO",
        caption="Servo: brown -> (-) rail,  red -> (+) rail,  orange -> pin 9",
        text="Step 3 of 3 - Servo connection. Connect the servo brown wire to the "
             "negative rail, red wire to the positive rail, and orange signal wire "
             "to Arduino digital pin 9.",
        log="[Planner] Generated Step 3 (servo wiring).",
    ),
}

_DONE_STEP = dict(
    kind="done", label="BUILD COMPLETE",
    caption="Servo control circuit verified  -  3 / 3 steps",
    text="Assembly complete. All three steps verified - your servo control circuit "
         "is wired correctly. Upload a sweep sketch to the Arduino to test it.",
    log="[Planner] Build complete. 3/3 steps verified.",
)

_CORRECTIONS = {
    "error_short_circuit": dict(
        text="SAFETY STOP. The servo power wires appear reversed - red must go to "
             "the positive rail and brown to the negative rail. Swapped polarity "
             "will damage the servo immediately. Disconnect and rewire before continuing.",
        log="[Planner] SAFETY INTERRUPT - servo polarity reversal detected. Re-scan required.",
    ),
    "error_occluded": dict(
        text="I can't see the board clearly - a hand or shadow is covering the "
             "work area. Pull back and hold still so I can re-scan.",
        log="[Planner] View occluded - requesting a clean frame.",
    ),
    "error_wrong_placement": dict(
        text="That wire isn't in the expected position. Re-check which rail or pin "
             "it connects to against the instruction and reposition before continuing.",
        log="[Planner] Wrong placement detected - correction issued.",
    ),
}


# --- placeholder media generators ------------------------------------------

def _build_silent_wav(seconds=1.0, rate=8000):
    """A valid 1s 16-bit PCM mono WAV - decodeAudioData() accepts it; plays silent."""
    n = int(seconds * rate)
    data = b"\x00\x00" * n
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return base64.b64encode(header + data).decode()


_SILENT_WAV = _build_silent_wav()


def _svg_data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()


def _board_base():
    """Static breadboard SVG fragment (dark mission-control styling)."""
    holes = []
    for r in range(5):
        for c in range(18):
            cx = 110 + c * 30
            cy = 168 + r * 34
            holes.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="#c8c0a4"/>')
    return (
        '<rect x="80" y="120" width="560" height="240" rx="14" '
        'fill="#e9e3d2" stroke="#bdb59a" stroke-width="3"/>'
        '<line x1="110" y1="142" x2="610" y2="142" stroke="#e23b3b" stroke-width="4"/>'
        '<line x1="110" y1="338" x2="610" y2="338" stroke="#3b6ee2" stroke-width="4"/>'
        + "".join(holes)
    )


# component highlights drawn in orange on top of the board
_HIGHLIGHT = {
    "wire": (
        '<line x1="180" y1="64" x2="180" y2="142" stroke="#f8932b" '
        'stroke-width="10" stroke-linecap="round"/>'
        '<circle cx="180" cy="64" r="9" fill="#f8932b"/>'
        '<text x="180" y="52" fill="#f8932b" font-family="Arial" font-size="13" '
        'text-anchor="middle">5V</text>'
    ),
    "led": (
        '<circle cx="320" cy="236" r="26" fill="#f8932b" stroke="#c2700f" stroke-width="3"/>'
        '<line x1="312" y1="262" x2="312" y2="320" stroke="#f8932b" stroke-width="6"/>'
        '<line x1="328" y1="262" x2="328" y2="304" stroke="#f8932b" stroke-width="6"/>'
    ),
    "resistor": (
        '<rect x="360" y="300" width="120" height="34" rx="8" fill="#f8932b" '
        'stroke="#c2700f" stroke-width="3"/>'
        '<line x1="336" y1="317" x2="360" y2="317" stroke="#f8932b" stroke-width="6"/>'
        '<line x1="480" y1="317" x2="520" y2="317" stroke="#f8932b" stroke-width="6"/>'
    ),
}

_WARNING_SHAPE = (
    '<polygon points="360,150 470,330 250,330" fill="#f8932b" '
    'stroke="#c2700f" stroke-width="4"/>'
    '<rect x="352" y="205" width="16" height="70" rx="6" fill="#1b1205"/>'
    '<circle cx="360" cy="300" r="11" fill="#1b1205"/>'
)

_DONE_SHAPE = (
    '<circle cx="360" cy="240" r="80" fill="#1f9d57" stroke="#0d6e38" stroke-width="5"/>'
    '<polyline points="320,242 350,272 408,210" fill="none" stroke="#ffffff" '
    'stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>'
)


def _mock_image(kind, label, caption):
    """Build a placeholder instruction image as an inline SVG data URI."""
    width, height = 720, 440
    if kind in _HIGHLIGHT:
        body = _board_base() + _HIGHLIGHT[kind]
    elif kind == "warning":
        body = _WARNING_SHAPE
    elif kind == "done":
        body = _DONE_SHAPE
    else:
        body = _board_base()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#0f1729"/>'
        f'<text x="{width // 2}" y="42" fill="#f8932b" font-family="Arial" '
        f'font-size="22" font-weight="bold" text-anchor="middle">{label}</text>'
        f'{body}'
        f'<text x="{width // 2}" y="{height - 22}" fill="#9fb0c9" '
        f'font-family="Arial" font-size="15" text-anchor="middle">{caption}</text>'
        f'</svg>'
    )
    return _svg_data_uri(svg)


# ===========================================================================
#  REAL google-genai IMPLEMENTATION
#  Lazily imported so MOCK_MODE works even if the SDK is not installed.
# ===========================================================================

_genai_client = None


def _client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set but MOCK_MODE=false")
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


def _decode_image(image_b64):
    raw = image_b64.split(",", 1)[1] if image_b64.startswith("data:") else image_b64
    return base64.b64decode(raw)


_SYSTEM_EVAL = (
    "You are the Watcher sub-agent of a hardware-assembly tutor. You receive a "
    "webcam image of an Arduino breadboard mid-build plus a description of the "
    "expected state for the current step. Compare the image to the expected "
    "state and respond with STRICT JSON only:\n"
    '{"verdict": "...", "confidence": 0.0-1.0, "detected_components": [...], '
    '"reasoning": "..."}\n'
    "verdict must be exactly one of:\n"
    "  success_advance        - board matches the expected state\n"
    "  error_short_circuit    - a dangerous connection exists (e.g. VCC to GND)\n"
    "  error_wrong_placement  - a component/wire is present but mislocated\n"
    "  error_occluded         - the board cannot be assessed (hand/shadow/blur)\n"
    "GROUNDING RULE: if your confidence is below 0.7 you MUST return "
    '"error_occluded" instead of guessing. Never invent components you cannot '
    "clearly see."
)


async def _real_evaluate_frame(image_b64, current_step, expected_state):
    from google.genai import types
    client = _client()
    prompt = (
        f"Current step index: {current_step}\n"
        f"Expected board state: {expected_state}\n"
        "Assess the image now and return the strict JSON verdict."
    )
    resp = await client.aio.models.generate_content(
        model=os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash"),
        contents=[
            types.Part.from_bytes(data=_decode_image(image_b64), mime_type="image/jpeg"),
            types.Part.from_text(text=prompt),
        ],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_EVAL,
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    data = json.loads(resp.text)
    # Enforce the grounding rule even if the model ignored it.
    if data.get("confidence", 1.0) < 0.7:
        data["verdict"] = "error_occluded"
    if data.get("verdict") not in _VALID_VERDICTS:
        data["verdict"] = "error_occluded"
    data.setdefault("confidence", 0.0)
    data.setdefault("detected_components", [])
    data.setdefault("reasoning", "")
    return data


def _instruction_text(step_index, context):
    step = context.get("step") or {}
    instr = step.get("instruction", f"assembly step {step_index}")
    if context.get("correction"):
        instr = f"CORRECTION for {context.get('verdict', 'error')}: {instr}"
    if context.get("complete"):
        instr = "Final confirmation: the build is complete and verified."
    return instr


async def _real_generate_single_pass(step_index, context):
    """Optimistic path: one call returning TEXT + IMAGE + AUDIO together."""
    # TODO verify: does google-genai support response_modalities with AUDIO+IMAGE
    #              in a single generate_content call for the chosen model?
    from google.genai import types
    client = _client()
    instr = _instruction_text(step_index, context)
    prompt = (
        f"Generate one assembly-tutor turn for: {instr}\n"
        f"Return spoken narration (audio), an instruction diagram (image) drawn as "
        f"{_IMAGE_STYLE}, and a one-sentence text caption."
    )
    resp = await client.aio.models.generate_content(
        model=os.getenv("GEMINI_MULTIMODAL_MODEL", "gemini-2.5-flash"),
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE", "AUDIO"],  # TODO unverified surface
        ),
    )
    text, image_b64, audio_b64 = "", None, None
    for part in resp.candidates[0].content.parts:
        if getattr(part, "text", None):
            text = part.text
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            mime = inline.mime_type or ""
            payload = base64.b64encode(inline.data).decode()
            if mime.startswith("image/"):
                image_b64 = f"data:{mime};base64,{payload}"
            elif mime.startswith("audio/"):
                audio_b64 = payload  # TODO may be raw PCM - wrap as WAV if so
    return {
        "audio_b64": audio_b64 or _SILENT_WAV,
        "image_b64": image_b64 or _mock_image("warning", "IMAGE PENDING",
                                              "single_pass returned no image"),
        "text": text or instr,
        "agent_log": "[Planner] single_pass generation complete.",
    }


async def _real_generate_parallel(step_index, context):
    """Robust path: three concurrent calls, each leg degrades independently."""
    instr = _instruction_text(step_index, context)
    text, image_b64, audio_b64 = await asyncio.gather(
        _gen_text(instr), _gen_image(instr), _gen_audio(instr),
        return_exceptions=True,
    )
    if isinstance(text, Exception) or not text:
        text = instr
    if isinstance(image_b64, Exception) or not image_b64:
        image_b64 = _mock_image("warning", "IMAGE PENDING", "image leg failed")
    if isinstance(audio_b64, Exception) or not audio_b64:
        audio_b64 = _SILENT_WAV
    return {
        "audio_b64": audio_b64,
        "image_b64": image_b64,
        "text": text,
        "agent_log": "[Planner] parallel generation complete (text+image+audio).",
    }


async def _gen_text(instr):
    from google.genai import types
    client = _client()
    resp = await client.aio.models.generate_content(
        model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash"),
        contents=[
            "Write one short, friendly spoken instruction for this hardware "
            f"assembly step. One or two sentences, no markdown: {instr}"
        ],
        config=types.GenerateContentConfig(temperature=0.4),
    )
    return resp.text.strip()


async def _gen_image(instr):
    # TODO verify Imagen model id + method signature against installed google-genai.
    from google.genai import types
    client = _client()
    resp = await client.aio.models.generate_images(
        model=os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002"),
        prompt=f"{instr}. Style: {_IMAGE_STYLE}.",
        config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="4:3"),
    )
    raw = resp.generated_images[0].image.image_bytes
    return "data:image/png;base64," + base64.b64encode(raw).decode()


async def _gen_audio(instr):
    # TODO verify TTS model id + audio container. Gemini TTS commonly returns raw
    #      24kHz PCM - if so it must be wrapped in a WAV header before the browser
    #      can decodeAudioData() it. Reuse _build_silent_wav's header logic.
    from google.genai import types
    client = _client()
    resp = await client.aio.models.generate_content(
        model=os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        contents=[f"Say this clearly for a hardware tutorial: {instr}"],
        config=types.GenerateContentConfig(response_modalities=["AUDIO"]),
    )
    for part in resp.candidates[0].content.parts:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data and (inline.mime_type or "").startswith("audio/"):
            return base64.b64encode(inline.data).decode()
    raise RuntimeError("no audio part in TTS response")
