#!/usr/bin/env python3
"""Self-healing demo: watch the repair loop run live, then open the result in PLR's visualizer.

    python demo/server.py            # then open http://127.0.0.1:8000

The page picks a protocol and a local Ollama model and starts a run. The server runs
SelfHealer.heal in a background thread and streams each event (stage results, the diagnostic,
the model's reasoning and edits, the harness verdict) to the page with Server-Sent Events.
When a run ends with a passing protocol, "Watch in PyLabRobot" starts stage 4 (PyLabRobot's own
browser visualizer) and replays it there.

The Execute page (/execute) runs stage 5 on a protocol in healed/ (written by `python pipeline.py <protocol>`):
it re-runs the compiler and simulator, walks the operator through the deck setup checklist built from the deck
config and the passing IR, then runs it on the STARlet (or a ChatterBox rehearsal), step by step, either
here or on the Pi the STARlet's USB cable is plugged into (config/remote.json, over SSH).
"""

import argparse
import asyncio
import copy
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import diagnostics, proposals  # noqa: E402
from pipeline.deck import DEFAULT_DECK, INSTRUMENT_DECK, deck_config_for, is_reference, load_deck_config  # noqa: E402
from pipeline.instrument import load_instrument, real_deck_layout  # noqa: E402
from pipeline.remote import RemoteExecutor, load_remote, refusal, remote_status  # noqa: E402
from pipeline.remote import sync as sync_remote  # noqa: E402
from pipeline.self_heal import OllamaBackend, SelfHealer, ir_diff  # noqa: E402
from pipeline.stage2_compiler import compile_protocol  # noqa: E402
from pipeline.setup_guide import _used_labware, deck_drawing, setup_checklist  # noqa: E402
from pipeline.venus_layout import LayoutError, compare_with_deck, import_layout  # noqa: E402
from pipeline.stage4_visualizer import VisualizerSession, replay, start_visualizer  # noqa: E402
from pipeline.stage5_executor import BACKENDS, MODES, ExecutionError, HardwareExecutor  # noqa: E402

CONFIG = ROOT / "config"
PROTOCOLS = ROOT / "protocols"
WORK = ROOT / "build" / "demo"
HEALED = ROOT / "healed"  # written by `python pipeline.py ...`
BENCHMARKS = ROOT / "build" / "benchmark"  # written by `python -m benchmark.run`
OLLAMA = "http://localhost:11434"
REPLAY_STEP_DELAY_S = 0.4

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"), static_url_path="/static")


class Run:
    """One self-healing run: its settings, the events emitted so far, and the outcome."""

    def __init__(self, protocol_file: str, protocol: Dict[str, Any], model: str, max_rounds: int, feedback: str,
                 escalate: bool = True):
        self.id = uuid.uuid4().hex[:8]
        self.protocol_file = protocol_file
        self.original = protocol
        self.deck_config = deck_config_for(protocol, ROOT)
        self.model, self.max_rounds, self.feedback = model, max_rounds, feedback
        self.escalate = escalate  # let a repeating failure escalate to a knowledge-base proposal
        self.started = time.time()
        self.events: List[Dict[str, Any]] = []
        self.cond = threading.Condition()
        self.finished = False
        self.passing: Optional[Dict[str, Any]] = None  # the protocol that passed compile and simulate, if any

    def emit(self, kind: str, data: Dict[str, Any]) -> None:
        with self.cond:
            self.events.append({"kind": kind, "t": round(time.time() - self.started, 1), "data": data})
            self.cond.notify_all()

    def finish(self) -> None:
        with self.cond:
            self.finished = True
            self.cond.notify_all()


RUNS: Dict[str, Run] = {}


def run_worker(run: Run) -> None:
    run.emit("start", {
        "protocol_file": run.protocol_file,
        "protocol_name": run.original.get("protocol_name", run.protocol_file),
        "step_count": len(run.original["steps"]),
        "initial_volumes_ul": run.original.get("initial_volumes_ul", {}),
        "model": run.model, "max_rounds": run.max_rounds, "feedback": run.feedback, "escalate": run.escalate,
    })
    work_dir = WORK / run.id
    try:
        healer = SelfHealer(
            deck_config=run.deck_config,
            backend=OllamaBackend(model=run.model),
            work_dir=str(work_dir),
            feedback_mode=run.feedback,
        )
        result = healer.heal(run.original, max_rounds=run.max_rounds, on_event=run.emit,
                             escalate_after=1 if run.escalate else None)
        diagnostics.record_run(result.rounds, run.protocol_file, run.model)
        stored = proposals.submit(result.proposals, run.protocol_file, run.model)
        done: Dict[str, Any] = {
            "status": result.status,
            "repair_rounds": len(result.rounds) - 1,
            "step_count": len(result.protocol["steps"]),
            "initial_volumes_ul": result.protocol.get("initial_volumes_ul", {}),
            "proposals": stored,  # pending, waiting for a person to approve or reject
            "proposals_not_kept": [c for c in result.proposals if c["problems"]],
        }
        if result.status in ("HEALED", "ALREADY_PASSING"):
            run.passing = result.protocol
        if result.status == "HEALED":
            stem = Path(run.protocol_file).stem
            (work_dir / f"{stem}_healed.json").write_text(json.dumps(result.protocol, indent=2))
            (work_dir / f"{stem}_healed_plr.py").write_text(compile_protocol(result.protocol, run.deck_config))
            done["diff"] = ir_diff(run.original, result.protocol)
            done["saved_to"] = str(work_dir.relative_to(ROOT))
        run.emit("done", done)
    except urllib.error.URLError:
        run.emit("run_error", {"message": f"Could not reach Ollama at {OLLAMA}. Is it running (`ollama serve`)?"})
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
        await replay(session, protocol, deck_config_for(protocol, ROOT), step_delay_s=REPLAY_STEP_DELAY_S)
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
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.loads(r.read())["models"]]
        return jsonify({"available": True, "models": names})
    except OSError:
        return jsonify({"available": False, "models": []})


