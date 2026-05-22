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


@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    session = None
    print("[main] client connected")
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            event = msg.get("event")

            if event == "start_session":
                session = AgentSession(msg.get("circuit_id", "temperature_alarm"))
                await ws.send_json(await session.start())
                print("[main] session started:", session.circuit_id)

            elif event == "frame_eval":
                if session is None:
                    # tolerate a missing start_session so the UI never deadlocks
                    session = AgentSession(msg.get("circuit_id", "temperature_alarm"))
                payload = await session.handle_frame(
                    msg["image_b64"], int(msg["current_step"]))
                await ws.send_json(payload)
                print(f"[main] frame_eval step={msg.get('current_step')} "
                      f"-> {payload['status']} (next={payload['current_step']})")

            else:
                await ws.send_json({
                    "status": "error_occluded",
                    "audio_b64": "",
                    "image_b64": "",
                    "text": f"Unknown event: {event}",
                    "agent_log": f"[main] dropped unknown event '{event}'",
                    "current_step": session.current_step if session else 1,
                    "citation": "",
                })

    except WebSocketDisconnect:
        print("[main] client disconnected")
    except Exception as e:  # noqa: BLE001 - log and close cleanly, never crash the server
        print(f"[main] ws error: {e!r}")
        try:
            await ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    # Cloud Run injects PORT; default 8080 to match the frontend + Dockerfile.
    port = int(os.getenv("PORT", "8080"))
    print(f"[main] starting on :{port}  MOCK_MODE={MOCK_MODE}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
