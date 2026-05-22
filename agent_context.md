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