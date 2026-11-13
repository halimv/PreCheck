#!/usr/bin/env python3
"""Precheck in the browser: the same flow as `python pipeline.py`, watched live.

    python demo/server.py            # then open http://127.0.0.1:8000

The page takes a protocol (its text, a PDF or text file, or a saved IR) and starts a run. The server drafts the
IR and its deck with the Claude CLI when it was given text, then runs SelfHealer.heal in a background thread
(Claude Haiku by default, or a local Ollama model) and streams each event (stage results, the diagnostic, the
model's reasoning and edits, the harness verdict) to the page with Server-Sent Events. A passing protocol is
written to healed/ with its design review, suggestions and AHC layout (pipeline/flow.py); the page shows them,
replays the assay in PyLabRobot's 3D viewer (stage 4), and sends a change the scientist asks for back through
the same loop as the next version.

The Execute page (/execute) runs stage 5 on a protocol in healed/ (written by `python pipeline.py <protocol>`):
it re-runs the compiler and simulator, walks the operator through the deck setup checklist built from the deck
config and the passing IR, then runs it on the STARlet (or a ChatterBox rehearsal), step by step, either
here or on the Pi the STARlet's USB cable is plugged into (config/remote.json, over SSH).
"""

import argparse
import asyncio
import copy
import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from flask import Flask, Response, abort, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent.parent  # the plugin: the code and the lab's ground truth; run outputs are in the working folder (pipeline/paths.py)
sys.path.insert(0, str(ROOT))

from pipeline import diagnostics, proposals  # noqa: E402
from pipeline import library_view, runs, summary  # noqa: E402
from pipeline.deck import DEFAULT_DECK, INSTRUMENT_DECK, DeckError, deck_config_for, load_deck_config  # noqa: E402
from pipeline.instrument import load_instrument, real_deck_layout  # noqa: E402
from pipeline.remote import RemoteExecutor, load_remote, refusal, remote_status  # noqa: E402
from pipeline.remote import sync as sync_remote  # noqa: E402
from pipeline.flow import finish, next_stem  # noqa: E402
from pipeline.self_heal import CLAUDE_MODEL, SelfHealer, ir_diff, make_backend  # noqa: E402
from pipeline.stage0_drafter import DraftError, draft, revise  # noqa: E402
from pipeline.setup_guide import _used_labware, deck_drawing, setup_checklist  # noqa: E402
from pipeline.venus_layout import LayoutError, compare_with_deck, import_layout  # noqa: E402
from pipeline.stage4_visualizer import VisualizerSession, replay, start_visualizer  # noqa: E402
from pipeline.stage5_executor import BACKENDS, MODES, ExecutionError, HardwareExecutor  # noqa: E402

from pipeline import paths  # noqa: E402

CONFIG = ROOT / "config"
PROTOCOLS = paths.WORK / "protocols"
WORK = paths.BUILD / "demo"
HEALED = paths.HEALED  # written by `python pipeline.py ...` in the working folder
OLLAMA = "http://localhost:11434"
UPLOADS = WORK / "uploads"
CLAUDE_MODELS = [CLAUDE_MODEL, "claude-sonnet-5-5", "claude-opus-5-5"]  # repair models offered; the first is the default
MAX_SOURCE_BYTES = 20 * 1024 * 1024
REPLAY_STEP_DELAY_S = 1.0  # seconds after each pipetting call, so the viewer can be followed (about 90 s for a 91-step protocol)

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"), static_url_path="/static")


class Run:
    """One Precheck run: where the protocol comes from, its settings, the events emitted so far, and the outcome.
    `source` is {"kind": "protocol", "file"} (a saved IR), {"kind": "text", "text" | "path"} (to draft), or
    {"kind": "revise", "from", "note"} (a passing protocol and the change asked for)."""

    def __init__(self, source: Dict[str, Any], healer: str, model: Optional[str], max_rounds: int, feedback: str,
                 escalate: bool = True):
        self.id = uuid.uuid4().hex[:8]
        self.source = source
        self.healer, self.model, self.max_rounds, self.feedback = healer, model, max_rounds, feedback
        self.escalate = escalate  # let a repeating failure escalate to a knowledge-base proposal
        self.started = time.time()
        self.events: List[Dict[str, Any]] = []
        self.cond = threading.Condition()
        self.finished = False
        self.passing: Optional[Dict[str, Any]] = None  # the protocol that passed compile and simulate, if any
        self.name: Optional[str] = None  # its name in healed/

    def emit(self, kind: str, data: Dict[str, Any]) -> None:
        with self.cond:
            self.events.append({"kind": kind, "t": round(time.time() - self.started, 1), "data": data})
            self.cond.notify_all()

    def finish(self) -> None:
        with self.cond:
            self.finished = True
            self.cond.notify_all()


