"""
main.py - FastAPI WebSocket gateway for the Physical IDE agent.

Run locally:
    python main.py                                      # binds 0.0.0.0:8080
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload

WebSocket endpoint: /ws/agent   (see MOCK_MODE.md for the message contract)
"""
import os
import json

try:  # load backend/.env before anything reads env vars
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent import AgentSession
from live_agent import LiveAssemblySession

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

app = FastAPI(title="Physical IDE Agent")

# TODO: lock down before submission - restrict to the deployed frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "physical-ide-agent", "mock_mode": MOCK_MODE, "ws": "/ws/agent"}


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _error_payload(session, text, agent_log):
    """Build a contract-valid downstream payload for a protocol-level error.

    status 'error_protocol' is emitted ONLY here in main.py - for malformed
    input or unprocessable events. It is never a Watcher verdict, so the agent
    pipeline never produces it.
    """
    return {
        "status": "error_protocol",
        "audio_b64": "",
        "image_b64": "",
        "text": text,
        "agent_log": agent_log,
        "current_step": session.current_step if session else 1,
        "citation": "",
    }


@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    session = None
    print(f"[main] client connected  (MOCK_MODE={MOCK_MODE})")
    try:
        while True:
            # --- receive: WebSocketDisconnect propagates to the outer handler -
            raw = await ws.receive_text()

            # --- parse: a malformed message must NOT kill the connection ------
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                await ws.send_json(_error_payload(
                    session, f"malformed JSON: {e}",
                    "[main] dropped malformed JSON"))
                continue

            # --- dispatch: any handler error degrades to an error payload -----
            try:
                event = msg.get("event")

                if event == "start_session":
                    circuit_id = msg.get("circuit_id", "servo_control")
                    constraints = msg.get("user_constraints", [])
                    if MOCK_MODE:
                        session = AgentSession(circuit_id, constraints)
                    else:
                        session = LiveAssemblySession(circuit_id)
                    await ws.send_json(await session.start())
                    mode = "mock" if MOCK_MODE else "Gemini Live"
                    print(f"[main] session started: {circuit_id} via {mode} constraints={constraints}")

                elif event == "frame_eval":
                    if session is None:
                        # tolerate a missing start_session so the UI never deadlocks
                        if MOCK_MODE:
                            session = AgentSession(msg.get("circuit_id", "servo_control"))
                        else:
                            session = LiveAssemblySession(msg.get("circuit_id", "servo_control"))
                            await session.start()
                    payload = await session.handle_frame(
                        msg["image_b64"], int(msg["current_step"]))
                    await ws.send_json(payload)
                    print(f"[main] frame_eval step={msg.get('current_step')} "
                          f"-> {payload['status']} (next={payload['current_step']})")

                else:
                    await ws.send_json(_error_payload(
                        session, f"Unknown event: {event}",
                        f"[main] dropped unknown event '{event}'"))

            except WebSocketDisconnect:
                raise  # MUST re-raise: it is an Exception subclass, not a bug
            except Exception as e:  # noqa: BLE001 - one bad message must not crash the session
                print(f"[main] handler error: {e!r}")
                await ws.send_json(_error_payload(
                    session, f"could not process event: {e}",
                    f"[main] handler error: {e!r}"))
                continue

    except WebSocketDisconnect:
        print("[main] client disconnected")
    except Exception as e:  # noqa: BLE001 - log and close cleanly, never crash the server
        print(f"[main] ws error: {e!r}")
        try:
            await ws.close()
        except Exception:
            pass
    finally:
        if session and hasattr(session, "close"):
            await session.close()


if __name__ == "__main__":
    import uvicorn
    # Cloud Run injects PORT; default 8080 to match the frontend + Dockerfile.
    port = int(os.getenv("PORT", "8080"))
    print(f"[main] starting on :{port}  MOCK_MODE={MOCK_MODE}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
