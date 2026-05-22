# SYSTEM CONTEXT & ARCHITECTURE: PROJECT PREFLIGHT (The Physical IDE)

## 1. Project Overview
**Project Name:** Project  The Physical IDE
**Core Value Proposition:** An autonomous, vision-anchored safety and compliance agent.
*   **The Wedge (EdTech):** A dynamic, "Lego-style" instructor that prevents beginners from shorting circuits during unpowered assembly.
*   **The Enterprise Pivot (Industrial QA):** An autonomous assembly auditor for manufacturing. It replaces manual, error-prone visual inspection of complex hardware by using a State-Aware Vision Agent to verify high-density wiring against a master digital twin.

## 2. The Paradigm Shift: "The Physical IDE"
We are moving beyond "Education." We are building a **compiler for the real-world**.
*   **Physical IDE:** Just as software engineers have IDEs to catch syntax errors before compilation, PreFlight provides real-time "hardware syntax highlighting" for assembly.
*   **Constraint Routing:** The agent dynamically recalculates schematics on the fly if inventory is constrained (e.g., missing components), ensuring the assembly process continues without human intervention.
*   **Pre-Flight Safety Protocol:** By enforcing an unpowered assembly state, the agent acts as an autonomous gatekeeper, verifying the "Digital Twin" of the circuit before it is ever energized.

## 3. Industrial QA & Compliance Application
The same architecture that guides a student also audits a factory worker:
*   **Assembly Compliance:** In aerospace/robotics, a wire placed in the wrong pin (e.g., 0.1mm deviation) causes total failure. PreFlight uses fiducial-anchored coordinate grids to perform sub-millimeter visual auditing.
*   **Audit Trail:** The Antigravity graph logs every physical assembly step and verification result to the cloud, creating a mathematically verified audit trail of assembly—a requirement for FAA/ISO manufacturing compliance.

## 5. Team Roles & Responsibilities

---

### Athif — Frontend & Real-Time UX

**Focus:** Everything the user sees and interacts with in real time.

**Responsibilities:**
- Build the React UI: webcam feed display, live overlay rendering, step-by-step instruction panel
- Integrate MediaPipe on the client for real-time hand and component detection
- Implement the WebSocket client: capture and stream frames to the backend, receive and render audio + image payloads
- Build the "Physical IDE" HUD — visual error highlighting (wrong pin, wrong component), constraint warnings, and assembly progress indicators
- Handle UI state for the assembly flow: idle → active → verified → error states
- Design and implement the instruction display (Lego-style guided steps)
- Ensure the UI is demo-ready: clean, responsive, and visually compelling for judges/stakeholders

---

### Adil — Backend & Agent Orchestration

**Focus:** The server, real-time data pipeline, and the agent logic that ties everything together.

**Responsibilities:**
- Build and maintain the FastAPI server with WebSocket support for handling live frame streams
- Design and implement the Antigravity 2.0 graph: state machine that tracks where the user is in the assembly process
- Route requests between Gemini 3.5 Live (spatial verification) and Gemini 3.1 Pro (instruction generation) based on assembly state
- Implement constraint routing logic — detect missing or substituted components and dynamically recalculate the schematic to keep assembly moving
- Define and own the WebSocket contract (payload schema) between the frontend and backend
- Define the API interface for Vertex AI calls so the vision/AI engineer can plug in cleanly
- Deploy and manage the backend on Cloud Run
- Handle error states, retries, and session management across WebSocket connections

---

### Eshwar — Vision AI & Data / Compliance

**Focus:** The AI models, spatial accuracy, and the audit/compliance layer.

**Responsibilities:**
- Prompt engineer and tune both Vertex AI models: Gemini 3.5 Live for spatial/pin-level verification and Gemini 3.1 Pro for instruction generation
- Set up fiducial markers and build the coordinate grid system for sub-millimeter component auditing
- Build and maintain the digital twin — the ground truth schematic the agent compares physical assembly against
- Implement the verification pipeline: compare the live webcam frame against the digital twin and return pass/fail with spatial annotations
- Build the audit trail logging system: every assembly step, verification result, and deviation gets logged to the cloud (structured for FAA/ISO compliance)
- Own model accuracy: iterate on prompts and detection logic to minimize false positives/negatives
- Expose a clean interface for the backend to call into the vision pipeline

---

## 4. Architecture & Data Flow
**Pattern:** Edge-Triggered Webcam -> WebSocket -> FastAPI/Antigravity Backend -> Vertex AI -> Interleaved UI Payload.

```text
[React UI + MediaPipe] --(WebSocket Frame)--> [Cloud Run FastAPI] 
                                                    |
                                          [Google Antigravity 2.0]
                                          /                      \
                    [Vertex AI: Gemini 3.5 Live]        [Vertex AI: Gemini 3.1 Pro]
                     (Spatial Verification)             (Lego/Instruction Generation)
                                          \                      /
[React UI] <--(Audio+Image Payload over WS)--- [Cloud Run FastAPI]
```

---

## 6. Two-Phase Product Architecture

The product has two distinct phases that connect end-to-end:

### Phase 1 — Tutorial Phase (PLANNED, not yet built)
**Goal:** User describes what they want their breadboard to do in natural language. The system generates a full Lego-style step-by-step wiring guide.

**Flow:**
```
User speaks goal → Gemini 3.1 Pro generates circuit plan + steps
                 → Imagen 3 generates isometric Lego-style image per step
                 → gemini-3.1-flash-tts-preview narrates each step aloud
                 → Frontend displays image + plays audio for each step
```

**Models used:**
- `gemini-3.1-pro-preview` — understands the goal, generates the circuit design and step instructions
- `imagen-3.0-generate-002` — generates the Lego-style isometric assembly diagrams
- `gemini-3.1-flash-tts-preview` — dedicated TTS model narrates each step with high-quality voice

**What it produces:** A numbered step list, each with an image and audio — like an interactive Lego manual generated on the fly for any circuit goal.

---

### Phase 2 — Verification Phase (BUILT AND WORKING)
**Goal:** As the user physically assembles the circuit from Phase 1, the agent watches via webcam and catches errors in real time.

**Flow:**
```
User removes hands from frame → MediaPipe triggers scan
                              → JPEG frame sent over WebSocket to FastAPI
                              → Gemini Live API evaluates frame (vision + audio native)
                              → Spoken verdict + WAV audio returned
                              → Frontend plays audio, updates instruction panel
```

**Models used:**
- `gemini-3.1-flash-live-preview` (Gemini Live API) — sees the board, speaks the verdict natively. One call handles vision + verdict + voice.

**Verdicts:**
- `PASS` → step verified, advance to next
- `WRONG` → component misplaced or out of order
- `DANGER` → dangerous connection (reversed polarity, short circuit)
- `UNCLEAR` → board not visible, hand in frame

---

### How the phases connect
Phase 1 generates the `circuits.py` step definitions dynamically (instead of hardcoded). Phase 2 verifies against those steps. The full loop: *describe → plan → build → verify*.

Currently Phase 2 uses a hardcoded `servo_control` circuit. When Phase 1 is built, it will generate the circuit definition and pass it into the verification pipeline automatically.