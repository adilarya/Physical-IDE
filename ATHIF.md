# ATHIF — Frontend & Real-Time UX
**Role:** Everything the user sees and interacts with in real time.
**Stack:** React, Vite, TailwindCSS, MediaPipe, Web Audio API, WebSocket

---

## How to Run Your Part Independently

You do not need the backend running at any point during development.

```bash
# 1. Create your local env file
cd frontend
cp .env.example .env

# 2. Enable the in-browser mock (no Python, no API keys)
# Edit .env and uncomment:
VITE_MOCK_SOCKET=true

# 3. Start the dev server
npm install
npm run dev
```

The scripted demo beat plays entirely in-browser:
- Session initializes → Step 1 instruction appears
- FORCE CAPTURE or hands-out → Step 1 passes → Step 2
- Step 2 first scan → `error_short_circuit` correction fires
- Step 2 second scan → passes → Step 3
- Step 3 scan → build complete

When you want to test against Adil's real backend, flip `VITE_MOCK_SOCKET=false` and make sure the backend is running on port 8080.

---

## Files You Own

```
frontend/
  src/
    App.jsx                        ← main layout and state wiring
    components/
      AgentLog.jsx                 ← scrolling agent log panel (right column)
      InstructionCard.jsx          ← step instruction + image display (center)
      ScanOverlay.jsx              ← animated scanning overlay on webcam feed
    hooks/
      useWebcam.js                 ← getUserMedia, captureFrame()
      useHandTracker.js            ← MediaPipe Hands — fires onHandClear callback
      useAgentSocket.js            ← WebSocket client (real or mock)
      useMockAgentSocket.js        ← in-browser scripted mock (your dev harness)
    index.css
    main.jsx
  index.html
  vite.config.js
  .env.example
```

Do not touch anything in `backend/`.

---

## What You Need to Build

### 1. Assembly HUD — Visual Error States

The UI currently shows a `StatusPill` and `InstructionCard` for the agent response, but the visual differentiation between states is minimal. You need to make each state feel distinct and unambiguous at a glance.

**Required states and their visual treatment:**

| `status` value | What happened | Visual treatment |
|---|---|---|
| `session_init` | Session just started | Neutral — show Step 1 instruction |
| `success_advance` | Step verified, advancing | Green flash/highlight, brief "VERIFIED" banner |
| `error_short_circuit` | Dangerous wiring detected | Red alert state, pulsing border on instruction card |
| `error_occluded` | Board not visible | Amber warning, "CLEAR VIEW" prompt overlaid on webcam |
| `error_wrong_placement` | Component misplaced | Amber warning, highlight the problem area in the instruction image |
| build complete (`currentStep > TOTAL_STEPS`) | Done | Full success screen, all steps shown as checked |

**Key file:** `src/App.jsx` — the `STATUS_META` map already has labels, extend it with CSS classes and visual behaviors.

### 2. Instruction Card — Image + Text Display

`InstructionCard.jsx` receives:
- `image` — a `data:image/svg+xml;base64,...` URI (the step diagram)
- `text` — the spoken instruction as a string
- `citation` — source reference (e.g. "Arduino Uno R3 - power pins reference, p.2")
- `step` / `total` — current step number out of total
- `status` — the current agent verdict

**What it needs to do:**
- Display the instruction image at full width with correct aspect ratio
- Display the instruction text below in a readable, large font
- Show the citation in a small secondary style beneath the text
- Show a step progress indicator (e.g. "STEP 2 / 3" with filled dots or a progress bar)
- On `error_*` statuses, visually distinguish the correction text from a normal step instruction (different background, icon, or border color)
- Handle the `null` image state gracefully (show a skeleton/placeholder while waiting)

### 3. Webcam Feed — Scan Overlay and Hand Tracking Indicator

`ScanOverlay.jsx` displays over the live webcam feed when `socket.scanning === true`.

**What it needs to do:**
- Display an animated "scanning" visual (e.g. a sweeping line, pulsing corners, or a grid overlay) while the agent is evaluating a frame
- Disappear cleanly once a response arrives
- The "HANDS IN FRAME" / "FRAME CLEAR" indicator in the top-left corner of the feed is already wired — make sure it's visually clear and not just a dot + text

