"""What the command line (pipeline.py), the demo server and the Claude skill all do with a protocol that passed:
write it to healed/, review it, and hand it on.

A passing protocol leaves these in healed/:
    <stem>.json             the IR that passed compile and simulate on the instrument's model
    <stem>_plr.py           the same protocol as a standalone PyLabRobot script
    <stem>_heal_log.json    every round: the failure, the model's edits, the harness's verdict
    <stem>.ahc_layout.yaml  the same deck as an AHC layout
    <stem>_report.json      everything above in one object, with the design review and suggestions
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline import summary
from pipeline.ahc_export import load_ahc_types, to_ahc_layout, write_layout
from pipeline.deck import DEFAULT_DECK
from pipeline.design_review import review, suggestions
from pipeline.stage0_drafter import revision_stem
from pipeline.stage2_compiler import compile_standalone

from pipeline import paths  # noqa: E402

ROOT = paths.PLUGIN  # the ground truth
HEALED = paths.HEALED  # the working folder


def _shown(path: Path) -> str:
    return paths.in_work(path)


def next_stem(stem: str, healed: Path = HEALED) -> str:
    """The next version's name (<name>_r2, _r3, ...), never one already in healed/."""
    stem = revision_stem(stem)
    while (healed / f"{stem}.json").exists():
        stem = revision_stem(stem)
    return stem


class NotPassing(ValueError):
    """The protocol does not pass the gate, so it is not written to healed/."""

    def __init__(self, gate: Any):
        super().__init__(f"not written: it fails {gate.stage}: {gate.summary}")
        self.gate = gate


def finish(protocol: Dict[str, Any], deck_config: Dict[str, Any], stem: str, rounds: List[Dict[str, Any]],
           status: str = "PASSED", healed: Path = HEALED, plugins: Optional[Path] = None,
           tiers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Write a passing protocol's files and return the report (also saved as <stem>_report.json).

    Nothing is written unless the protocol passes the gate now: the compiler and the simulator on the instrument's
    model, checked again here, whatever the caller's status says. A protocol that does not pass raises
    NotPassing and leaves healed/ untouched."""
    from pipeline.self_heal import SelfHealer
    gate = SelfHealer(deck_config=deck_config, work_dir=str(paths.BUILD / "gate" / stem)).evaluate(protocol, 0)
    if not gate.passed:
        raise NotPassing(gate)
    healed.mkdir(exist_ok=True)
    ir_path, plr_path = healed / f"{stem}.json", healed / f"{stem}_plr.py"
    ir_path.write_text(json.dumps(protocol, indent=2))
    plr_path.write_text(compile_standalone(protocol, deck_config, protocol.get("deck_config", DEFAULT_DECK),
                                           f"healed/{plr_path.name}"))
    (healed / f"{stem}_heal_log.json").write_text(json.dumps(rounds, indent=2))

    ahc = load_ahc_types(ROOT, plugins)
    layout, problems, warnings = to_ahc_layout(deck_config, ahc, protocol.get("initial_volumes_ul"))
    layout_path = healed / f"{stem}.ahc_layout.yaml"
    write_layout(layout, layout_path, f"healed/{stem}.json", problems, warnings)

    deck_path = paths.resolve(protocol["deck_config"]) if protocol.get("deck_config") else None
    simulated_on = ("PyLabRobot's STAR model, configured as this instrument" if deck_config.get("instrument")
                    else "the generic ChatterBox (the deck names no instrument)")
    report = {
        "status": status,
        "name": stem,
        "protocol_name": protocol.get("protocol_name"),
        "steps": len(protocol.get("steps", [])),
        "repair_rounds": max(len(rounds) - 1, 0),
        "simulated_on": ("PyLabRobot's STAR model, configured as this instrument" if deck_config.get("instrument")
                         else "the generic ChatterBox (the deck names no instrument)"),
        "files": {"ir": _shown(ir_path), "script": _shown(plr_path), "heal_log": _shown(healed / f"{stem}_heal_log.json"),
                  "ahc_layout": _shown(layout_path), "summary": _shown(healed / f"{stem}_summary.md"),
                  "report": _shown(healed / f"{stem}_report.json")},
        "review": review(protocol, deck_config),
        "suggestions": suggestions(protocol, deck_config),
        "ahc": {"accepted_types_from": ahc.get("source"), "not_on_layout": problems, "differs_from_venus": warnings},
    }
    report["needs_review"] = summary.review_items(protocol, rounds, report["review"], report["suggestions"], report["ahc"],
                                                  deck_path=deck_path, passed=True)
    summary_path = healed / f"{stem}_summary.md"
    summary_path.write_text(summary.markdown(protocol, rounds, tiers or [], report["review"], report["needs_review"],
                                             {**report["files"], "simulated_on": simulated_on}, passed=True))
    (healed / f"{stem}_report.json").write_text(json.dumps(report, indent=2))
    return report


def result_summary(status: str, tiers: List[Dict[str, Any]], max_rounds: int, log: Path, protocol_name: str) -> str:
    """The result of a run as the person reads it: passed or not, which models were tried and for how many rounds,
    the last failure, and what was written. A protocol that did not pass writes nothing to healed/."""
    passed = status in ("HEALED", "ALREADY_PASSING", "PASSED")
    head = "PASSED: ready for AHC" if passed else "NOT READY: did not pass the simulator"
    lines = [head, f"Protocol: {protocol_name}", "Repair models tried (up to %d rounds each):" % max_rounds]
    for tier in tiers:
        used = max(len(tier["rounds"]) - 1, 0)
        lines.append(f"  {tier['model']:<20} {used} round(s): {tier['status']}")
    rounds = tiers[-1]["rounds"] if tiers else []
    lines += ["", "Final round:"]
    if rounds:
        last = rounds[-1]
        verdict = "PASSED" if last.get("passed") else f"FAILED: {last.get('result', '')}"
        lines.append(f"  round {last['round']}: {verdict}")
    lines.append("")
    if passed:
        lines.append("Written to healed/: the protocol, its standalone script, the heal log, the AHC layout and the report.")
    else:
        lines.append("Written: nothing to healed/. The heal log is kept for review: " + str(log))
    return "\n".join(lines)
