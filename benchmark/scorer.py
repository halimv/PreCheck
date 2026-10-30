"""Checkpoint scorer (spec section 5): C1-C5, the -1 budget penalty, sub-scores and failure labels.

A run is scored at several retry budgets from one log. The repair prompt never mentions the
round limit, so at temperature 0 a run capped at k rounds would be the first k rounds of a
longer run, and the retry sweep needs no extra runs.

C2 and C3 are keyword and value checks on the model's reasoning and edits, an approximation
until the loop emits a structured diagnosis (spec 5.3). Validate them against hand labels.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.scenes import Fault, Scene

PLATE = "corning_3595"
STOCK_UM = {"tube_15ml": 1000.0}
TOLERANCE = 0.01

ALIASES = {"tube_15ml": ("tube_15ml", "tube", "stock"), "reservoir_50ml": ("reservoir_50ml", "reservoir", "trough", "diluent")}
KEYWORDS = {
    "CHANNEL_SPACING": ("spacing", "too small", "narrow", "fit", "9 mm", "single channel", "one channel",
                        "each channel", "separate", "individual"),
    "INSUFFICIENT_LIQUID": ("insufficient", "not enough", "run dry", "runs dry", "too little", "more reagent",
                            "load more", "initial volume", "set_initial_volume", "only holds", "more liquid"),
}


def final_concentrations(protocol: Dict[str, Any]) -> Dict[Tuple[int, int], Optional[float]]:
    """Concentration (uM) left in each plate well, assuming every dispense mixes fully."""
    wells: Dict[Tuple[int, int], List[float]] = {}  # (channel/row, column) -> [volume, amount]
    tips: Dict[int, List[float]] = {}
    for s in protocol["steps"]:
        action, labware, column = s["action"], s["labware"], s.get("column")
        v = float(s.get("volume_ul", 0))
        for ch in s.get("channels", [0]):
            if action == "tips_on":
                tips[ch] = [0.0, 0.0]
            elif action == "tips_off":
                tips.pop(ch, None)
            elif action == "aspirate":
                tip = tips.setdefault(ch, [0.0, 0.0])
                if labware == PLATE:
                    w = wells.setdefault((ch, column), [0.0, 0.0])
                    conc = w[1] / w[0] if w[0] > 1e-9 else 0.0
                    w[0] -= v
                    w[1] -= v * conc
                else:
                    conc = STOCK_UM.get(labware, 0.0)
                tip[0] += v
                tip[1] += v * conc
            elif action == "dispense":
                tip = tips.setdefault(ch, [0.0, 0.0])
                conc = tip[1] / tip[0] if tip[0] > 1e-9 else 0.0
                tip[0] -= v
                tip[1] -= v * conc
                if labware == PLATE:
                    w = wells.setdefault((ch, column), [0.0, 0.0])
                    w[0] += v
                    w[1] += v * conc
    return {k: (w[1] / w[0] if w[0] > 1e-9 else None) for k, w in wells.items()}


def concentrations_ok(protocol: Dict[str, Any], expected: Dict[int, float]) -> bool:
    got = final_concentrations(protocol)
    for col, want in expected.items():
        for ch in range(8):
            c = got.get((ch, col))
            if c is None or abs(c - want) / want > TOLERANCE:
                return False
    return True


def applied_edits(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The edits the harness applied in a round. Runs from before partial acceptance have no
    `edits_applied`; there a round was applied whole or not at all."""
    edits = record.get("edits", [])
    if "edits_applied" in record:
        return [edits[i] for i in record["edits_applied"]]
    return [] if record.get("edit_errors") else edits


def _text(record: Dict[str, Any]) -> str:
    return (record.get("model_reasoning", "") + " " + json.dumps(record.get("edits", []))).lower()


def identified(fault: Fault, record: Dict[str, Any]) -> bool:
    text = _text(record)
    return any(k in text for k in KEYWORDS[fault.code]) and any(a in text for a in ALIASES[fault.labware])


