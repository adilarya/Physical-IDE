# ESHWAR — Vision AI & Data / Compliance
**Role:** Gemini model integration, spatial verification pipeline, digital twin, audit trail.
**Stack:** Python, google-genai SDK, Vertex AI (Gemini 2.5 Flash, Imagen 3, Gemini TTS), MediaPipe (reference)

---

## How to Run Your Part Independently

You do not need the frontend or the full backend server running. You work directly against the `gemini_client.py` functions.

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run the vision pipeline test harness (mock mode — no keys needed)
python test_vision.py

# Run with real Gemini (needs API key)
MOCK_MODE=false GEMINI_API_KEY=your_key python test_vision.py

# Run with a real board photo against real Gemini
MOCK_MODE=false GEMINI_API_KEY=your_key python test_vision.py --image /path/to/board.jpg
```

Expected output (mock):
```
MOCK_MODE=True  |  image: blank placeholder frame
── evaluate_frame() ──────────────────────────────
  [OK] step=1 verdict='success_advance' conf=0.96 ...
  [OK] step=2 verdict='error_short_circuit' conf=0.92 ...
  [OK] step=3 verdict='success_advance' conf=0.96 ...
── generate_next_step() — normal steps ───────────
  [OK] step=1 text='Step 1 of 3 - Power rail...'
  ...
PASSED — all vision pipeline outputs validated
```

---

## Files You Own

```
backend/
  gemini_client.py    ← the entire vision and generation pipeline
  test_vision.py      ← your standalone test harness
```

You share `gemini_client.py` with Adil. He calls two public functions from it — those signatures are locked. You build everything inside them.

**Do not modify `agent.py` or `main.py`.** Those are Adil's. Your only integration surface is the two public functions in `gemini_client.py`.

---

## The Two Public Functions You Own

These are the complete interface between your work and the rest of the system. **Do not rename them, do not change their signatures, do not change their return shapes.**

### `evaluate_frame(image_b64, current_step, expected_state) → dict`

Called by the Watcher sub-agent every time the user removes their hands from the frame.

**Inputs:**
- `image_b64` — a base64-encoded JPEG of the breadboard, format: `"data:image/jpeg;base64,..."` or raw base64 string
- `current_step` — integer (1, 2, 3, ...)
- `expected_state` — string from `circuits.py` describing what the board should look like at this step (e.g. `"Red wire visible from Arduino 5V to breadboard + rail"`)

**Required output:**
```python
{
    "verdict": str,           # one of the four valid verdicts below
    "confidence": float,      # 0.0 – 1.0
    "detected_components": list[str],  # what the model actually saw
    "reasoning": str,         # short explanation of the verdict
}
```

**Valid verdicts (exactly these four strings, nothing else):**
- `"success_advance"` — board matches the expected state, user can proceed
- `"error_short_circuit"` — dangerous electrical connection detected (e.g. VCC directly to GND, LED bridging power rails)
- `"error_wrong_placement"` — a component is present but in the wrong position or row
- `"error_occluded"` — board cannot be assessed (hand in frame, shadow, blur, or confidence below 0.7)

**Grounding rule (must be enforced in code, not just prompt):**
```python
if result["confidence"] < 0.7:
    result["verdict"] = "error_occluded"
```

This is already implemented in `_real_evaluate_frame`. Do not remove it.

---

### `generate_next_step(step_index, context) → dict`

Called by the Planner sub-agent to produce the interleaved instruction payload.

**Inputs:**
- `step_index` — integer (1, 2, 3) or the string `"done"` for build complete
- `context` — dict with one of three shapes:

```python
# Normal step instruction
{"fresh": True, "step": step_dict_from_circuits}

# Correction after an error verdict
{"correction": True, "verdict": "error_short_circuit", "step": step_dict, "watcher": watcher_result_dict}

