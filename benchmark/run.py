#!/usr/bin/env python3
"""Run the serial dilution benchmark and score every run at several retry budgets.

Conditions:
  B0          fail-on-error, no repair
  B1          rule-based: applies the translator's suggested fix, no model
  translated  local model, lab-concept diagnostics (the pipeline default)
  raw         local model, raw PLR exception text only

Usage:
  python -m benchmark.run                                   # all scenes, all conditions
  python -m benchmark.run --conditions B0,B1                # baselines only (seconds)
  python -m benchmark.run --conditions translated --scenes S2_stock_790
"""

import argparse
import contextlib
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from benchmark.backends import CountingOllamaBackend, RuleBackend
from benchmark.scenes import ROOT, Scene, build_scenes, expected_concentrations
from benchmark.scorer import score
from pipeline.deck import load_deck_config
from pipeline.self_heal import SelfHealer

CONFIG_DIR = ROOT / "config"
CONDITIONS = ("B0", "B1", "translated", "raw")


def run_one(scene: Scene, condition: str, args, work_dir: Path, deck_config: Dict[str, Any]) -> Dict[str, Any]:
    if condition in ("B0", "B1"):
        backend: Any = RuleBackend()
        feedback = "translated"
    else:
        backend = CountingOllamaBackend(model=args.model, temperature=args.temperature, num_ctx=args.num_ctx)
        feedback = condition
    max_rounds = 0 if condition == "B0" else args.max_rounds
    healer = SelfHealer(
        deck_config=deck_config,
        backend=backend,
        work_dir=str(work_dir),
        feedback_mode=feedback,
    )

    # Rebuild the round records from events so a crash mid-run still leaves the rounds before it.
    rounds: List[Dict[str, Any]] = []

    def on_event(kind: str, data: Dict[str, Any]) -> None:
        if kind == "gate":
            rounds.append({"round": data["round"], "stage": data["stage"], "passed": data["passed"],
                           "result": data["summary"]})
        elif kind == "model_reply":
            rounds[-1].update(model_reasoning=data["reasoning"], edits=data["edits"])
        elif kind == "edits":
            if data.get("errors"):
                rounds[-1]["edit_errors"] = data["errors"]
            if data["accepted"]:
                rounds[-1]["edits_applied"] = data.get("applied", list(range(len(rounds[-1].get("edits", [])))))

    status, error, crashed_round = None, None, None
    start = time.time()
    with open(work_dir / "console.log", "w") as log, contextlib.redirect_stdout(log):
        try:
            status = healer.heal(scene.protocol, max_rounds=max_rounds, on_event=on_event).status
        except Exception as e:  # a model reply that isn't valid JSON, a timeout, ...
            status, error = "CRASH", f"{type(e).__name__}: {e}"
            crashed_round = rounds[-1]["round"] if rounds else 0
    wall = time.time() - start

    expected = expected_concentrations()
    budgets = [0] if condition == "B0" else [b for b in args.budgets if b <= max_rounds]
    return {
        "scene": scene.scene_id, "family": scene.family, "injection": scene.injection,
        "condition": condition, "model": backend.model, "temperature": args.temperature if condition not in ("B0", "B1") else None,
        "feedback": feedback, "max_rounds": max_rounds, "num_ctx": args.num_ctx,
        "status": status, "error": error, "wall_seconds": round(wall, 1),
        "prompt_tokens": sum(c["prompt_tokens"] for c in backend.calls),
        "output_tokens": sum(c["output_tokens"] for c in backend.calls),
        "calls": backend.calls, "rounds": rounds,
        "scores": [score(scene, rounds, work_dir, expected, b, crashed_round, backend.calls, args.num_ctx)
                   for b in budgets],
    }


def summarize(records: List[Dict[str, Any]]) -> str:
    lines = [
        "| Condition | Budget | Runs | Mean score | Healed | Diagnosis | Execution | Mean tokens | Mean time (s) | Failure labels |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    groups: Dict[tuple, List[tuple]] = {}
    for r in records:
        for s in r["scores"]:
            groups.setdefault((r["condition"], s["budget"]), []).append((r, s))
    order = {c: i for i, c in enumerate(CONDITIONS)}
    for (cond, budget), rows in sorted(groups.items(), key=lambda kv: (order.get(kv[0][0], 9), kv[0][1])):
        n = len(rows)
        mean = lambda key: sum(s[key] for _, s in rows) / n
        labels = Counter(s["failure_label"] for _, s in rows if s["failure_label"])
        lines.append(
            f"| {cond} | {budget} | {n} | {mean('score'):.2f} | {sum(s['healed'] for _, s in rows)}/{n} | "
            f"{mean('diagnosis'):.2f} | {mean('execution'):.2f} | "
            f"{sum(r['prompt_tokens'] + r['output_tokens'] for r, _ in rows) / n:.0f} | "
            f"{sum(r['wall_seconds'] for r, _ in rows) / n:.0f} | "
            f"{', '.join(f'{k} {v}' for k, v in labels.most_common()) or '-'} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Serial dilution self-healing benchmark")
    parser.add_argument("--conditions", default=",".join(CONDITIONS))
    parser.add_argument("--scenes", default="", help="Comma-separated scene IDs or prefixes (default: all)")
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--num-ctx", type=int, default=32768)
    parser.add_argument("--max-rounds", type=int, default=10)
    parser.add_argument("--budgets", default="1,2,3,5,10", help="Retry budgets to score each run at")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", default=str(ROOT / "build" / "benchmark"))
    args = parser.parse_args()
    args.budgets = [int(b) for b in args.budgets.split(",")]

    conditions = [c for c in args.conditions.split(",") if c]
    unknown = set(conditions) - set(CONDITIONS)
    if unknown:
        sys.exit(f"Unknown condition(s): {', '.join(sorted(unknown))}")
    wanted = [s for s in args.scenes.split(",") if s]
    scenes = [s for s in build_scenes() if not wanted or any(s.scene_id.startswith(w) for w in wanted)]

    run_dir = Path(args.output) / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    deck_config = load_deck_config(str(CONFIG_DIR / "reference" / "plr_deck.json"))
    jobs = [(c, s, k) for c in conditions for s in scenes for k in range(args.repeats if c not in ("B0", "B1") else 1)]
    print(f"{len(jobs)} runs -> {run_dir}")

    records = []
    with open(run_dir / "runs.jsonl", "w") as out:
        for i, (cond, scene, rep) in enumerate(jobs, start=1):
            work_dir = run_dir / cond / scene.scene_id / f"rep{rep}"
            work_dir.mkdir(parents=True, exist_ok=True)
            rec = run_one(scene, cond, args, work_dir, deck_config)
            rec["repeat"] = rep
            out.write(json.dumps(rec) + "\n")
            out.flush()
            records.append(rec)
            best = rec["scores"][-1]
            print(f"[{i}/{len(jobs)}] {cond:<10} {scene.scene_id:<18} {rec['status']:<14} "
                  f"score {best['score']:>2} (budget {best['budget']})  {rec['wall_seconds']:.0f}s")

    summary = summarize(records)
    (run_dir / "summary.md").write_text(summary + "\n")
    print("\n" + summary)


if __name__ == "__main__":
    main()