RUNS: Dict[str, Run] = {}


def _instrument_deck_file() -> str:
    return load_instrument()["deck_layout"]["file"]


def _draft_summary(d) -> Dict[str, Any]:
    mapping = json.loads(d.mapping_path.read_text()) if d.mapping_path else {"labware": {}, "operator_changes": []}
    return {
        "file": str(d.path.relative_to(ROOT)), "attempts": d.attempts, "cost_usd": round(d.cost_usd, 4),
        "protocol_name": d.protocol.get("protocol_name"), "step_count": len(d.protocol["steps"]),
        "assumptions": d.protocol.get("assumptions", []),
        "labware": [{"name": name, "type": m.get("venus_type") or "tip waste", "action": m["action"].replace("_", " "),
                     "where": (f"{m['carrier']['venus_type']} rail {m['carrier']['rails']}, position "
                               f"{m['position']['hamilton']}") if m.get("carrier") else "the deck's tip waste"}
                    for name, m in mapping["labware"].items()],
        "operator_changes": mapping["operator_changes"],
    }


def _protocol_for(run: Run):
    """(protocol, file name, the protocol it revises or None): drafted or revised by Claude when the source asks."""
    src = run.source
    if src["kind"] == "protocol":
        return yaml.safe_load((PROTOCOLS / src["file"]).read_text()), src["file"], None
    deck_file = _instrument_deck_file()
    base_deck = load_deck_config(str(ROOT / deck_file))  # the deck on the STARlet: needs resolve against it
    if src["kind"] == "text":
        run.emit("draft_request", {"what": "Drafting the protocol and choosing its labware with Claude"})
        d = draft(src.get("path") or src["text"], base_deck, deck_file=deck_file, out=io.StringIO())
        previous = None
    else:
        run.emit("draft_request", {"what": "Revising the protocol with Claude", "note": src["note"]})
        previous = src["from"]
        d = revise(previous, src["note"], base_deck, current_name=f"{src['name']}.json", deck_file=deck_file,
                   out=io.StringIO(), stem=next_stem(src["name"]))
    run.emit("draft", _draft_summary(d))
    return d.protocol, d.path.name, previous


