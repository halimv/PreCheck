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

from pipeline import proposals
from pipeline.diagnostics import rejection_kind
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
        "duration_s": {"type": "number"},
        "temperature_c": {"type": "number"},
        "speed_rpm": {"type": "number"},
        "waste": {"type": "string"},
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

# An escalated round's reply also carries a proposed change to the knowledge base (pipeline/proposals.py).
PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["add_fix", "replace_fixes", "new_entry"]},
        "fix": {"type": "string"},
        "why": {"type": "string"},
        "code": {"type": "string"},
        "title": {"type": "string"},
        "explanation": {"type": "string"},
        "match_text": {"type": "string"},
    },
    "required": ["kind", "fix", "why"],
}
ESCALATION_SCHEMA = {
    **EDIT_SCHEMA,
    "properties": {**EDIT_SCHEMA["properties"], "knowledge_proposal": PROPOSAL_SCHEMA},
    "required": ["reasoning", "edits", "knowledge_proposal"],
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

# Appended to SYSTEM_PROMPT only for protocols that use these actions, so prompts for
# liquid-transfer-only protocols (and their benchmark results) stay unchanged.
EXTENDED_ACTIONS = ("empty", "incubate", "shake")
EXTENDED_PROMPT = """
More actions (volume_ul is 0 for all three):
- empty: aspirate everything in a plate column on the given channels and dispense it into the \
waste. Wells may go to 0 uL. The tips count as having aspirated from that column.
- incubate: hold a plate on its heater-shaker for duration_s seconds, at temperature_c if given \
(leave temperature_c out for room temperature, which switches the heater off).
- shake: shake a plate on its heater-shaker at speed_rpm for duration_s seconds (temperature_c optional).
- Tips must be off before incubate or shake. The heater-shaker can heat but cannot actively cool.
- Repairs must keep every heated incubate and every shake at its original temperature, speed and \
total time. Room-temperature incubates may be added or lengthened (for example to let the plate cool) \
but not shortened or removed.
"""


class OllamaBackend:
    """Calls a local model through Ollama's chat API with a JSON-schema constrained reply."""

    def __init__(self, model: str = "qwen2.5-coder:7b", host: str = "http://localhost:11434", num_ctx: int = 32768):
        self.model = model
        self.host = host
        self.num_ctx = num_ctx

    def propose_edits(self, system: str, prompt: str, schema: Dict[str, Any] = EDIT_SCHEMA) -> Dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=900) as resp:
            reply = json.loads(resp.read())
        return json.loads(reply["message"]["content"])


CLAUDE_MODEL = "claude-haiku-5-5"  # the default repair model: fast and cheap, and the edits are small


class ClaudeBackend:
    """Calls Claude through the Claude Code CLI (`claude -p`), the login the drafter already uses. The CLI has
    no schema-constrained output, so the schema goes in the prompt and the reply is parsed as JSON; the harness
    validates every edit anyway. Tools are off: the model only reads the prompt and answers."""

    def __init__(self, model: str = CLAUDE_MODEL, timeout_s: int = 300):
        self.model = model
        self.timeout_s = timeout_s
        self.cost_usd = 0.0

    def propose_edits(self, system: str, prompt: str, schema: Dict[str, Any] = EDIT_SCHEMA) -> Dict[str, Any]:
        import shutil
        import subprocess
        import tempfile

        from pipeline.stage0_drafter import CLAUDE_BIN, _claude_env

        if shutil.which(CLAUDE_BIN) is None and not Path(CLAUDE_BIN).is_file():
            raise RuntimeError(f"The Claude CLI ('{CLAUDE_BIN}') is not on PATH. Install it and run `claude` once to "
                               "log in, or repair with a local model instead (--healer ollama).")
        text = (f"{system}\n\n{prompt}\n\nReply with one JSON object and nothing else (no prose, no code fence). "
                f"It must match this JSON schema:\n{json.dumps(schema)}")
        cmd = [CLAUDE_BIN, "-p", "--output-format", "json", "--model", self.model,
               "--disallowedTools", "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Task"]
        with tempfile.TemporaryDirectory() as empty:  # no project files, memory or CLAUDE.md in reach
            proc = subprocess.run(cmd, input=text, capture_output=True, text=True, cwd=empty, env=_claude_env(),
                                  timeout=self.timeout_s)
        try:
            reply = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"The Claude CLI exited with code {proc.returncode}: "
                               f"{(proc.stderr or proc.stdout).strip()[:500]}") from None
        if reply.get("is_error"):
            raise RuntimeError(f"The Claude CLI reported an error: {reply.get('result') or reply.get('subtype')}")
        self.cost_usd += float(reply.get("total_cost_usd") or 0.0)
        try:
            return _json_object(reply.get("result", ""))
        except ValueError as e:  # not JSON: the round counts as one with no edits, and the model is told why
            return {"reasoning": f"(reply was not the JSON asked for: {e})", "edits": []}