# Build complete
{"complete": True}
```

**Required output:**
```python
{
    "audio_b64": str,   # base64-encoded WAV audio (no data: prefix)
    "image_b64": str,   # full data URI: "data:image/png;base64,..." or SVG equivalent
    "text": str,        # the instruction text shown in the UI
    "agent_log": str,   # a short internal log string shown in the agent log panel
}
```

**Rules:**
- `audio_b64` must NOT have a `data:` prefix — the browser's `decodeAudioData()` strips it and fails if the prefix is present
- `image_b64` MUST have a `data:` prefix — the browser renders it as an `<img src>` directly
- `text` must never be empty
- `agent_log` must never be empty

---

## What You Need to Build

### 1. Real `evaluate_frame` — Gemini 2.5 Flash Vision

The stub `_real_evaluate_frame` is already written in `gemini_client.py`. Your job is to:

**a) Verify it works with the actual google-genai SDK installed:**
```bash
MOCK_MODE=false GEMINI_API_KEY=... python test_vision.py --image your_board.jpg
```

**b) Tune the system prompt (`_SYSTEM_EVAL`) for accuracy:**

The current prompt is a good starting point. You need to test it against real breadboard photos and iterate. Key things to tune:
- The model must reliably distinguish `error_short_circuit` from `error_wrong_placement` — these have different safety implications
- The model must return `error_occluded` when the image is blurry, not guess
- The model must identify LED polarity correctly (longer leg = anode)

**c) Add step-specific context to the prompt:**

The current `_real_evaluate_frame` builds a generic prompt. Improve it by including:
- The step's `expected_components` list (from `circuits.py`)
- The step's `common_errors` list (the known failure modes for that step)
- Explicit coordinates if you have them (e.g. "anode in row 10, column F")

Example enhanced prompt addition:
```python
prompt = (
    f"Current step index: {current_step}\n"
    f"Expected board state: {expected_state}\n"
    f"Expected components: {', '.join(step.get('expected_components', []))}\n"
    f"Common errors to watch for: {', '.join(step.get('common_errors', []))}\n"
    "Assess the image now and return the strict JSON verdict."
)
```

**d) Enforce the grounding rule post-call:**
```python
if data.get("confidence", 1.0) < 0.7:
    data["verdict"] = "error_occluded"
if data.get("verdict") not in _VALID_VERDICTS:
    data["verdict"] = "error_occluded"
```
This is already in the code. Keep it. It is the safety net that prevents the model from hallucinating bad verdicts.

---

### 2. Real `generate_next_step` — Text + Image + Audio

The stub has two strategies: `single_pass` and `parallel`. Use `GEMINI_STRATEGY=parallel` (the default) — it is more reliable because each leg degrades independently.

**a) Text generation (`_gen_text`):**

Model: `gemini-2.5-flash` (or `GEMINI_TEXT_MODEL` env var).

The current prompt is minimal. Improve it to:
- Keep instructions to 1-2 sentences maximum (the UI has limited space)
- Use plain, direct language — no markdown, no asterisks
- For corrections, lead with the specific problem: "The LED is reversed — the short leg must go in row 11, not row 10."
- For `complete`, be celebratory but brief

**b) Image generation (`_gen_image`):**

Model: `imagen-3.0-generate-002` (or `GEMINI_IMAGE_MODEL` env var).

The `_IMAGE_STYLE` string is already defined — it must appear verbatim in the prompt. This is the visual language for the instruction diagrams.

**Important:** The Imagen API call uses `generate_images`, not `generate_content`. Verify the method signature matches the installed SDK version:
```python
resp = await client.aio.models.generate_images(
    model="imagen-3.0-generate-002",
    prompt=f"{instr}. Style: {_IMAGE_STYLE}.",
    config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="4:3"),
)
raw = resp.generated_images[0].image.image_bytes
```
If the SDK version has a different method name or response shape, adjust accordingly. The fallback to the mock SVG is already in place — it will catch failures during development.

**c) Audio generation (`_gen_audio`):**

Model: `gemini-2.5-flash-preview-tts` (or `GEMINI_TTS_MODEL` env var).

**Critical issue documented in the code:** Gemini TTS may return raw 24kHz 16-bit PCM audio, not a fully-formed WAV file. The browser's `decodeAudioData()` requires a valid WAV header. If the audio plays as silence or throws a decode error, you need to wrap the raw PCM in a WAV header:

```python
import struct