def run_worker(run: Run) -> None:
    work_dir = WORK / run.id
    try:
        protocol, protocol_file, previous = _protocol_for(run)
        deck_config = deck_config_for(protocol, ROOT)
        backend = make_backend(run.healer, run.model)
        run.emit("start", {
            "protocol_file": protocol_file,
            "protocol_name": protocol.get("protocol_name", protocol_file),
            "step_count": len(protocol["steps"]),
            "initial_volumes_ul": protocol.get("initial_volumes_ul", {}),
            "model": backend.model, "max_rounds": run.max_rounds, "feedback": run.feedback, "escalate": run.escalate,
            "simulated_on": "the STAR model of this instrument" if deck_config.get("instrument") else "the generic ChatterBox",
        })
        healer = SelfHealer(deck_config=deck_config, backend=backend, work_dir=str(work_dir), feedback_mode=run.feedback)
        result = healer.heal(protocol, max_rounds=run.max_rounds, on_event=run.emit,
                             escalate_after=1 if run.escalate else None)
        diagnostics.record_run(result.rounds, protocol_file, backend.model)
        stored = proposals.submit(result.proposals, protocol_file, backend.model)
        done: Dict[str, Any] = {
            "status": result.status,
            "repair_rounds": len(result.rounds) - 1,
            "step_count": len(result.protocol["steps"]),
            "initial_volumes_ul": result.protocol.get("initial_volumes_ul", {}),
            "proposals": stored,  # pending, waiting for a person to approve or reject
            "proposals_not_kept": [c for c in result.proposals if c["problems"]],
        }
        tiers = [{"model": backend.model, "status": result.status, "rounds": result.rounds}]
        source = run.source.get("text") if run.source.get("kind") == "text" else run.source.get("path") or run.source.get("file")
        if result.status in ("HEALED", "ALREADY_PASSING"):
            run.passing, run.name = result.protocol, Path(protocol_file).stem
            done["report"] = finish(result.protocol, deck_config, run.name, result.rounds, status=result.status)
            files = done["report"]["files"]
            runs.record(run.name, source, result.protocol, result.rounds, tiers, True,
                        (paths.WORK / files["summary"]).read_text(), done["report"],
                        script=(paths.WORK / files["script"]).read_text(),
                        layout=paths.WORK / files["ahc_layout"], runs_dir=paths.WORK / "runs")
        else:
            failed_text = summary.failure_markdown(protocol, tiers, run.max_rounds, work_dir / "heal_log.json")
            runs.record(Path(protocol_file).stem, source, protocol, result.rounds, tiers, False, failed_text, None,
                        runs_dir=paths.WORK / "runs")
            if result.status == "HEALED":
                done["diff"] = ir_diff(protocol, result.protocol)
            if previous is not None:
                done["revision_diff"] = ir_diff(previous, result.protocol)
        run.emit("done", done)
    except urllib.error.URLError:
        run.emit("run_error", {"message": f"Could not reach Ollama at {OLLAMA}. Is it running (`ollama serve`)?"})
    except (DraftError, DeckError) as e:
        run.emit("run_error", {"message": str(e)})
    except Exception as e:  # surface anything else on the page instead of a silent stall
        run.emit("run_error", {"message": f"{type(e).__name__}: {e}"})
    finally:
        run.finish()


# --- Stage 4: PyLabRobot's visualizer runs on its own event loop in a background thread ---

VIS_LOOP = asyncio.new_event_loop()
threading.Thread(target=VIS_LOOP.run_forever, daemon=True, name="visualizer-loop").start()
VIS: Dict[str, Optional[VisualizerSession]] = {"session": None}


async def _replay_logged(session: VisualizerSession, protocol: Dict[str, Any]) -> None:
    try:
        # Wait up to a minute for the viewer tab to connect, so the replay is watched from its first step.
        await replay(session, protocol, deck_config_for(protocol, ROOT), step_delay_s=REPLAY_STEP_DELAY_S,
                     wait_for_browser_s=60.0)
    except Exception as e:
        print(f"[stage 4] replay stopped: {type(e).__name__}: {e}")


async def _open_visualizer(protocol: Dict[str, Any], name: str, run_steps: bool = True,
                           deck_config: Optional[Dict[str, Any]] = None) -> str:
    """PyLabRobot's visualizer on the protocol's deck (or `deck_config`), replaying the steps if asked."""
    if VIS["session"] is not None:  # one visualizer at a time
        try:
            await VIS["session"].stop()
        except Exception:
            pass
    session = await start_visualizer(protocol, deck_config or deck_config_for(protocol, ROOT), open_browser=False,
                                     name=name)
    VIS["session"] = session
    if run_steps:
        asyncio.get_running_loop().create_task(_replay_logged(session, protocol))
    return session.url


# --- HTTP API ---

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/protocols")
def list_protocols():
    items = []
    for path in sorted(PROTOCOLS.glob("*")):
        if path.suffix not in (".json", ".yaml", ".yml"):
            continue
        p = yaml.safe_load(path.read_text())
        items.append({
            "file": path.name,
            "name": p.get("protocol_name", path.stem),
            "step_count": len(p.get("steps", [])),
            "initial_volumes_ul": p.get("initial_volumes_ul", {}),
        })
    return jsonify(items)


