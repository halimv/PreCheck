"""Self-healing loop: a local model repairs the protocol IR until it passes every gate.

Each round runs the IR through stage 1 (verifier), stage 2 (deterministic compiler) and
stage 3 (ChatterBox simulation). On the first failure, the diagnostic goes to a local
model (via Ollama), which proposes a few targeted IR edits. The model never writes Python.
The loop stops when all three stages pass or after `max_rounds` repairs.

`feedback_mode="raw"` sends only the raw exception text instead of the lab-concept
diagnostic, so the two can be compared on the same model.
"""

import copy
import difflib
import json
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pipeline.stage1_verifier import Verifier
from pipeline.stage2_compiler import ACTIONS, CompilationError, compile_protocol, translate_step
from pipeline.stage3_simulator import PLRSimulator

ROWS = "ABCDEFGH"

STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "labware": {"type": "string"},
        "column": {"type": "integer"},
        "volume_ul": {"type": "number"},
        "channels": {"type": "array", "items": {"type": "integer"}},
        "description": {"type": "string"},
    },
    "required": ["action", "labware", "volume_ul", "channels", "description"],
}

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["replace_step", "set_initial_volume"]},
                    "step": {"type": "integer"},
                    "new_steps": {"type": "array", "items": STEP_SCHEMA},
                    "labware": {"type": "string"},
                    "volume_ul": {"type": "number"},
                },
                "required": ["op"],
            },
        },
    },
    "required": ["reasoning", "edits"],
}

SYSTEM_PROMPT = """\
You repair liquid-handling protocols for a Hamilton STARlet with an 8-channel head. \
A protocol is a JSON list of steps. A safety pipeline ran it and reported a failure. \
Propose the smallest set of edits that fixes the failure while keeping the experiment the \
same: same reagents, same final volumes in every well, same order of operations.

Step fields: action (tips_on, tips_off, aspirate, dispense), labware, column (1-12, for \
plates and tip racks only), volume_ul (always include it; 0 for tips_on and tips_off), channels (list of channel numbers 0-7), description.
Rules the protocol must follow:
- Channel i works on row "ABCDEFGH"[i] of a plate or tip rack.
- tips_on picks up tips from one column of a tip rack; each tip column can be used once.
- tips_off drops every mounted tip into the waste.
- Tips may aspirate repeatedly from the same source, but need tips_off and fresh tips before \
aspirating from a different source.
- Plate wells must keep at least 30 uL and hold at most 330 uL.

Edit operations (step numbers refer to the protocol exactly as shown to you):
- {"op": "replace_step", "step": N, "new_steps": [...]}: replace step N with the listed steps \
(one step to modify it, several to split it, an empty list to delete it). Steps are renumbered \
afterwards, so do not include step numbers in new_steps.
- {"op": "set_initial_volume", "labware": "<id>", "volume_ul": V}: change how much liquid the \
scientist loads into a container before the run.

Reply with JSON: {"reasoning": "...", "edits": [...]}. Only use labware IDs listed in the deck.
"""


class OllamaBackend:
    """Calls a local model through Ollama's chat API with a JSON-schema constrained reply."""

    def __init__(self, model: str = "qwen2.5-coder:7b", host: str = "http://localhost:11434", num_ctx: int = 32768):
        self.model = model
        self.host = host
        self.num_ctx = num_ctx

    def propose_edits(self, system: str, prompt: str) -> Dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": EDIT_SCHEMA,
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=900) as resp:
            reply = json.loads(resp.read())
        return json.loads(reply["message"]["content"])


@dataclass
class GateResult:
    stage: str  # "verify", "compile" or "simulate"
    passed: bool
    summary: str
    feedback: str = ""
    step: Optional[int] = None  # IR step that failed, when known
    detail: Dict[str, Any] = field(default_factory=dict)


def _step_in(message: str) -> Optional[int]:
    m = re.search(r"Step (\d+)", message)
    return int(m.group(1)) if m else None