def _json_object(text: str) -> Dict[str, Any]:
    """The JSON object in a model's reply, with or without a code fence or words around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"The model's reply holds no JSON object: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def make_backend(healer: str = "claude", model: Optional[str] = None):
    """The repair model: Claude through its CLI (the default) or a local model through Ollama."""
    if healer == "ollama":
        return OllamaBackend(model=model or "qwen2.5-coder:7b")
    if healer == "claude":
        return ClaudeBackend(model=model or CLAUDE_MODEL)
    raise ValueError(f"Unknown healer {healer!r}: use 'claude' or 'ollama'.")


@dataclass
class GateResult:
    stage: str  # "compile" or "simulate"
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
    # Knowledge-base changes proposed in escalated rounds; those with no "problems" are ready
    # for a person to review (store them with proposals.submit).
    proposals: List[Dict[str, Any]] = field(default_factory=list)


def _step_lines(protocol: Dict[str, Any]) -> List[str]:
    keys = ("step", "action", "labware", "column", "volume_ul", "channels", "duration_s", "temperature_c", "speed_rpm")
    return [json.dumps({k: s[k] for k in keys if k in s}) for s in protocol["steps"]]


def apply_valid_edits(
    protocol: Dict[str, Any],
    edits: List[Dict[str, Any]],
    labware_kinds: Dict[str, str],
    allowed_step: Optional[int] = None,
) -> Tuple[Dict[str, Any], List[int], List[str]]:
    """Apply each model edit that passes its own checks to a copy of the IR and renumber steps.

    Returns (new_ir, indices of the applied edits, errors for the rest). When `allowed_step` is
    set, replace_step may only target that step, which keeps each repair local to the failure
    instead of letting the model rewrite working steps.
    """
    new = copy.deepcopy(protocol)
    errors: List[str] = []
    applied: List[int] = []
    by_number = {s["step"]: i for i, s in enumerate(new["steps"])}
    replacements: Dict[int, List[Dict[str, Any]]] = {}

    for idx, edit in enumerate(edits):
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
            steps, step_errors = [], []
            for k, s in enumerate(edit.get("new_steps", []), start=1):
                step = {key: v for key, v in s.items() if key != "step"}
                # Each replacement step must be translatable on its own (known labware, required fields).
                try:
                    translate_step({**step, "step": f"{n} (new step {k})"}, labware_kinds)
                except CompilationError as e:
                    step_errors.append(str(e))
                steps.append(step)
            if step_errors:
                errors.extend(step_errors)
                continue
            replacements[n] = steps
        else:
            errors.append(f"Unknown edit op '{op}'.")
            continue
        applied.append(idx)

    for n in sorted(replacements, reverse=True):
        i = by_number[n]
        new["steps"][i:i + 1] = replacements[n]
    for i, s in enumerate(new["steps"], start=1):
        s["step"] = i
    return new, applied, errors


def apply_edits(
    protocol: Dict[str, Any],
    edits: List[Dict[str, Any]],
    labware_kinds: Dict[str, str],
    allowed_step: Optional[int] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """All-or-nothing version of `apply_valid_edits`. Returns (new_ir, errors); on any error the
    original IR comes back unchanged."""
    new, _, errors = apply_valid_edits(protocol, edits, labware_kinds, allowed_step)
    return (protocol, errors) if errors else (new, [])


class SelfHealer:
    def __init__(
        self,
        deck_config: Dict[str, Any],
        backend: Optional[OllamaBackend] = None,
        work_dir: str = "build/heal",
        feedback_mode: str = "translated",
    ):
        self.deck_config = deck_config
        self.labware_kinds = {lid: spec["kind"] for lid, spec in deck_config["labware"].items()}
        self.backend = backend
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_mode = feedback_mode
        self.simulator = PLRSimulator(deck_config)

    def evaluate(self, protocol: Dict[str, Any], round_num: int) -> GateResult:
        """Compile and simulate the IR, stopping at the first failure. (The stage 1 verifier is out of the loop for
        now: the simulator's failures are what the diagnostics, and so the repairs, are built on.)"""
        ir_path = self.work_dir / f"round_{round_num}.json"
        ir_path.write_text(json.dumps(protocol, indent=2))

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
        """The experiment's fingerprint: total volume each channel aspirates/dispenses at each location,
        how many times each channel empties each plate column, and the total hold time of each device
        condition (plate, temperature, speed)."""
        totals: Dict[Tuple, float] = {}

        def add(key: Tuple, amount: float) -> None:
            totals[key] = round(totals.get(key, 0.0) + amount, 3)

        for s in protocol["steps"]:
            action = s.get("action")
            if action in ("incubate", "shake"):
                add((action, s.get("labware"), s.get("temperature_c"), s.get("speed_rpm")), float(s.get("duration_s", 0)))
                continue
            if action not in ("aspirate", "dispense", "empty"):
                continue
            kind = self.labware_kinds.get(s.get("labware"))
            where = (s.get("labware"), s.get("column") if kind == "plate" else None)
            for ch in s.get("channels", [0]):
                add((action, *where, ch), 1.0 if action == "empty" else float(s.get("volume_ul", 0)))
        return totals

    @staticmethod
    def _intent_violations(baseline: Dict[Tuple, float], candidate: Dict[Tuple, float]) -> List[str]:
        changed = []
        for key in sorted(set(baseline) | set(candidate), key=str):
            before, after = baseline.get(key, 0.0), candidate.get(key, 0.0)
            if before == after:
                continue
            action, labware, a, b = key
            if action == "incubate" and a is None and after > before:
                continue  # extra room-temperature hold, e.g. to let the plate cool
            if action in ("incubate", "shake"):
                cond = f"{a:g} C" if a is not None else "room temperature"
                if b is not None:
                    cond += f", {b:g} rpm"
                changed.append(f"{action} {labware} at {cond}: {before:g} -> {after:g} s")
            else:
                where = f"{labware} column {a}" if a is not None else labware
                unit = " time(s)" if action == "empty" else " uL"
                changed.append(f"channel {b} {action} at {where}: {before:g} -> {after:g}{unit}")
        return changed

    @staticmethod
    def _intent_error(changed: List[str]) -> str:
        shown = "; ".join(changed[:3]) + ("; ..." if len(changed) > 3 else "")
        if any(c.startswith(("incubate", "shake")) for c in changed):
            return (f"the edit changes the experiment ({shown}). A repair must keep every channel's total "
                    "aspirated and dispensed volumes, every empty, and every heated or shaken hold the same")
        return (f"the edit changes how much liquid is moved ({shown}). A repair must keep every channel's total "
                "aspirated and dispensed volumes the same; load more reagent instead of moving less")

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

    @staticmethod
    def _escalation(gate: GateResult, repeats: int, tried: List[str]) -> str:
        """Extra instructions for a failure that keeps coming back: reason past the knowledge base,
        and propose a change to it."""
        d = gate.detail
        names = ", ".join("{" + n + "}" for n in proposals.placeholders_for(d.get("kb_entry")))
        unrecognized = d.get("kb_entry") == proposals.UNRECOGNIZED
        lines = [
            f"This failure has come back {repeats} time(s) in a row ({d['error_code']} at step {gate.step}). "
            "Nothing tried so far has resolved it, so think past the suggested fixes.",
            f"Raw PyLabRobot error: {d['raw_error']}",
            "Already tried for this failure:\n" + "\n".join(f"- {t}" for t in tried),
            "Work out the physical cause yourself and propose edits that fix it. The harness rules still hold: "
            f"edit only step {gate.step} and/or use set_initial_volume, and keep every channel's total aspirated "
            "and dispensed volumes the same.",
            "Also propose a change to the knowledge base in \"knowledge_proposal\", so the next protocol with this "
            "failure is fixed the first time. A scientist reviews it before it is used.",
            ('- kind: "new_entry" (this error has no entry yet).' if unrecognized else
             '- kind: "add_fix" to add your fix to this error\'s suggestions, or "replace_fixes" if the current '
             "suggestions are wrong."),
            "- fix: the fix in general terms, for any protocol with this failure. You may use these placeholders, "
            f"which are filled in when the error happens: {names}.",
            "- why: one or two sentences for the scientist: why the current suggestions did not work and why this does.",
        ]
        if unrecognized:
            lines.append("- code (UPPER_SNAKE_CASE), title, explanation (what went wrong, in lab terms), and "
                         "match_text: a short piece of the raw error message that identifies this error.")
        return "\n".join(lines)

    def heal(
        self,
        protocol: Dict[str, Any],
        max_rounds: int = 5,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        escalate_after: Optional[int] = None,
    ) -> HealResult:
        """Run the repair loop. `on_event(kind, data)`, if given, is called as each round progresses:
        "gate" (stages 1-3 result), "escalate", "model_request", "model_reply" and "edits" (accepted
        or rejected).

        With `escalate_after=k`, a simulator failure that comes back k times in a row (same
        knowledge-base entry, same step) is escalated: the model is told the knowledge base's
        suggestions have not worked, asked to reason past them, and asked to propose a change to
        the knowledge base (HealResult.proposals). None never escalates."""
        emit = on_event or (lambda kind, data: None)
        current = copy.deepcopy(protocol)
        rounds: List[Dict[str, Any]] = []
        history: List[str] = []
        rejection = ""
        policy = f"escalate after {escalate_after} repeat(s)" if escalate_after is not None else "never escalate"
        previous: Optional[Tuple] = None  # (entry, step) of the last round's simulator failure
        repeats = 0
        tried: Dict[Tuple, List[str]] = {}  # what was attempted for each failure, for an escalated prompt

        def finish(status: str) -> HealResult:
            return HealResult(status, current, rounds, proposals.collect(rounds, status))

        # Intent guard: a repair may restructure steps, but every channel must still move the same
        # total volume from and to the same places as in the original plan.
        baseline = self._transfers(protocol)
        system = SYSTEM_PROMPT
        if any(s.get("action") in EXTENDED_ACTIONS for s in protocol["steps"]):
            system += EXTENDED_PROMPT

        for round_num in range(max_rounds + 1):
            gate = self.evaluate(current, round_num)
            gate.feedback += rejection
            rejection = ""
            record: Dict[str, Any] = {"round": round_num, "stage": gate.stage, "passed": gate.passed, "result": gate.summary}
            failure = (gate.detail["kb_entry"], gate.step) if gate.detail.get("kb_entry") else None
            repeats = repeats + 1 if failure is not None and failure == previous else 0
            if failure:  # the knowledge-base entry that explained this failure
                record.update(kb_entry=gate.detail["kb_entry"], step=gate.step, raw_error=gate.detail["raw_error"],
                              match=gate.detail.get("match", {}), fields=gate.detail.get("fields", {}), repeats=repeats)
                if repeats:
                    record["previous_rejections"] = sorted({rejection_kind(e) for e in rounds[-1].get("edit_errors", [])})
            previous = failure
            rounds.append(record)
            print(f"  round {round_num}: {gate.stage} {'PASSED' if gate.passed else 'FAILED'} - {gate.summary}")
            emit("gate", {
                "round": round_num, "stage": gate.stage, "passed": gate.passed, "summary": gate.summary,
                "step": gate.step, "step_count": len(current["steps"]), "feedback": gate.feedback,
                **{k: gate.detail.get(k) for k in ("error_code", "explanation", "suggested_fixes", "raw_error")},
            })
            if gate.passed:
                return finish("ALREADY_PASSING" if round_num == 0 else "HEALED")
            if round_num == max_rounds:
                break

            escalated = escalate_after is not None and failure is not None and repeats >= escalate_after
            record.update(mode="escalated" if escalated else "knowledge_base", policy=policy)
            prompt = self._prompt(current, gate, history)
            if escalated:
                emit("escalate", {"round": round_num, "kb_entry": failure[0], "code": gate.detail["error_code"],
                                  "step": gate.step, "repeats": repeats})
                prompt += "\n\n" + self._escalation(gate, repeats, tried.get(failure, []))
            emit("model_request", {"round": round_num, "model": getattr(self.backend, "model", ""), "escalated": escalated})
            if escalated:
                reply = self.backend.propose_edits(system, prompt, schema=ESCALATION_SCHEMA)
                record["knowledge_proposal"] = reply.get("knowledge_proposal")
            else:
                reply = self.backend.propose_edits(system, prompt)
            record["model_reasoning"] = reply.get("reasoning", "")
            record["edits"] = reply.get("edits", [])
            emit("model_reply", {"round": round_num, "reasoning": record["model_reasoning"], "edits": record["edits"],
                                 "knowledge_proposal": record.get("knowledge_proposal")})
            print(f"    model: {record['model_reasoning'][:300]}")
            # Each edit that passes its own checks is kept, so one bad edit doesn't sink a correct one
            # sent with it. Only replace_step can change the experiment, so on an intent violation
            # those are dropped and the rest is kept.
            edits = record["edits"]
            updated, applied, errors = apply_valid_edits(current, edits, self.labware_kinds, allowed_step=gate.step)
            changed = self._intent_violations(baseline, self._transfers(updated)) if applied else []
            if changed:
                errors.append(self._intent_error(changed))
                keep = [i for i in applied if edits[i].get("op") != "replace_step"]
                updated, kept, _ = apply_valid_edits(current, [edits[i] for i in keep], self.labware_kinds, gate.step)
                applied = [keep[i] for i in kept]
            applied_edits = [edits[i] for i in applied]
            if not edits:
                errors = ["no edits were proposed"]
            if errors:
                record["edit_errors"] = errors
            if not applied:
                print(f"    edits rejected: {errors}")
                emit("edits", {"round": round_num, "accepted": False, "errors": errors})
                rejection = "\nYour previous attempt was rejected: " + "; ".join(errors)
                if failure:
                    tried.setdefault(failure, []).append(f"round {round_num}: rejected by the harness: " + "; ".join(errors))
                continue
            record["edits_applied"] = applied
            description = self._describe(gate, applied_edits)[2:]
            if failure:
                tried.setdefault(failure, []).append(
                    f"round {round_num}: applied ({description.rsplit(' was fixed: ', 1)[-1]})"
                    + (f"; also rejected: {'; '.join(errors)}" if errors else ""))
            print(f"    applied: {description}" + (f"; rejected: {errors}" if errors else ""))
            emit("edits", {"round": round_num, "accepted": True, "description": description,
                           "applied": applied, "errors": errors, "step_count": len(updated["steps"])})
            if errors:
                rejection = ("\nPart of your previous attempt was applied (listed under earlier repair rounds); "
                             "the rest was rejected: " + "; ".join(errors))
            history.append(self._describe(gate, applied_edits))
            current = updated

        return finish("GAVE_UP")


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
