"""
tutorial.py — Phase 1: Tutorial generation engine.

Takes a natural language goal ("make an LED blink") and generates a
step-by-step Lego-style circuit assembly guide, streaming each step back
over the WebSocket as it's ready.

Models used:
- gemini-3.5-flash        — circuit planning (JSON step list)
- gemini-3.1-flash-image-preview — Lego-style isometric diagram per step
"""
import asyncio
import base64
import json
import os

from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PLANNER_MODEL = os.getenv("GEMINI_PLANNER_MODEL", "gemini-3.5-flash")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")

_IMAGE_STYLE = (
    "isometric top-down vector illustration, Lego-style hardware assembly instruction, "
    "clean flat background, bold outlines, single component highlighted in orange, "
    "breadboard and Arduino visible, minimal shading, instructional diagram style"
)

_PLANNER_PROMPT = """
You are a hardware electronics instructor. The user wants to build: {goal}

Generate a clear step-by-step guide to wire this circuit on a breadboard with an Arduino.
Each step should be a single physical action (place one wire, insert one component).
Use standard wire color conventions: red=power, black/brown=ground, green/yellow=signal.

Respond with ONLY a JSON array of steps, no markdown, no explanation:
[
  {{
    "step": 1,
    "title": "Short title (3-5 words)",
    "instruction": "One clear sentence describing exactly what to physically do.",
    "wire_color": "red|black|brown|green|yellow|none"
  }},
  ...
]

Limit to 4 steps maximum. Make each step concrete and beginner-friendly.
"""


async def generate_tutorial(goal: str, send_fn):
    """
    Generate a tutorial for the given goal, calling send_fn for each event.
    send_fn is an async callable that accepts a dict and sends it over WebSocket.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    # --- Step 1: Plan the circuit -------------------------------------------
    await send_fn({"event": "tutorial_thinking", "text": f"Planning your circuit for: {goal}..."})

    try:
        plan_resp = await client.aio.models.generate_content(
            model=PLANNER_MODEL,
            contents=[_PLANNER_PROMPT.format(goal=goal)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        steps = json.loads(plan_resp.text)
        if not isinstance(steps, list):
            raise ValueError("planner did not return a list")
    except Exception as e:
        await send_fn({"event": "tutorial_error", "text": f"Could not plan circuit: {e}"})
        return

    await send_fn({"event": "tutorial_start", "total_steps": len(steps), "goal": goal})

    # --- Step 2: Generate image + send each step ----------------------------
    for s in steps:
        step_num = s.get("step", 1)
        title = s.get("title", f"Step {step_num}")
        instruction = s.get("instruction", "")
        wire_color = s.get("wire_color", "none")

        # Generate Lego-style diagram for this step
        image_b64 = await _generate_step_image(client, title, instruction, wire_color, step_num)

        await send_fn({
            "event": "tutorial_step",
            "step": step_num,
            "total": len(steps),
            "title": title,
            "instruction": instruction,
            "wire_color": wire_color,
            "image_b64": image_b64,
        })

    await send_fn({"event": "tutorial_complete", "total_steps": len(steps)})


async def _generate_step_image(client, title, instruction, wire_color, step_num):
    """Generate a Lego-style diagram for one step. Returns a data URI or empty string."""
    color_hint = f"Use a {wire_color} wire as the highlighted component. " if wire_color != "none" else ""
    prompt = (
        f"Create a clear assembly instruction diagram for this step: {title}. "
        f"{instruction} "
        f"{color_hint}"
        f"Style: {_IMAGE_STYLE}."
    )
    try:
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
            ),
            timeout=20.0,
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                mime = part.inline_data.mime_type
                b64 = base64.b64encode(part.inline_data.data).decode()
                return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[tutorial] image gen failed for step {step_num}: {e!r}")
    return ""
