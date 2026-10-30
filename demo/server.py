#!/usr/bin/env python3
"""Self-healing demo: watch the repair loop run live, then open the result in PLR's visualizer.

    python demo/server.py            # then open http://127.0.0.1:8000

The page picks a protocol and a local Ollama model and starts a run. The server runs
SelfHealer.heal in a background thread and streams each event (stage results, the diagnostic,
the model's reasoning and edits, the harness verdict) to the page with Server-Sent Events.
When a run ends with a passing protocol, "Watch in PyLabRobot" starts stage 4 (PyLabRobot's own
browser visualizer) and replays it there.
"""

import argparse
import asyncio
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

from pipeline import diagnostics  # noqa: E402
from pipeline.deck import DEFAULT_DECK, deck_config_for  # noqa: E402
from pipeline.self_heal import OllamaBackend, SelfHealer, ir_diff  # noqa: E402
from pipeline.stage2_compiler import compile_protocol  # noqa: E402
from pipeline.stage4_visualizer import VisualizerSession, replay, start_visualizer  # noqa: E402

CONFIG = ROOT / "config"
PROTOCOLS = ROOT / "protocols"
WORK = ROOT / "build" / "demo"
BENCHMARKS = ROOT / "build" / "benchmark"  # written by `python -m benchmark.run`
OLLAMA = "http://localhost:11434"
REPLAY_STEP_DELAY_S = 0.4

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"), static_url_path="/static")


class Run:
    """One self-healing run: its settings, the events emitted so far, and the outcome."""

    def __init__(self, protocol_file: str, protocol: Dict[str, Any], model: str, max_rounds: int, feedback: str):
        self.id = uuid.uuid4().hex[:8]
        self.protocol_file = protocol_file
        self.original = protocol
        self.deck_config = deck_config_for(protocol, ROOT)
        self.model, self.max_rounds, self.feedback = model, max_rounds, feedback
        self.started = time.time()
        self.events: List[Dict[str, Any]] = []
        self.cond = threading.Condition()
        self.finished = False
        self.passing: Optional[Dict[str, Any]] = None  # the protocol that passed stages 1-3, if any

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
        "model": run.model, "max_rounds": run.max_rounds, "feedback": run.feedback,
    })
    work_dir = WORK / run.id
    try:
        healer = SelfHealer(
            deck_config=run.deck_config,
            labware_path=str(CONFIG / "labware.json"),
            protocol_defaults_path=str(CONFIG / "protocol_defaults.json"),
            backend=OllamaBackend(model=run.model),
            work_dir=str(work_dir),
            feedback_mode=run.feedback,
        )
        result = healer.heal(run.original, max_rounds=run.max_rounds, on_event=run.emit)
        diagnostics.record_run(result.rounds, run.protocol_file, run.model)
        done: Dict[str, Any] = {
            "status": result.status,
            "repair_rounds": len(result.rounds) - 1,
            "step_count": len(result.protocol["steps"]),
            "initial_volumes_ul": result.protocol.get("initial_volumes_ul", {}),
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


async def _open_visualizer(protocol: Dict[str, Any], name: str) -> str:
    if VIS["session"] is not None:  # one visualizer at a time
        try:
            await VIS["session"].stop()
        except Exception:
            pass
    session = await start_visualizer(protocol, deck_config_for(protocol, ROOT), open_browser=False, name=name)
    VIS["session"] = session
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
    )
    RUNS[run.id] = run
    threading.Thread(target=run_worker, args=(run,), daemon=True, name=f"run-{run.id}").start()
    return jsonify({"run_id": run.id})


@app.get("/api/runs/<run_id>/events")
def run_events(run_id: str):
    run = RUNS.get(run_id) or abort(404)

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
        return jsonify({"error": "Only a protocol that passed stages 1-3 can be replayed."}), 409
    name = f"{Path(run.protocol_file).stem} ({len(run.passing['steps'])} steps)"
    try:
        url = asyncio.run_coroutine_threadsafe(_open_visualizer(run.passing, name), VIS_LOOP).result(timeout=30)
    except Exception as e:
        return jsonify({"error": f"Could not start the visualizer: {type(e).__name__}: {e}"}), 500
    return jsonify({"url": url})


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
        items.append({
            "id": path.parent.name,
            "runs": len(records),
            "scenes": len({r["scene"] for r in records}),
            "conditions": sorted({r["condition"] for r in records}),
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
             for path in sorted(CONFIG.glob("plr_deck*.json"))]
    return jsonify({
        "inventory": json.loads((CONFIG / "labware.json").read_text()),
        "decks": decks,
        "knowledge": json.loads(diagnostics.KNOWLEDGE_BASE.read_text()),
    })


def main():
    parser = argparse.ArgumentParser(description="Self-healing demo server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Self-healing demo: http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
