"""Stage 3: PyLabRobot Simulator (ChatterBox dry run) and error interceptor.

Runs a stage-2 module against PLR's LiquidHandlerChatterboxBackend with tip and volume
tracking on, so PLR's own world model checks every tip and microliter. If the run raises,
the interceptor maps the exception to the IR step that caused it, snapshots the deck, and
returns a lab-concept diagnostic (pipeline/diagnostics.py).
"""

import asyncio
import concurrent.futures
import contextlib
import io
import re
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pylabrobot.resources import set_tip_tracking, set_volume_tracking

from pipeline import diagnostics
from pipeline.deck import build_deck, machines
from pipeline.instrument import firmware_configuration
from pipeline.pipetting import close_device, open_device

MODULE_FILENAME = "<plr_module>"
STEP_COMMENT = re.compile(r"#\s*step\s+(\d+)\b")


@dataclass
class SimulationResult:
    status: str  # "PASSED" or "FAILED"
    message: str
    diagnostic: Optional[Dict[str, Any]] = None
    log: str = ""
    final_state: Dict[str, Any] = field(default_factory=dict)


def _failing_step(code: str, exc: BaseException) -> Optional[int]:
    """Return the IR step number whose `# step N` comment precedes the failing line of the module."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == MODULE_FILENAME]
    if not frames:
        return None
    lines = code.splitlines()[: frames[-1].lineno]
    for line in reversed(lines):
        m = STEP_COMMENT.search(line)
        if m:
            return int(m.group(1))
    return None


class PLRSimulator:
    """Dry-runs compiled protocols on the simulated STAR device (pipeline/pipetting.py)."""

    def __init__(self, deck_config: Dict[str, Any]):
        self.deck_config = deck_config

    def run(self, module_code: str, protocol: Dict[str, Any]) -> SimulationResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._run(module_code, protocol))
        # Already inside an event loop (e.g. Jupyter): run the simulation on its own loop in a worker thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, self._run(module_code, protocol)).result()

    async def _run(self, module_code: str, protocol: Dict[str, Any]) -> SimulationResult:
        set_tip_tracking(True)
        set_volume_tracking(True)

        namespace: Dict[str, Any] = {}
        exec(compile(module_code, MODULE_FILENAME, "exec"), namespace)
        run_protocol = namespace["run_protocol"]

        deck, res = build_deck(self.deck_config, protocol.get("initial_volumes_ul"))
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            lh = await open_device(deck, "chatterbox", firmware_configuration(self.deck_config))
            for machine in machines(res):
                await machine.setup()
            try:
                await run_protocol(lh, res)
            except Exception as exc:
                step_num = _failing_step(module_code, exc)
                step = next((s for s in protocol["steps"] if s.get("step") == step_num), None)
                state = diagnostics.capture_state(lh, res, self.deck_config, step)
                diag = diagnostics.translate(exc, step, protocol, res, state)
                return SimulationResult(
                    status="FAILED",
                    message=f"Step {step_num}: {diag['error_code']} ({diag['raw_error']})",
                    diagnostic=diag,
                    log=log.getvalue(),
                )
            finally:
                for machine in machines(res):
                    await machine.stop()
                await close_device(lh)

        state = diagnostics.capture_state(lh, res, self.deck_config, None)
        return SimulationResult(
            status="PASSED",
            message=f"All {len(protocol['steps'])} steps ran on the STAR device (simulated) with tip and volume tracking.",
            log=log.getvalue(),
            final_state=state,
        )