@app.get("/api/models")
def list_models():
    """The repair models on offer: Claude through its CLI (the default), and whatever Ollama has pulled."""
    import shutil
    from pipeline.stage0_drafter import CLAUDE_BIN
    claude = shutil.which(CLAUDE_BIN) is not None or Path(CLAUDE_BIN).is_file()
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as r:
            local = [m["name"] for m in json.loads(r.read())["models"]]
    except OSError:
        local = []
    return jsonify({"claude": {"available": claude, "models": CLAUDE_MODELS, "default": CLAUDE_MODEL},
                    "ollama": {"available": bool(local), "models": local}})


def _settings(body: Dict[str, Any]) -> Dict[str, Any]:
    healer = body.get("healer", "claude")
    feedback = body.get("feedback", "translated")
    if healer not in ("claude", "ollama"):
        abort(Response(json.dumps({"error": "healer must be 'claude' or 'ollama'."}), 400, mimetype="application/json"))
    if feedback not in ("translated", "raw"):
        abort(Response(json.dumps({"error": "feedback must be 'translated' or 'raw'."}), 400, mimetype="application/json"))
    escalate = body.get("escalate", True)
    return {"healer": healer, "model": body.get("model") or None, "feedback": feedback,
            "max_rounds": max(1, min(int(body.get("max_rounds", 5)), 10)),
            "escalate": escalate not in (False, "false", "0", "")}


def _start(run: Run):
    RUNS[run.id] = run
    threading.Thread(target=run_worker, args=(run,), daemon=True, name=f"run-{run.id}").start()
    return jsonify({"run_id": run.id})


@app.post("/api/runs")
def create_run():
    """Start a run from a saved IR (`protocol`), from protocol text (`text`), or from an uploaded PDF or text
    file (`file`, multipart)."""
    if any(not r.finished for r in RUNS.values()):
        return jsonify({"error": "A run is already in progress."}), 409
    body = request.form.to_dict() if request.files or request.form else request.get_json(force=True)
    upload = request.files.get("file")
    if upload and upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in (".pdf", ".txt", ".md"):
            return jsonify({"error": "Upload a PDF or a text file."}), 400
        data = upload.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            return jsonify({"error": "That file is larger than 20 MB."}), 400
        UPLOADS.mkdir(parents=True, exist_ok=True)
        stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(upload.filename).stem)[:60] or "protocol"
        path = UPLOADS / f"{uuid.uuid4().hex[:6]}_{stem}{suffix}"
        path.write_bytes(data)
        source = {"kind": "text", "path": str(path)}
    elif (body.get("text") or "").strip():
        source = {"kind": "text", "text": body["text"].strip()}
    else:
        path = PROTOCOLS / Path(body.get("protocol") or "").name
        if not path.is_file():
            return jsonify({"error": "Describe a protocol, attach a file, or choose a saved protocol."}), 400
        source = {"kind": "protocol", "file": path.name}
    return _start(Run(source=source, **_settings(body)))


@app.post("/api/runs/<run_id>/revise")
def revise_run(run_id: str):
    """Send a passing protocol back through the loop with the change the scientist asks for, as its next version."""
    parent = RUNS.get(run_id) or abort(404)
    if parent.passing is None:
        return jsonify({"error": "Only a protocol that passed can be revised."}), 409
    if any(not r.finished for r in RUNS.values()):
        return jsonify({"error": "A run is already in progress."}), 409
    body = request.get_json(force=True)
    note = (body.get("note") or "").strip()
    if not note:
        return jsonify({"error": "Say what to change."}), 400
    settings = {"healer": parent.healer, "model": parent.model, "feedback": parent.feedback,
                "max_rounds": parent.max_rounds, "escalate": parent.escalate}
    return _start(Run(source={"kind": "revise", "from": parent.passing, "name": parent.name, "note": note}, **settings))


@app.get("/api/runs/<run_id>/events")
def run_events(run_id: str):
    return _event_stream(RUNS.get(run_id) or abort(404))


def _event_stream(run) -> Response:
    """Server-Sent Events for anything with `events`, `cond` and `finished` (a Run or an Execution)."""

    def stream():
        sent = 0
        while True:
            with run.cond:
                if sent >= len(run.events) and not run.finished:
                    run.cond.wait(timeout=15)
                batch, finished = run.events[sent:], run.finished
                sent += len(batch)
            for event in batch:
                yield f"event: {event['kind']}\ndata: {json.dumps(event)}\n\n"
            if finished and sent >= len(run.events):
                yield "event: end\ndata: {}\n\n"
                return
            if not batch:
                yield ": keep-alive\n\n"

    return Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/runs/<run_id>/healed.json")
