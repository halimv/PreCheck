"""Stage 5: Executor (run a protocol that passed stages 1-3 on the Hamilton STARlet).

The deck is built from the same deck config as stages 2-4 and the run uses the same compiled
statements, one IR step at a time, so progress can be reported per step and an abort takes
effect at the next step boundary. Tip and volume tracking stay on: PLR refuses a command its
world model says is unsafe before it reaches the instrument.

Backends:
- "star":       PyLabRobot's STARBackend over USB (the real instrument).
- "chatterbox": PLR's simulated backend, to rehearse the run and the setup flow without hardware.

Modes:
- "full":      every step.
- "tip_check": for each tip rack the protocol uses, pick up its first column and put it back.
               Moves no liquid; confirms the tip carrier sits where the deck config says.

Remote runs: macOS never enumerates the STAR, so its USB cable goes to a Raspberry Pi. There,
`python -m pipeline.stage5_executor serve` runs one execution for pipeline/remote.py over SSH: a JSON
request line on stdin, then events as JSON lines on stdout (everything else printed goes to stderr).
`{"abort": true}` on stdin, stdin closing (the SSH connection is gone) or SIGHUP/SIGTERM all stop
the run before its next step. A STARlet run holds an exclusive flock on the lock file the AHC bridge
uses (~/ahc/.star-bridge/lock), so the two never drive the instrument at the same time.
`python -m pipeline.stage5_executor status` reports what the page needs without touching the STAR.
"""

import argparse
import asyncio
import fcntl
import json
import os
import signal
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional

from pylabrobot.legacy.liquid_handling import LiquidHandler
from pylabrobot.legacy.liquid_handling.backends import LiquidHandlerChatterboxBackend, STARBackend
from pylabrobot.resources import set_tip_tracking, set_volume_tracking

from pipeline import deck as deck_module
from pipeline.deck import build_deck, machines
from pipeline.instrument import simulation_backend
from pipeline.stage2_compiler import DEVICE_ACTIONS, translate_step, venus_troughs

BACKENDS = ("star", "chatterbox")
MODES = ("full", "tip_check")


class ExecutionError(RuntimeError):
    pass


def _step_coroutine(step: Dict[str, Any], kinds: Dict[str, str], troughs: frozenset = frozenset()):
    """Compile one IR step into `async def _step(lh, res)` with the stage-2 translation."""
    body = translate_step(step, kinds, troughs)
    src = "async def _step(lh, res):\n" + "\n".join("    " + line for line in body.splitlines())
    namespace: Dict[str, Any] = {"heater_shaker": deck_module.heater_shaker, "reach": deck_module.reach}
    exec(compile(src, f"<step {step.get('step')}>", "exec"), namespace)
    return namespace["_step"]