def correct_fix(fault: Fault, edits: List[Dict[str, Any]]) -> bool:
    for e in edits:
        if fault.code == "INSUFFICIENT_LIQUID" and e.get("op") == "set_initial_volume":
            if e.get("labware") == fault.labware and isinstance(e.get("volume_ul"), (int, float)) \
                    and e["volume_ul"] >= fault.required_ul:
                return True
        if fault.code == "CHANNEL_SPACING" and e.get("op") == "replace_step":
            steps = e.get("new_steps") or []
            chans = [c for s in steps for c in s.get("channels", [])]
            if steps and all(s.get("action") == "aspirate" and s.get("labware") == fault.labware
                             and len(s.get("channels", [])) == 1 for s in steps) \
                    and sorted(chans) == list(range(8)) and len({s.get("volume_ul") for s in steps}) == 1:
                return True
    return False


def correct_result_stated(fault: Fault, record: Dict[str, Any]) -> bool:
    """C3: the model proposed the right fix, or its reasoning states the right value, even if execution failed."""
    if correct_fix(fault, record.get("edits", [])):
        return True
    reasoning = record.get("model_reasoning", "").lower()
    if fault.code == "INSUFFICIENT_LIQUID":
        numbers = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*(?:ul|µl|microliter)", reasoning)]
        return any(a in reasoning for a in ALIASES[fault.labware]) and any(n >= fault.required_ul for n in numbers)
    return ("single channel" in reasoning or "one channel" in reasoning or "each channel" in reasoning) \
        and ("split" in reasoning or "separate" in reasoning or "8 steps" in reasoning)


def score(
    scene: Scene,
    rounds: List[Dict[str, Any]],
    work_dir: Path,
    expected: Dict[int, float],
    budget: int,
    crashed_round: Optional[int] = None,
    calls: Optional[List[Dict[str, Any]]] = None,
    num_ctx: int = 32768,
) -> Dict[str, Any]:
    """Score one run as if it had been capped at `budget` repair rounds."""
    healed_round = next((r["round"] for r in rounds if r["passed"]), None)
    healed = healed_round is not None and healed_round <= budget
    model_rounds = [r for r in rounds if "model_reasoning" in r and r["round"] < budget]
    accepted = [r for r in model_rounds if applied_edits(r)]

    first_step = re.search(r"Step (\d+)", rounds[0].get("result", "")) if rounds else None
    c1 = int(bool(rounds) and (rounds[0]["passed"] or (first_step is not None and int(first_step.group(1)) > 1)))
    seen = [f for f in scene.faults if any(identified(f, r) for r in model_rounds)]
    c2 = int(bool(seen))
    c3 = int(bool(seen) and all(any(correct_result_stated(f, r) for r in model_rounds) for f in seen))
    c4 = int(all(any(correct_fix(f, applied_edits(r)) for r in accepted) for f in scene.faults))
    c5 = 0
    if healed:
        final_ir = json.loads((work_dir / f"round_{healed_round}.json").read_text())
        c5 = int(concentrations_ok(final_ir, expected))

    label = None
    if not healed:
        if crashed_round is not None and crashed_round < budget:
            label = "CRASH"
        elif any(c["prompt_tokens"] >= num_ctx * 0.98 for c in (calls or [])[:budget]):
            label = "CONTEXT_LIMIT"
        elif not model_rounds:
            label = "NO_REPAIR"
        elif not accepted:
            label = "REJECTED_ALL"
        elif any("Only the failing step" in e for r in model_rounds for e in r.get("edit_errors", [])):
            label = "WRONG_TARGET"
        elif any(json.dumps(a.get("edits")) == json.dumps(b.get("edits"))
                 for a, b in zip(model_rounds, model_rounds[1:])):
            label = "STALLED"
        else:
            label = "GAVE_UP"

    total = c1 + c2 + c3 + c4 + c5 - (0 if healed else 1)
    return {
        "budget": budget, "healed": healed, "healed_round": healed_round if healed else None,
        "C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5,
        "diagnosis": c2 + c3, "execution": c4 + c5, "score": total, "failure_label": label,
    }