The `useHandTracker.js` hook fires `onHandClear` when hands leave the frame. The trigger for a scan is hands leaving — make sure this is communicated to the user before they even place their hands (e.g. a brief instruction: "place circuit, remove hands to scan").

### 4. Force Capture Button

Already exists. Ensure:
- It is disabled and visually greyed out while `socket.scanning === true` or `!socket.connected`
- It provides clear feedback when tapped (brief active state)
- On mobile / touch screens it is large enough to tap reliably

### 5. Agent Log Panel

`AgentLog.jsx` receives `log` — an array of `{ t: timestamp, line: string, kind: 'agent' | 'sys' | 'error' }`.

**What it needs to do:**
- Auto-scroll to the bottom on new entries
- Color-code by `kind`: `agent` = default, `sys` = muted/grey, `error` = red
- Show timestamps in a readable relative format (e.g. `+0.3s`, `+1.2s` from session start)
- Truncate long lines cleanly (don't break the layout)
- The log is capped at 120 entries by the hook — no need to handle more

### 6. Start Screen

Already implemented. Verify:
- Camera permission prompt fires immediately on "INITIALIZE SESSION"
- If `getUserMedia` is denied, the UI falls back gracefully (webcam error message is already handled in `App.jsx`)
- Audio context is resumed inside the button click handler (already done — do not move it)

### 7. Responsive Layout

The current grid is `col-span-4 / col-span-5 / col-span-3` (webcam / instruction / log). This breaks on screens narrower than ~1024px.

**Minimum:** ensure the layout stacks vertically on a standard 1080p presentation laptop at full-screen browser. The demo will be presented on a laptop — it does not need to be mobile-responsive.

---

## The WebSocket Contract (Read-Only for You)

You consume this payload from the backend. **Do not change the field names** — Adil owns the contract.

```json
{
  "status": "success_advance | error_short_circuit | error_occluded | error_wrong_placement | session_init",
  "audio_b64": "base64-encoded WAV (no data: prefix)",
  "image_b64": "data:image/svg+xml;base64,...",
  "text": "Step 3: Connect the 220-ohm resistor...",
  "agent_log": "[Watcher] step 3 verdict=success_advance :: ... [Planner] ...",
  "current_step": 3,
  "citation": "Resistor color codes - 220 ohm band reference, p.4"
}
```

You send two event types:

```json
// On connect:
{ "event": "start_session", "circuit_id": "temperature_alarm", "user_constraints": [] }

// On hand-clear or force capture:
{ "event": "frame_eval", "image_b64": "data:image/jpeg;base64,...", "current_step": 2, "circuit_id": "temperature_alarm" }
```

`useAgentSocket.js` handles all of this. You do not need to touch the socket layer.

---

## Testing Your Work

**Test each visual state manually:**

| How to trigger | State to test |
|---|---|
| Press "INITIALIZE SESSION" | `session_init` |
| Press FORCE CAPTURE (step 1) | `success_advance` → step advances to 2 |
| Press FORCE CAPTURE (step 2, first time) | `error_short_circuit` correction appears |
| Press FORCE CAPTURE (step 2, second time) | `success_advance` → step advances to 3 |
| Press FORCE CAPTURE (step 3) | `success_advance` → build complete screen |

**To test error states that don't appear in the scripted beat** (occluded, wrong_placement), temporarily edit `useMockAgentSocket.js` and change the `sendFrame` function to return whichever verdict you want to test. Revert after.

**To verify audio:** the mock sends a 1-second silent WAV — you will not hear anything. That is correct. Real audio comes from Eshwar's Gemini TTS integration via Adil's backend.

---

## Definition of Done

- [ ] All 5 status states are visually distinct and unambiguous
- [ ] Instruction card displays image, text, citation, and step progress correctly
- [ ] Scan overlay animates while `scanning === true` and disappears cleanly
- [ ] Agent log auto-scrolls, is color-coded, and does not break layout
- [ ] Build complete screen appears when `currentStep > TOTAL_STEPS`
- [ ] FORCE CAPTURE button is correctly disabled during scanning
- [ ] Layout holds on a 1080p screen at full-browser width
- [ ] `VITE_MOCK_SOCKET=false` + `npm run dev` works against a running backend with no code changes