def _wrap_pcm_as_wav(pcm_bytes, sample_rate=24000, channels=1, bits=16):
    n = len(pcm_bytes)
    header = b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate,
                                    sample_rate * channels * bits // 8,
                                    channels * bits // 8, bits)
    header += b"data" + struct.pack("<I", n)
    return header + pcm_bytes
```

Use `_build_silent_wav` as a reference — it already constructs a valid WAV header.

After getting the raw audio bytes from the TTS response:
```python
# Check if it's already a WAV (starts with RIFF)
if not inline.data.startswith(b"RIFF"):
    audio_bytes = _wrap_pcm_as_wav(inline.data)
else:
    audio_bytes = inline.data
return base64.b64encode(audio_bytes).decode()
```

---

### 3. Fiducial Marker System & Coordinate Grid

This is the technical foundation of the "sub-millimeter auditing" claim in the enterprise pitch.

**What it is:** Fiducial markers are small, machine-readable patterns (like ArUco markers) placed at known positions on the breadboard. The camera detects them, and from their known real-world positions the system can compute a coordinate mapping — so "row 10, column F" maps to a precise pixel region in the camera image.

**What you need to implement:**

**a) Marker detection** — use OpenCV's ArUco detector (already available if OpenCV is installed):
```python
import cv2