@app.post("/api/runs")
def create_run():
    if any(not r.finished for r in RUNS.values()):
        return jsonify({"error": "A run is already in progress."}), 409
    body = request.get_json(force=True)
    path = PROTOCOLS / Path(body.get("protocol", "")).name
    if not path.is_file():
        return jsonify({"error": f"Unknown protocol {body.get('protocol')!r}."}), 400
    feedback = body.get("feedback", "translated")
    if feedback not in ("translated", "raw"):
        return jsonify({"error": "feedback must be 'translated' or 'raw'."}), 400
    run = Run(
        protocol_file=path.name,
        protocol=yaml.safe_load(path.read_text()),
        model=body.get("model") or "qwen2.5-coder:7b",
        max_rounds=max(1, min(int(body.get("max_rounds", 5)), 10)),
        feedback=feedback,
        escalate=bool(body.get("escalate", True)),
    )
    RUNS[run.id] = run
    threading.Thread(target=run_worker, args=(run,), daemon=True, name=f"run-{run.id}").start()
    return jsonify({"run_id": run.id})


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
    stem = Path(run.protocol_file).stem
    return Response(
        json.dumps(run.passing, indent=2), mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{stem}_healed.json"'},
    )


@app.post("/api/runs/<run_id>/visualize")
def visualize(run_id: str):
    run = RUNS.get(run_id) or abort(404)
    if run.passing is None:
        return jsonify({"error": "Only a protocol that passed the simulator can be replayed."}), 409
    name = f"{Path(run.protocol_file).stem} ({len(run.passing['steps'])} steps)"
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
        backend=None, work_dir=str(ROOT / "build" / "execute" / name),
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
        if path.stem.endswith("_heal_log"):
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
    return jsonify({
        "name": path.stem,
        "protocol": protocol,
        "gate": _gate(protocol, path.stem),
        "setup": setup_checklist(protocol, deck_config),
        "script": str((HEALED / f"{path.stem}_plr.py").relative_to(ROOT)),
        "deck_file": protocol.get("deck_config", DEFAULT_DECK),
        "deck_kind": "reference" if is_reference(deck_config) else "instrument",
        "real_deck": _real_deck_view(protocol, deck_config),
        "instrument_layout": _instrument_layout_id(deck_config),
    })


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
    if backend == "star" and is_reference(deck_config):
        return jsonify({"error": f"This protocol was drafted for {protocol.get('deck_config', DEFAULT_DECK)}, the reference "
                                 f"simulation deck, not the instrument's. Draft it again for {INSTRUMENT_DECK}."}), 409
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
    what its deck adds (labware, carriers) drawn as still to place. A protocol on the reference deck uses nothing
    on the real one."""
    real = _real_deck()
    view: Dict[str, Any] = {"file": INSTRUMENT_DECK, "reference": is_reference(deck_config), "warning": None}
    used, labels, added = set(), {}, set()
    if not view["reference"]:
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
    view["drawing"]["show_use"] = not view["reference"]
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



# --- Benchmark results (read-only views of build/benchmark/<run>/runs.jsonl) ---

def _benchmark_records(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@app.get("/benchmark")
def benchmark_page():
    return send_from_directory(app.static_folder, "benchmark.html")


@app.get("/api/benchmarks")
def list_benchmarks():
    items = []
    for path in sorted(BENCHMARKS.glob("*/runs.jsonl"), reverse=True):
        records = _benchmark_records(path)
        model_runs = [r for r in records if r.get("temperature") is not None]
        items.append({
            "id": path.parent.name,
            "runs": len(records),
            "scenes": len({r["scene"] for r in records}),
            "conditions": sorted({r["condition"] for r in records}),
            "temperature": model_runs[0]["temperature"] if model_runs else None,
            "repeats": len({r.get("repeat", 0) for r in model_runs}) or 1,
        })
    return jsonify(items)


@app.get("/api/benchmarks/<bench_id>")
def get_benchmark(bench_id: str):
    path = BENCHMARKS / Path(bench_id).name / "runs.jsonl"
    if not path.is_file():
        abort(404)
    return jsonify(_benchmark_records(path))


# --- Library: the static data the pipeline relies on ---

@app.get("/library")
def library_page():
    return send_from_directory(app.static_folder, "library.html")


@app.get("/api/library")
def library():
    """The labware inventory, every deck layout (and which protocols use it), and the diagnostics
    knowledge base, read fresh so recorded runs show up on reload."""
    used_by: Dict[str, List[str]] = {}
    for path in sorted(PROTOCOLS.glob("*")):
        if path.suffix in (".json", ".yaml", ".yml"):
            deck = Path(yaml.safe_load(path.read_text()).get("deck_config", DEFAULT_DECK)).name
            used_by.setdefault(deck, []).append(path.name)
    decks = [{"file": path.name, **json.loads(path.read_text()), "used_by": used_by.get(path.name, [])}
             for path in sorted((CONFIG / "reference").glob("plr_deck*.json"))]
    return jsonify({
        "inventory": json.loads((CONFIG / "reference" / "labware.json").read_text()),
        "decks": decks,
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
