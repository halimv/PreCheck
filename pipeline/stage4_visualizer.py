"""Stage 4: Visualizer (replay in PyLabRobot's 3D viewer).

Replays a protocol that passed the simulator so a person can watch the whole assay before it goes on: which
channels go where, in what order, one tip at a time or eight. It uses PyLabRobot's own
`pylabrobot.visualizer3D.Viewer3D`, which serves a web page that draws the deck in 3D and follows the tracking
state live as tips leave their racks and wells fill. `three_d=False` gives the older top-down `Visualizer`.

The replay runs on a fresh deck with the same deck config, compiled code, trackers and simulation backend
(pipeline.instrument.simulation_backend) as stage 3, pausing after each step so the changes are visible.
"""

import asyncio
import contextlib
import inspect
import io
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pylabrobot.legacy.liquid_handling import LiquidHandler
from pylabrobot.resources import set_tip_tracking, set_volume_tracking

from pipeline.deck import build_deck, machines
from pipeline.instrument import simulation_backend
from pipeline.stage2_compiler import compile_protocol


class Paced:
    """Wraps a LiquidHandler so every call the protocol makes pauses afterwards, slow enough to watch."""

    def __init__(self, lh: LiquidHandler, delay_s: float):
        self._lh, self._delay_s = lh, delay_s

    def __getattr__(self, name: str):
        method = getattr(self._lh, name)

        async def paced(*args, **kwargs):
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            await asyncio.sleep(self._delay_s)
            return result
        return paced


@dataclass
class VisualizerSession:
    """A running visualizer and the simulated deck it shows. Call `stop()` when done."""

    visualizer: Any  # Viewer3D, or the top-down Visualizer
    lh: LiquidHandler
    resources: Dict[str, Any]
    url: str

    async def stop(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            await self.visualizer.stop()
            for machine in machines(self.resources):
                await machine.stop()
            await self.lh.stop()


async def start_visualizer(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    open_browser: bool = True,
    name: Optional[str] = None,
    three_d: bool = True,
) -> VisualizerSession:
    """Build a fresh simulated deck for `protocol` and start the viewer on it (no steps run yet)."""
    set_tip_tracking(True)
    set_volume_tracking(True)
    deck, resources = build_deck(deck_config, protocol.get("initial_volumes_ul"))
    lh = LiquidHandler(backend=simulation_backend(deck_config), deck=deck)
    title = name or protocol.get("protocol_name") or "protocol"
    with contextlib.redirect_stdout(io.StringIO()):  # hide the backend's and the servers' printouts
        await lh.setup()
        for machine in machines(resources):
            await machine.setup()
        if three_d:
            from pylabrobot.visualizer3D import Viewer3D
            visualizer = Viewer3D(lh, open_browser=open_browser, name=title, fs_port=_free_port(), ws_port=_free_port())
            await visualizer.start()
            url = visualizer.url
        else:
            from pylabrobot.visualizer import Visualizer
            visualizer = Visualizer(resource=lh, open_browser=open_browser, name=title)
            await visualizer.setup()
            url = f"http://{visualizer.host}:{visualizer.fs_port}"
    return VisualizerSession(visualizer, lh, resources, url)


def _free_port() -> int:
    """A port nothing listens on now, so this viewer never lands on AHC's or another run's."""
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def _wait_for_browser(visualizer: Any, timeout_s: float) -> None:
    if hasattr(visualizer, "wait_for_browser"):  # Viewer3D
        try:
            await visualizer.wait_for_browser(timeout_s)
        except (asyncio.TimeoutError, TimeoutError):
            pass
        return
    for _ in range(int(timeout_s / 0.2)):
        if visualizer.has_connection():
            break
        await asyncio.sleep(0.2)


async def replay(
    session: VisualizerSession,
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 0.4,
    wait_for_browser_s: float = 20.0,
) -> None:
    """Wait up to `wait_for_browser_s` for the page to connect, then run `protocol` step by step.

    The visualizer stays running afterwards. Exceptions from the protocol propagate (stage 3 should
    have caught them already) and stop the session.
    """
    namespace: Dict[str, Any] = {}
    exec(compile(compile_protocol(protocol, deck_config), "<stage4_replay>", "exec"), namespace)

    await _wait_for_browser(session.visualizer, wait_for_browser_s)

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            await namespace["run_protocol"](Paced(session.lh, step_delay_s), session.resources)
    except Exception:
        await session.stop()
        raise


async def visualize_protocol(
    protocol: Dict[str, Any],
    deck_config: Dict[str, Any],
    step_delay_s: float = 0.4,
    open_browser: bool = True,
    wait_for_browser_s: float = 20.0,
    name: Optional[str] = None,
    three_d: bool = True,
) -> VisualizerSession:
    """Start the visualizer and replay `protocol` on it; returns the still-running session."""
    session = await start_visualizer(protocol, deck_config, open_browser=open_browser, name=name, three_d=three_d)
    await replay(session, protocol, deck_config, step_delay_s=step_delay_s, wait_for_browser_s=wait_for_browser_s)
    return session