def detect_fiducials(image_bytes):
    """Detect ArUco markers in the image and return their corner coordinates."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    corners, ids, _ = detector.detectMarkers(img)
    return corners, ids
```

**b) Coordinate mapping** — given the detected marker corners and their known real-world positions (defined by you), compute a homography matrix that maps pixel coordinates to breadboard coordinates (row/column).

**c) Integration with `evaluate_frame`** — if fiducials are detected, pass the coordinate-mapped region of interest to Gemini as additional context in the prompt. If fiducials are not detected, fall back to the standard whole-image evaluation.

**For the demo:** At minimum, place 2-4 ArUco markers at the corners of the breadboard. Print them and tape them down. The demo setup should always have them in the same position.

---

### 4. Digital Twin — Ground Truth Schematic

The digital twin is the authoritative "correct state" for each step. It is currently represented in `circuits.py` as text strings (`success_criteria`, `expected_components`). For the vision model to be accurate, the digital twin needs to be richer.

**Enhance `circuits.py` to include spatial data:**

```python
{
    "index": 2,
    "instruction": "Place the LED on the breadboard...",
    "expected_components": ["led_at_row_10_11"],
    "success_criteria": "LED with anode in row 10, cathode in row 11",
    "spatial": {
        "led_anode": {"row": 10, "col": "F"},
        "led_cathode": {"row": 11, "col": "F"},
    },
    "common_errors": ["led_reversed", "led_short_circuit_to_ground"],
    "citation": "LED polarity guide - anode vs cathode, p.1",
}
```

These `spatial` coordinates feed into:
1. The Gemini evaluation prompt (as specific expected positions)
2. The fiducial coordinate grid (to define which pixel region to zoom into)
3. The instruction image generation (to highlight the correct position in the diagram)

---

### 5. Audit Trail Logging

Every assembly step verification needs to be logged to the cloud for the compliance story. This is what makes the demo relevant to aerospace and industrial QA.

**Minimum implementation for the demo:**

Log each `evaluate_frame` call result to a structured record. For the hackathon, writing to a local JSON file or Google Cloud Logging is sufficient — full Firestore integration is a stretch goal.

```python
import json
import datetime

def log_audit_event(circuit_id, step, verdict, confidence, reasoning, session_id):
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "session_id": session_id,
        "circuit_id": circuit_id,
        "step": step,
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "compliant": verdict == "success_advance",
    }
    # For demo: write to audit_log.jsonl (one JSON object per line)
    with open("audit_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")
    return record
```

**Expose the audit trail as an HTTP endpoint** so it can be shown during the demo:
```python
# Add to main.py (coordinate with Adil)
@app.get("/audit")
def get_audit_log():
    try:
        with open("audit_log.jsonl") as f:
            records = [json.loads(line) for line in f if line.strip()]
        return {"records": records, "count": len(records)}
    except FileNotFoundError:
        return {"records": [], "count": 0}
```

**The compliance pitch:** "Every physical assembly action is logged with a timestamp, confidence score, and pass/fail verdict — mathematically verified and auditable, meeting FAA/ISO documentation requirements."

---

## GEMINI_STRATEGY Explained

Set via env var `GEMINI_STRATEGY`. Two options:

| Strategy | How it works | When to use |
|---|---|---|
| `parallel` (default) | 3 separate API calls: text, image, audio run concurrently with `asyncio.gather`. Each leg falls back independently. | Always — safer for a live demo |
| `single_pass` | 1 API call requesting TEXT + IMAGE + AUDIO together | Experimental — the multi-modal output surface is not fully verified |

Use `parallel` for the demo. Use `single_pass` only if you have verified that the SDK supports combined modalities for the chosen model.

---

## Environment Variables You Control

```bash
MOCK_MODE=true              # true = no API calls (default), false = real Gemini
GEMINI_API_KEY=...          # required when MOCK_MODE=false
GEMINI_STRATEGY=parallel    # parallel | single_pass
GEMINI_VISION_MODEL=gemini-2.5-flash        # model for evaluate_frame
GEMINI_TEXT_MODEL=gemini-2.5-flash          # model for text generation
GEMINI_IMAGE_MODEL=imagen-3.0-generate-002  # model for image generation
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts  # model for audio generation
```

---

## Testing Your Work

**Test 1 — Mock mode (always passes):**
```bash
python test_vision.py
```

**Test 2 — Real Gemini, no image:**
```bash
MOCK_MODE=false GEMINI_API_KEY=... python test_vision.py
```
A blank 1x1 JPEG is sent. Gemini should return `error_occluded` (it can't see anything meaningful). If it returns `success_advance`, the grounding rule is not being enforced.

**Test 3 — Real Gemini, real image:**
```bash
MOCK_MODE=false GEMINI_API_KEY=... python test_vision.py --image board_step2_correct.jpg
```
Should return `success_advance` for a correctly assembled step 2.

```bash
MOCK_MODE=false GEMINI_API_KEY=... python test_vision.py --image board_step2_short.jpg
```
Should return `error_short_circuit` for a board with a dangerous connection.

**Test 4 — Audio WAV validity:**
After running in real mode, decode the returned `audio_b64` and check it plays:
```python
import base64, wave, io
data = base64.b64decode(your_audio_b64)
w = wave.open(io.BytesIO(data))
print(w.getframerate(), w.getnchannels(), w.getnframes())
# Should print valid values, not throw an exception
```

---

## Definition of Done

- [ ] `python test_vision.py` passes in mock mode
- [ ] `evaluate_frame` with a real board photo returns the correct verdict for step 1, 2 (short circuit case), and step 3
- [ ] `evaluate_frame` returns `error_occluded` when confidence < 0.7 (grounding rule enforced)
- [ ] `generate_next_step` returns valid audio, image, and text for all 3 steps and all 3 correction types
- [ ] Audio is a valid WAV file that `decodeAudioData()` can decode in the browser
- [ ] Image is a `data:` URI the browser can render as `<img src>`
- [ ] Fiducial detection works on a real photo with printed ArUco markers
- [ ] Audit trail writes a `audit_log.jsonl` entry for every `evaluate_frame` call
- [ ] `MOCK_MODE=false` with `GEMINI_API_KEY` produces all four verdict types correctly across the 3-step circuit