@dataclass
class HealResult:
    status: str  # "HEALED", "ALREADY_PASSING" or "GAVE_UP"
    protocol: Dict[str, Any]
    rounds: List[Dict[str, Any]]


def _step_lines(protocol: Dict[str, Any]) -> List[str]:
    keys = ("step", "action", "labware", "column", "volume_ul", "channels")
    return [json.dumps({k: s[k] for k in keys if k in s}) for s in protocol["steps"]]


def apply_edits(
    protocol: Dict[str, Any],
    edits: List[Dict[str, Any]],
    labware_kinds: Dict[str, str],
    allowed_step: Optional[int] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Apply model edits to a copy of the IR and renumber steps. Returns (new_ir, errors).

    When `allowed_step` is set, replace_step may only target that step, which keeps each
    repair local to the failure instead of letting the model rewrite working steps.
    """
    new = copy.deepcopy(protocol)
    errors: List[str] = []
    by_number = {s["step"]: i for i, s in enumerate(new["steps"])}
    replacements: Dict[int, List[Dict[str, Any]]] = {}

    for edit in edits:
        op = edit.get("op")
        if op == "set_initial_volume":
            lid, vol = edit.get("labware"), edit.get("volume_ul")
            if not isinstance(lid, str) or labware_kinds.get(lid) != "container" \
                    or not isinstance(vol, (int, float)) or vol < 0:
                errors.append(f"set_initial_volume needs a container ID from the deck and a volume >= 0, got {edit}.")
                continue
            new.setdefault("initial_volumes_ul", {})[lid] = vol
        elif op == "replace_step":
            n = edit.get("step")
            if not isinstance(n, int) or n not in by_number:
                errors.append(f"replace_step refers to step {n}, which does not exist.")
                continue
            if allowed_step is not None and n != allowed_step:
                errors.append(f"Only the failing step {allowed_step} may be replaced this round, not step {n}.")
                continue
            if n in replacements:
                errors.append(f"Step {n} is replaced twice; combine those edits into one.")
                continue
            steps = []
            for k, s in enumerate(edit.get("new_steps", []), start=1):
                step = {key: v for key, v in s.items() if key != "step"}
                # Each replacement step must be translatable on its own (known labware, required fields).
                try:
                    translate_step({**step, "step": f"{n} (new step {k})"}, labware_kinds)
                except CompilationError as e:
                    errors.append(str(e))
                steps.append(step)
            replacements[n] = steps
        else:
            errors.append(f"Unknown edit op '{op}'.")

    if errors:
        return protocol, errors
    for n in sorted(replacements, reverse=True):
        i = by_number[n]
        new["steps"][i:i + 1] = replacements[n]
    for i, s in enumerate(new["steps"], start=1):
        s["step"] = i
    return new, []


class SelfHealer:
    def __init__(
        self,
        deck_config: Dict[str, Any],
        labware_path: str,
        protocol_defaults_path: str,
        backend: OllamaBackend,
        work_dir: str,
        feedback_mode: str = "translated",
    ):
        self.deck_config = deck_config
        self.labware_kinds = {lid: spec["kind"] for lid, spec in deck_config["labware"].items()}
        self.labware_path = labware_path
        self.protocol_defaults_path = protocol_defaults_path
        self.backend = backend
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_mode = feedback_mode
        self.simulator = PLRSimulator(deck_config)

    def evaluate(self, protocol: Dict[str, Any], round_num: int) -> GateResult:
        """Run stages 1-3 on the IR, stopping at the first failure."""
        ir_path = self.work_dir / f"round_{round_num}.json"
        ir_path.write_text(json.dumps(protocol, indent=2))

        verdict = Verifier(self.labware_path, str(ir_path), self.protocol_defaults_path).run_verification()
        if verdict["status"] != "PASSED":
            msg = f"Safety verifier rejected the protocol: {verdict['error_code']}: {verdict['message']}"
            return GateResult("verify", False, msg, feedback=msg, step=_step_in(verdict["message"]), detail=verdict)

        try:
            code = compile_protocol(protocol, self.deck_config)
        except CompilationError as e:
            msg = f"Compiler rejected the protocol: {e}"
            return GateResult("compile", False, msg, feedback=msg, step=_step_in(str(e)))
        (self.work_dir / f"round_{round_num}_plr.py").write_text(code)

        sim = self.simulator.run(code, protocol)
        if sim.status == "PASSED":
            return GateResult("simulate", True, sim.message)
        d = sim.diagnostic
        assert d is not None, "a failed simulation always carries a diagnostic"
        if self.feedback_mode == "raw":
            feedback = f"Simulation failed at step {d['step']}: {d['raw_error']}"
        else:
            feedback = (
                f"Simulation failed at step {d['step']} ({d['error_code']}).\n{d['explanation']}\n"
                "Suggested fixes:\n" + "\n".join(f"- {f}" for f in d["suggested_fixes"])
            )
        return GateResult("simulate", False, sim.message, feedback=feedback, step=d["step"], detail=d)

    def _transfers(self, protocol: Dict[str, Any]) -> Dict[Tuple, float]:
        """Total volume each channel aspirates/dispenses at each location (the experiment's liquid movement)."""
        totals: Dict[Tuple, float] = {}
        for s in protocol["steps"]:
            if s.get("action") not in ("aspirate", "dispense"):
                continue
            kind = self.labware_kinds.get(s.get("labware"))
            where = (s.get("labware"), s.get("column") if kind == "plate" else None)
            for ch in s.get("channels", [0]):
                key = (s["action"], *where, ch)
                totals[key] = round(totals.get(key, 0.0) + float(s.get("volume_ul", 0)), 3)
        return totals

    @staticmethod
    def _intent_violations(baseline: Dict[Tuple, float], candidate: Dict[Tuple, float]) -> List[str]:
        changed = []
        for key in sorted(set(baseline) | set(candidate), key=str):
            before, after = baseline.get(key, 0.0), candidate.get(key, 0.0)
            if before != after:
                action, labware, column, ch = key
                where = f"{labware} column {column}" if column is not None else labware
                changed.append(f"channel {ch} {action} at {where}: {before:g} -> {after:g} uL")
        return changed

    def _prompt(self, protocol: Dict[str, Any], gate: GateResult, history: List[str]) -> str:
        deck = "\n".join(f"- {lid} ({spec['kind']})" for lid, spec in self.deck_config["labware"].items())
        parts = [
            f"Deck labware:\n{deck}",
            f"Initial volumes loaded by the scientist (uL): {json.dumps(protocol.get('initial_volumes_ul', {}))}",
            "Protocol steps:\n" + "\n".join(_step_lines(protocol)),
        ]
        if history:
            parts.append(
                "Earlier repair rounds. These are already applied in the steps above and the steps were "
                "renumbered afterwards, so do not repeat them:\n" + "\n".join(history)
            )
        parts.append(f"Failure to fix now:\n{gate.feedback}")
        if gate.step is not None:
            parts.append(
                f"Edit only step {gate.step}: replace it with one or more steps that fix the failure, "
                "and/or use set_initial_volume. Do not touch any other step."
            )
        return "\n\n".join(parts)

    @staticmethod
    def _describe(gate: GateResult, edits: List[Dict[str, Any]]) -> str:
        changes = []
        for e in edits:
            if e.get("op") == "replace_step":
                changes.append(f"replaced the failing step with {len(e.get('new_steps', []))} step(s)")
            elif e.get("op") == "set_initial_volume":
                changes.append(f"set the initial volume of {e.get('labware')} to {e.get('volume_ul')} uL")
        code = gate.detail.get("error_code", gate.stage)
        return f"- {code} (\"{gate.summary}\") was fixed: " + "; ".join(changes)

    def heal(
        self,
        protocol: Dict[str, Any],
        max_rounds: int = 5,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> HealResult:
        """Run the repair loop. `on_event(kind, data)`, if given, is called as each round progresses:
        "gate" (stages 1-3 result), "model_request", "model_reply" and "edits" (accepted or rejected)."""
        emit = on_event or (lambda kind, data: None)
        current = copy.deepcopy(protocol)
        rounds: List[Dict[str, Any]] = []
        history: List[str] = []
        rejection = ""
        # Intent guard: a repair may restructure steps, but every channel must still move the same
        # total volume from and to the same places as in the original plan.
        baseline = self._transfers(protocol)

        for round_num in range(max_rounds + 1):
            gate = self.evaluate(current, round_num)
            gate.feedback += rejection
            rejection = ""
            record: Dict[str, Any] = {"round": round_num, "stage": gate.stage, "passed": gate.passed, "result": gate.summary}
            rounds.append(record)
            print(f"  round {round_num}: {gate.stage} {'PASSED' if gate.passed else 'FAILED'} - {gate.summary}")
            emit("gate", {
                "round": round_num, "stage": gate.stage, "passed": gate.passed, "summary": gate.summary,
                "step": gate.step, "step_count": len(current["steps"]), "feedback": gate.feedback,
                **{k: gate.detail.get(k) for k in ("error_code", "explanation", "suggested_fixes", "raw_error")},
            })
            if gate.passed:
                return HealResult("ALREADY_PASSING" if round_num == 0 else "HEALED", current, rounds)
            if round_num == max_rounds:
                break

            emit("model_request", {"round": round_num, "model": getattr(self.backend, "model", "")})
            reply = self.backend.propose_edits(SYSTEM_PROMPT, self._prompt(current, gate, history))
            record["model_reasoning"] = reply.get("reasoning", "")
            record["edits"] = reply.get("edits", [])
            emit("model_reply", {"round": round_num, "reasoning": record["model_reasoning"], "edits": record["edits"]})
            print(f"    model: {record['model_reasoning'][:300]}")
            updated, errors = apply_edits(current, record["edits"], self.labware_kinds, allowed_step=gate.step)
            if not errors:
                changed = self._intent_violations(baseline, self._transfers(updated))
                if changed:
                    errors = [
                        f"the edit changes how much liquid is moved ({'; '.join(changed[:3])}"
                        f"{'; ...' if len(changed) > 3 else ''}). A repair must keep every channel's total "
                        "aspirated and dispensed volumes the same; load more reagent instead of moving less"
                    ]
            if errors:
                record["edit_errors"] = errors
                print(f"    edits rejected: {errors}")
                emit("edits", {"round": round_num, "accepted": False, "errors": errors})
                rejection = "\nYour previous attempt was rejected: " + "; ".join(errors)
                continue
            print(f"    applied: {self._describe(gate, record['edits'])[2:]}")
            emit("edits", {"round": round_num, "accepted": True, "description": self._describe(gate, record["edits"])[2:],
                           "step_count": len(updated["steps"])})
            history.append(self._describe(gate, record["edits"]))
            current = updated

        return HealResult("GAVE_UP", current, rounds)


def ir_diff(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    """Diff of initial volumes and step contents, for the scientist to review the repair.

    Step numbers are left out of the compared lines so renumbering after a split doesn't
    show every later step as changed.
    """
    keys = ("action", "labware", "column", "volume_ul", "channels")

    def lines(p):
        return [f"initial_volumes_ul: {json.dumps(p.get('initial_volumes_ul', {}))}"] + [
            json.dumps({k: s[k] for k in keys if k in s}) for s in p["steps"]
        ]
    return "\n".join(difflib.unified_diff(lines(before), lines(after), "original", "healed", lineterm="", n=1))