def healed_ir(run_id: str):
    run = RUNS.get(run_id) or abort(404)
    if run.passing is None:
        abort(404)
    return Response(
        json.dumps(run.passing, indent=2), mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{run.name}.json"'},
    )


@app.post("/api/runs/<run_id>/visualize")
def visualize(run_id: str):
    run = RUNS.get(run_id) or abort(404)
    if run.passing is None:
        return jsonify({"error": "Only a protocol that passed the simulator can be replayed."}), 409
    name = f"{run.name} ({len(run.passing['steps'])} steps)"
    try:
        url = asyncio.run_coroutine_threadsafe(_open_visualizer(run.passing, name), VIS_LOOP).result(timeout=30)
    except Exception as e:
        return jsonify({"error": f"Could not start the visualizer: {type(e).__name__}: {e}"}), 500
    return jsonify({"url": url})


# --- Stage 5: deck setup and execution of a protocol in healed/ ---

class Execution:
    """One stage-5 run: its events, and the executor (so it can be aborted)."""

    def __init__(self, name: str, backend: str, mode: str):
        self.id = uuid.uuid4().hex[:8]
        self.name, self.backend, self.mode = name, backend, mode
        self.started = time.time()
        self.events: List[Dict[str, Any]] = []
        self.cond = threading.Condition()
        self.finished = False
        self.executor: Optional[HardwareExecutor] = None

    emit, finish = Run.emit, Run.finish


EXECUTIONS: Dict[str, Execution] = {}


def _healed_path(name: str) -> Path:
    path = HEALED / f"{Path(name).stem}.json"
    if not path.is_file() or path.stem.endswith("_heal_log"):
        abort(404)
    return path


