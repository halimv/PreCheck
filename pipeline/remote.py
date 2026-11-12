"""Run stage 5 on the machine the STARlet is plugged into, from this one, over SSH.

macOS never enumerates the STAR, so its USB cable goes to a Raspberry Pi (config/remote.json). The Pi
keeps a copy of pipeline/ and config/ and a Python with PyLabRobot; everything else stays here: the
self-healing loop, the stage 1-3 gate and the Execute page. A run sends the protocol and its deck
config to `python -m pipeline.stage5_executor serve` on the Pi and relays the events it prints.

- `sync` copies pipeline/, config/, healed/ and decks/ to the Pi with rsync.
- `remote_status` asks the Pi for its PyLabRobot version, whether the STAR is on USB, who holds the
  STARlet lock, and a digest of its code, which must equal this machine's before a run.
- `RemoteExecutor` has HardwareExecutor's interface (run, abort, check_supported), so the page
  treats both alike. If the SSH connection drops, the Pi stops before its next step.

This file is also imported on the Pi (for `code_digest`), so it imports only the standard library at the top.
"""

import collections
import hashlib
import json
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
REMOTE_CONFIG = "config/remote.json"
SYNCED = ("pipeline", "config")  # mirrored exactly; healed/ and decks/ are copied without deleting anything on the Pi
# VENUS's labware library (config/Labware) also holds images and 3D models (~140 MB); runs need only the definitions.
LIBRARY_SKIP = ["*.png", "*.PNG", "*.bmp", "*.BMP", "*.x", "*.hxx", "*.gltf", "*.bin", "*.stp", "*.med", "*.sub"]
DIGESTED = ("*.json", "*.lay", "*.tpl", "*.tml", "*.rck", "*.ctr")
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
               "-o", "ServerAliveCountMax=3"]


def load_remote(root: Path = ROOT) -> Optional[Dict[str, Any]]:
    path = root / REMOTE_CONFIG
    return json.loads(path.read_text()) if path.is_file() else None


def code_digest(root: Path = ROOT) -> str:
    """sha256 over the code and config a remote run uses, so both sides can tell they are the same."""
    h = hashlib.sha256()
    for path in sorted([*(root / "pipeline").glob("*.py"), *(p for g in DIGESTED for p in (root / "config").rglob(g))]):
        h.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def _ssh(remote: Dict[str, Any], command: str) -> List[str]:
    return ["ssh", *SSH_OPTIONS, remote["host"], f"cd {shlex.quote(remote['dir'])} && {command}"]


def _stage5(remote: Dict[str, Any], subcommand: str) -> str:
    return (f"exec {shlex.quote(remote['python'])} -m pipeline.stage5_executor {subcommand} "
            f"--lock {shlex.quote(remote['star_lock'])}")


def sync(remote: Dict[str, Any], root: Path = ROOT) -> str:
    """Copy the code, config and healed protocols to the Pi. Returns rsync's output."""
    dest = f"{remote['host']}:{remote['dir']}/"
    base = ["rsync", "-az", "-e", "ssh " + " ".join(SSH_OPTIONS), "--exclude", "__pycache__", "--exclude", ".DS_Store",
            *[x for pattern in LIBRARY_SKIP for x in ("--exclude", pattern)]]
    out = []
    kept = [d for d in ("healed", "decks") if (root / d).is_dir()]  # copied without deleting anything on the Pi
    for cmd in ([*base, "--delete", *SYNCED, dest], *([[*base, *kept, dest]] if kept else [])):
        done = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120)
        if done.returncode != 0:
            raise RuntimeError(f"rsync failed ({done.returncode}): {done.stderr.strip()}")
        out.append(done.stdout)
    return "".join(out)