def tip_check_steps(protocol: Dict[str, Any], deck_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The steps of a tip check: first used column of each tip rack, picked up and returned."""
    steps, seen = [], set()
    for s in protocol["steps"]:
        if s.get("action") == "tips_on" and s["labware"] not in seen:
            seen.add(s["labware"])
            steps.append({**s, "step": len(steps) + 1,
                          "description": f"Tip check: pick up {s['labware']} column {s['column']}"})
            steps.append({"step": len(steps) + 1, "action": "return_tips", "labware": s["labware"],
                          "channels": s.get("channels", [0]), "description": f"Tip check: return them to {s['labware']}"})
    return steps


class HardwareExecutor:
    """Runs a passing protocol. `on_event(kind, data)` receives "status", "step", "step_done",
    "done", "aborted" and "error"."""

    def __init__(self, deck_config: Dict[str, Any], backend: str = "star",
                 on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        if backend not in BACKENDS:
            raise ValueError(f"backend must be one of {BACKENDS}")
        self.deck_config = deck_config
        self.backend = backend
        self.emit = on_event or (lambda kind, data: print(f"[stage 5] {kind}: {data}"))
        self._abort = threading.Event()

    def abort(self) -> None:
        """Stop before the next step starts. The step in progress finishes; tips stay mounted."""
        self._abort.set()

    def check_supported(self, protocol: Dict[str, Any]) -> None:
        if self.backend == "star" and any(s.get("action") in DEVICE_ACTIONS for s in protocol["steps"]):
            raise ExecutionError("Heater-shaker steps are only simulated so far; the STAR backend cannot run them yet.")

    def run(self, protocol: Dict[str, Any], mode: str = "full") -> Dict[str, Any]:
        return asyncio.run(self._run(protocol, mode))

    async def _run(self, protocol: Dict[str, Any], mode: str) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.check_supported(protocol)
        steps = protocol["steps"] if mode == "full" else tip_check_steps(protocol, self.deck_config)
        kinds = {lid: spec["kind"] for lid, spec in self.deck_config["labware"].items()}
        compiled = [None if s["action"] == "return_tips" else _step_coroutine(s, kinds, venus_troughs(self.deck_config)) for s in steps]

        set_tip_tracking(True)
        set_volume_tracking(True)
        deck, res = build_deck(self.deck_config, protocol.get("initial_volumes_ul"))
        backend = STARBackend() if self.backend == "star" else simulation_backend(self.deck_config)
        lh = LiquidHandler(backend=backend, deck=deck)
        started = time.time()
        done = 0
        self.emit("status", {"message": "Connecting to the STARlet and initializing (this can take a minute)..."
                             if self.backend == "star" else "Starting the ChatterBox rehearsal...",
                             "total": len(steps), "mode": mode, "backend": self.backend})
        try:
            await lh.setup()
            for machine in machines(res):
                await machine.setup()
            self.emit("status", {"message": "Instrument ready.", "total": len(steps)})
            for step, fn in zip(steps, compiled):
                if self._abort.is_set():
                    mounted = [ch for ch in range(lh.backend.num_channels) if lh.head[ch].has_tip]
                    self.emit("aborted", {"after_step": done, "total": len(steps), "tips_mounted": mounted})
                    return {"status": "ABORTED", "steps_done": done}
                self.emit("step", {"step": step["step"], "total": len(steps), "action": step["action"],
                                   "description": step.get("description", "")})
                t0 = time.time()
                if fn is None:  # return_tips (tip check only)
                    await lh.return_tips(use_channels=step.get("channels"))
                else:
                    await fn(lh, res)
                done += 1
                self.emit("step_done", {"step": step["step"], "total": len(steps), "seconds": round(time.time() - t0, 1)})
            self.emit("done", {"steps": done, "seconds": round(time.time() - started, 1), "mode": mode})
            return {"status": "DONE", "steps_done": done}
        except Exception as e:
            failed = steps[done] if done < len(steps) else None
            self.emit("error", {"step": failed and failed["step"], "description": failed and failed.get("description"),
                                "message": f"{type(e).__name__}: {e}"})
            return {"status": "ERROR", "steps_done": done, "error": str(e)}
        finally:
            for machine in machines(res):
                await machine.stop()
            await lh.stop()


# --- Remote runs: the machine the STARlet's USB cable is plugged into (see the module docstring) ---

STAR_USB_ID = (0x08AF, 0x8000)  # Hamilton Bonaduz AG ML STAR


def _lock_path(path: str) -> str:
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.join(os.path.expanduser("~"), path)


def lock_holder(path: str) -> Optional[str]:
    """The pid written in the lock file while another process holds it, else None. Takes nothing."""
    try:
        fd = os.open(_lock_path(path), os.O_RDONLY)
    except FileNotFoundError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return os.read(fd, 32).decode("ascii", "replace").strip() or "unknown"
    finally:
        os.close(fd)
    return None


def take_lock(path: str) -> int:
    """Exclusive, non-blocking flock with this pid written in it (the AHC bridge's convention). The lock
    goes with the process however it ends."""
    path = _lock_path(path)
    if not os.path.isdir(os.path.dirname(path)):
        raise ExecutionError(f"The STARlet lock's folder {os.path.dirname(path)} does not exist; "
                             "set star_lock in config/remote.json.")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = os.read(fd, 32).decode("ascii", "replace").strip() or "unknown"
        os.close(fd)
        raise ExecutionError(f"Another program is driving the STARlet (pid {holder} holds {path}; the AHC bridge "
                             "uses this lock). Stop it first.") from None
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode("ascii"))
    return fd


def _lines(fd: int) -> Iterator[str]:
    """Lines read straight from a descriptor: a thread blocked in a buffered reader would hold its lock at exit."""
    buf = b""
    while True:
        chunk = os.read(fd, 4096)
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.decode("utf-8")


def serve(lock: str) -> int:
    out = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)  # PLR's ChatterBox prints its commands: keep them out of the event stream
    sys.stdout = sys.stderr

    def emit(kind: str, data: Dict[str, Any]) -> None:
        try:
            out.write(json.dumps({"kind": kind, "data": data}) + "\n")
        except OSError:
            pass  # the Mac side is gone; stdin closing aborts the run

    lines = _lines(0)
    request = json.loads(next(lines, "null") or "null")
    if not request:
        emit("result", {"status": "ERROR", "error": "no request"})
        return 2
    executor = HardwareExecutor(request["deck_config"], backend=request["backend"], on_event=emit)

    def watch() -> None:
        for line in lines:
            if line.strip() and json.loads(line).get("abort"):
                executor.abort()
        executor.abort()  # stdin closed: nobody is watching this run any more

    threading.Thread(target=watch, daemon=True).start()
    for sig in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, lambda *_: executor.abort())

    fd = None
    try:
        if request["backend"] == "star":
            fd = take_lock(lock)
        result = executor.run(request["protocol"], mode=request.get("mode", "full"))
    except Exception as e:
        emit("error", {"message": f"{type(e).__name__}: {e}"})
        result = {"status": "ERROR", "error": str(e)}
    finally:
        if fd is not None:
            os.close(fd)
    emit("result", result)
    return 0 if result["status"] == "DONE" else 1


def status(lock: str) -> Dict[str, Any]:
    """What the Execute page shows about this machine. Lists USB devices; opens none."""
    import importlib.metadata
    from pipeline.remote import code_digest

    info: Dict[str, Any] = {"pylabrobot": importlib.metadata.version("pylabrobot"),
                            "python": sys.version.split()[0], "digest": code_digest()}
    try:
        import libusb_package
        info["star_connected"] = bool(list(libusb_package.find(idVendor=STAR_USB_ID[0], idProduct=STAR_USB_ID[1],
                                                                 find_all=True)))
    except Exception as e:  # no USB support installed, or no libusb
        info["star_connected"], info["usb_error"] = None, f"{type(e).__name__}: {e}"
    info["lock"] = {"path": _lock_path(lock), "held_by": lock_holder(lock)}
    return info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5 on the machine the STARlet is plugged into.")
    parser.add_argument("command", choices=["serve", "status"])
    parser.add_argument("--lock", default="ahc/.star-bridge/lock",
                        help="lock file shared with the AHC bridge (relative to the home folder)")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(status(args.lock)))
    else:
        sys.exit(serve(args.lock))