def _gate(protocol: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Re-run the compiler and simulator on the file as it is now: only a protocol that passes may be executed."""
    healer = SelfHealer(
        deck_config=deck_config_for(protocol, ROOT),
        backend=None, work_dir=str(paths.BUILD / "execute" / name),
    )
    gate = healer.evaluate(protocol, 0)
    return {"passed": gate.passed, "stage": gate.stage, "summary": gate.summary}


@app.get("/execute")
def execute_page():
    return send_from_directory(app.static_folder, "execute.html")


@app.get("/api/healed")
def list_healed():
    items = []
    for path in sorted(HEALED.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.stem.endswith(("_heal_log", "_report")):
            continue
        p = json.loads(path.read_text())
        items.append({"name": path.stem, "protocol_name": p.get("protocol_name", path.stem),
                      "step_count": len(p.get("steps", [])), "modified": path.stat().st_mtime})
    return jsonify(items)


@app.get("/api/healed/<name>")
def healed_setup(name: str):
    path = _healed_path(name)
    protocol = json.loads(path.read_text())
    deck_config = deck_config_for(protocol, ROOT)
    setup, gate = setup_checklist(protocol, deck_config), _gate(protocol, path.stem)
    return jsonify({
        "name": path.stem,
        "protocol": protocol,
        "gate": gate,
        "setup": setup,
        "script": str((HEALED / f"{path.stem}_plr.py").relative_to(ROOT)),
        "deck_file": protocol.get("deck_config", DEFAULT_DECK),
        "real_deck": _real_deck_view(protocol, deck_config),
        "instrument_layout": _instrument_layout_id(deck_config),
    })


@app.post("/api/healed/<name>/replay")
def replay_healed(name: str):
    """Relaunch PyLabRobot's 3D viewer on a healed protocol and replay it (one pipetting step at a time, slowly). Only a
    protocol that passes the gate now is replayed."""
    path = _healed_path(name)
    protocol = json.loads(path.read_text())
    gate = _gate(protocol, path.stem)
    if not gate["passed"]:
        return jsonify({"error": f"Not replayed: the protocol no longer passes the simulator ({gate['summary']})."}), 409
    name_shown = f"{path.stem} ({len(protocol['steps'])} steps)"
    try:
        url = asyncio.run_coroutine_threadsafe(
            _open_visualizer(protocol, name_shown, run_steps=True, deck_config=deck_config_for(protocol, ROOT)),
            VIS_LOOP).result(timeout=30)
    except Exception as e:
        return jsonify({"error": f"Could not start the visualizer: {type(e).__name__}: {e}"}), 500
    return jsonify({"url": url, "steps": len(protocol["steps"])})


@app.post("/api/healed/<name>/deck")
def show_deck(name: str):
    """Open PyLabRobot's visualizer on the deck that is on the STARlet now (the instrument library's VENUS layout),
    nothing run: the real state before a run."""
    _healed_path(name)
    try:
        url = asyncio.run_coroutine_threadsafe(
            _open_visualizer({}, f"Deck on the STARlet ({INSTRUMENT_DECK})", run_steps=False, deck_config=_real_deck()),
            VIS_LOOP).result(timeout=30)
    except Exception as e:
        return jsonify({"error": f"Could not start the visualizer: {type(e).__name__}: {e}"}), 500
    return jsonify({"url": url})


def execute_worker(ex: Execution, protocol: Dict[str, Any]) -> None:
    try:
        ex.executor.run(protocol, mode=ex.mode)
    except Exception as e:
        ex.emit("error", {"message": f"{type(e).__name__}: {e}"})
    finally:
        ex.finish()


@app.post("/api/executions")
def start_execution():
    if any(not e.finished for e in EXECUTIONS.values()):
        return jsonify({"error": "A run is already in progress on the instrument."}), 409
    body = request.get_json(force=True)
    backend, mode, where = body.get("backend"), body.get("mode", "full"), body.get("where", "local")
    if backend not in BACKENDS or mode not in MODES or where not in ("local", "pi"):
        return jsonify({"error": f"backend must be one of {BACKENDS}, mode one of {MODES} and where local or pi."}), 400
    path = _healed_path(str(body.get("name", "")))
    protocol = json.loads(path.read_text())
    gate = _gate(protocol, path.stem)
    if not gate["passed"]:
        return jsonify({"error": f"The protocol no longer passes the simulator: {gate['summary']}"}), 409
    deck_config = deck_config_for(protocol, ROOT)
    if backend == "star":
        required = {i["id"] for i in setup_checklist(protocol, deck_config)["items"]}
        missing = required - set(body.get("confirmed", []))
        if missing:
            return jsonify({"error": f"{len(missing)} setup item(s) are not confirmed yet."}), 409
        layout_id = body.get("layout") or _instrument_layout_id(deck_config)  # default: the deck the library says is there
        if layout_id:
            layout = LAYOUTS.get(str(layout_id))
            if layout is None:
                return jsonify({"error": "The Venus layout is no longer loaded; load the .lay again."}), 409
            if not _layout_comparison(layout, protocol)["ok"]:
                return jsonify({"error": f"The Venus layout {layout['name']} does not match the deck this protocol "
                                         "was simulated on. Fix the deck (or the protocol's deck config) first."}), 409
    ex = Execution(path.stem, backend, mode)
    if where == "pi":
        remote = load_remote(ROOT)
        if remote is None:
            return jsonify({"error": "No Pi is configured (config/remote.json)."}), 409
        reason = refusal(remote_status(remote, ROOT), backend)
        if reason:
            return jsonify({"error": reason}), 409
        ex.executor = RemoteExecutor(deck_config, backend, remote, on_event=ex.emit)
    else:
        ex.executor = HardwareExecutor(deck_config, backend=backend, on_event=ex.emit)
    try:
        ex.executor.check_supported(protocol)
    except ExecutionError as e:
        return jsonify({"error": str(e)}), 409
    EXECUTIONS[ex.id] = ex
    threading.Thread(target=execute_worker, args=(ex, protocol), daemon=True, name=f"execute-{ex.id}").start()
    return jsonify({"execution_id": ex.id})


@app.get("/api/executions/<ex_id>/events")
def execution_events(ex_id: str):
    return _event_stream(EXECUTIONS.get(ex_id) or abort(404))


@app.post("/api/executions/<ex_id>/abort")
def abort_execution(ex_id: str):
    ex = EXECUTIONS.get(ex_id) or abort(404)
    ex.executor.abort()
    return jsonify({"status": "stopping after the current step"})


# --- The Pi the STARlet is plugged into (config/remote.json; pipeline/remote.py) ---

@app.get("/api/remote")
def get_remote():
    remote = load_remote(ROOT)
    if remote is None:
        return jsonify({"configured": False})
    return jsonify({"configured": True, **remote_status(remote, ROOT)})


@app.post("/api/remote/sync")
def post_remote_sync():
    """Copy pipeline/, config/ and healed/ to the Pi, then report its status."""
    remote = load_remote(ROOT) or abort(404)
    if any(not e.finished for e in EXECUTIONS.values()):
        return jsonify({"error": "A run is in progress; sync after it ends."}), 409
    try:
        sync_remote(remote, ROOT)
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500
    return jsonify({"configured": True, **remote_status(remote, ROOT)})


# --- Venus deck layouts (.lay): compare the deck that is physically on the STARlet with a protocol's ---

LAYOUTS: Dict[str, Dict[str, Any]] = {}
MAX_LAYOUT_BYTES = 5 * 1024 * 1024


REAL_DECK: Dict[str, Any] = {}


def _real_deck() -> Dict[str, Any]:
    """The deck on the STARlet now: the instrument library's VENUS layout, read again when the file changes."""
    path = ROOT / INSTRUMENT_DECK
    if REAL_DECK.get("mtime") != path.stat().st_mtime:
        REAL_DECK.update(mtime=path.stat().st_mtime, config=load_deck_config(str(path)))
    return copy.deepcopy(REAL_DECK["config"])


