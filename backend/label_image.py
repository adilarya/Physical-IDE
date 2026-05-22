"""
label_image.py — ask Gemini to identify and label key hardware components in an image.

Sends the image to Gemini 2.5 Flash with a prompt asking it to locate and describe:
  - breadboard power rails (+ and - rails)
  - Arduino pins (5V, GND, digital/analog)
  - any placed components (LEDs, resistors, wires)
  - breadboard row/column coordinates

Prints the structured label output to stdout so you can visually verify
that Gemini is correctly identifying what the vision pipeline needs to see.

Usage:
    cd backend
    python label_image.py path/to/image.jpg
    python label_image.py "example images/IMG_4389.jpg"
"""
import asyncio
import base64
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types

PROMPT = """
You are a hardware assembly vision inspector. Carefully examine this image and identify every relevant hardware element you can see.

For each element you identify, provide:
1. What it is (e.g. "breadboard positive power rail", "Arduino 5V pin", "LED anode leg", "220-ohm resistor")
2. Where it is in the image (e.g. "top-left rail", "row 10 column F", "left side of board")
3. Its current state (e.g. "empty", "wire inserted", "component placed correctly", "component reversed")
4. Any safety concerns (e.g. "short circuit risk", "reversed polarity", "component in wrong row")

Be specific about:
- Which breadboard rows and columns components are in (if visible)
- The polarity of LEDs (which leg is longer = anode)
- Wire colors and where they connect from/to
- Whether the power rails are connected to a power source

Format your response as a clear labeled list. If you cannot see something clearly, say so explicitly rather than guessing.
"""


def load_image(path):
    with open(path, "rb") as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
    return raw, mime


async def label(image_path):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    raw, mime = load_image(image_path)

    print(f"\nImage: {image_path}")
    print(f"Size: {len(raw) / 1024:.1f} KB  |  MIME: {mime}")
    print("─" * 60)
    print("Sending to Gemini 3.5 Flash for hardware component labeling...\n")

    resp = await client.aio.models.generate_content(
        model="gemini-3.5-flash",
        contents=[
            types.Part.from_bytes(data=raw, mime_type=mime),
            types.Part.from_text(text=PROMPT),
        ],
        config=types.GenerateContentConfig(temperature=0.1),
    )

    print(resp.text)
    print("\n" + "─" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python label_image.py <image_path>")
        print('Example: python label_image.py "example images/IMG_4389.jpg"')
        sys.exit(1)
    asyncio.run(label(sys.argv[1]))
