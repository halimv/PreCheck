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

from pipeline.ahc_export import load_ahc_types, to_ahc_layout, write_layout
from pipeline.deck import DEFAULT_DECK
from pipeline.design_review import review, suggestions
from pipeline.stage0_drafter import revision_stem
from pipeline.stage2_compiler import compile_standalone

ROOT = Path(__file__).resolve().parent.parent
HEALED = ROOT / "healed"


def _shown(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def next_stem(stem: str, healed: Path = HEALED) -> str:
    """The next version's name (<name>_r2, _r3, ...), never one already in healed/."""
    stem = revision_stem(stem)
    while (healed / f"{stem}.json").exists():
        stem = revision_stem(stem)
    return stem


def finish(protocol: Dict[str, Any], deck_config: Dict[str, Any], stem: str, rounds: List[Dict[str, Any]],
           status: str = "PASSED", healed: Path = HEALED, plugins: Optional[Path] = None) -> Dict[str, Any]:
    """Write a passing protocol's files and return the report (also saved as <stem>_report.json)."""
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

    report = {
        "status": status,
        "name": stem,
        "protocol_name": protocol.get("protocol_name"),
        "steps": len(protocol.get("steps", [])),
        "repair_rounds": max(len(rounds) - 1, 0),
        "simulated_on": ("PyLabRobot's STAR model, configured as this instrument" if deck_config.get("instrument")
                         else "the generic ChatterBox (the deck names no instrument)"),
        "files": {"ir": _shown(ir_path), "script": _shown(plr_path), "heal_log": _shown(healed / f"{stem}_heal_log.json"),
                  "ahc_layout": _shown(layout_path), "report": _shown(healed / f"{stem}_report.json")},
        "review": review(protocol, deck_config),
        "suggestions": suggestions(protocol, deck_config),
        "ahc": {"accepted_types_from": ahc.get("source"), "not_on_layout": problems, "differs_from_venus": warnings},
    }
    (healed / f"{stem}_report.json").write_text(json.dumps(report, indent=2))
    return report