def remote_status(remote: Dict[str, Any], root: Path = ROOT) -> Dict[str, Any]:
    """{"reachable", "in_sync", "pylabrobot", "star_connected", "lock": {"path", "held_by"}, ...} or an "error"."""
    info: Dict[str, Any] = {"name": remote.get("name", remote["host"]), "host": remote["host"], "reachable": False}
    try:
        done = subprocess.run(_ssh(remote, _stage5(remote, "status")), capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {**info, "error": f"No answer from {remote['host']} within 30 s."}
    if done.returncode == 255:
        return {**info, "error": f"SSH to {remote['host']} failed: {done.stderr.strip()[-300:]}"}
    info["reachable"] = True
    try:
        info.update(json.loads(done.stdout.strip().splitlines()[-1]))
    except (ValueError, IndexError):
        return {**info, "error": "The Pi could not report its status (not set up, or the code is out of date: sync it). "
                                 + done.stderr.strip()[-300:]}
    info["in_sync"] = info.get("digest") == code_digest(root)
    return info


def refusal(info: Dict[str, Any], backend: str) -> Optional[str]:
    """Why a run on the Pi cannot start now, or None."""
    if info.get("error"):
        return info["error"]
    if not info.get("in_sync"):
        return "The code on the Pi differs from this machine's. Sync it first."
    if backend == "star":
        if not info.get("star_connected"):
            return f"The STARlet is not on {info['host']}'s USB ({info.get('usb_error', 'no device 08af:8000')})."
        if info["lock"]["held_by"]:
            return (f"Another program is driving the STARlet: pid {info['lock']['held_by']} holds {info['lock']['path']} "
                    "(the AHC bridge uses this lock). Stop it first.")
    return None


class RemoteExecutor:
    """HardwareExecutor's interface, run on the Pi. `on_event(kind, data)` receives the Pi's events."""

    def __init__(self, deck_config: Dict[str, Any], backend: str, remote: Dict[str, Any],
                 on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        self.deck_config, self.backend, self.remote = deck_config, backend, remote
        self.emit = on_event or (lambda kind, data: print(f"[stage 5 @ {remote['host']}] {kind}: {data}"))
        self._proc: Optional[subprocess.Popen] = None
        self._abort = threading.Event()
        self._io = threading.Lock()

    def check_supported(self, protocol: Dict[str, Any]) -> None:
        from pipeline.stage5_executor import HardwareExecutor
        HardwareExecutor(self.deck_config, backend=self.backend).check_supported(protocol)

    def abort(self) -> None:
        """Stop before the next step starts, as on a local run."""
        self._abort.set()
        self._send({"abort": True})

    def _send(self, message: Dict[str, Any]) -> None:
        with self._io:
            if self._proc and self._proc.stdin and not self._proc.stdin.closed:
                try:
                    self._proc.stdin.write(json.dumps(message) + "\n")
                    self._proc.stdin.flush()
                except OSError:
                    pass

    def run(self, protocol: Dict[str, Any], mode: str = "full") -> Dict[str, Any]:
        host = self.remote["host"]
        proc = subprocess.Popen(_ssh(self.remote, _stage5(self.remote, "serve")), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self._proc = proc
        stderr_tail: collections.deque = collections.deque(maxlen=20)
        threading.Thread(target=lambda: stderr_tail.extend(line.rstrip() for line in proc.stderr),
                         daemon=True).start()
        # stdin stays open for the whole run: closing it tells the Pi to stop.
        self._send({"protocol": protocol, "deck_config": self.deck_config, "backend": self.backend, "mode": mode})
        if self._abort.is_set():
            self._send({"abort": True})
        result = None
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                stderr_tail.append(line.rstrip())
                continue
            if event.get("kind") == "result":
                result = event["data"]
            else:
                self.emit(event["kind"], event["data"])
        proc.wait()
        with self._io:
            try:
                proc.stdin.close()
            except OSError:
                pass
        if result is None:
            message = (f"The run on {host} ended without a result (ssh exit {proc.returncode}). If the connection "
                       "dropped, the Pi stops before its next step: check the instrument and its tips.")
            if stderr_tail:
                message += " Last output: " + " | ".join(list(stderr_tail)[-3:])
            self.emit("error", {"message": message})
            return {"status": "ERROR", "error": message}
        return result