def _real_deck_view(protocol: Dict[str, Any], deck_config: Dict[str, Any]) -> Dict[str, Any]:
    """The Execute page's deck drawing: the deck on the STARlet now, with the labware this protocol uses marked and
    what its deck adds (labware, carriers) drawn as still to place."""
    real = _real_deck()
    view: Dict[str, Any] = {"file": INSTRUMENT_DECK, "warning": None}
    used, labels, added = set(), {}, set()
    for lid in _used_labware(protocol):
        spec = deck_config["labware"].get(lid)
        if not spec or spec["kind"] == "trash":
            continue
        if spec.get("venus_id") in real["labware"]:
            used.add(spec["venus_id"])
            labels[spec["venus_id"]] = lid
            continue
        carrier = next((c for c in deck_config["carriers"] if c["name"] == spec.get("carrier")), None)
        if carrier and carrier["name"] not in {c["name"] for c in real["carriers"]}:
            real["carriers"].append(carrier)
        real["labware"][lid] = spec
        added.add(lid)
    try:
        view["drawing"] = deck_drawing(real, used, labels, added)
    except Exception as e:  # the .lay changed since the deck was built: the additions no longer fit
        view["warning"] = (f"This protocol's additions no longer fit the deck in {INSTRUMENT_DECK} "
                           f"({type(e).__name__}: {e}); draft it again.")
        view["drawing"] = deck_drawing(_real_deck(), set())
    view["drawing"]["show_use"] = True
    return view


def _instrument_layout_id(deck_config: Dict[str, Any]) -> Optional[str]:
    """The VENUS layout the instrument library has for the deck config's instrument, loaded (again when the file
    changes) under a fixed id, or None for a deck config that names no instrument."""
    if not deck_config.get("instrument"):
        return None
    instrument = load_instrument(deck_config["instrument"])
    path = real_deck_layout(instrument, ROOT)
    layout_id = f"instrument-{instrument['serial']}"
    cached = LAYOUTS.get(layout_id)
    if cached is None or cached.get("mtime") != path.stat().st_mtime:
        LAYOUTS[layout_id] = {**import_layout(path.read_bytes(), str(path.relative_to(ROOT)), ROOT),
                              "mtime": path.stat().st_mtime, "library": True}
    return layout_id


def _layout_comparison(layout: Dict[str, Any], protocol: Dict[str, Any]) -> Dict[str, Any]:
    return compare_with_deck(layout["deck_config"], deck_config_for(protocol, ROOT), _used_labware(protocol))


