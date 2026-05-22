"""
agent.py - ADK-style assembly-mentor state machine.

Two sub-agents:
  Watcher  - evaluates the physical board against the expected step state.
  Planner  - turns the Watcher verdict into the next interleaved instruction.

AgentSession owns the per-connection state (which step the user is on) and
orchestrates Watcher -> Planner for every captured frame. The output of
handle_frame() / start() is the locked downstream contract object.
"""
from circuits import get_circuit, get_step, step_count
from gemini_client import evaluate_frame, generate_next_step, reset_mock_state


class Watcher:
    """Sub-agent: 'does the board match the expected state?' Holds no state."""

    async def run(self, image_b64, current_step, expected_state):
        result = await evaluate_frame(image_b64, current_step, expected_state)
        log = (
            f"[Watcher] step {current_step} verdict={result['verdict']} "
            f"conf={result.get('confidence', 0):.2f} :: {result.get('reasoning', '')}"
        )
        return result, log


class Planner:
    """Sub-agent: produces the next interleaved (text+image+audio) instruction."""

    async def run(self, step_index, context):
        return await generate_next_step(step_index, context)


class AgentSession:
    """One instance per WebSocket connection. Drives a single circuit build."""

    def __init__(self, circuit_id):
        self.circuit_id = circuit_id
        self.circuit = get_circuit(circuit_id)   # raises KeyError on bad id
        self.current_step = 1
        self.watcher = Watcher()
        self.planner = Planner()

    async def start(self):
        """Emit the session_init payload (Step 1 instruction)."""
        reset_mock_state()   # so repeated demo runs replay the scripted beat
        self.current_step = 1
        step = get_step(self.circuit_id, 1)
        planner_out = await self.planner.run(1, {"fresh": True, "step": step})
        return _payload("session_init", planner_out, current_step=1,
                        citation=step.get("citation", ""))

    async def handle_frame(self, image_b64, current_step):
        """Run Watcher -> Planner for one frame; return a downstream payload."""
        self.current_step = current_step
        step = get_step(self.circuit_id, current_step)
        expected = step["success_criteria"] if step else ""

        # --- WATCHER -------------------------------------------------------
        watcher_result, watcher_log = await self.watcher.run(
            image_b64, current_step, expected)
        verdict = watcher_result["verdict"]

        # --- PLANNER -------------------------------------------------------
        if verdict == "success_advance":
            next_step = current_step + 1

            if next_step > step_count(self.circuit_id):
                # build finished - emit the completion turn
                planner_out = await self.planner.run("done", {"complete": True})
                self.current_step = next_step
                return _payload("success_advance", planner_out,
                                current_step=next_step, watcher_log=watcher_log)

            nstep = get_step(self.circuit_id, next_step)
            planner_out = await self.planner.run(
                next_step, {"fresh": True, "step": nstep})
            self.current_step = next_step
            return _payload("success_advance", planner_out, current_step=next_step,
                            watcher_log=watcher_log, citation=nstep.get("citation", ""))

        # error verdict - stay on the current step, push a correction
        planner_out = await self.planner.run(current_step, {
            "correction": True,
            "verdict": verdict,
            "step": step,
            "watcher": watcher_result,
        })
        return _payload(verdict, planner_out, current_step=current_step,
                        watcher_log=watcher_log,
                        citation=step.get("citation", "") if step else "")


def _payload(status, planner_out, current_step, watcher_log="", citation=""):
    """Assemble the locked Backend -> Frontend contract object."""
    agent_log = " ".join(
        p for p in (watcher_log, planner_out.get("agent_log", "")) if p
    )
    return {
        "status": status,
        "audio_b64": planner_out["audio_b64"],
        "image_b64": planner_out["image_b64"],
        "text": planner_out["text"],
        "agent_log": agent_log,
        "current_step": current_step,
        "citation": citation,
    }