def _layout_reply(layout_id: str, protocol_name: Optional[str]) -> Dict[str, Any]:
    layout = LAYOUTS[layout_id]
    reply = {"id": layout_id, **layout}
    if protocol_name:
        reply["comparison"] = _layout_comparison(layout, json.loads(_healed_path(protocol_name).read_text()))
    return reply


@app.post("/api/layouts")
def upload_layout():
    """The body is the .lay file itself; `?filename=` names it and `?name=` picks the protocol to compare with."""
    data = request.get_data(cache=False)
    if not data or len(data) > MAX_LAYOUT_BYTES:
        return jsonify({"error": "Send a .lay file of at most 5 MB."}), 400
    filename = Path(request.args.get("filename", "layout.lay")).name
    try:
        layout = import_layout(data, filename, ROOT)
    except LayoutError as e:
        return jsonify({"error": str(e)}), 400
    layout_id = uuid.uuid4().hex[:8]
    LAYOUTS[layout_id] = layout
    return jsonify(_layout_reply(layout_id, request.args.get("name")))


@app.get("/api/layouts/<layout_id>")
def get_layout(layout_id: str):
    if layout_id not in LAYOUTS:
        abort(404)
    return jsonify(_layout_reply(layout_id, request.args.get("name")))



@app.get("/library")
def library_page():
    return send_from_directory(app.static_folder, "library.html")


@app.get("/runs")
def runs_page():
    return send_from_directory(app.static_folder, "runs.html")


@app.get("/api/runs")
def list_run_records():
    """Every run in the working folder's runs/, newest first."""
    return jsonify(runs.list_runs(paths.WORK / "runs"))


@app.get("/api/runs/<run_id>")
def get_run_record(run_id: str):
    manifest = runs.load(run_id, paths.WORK / "runs")
    if manifest is None:
        abort(404)
    return jsonify(manifest)


@app.get("/api/runs/<run_id>/file/<name>")
def get_run_file(run_id: str, name: str):
    """A file from one run's folder (its summary, protocol, script, layout, report or input)."""
    path = runs.run_file(run_id, name, paths.WORK / "runs")
    if path is None:
        abort(404)
    return send_from_directory(path.parent, path.name, as_attachment=False, mimetype="text/plain")


@app.post("/api/runs/<run_id>/acknowledge")
def acknowledge_run_item(run_id: str):
    """A person's review of one item: their typed name and an optional note."""
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Type your name to acknowledge an item."}), 400
    try:
        manifest = runs.acknowledge(run_id, int(body.get("item", -1)), name, str(body.get("note", "")),
                                    paths.WORK / "runs")
    except (IndexError, FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(manifest)


@app.get("/api/library")
def library():
    """Ground truth only: VENUS's labware library and the deck on the STARlet (pipeline/library_view.py), the
    protocols drafted for that deck, and the diagnostics knowledge base, read fresh so recorded runs show up."""
    return jsonify({
        "inventory": library_view.inventory(ROOT),
        "decks": [{**library_view.instrument_deck(ROOT),
                   "used_by": library_view.used_by(sorted(PROTOCOLS.glob("*")) + sorted(HEALED.glob("*.json")), ROOT)}],
        "knowledge": json.loads(diagnostics.KNOWLEDGE_BASE.read_text()),
    })


@app.post("/api/proposals/<pid>/<decision>")
def review_proposal(pid: str, decision: str):
    """A person approves or rejects a pending knowledge-base proposal."""
    if decision not in ("approve", "reject"):
        abort(404)
    comment = str((request.get_json(silent=True) or {}).get("comment", ""))[:500]
    try:
        if decision == "approve":
            entry = proposals.approve(pid, comment=comment)
            return jsonify({"status": "approved", "entry": entry})
        proposals.reject(pid, comment=comment)
        return jsonify({"status": "rejected"})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:  # already reviewed, or the merged knowledge base would not load
        return jsonify({"error": str(e)}), 409


def main():
    parser = argparse.ArgumentParser(description="Self-healing demo server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Self-healing demo: http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
