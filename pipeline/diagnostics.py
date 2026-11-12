"""Translate PyLabRobot runtime exceptions into lab-concept diagnostics.

The simulator (stage 3) catches the exception, works out which IR step raised it, and
captures deck state. This module turns that into a structured diagnostic a scientist
(or a small model in the self-healing loop) can act on: what went wrong in physical
terms, the relevant numbers, and the IR changes that would fix it.

The wording and fixes come from knowledge/diagnostics.json, a reviewable knowledge base that
also keeps what past self-healing runs learned about each error (`record_run`).
"""

import datetime
import functools
import json
import math
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pylabrobot.legacy.liquid_handling.errors import ChannelizedError, ChannelsDoNotFitError
from pylabrobot.resources.errors import (
    CrossContaminationError,
    HasTipError,
    NoTipError,
    TooLittleLiquidError,
    TooLittleVolumeError,
)

from pipeline.deck import DeviceError

ROWS = "ABCDEFGH"
CHANNEL_PITCH_MM = 9.0  # minimum spacing between Hamilton 1 mL channels
KNOWLEDGE_BASE = Path(__file__).resolve().parent.parent / "knowledge" / "diagnostics.json"


def unwrap(exc: BaseException) -> BaseException:
    """PLR wraps per-channel failures in ChannelizedError; return the first underlying error."""
    if isinstance(exc, ChannelizedError) and exc.errors:
        return next(iter(exc.errors.values()))
    return exc


def planned_aspirate_ul(protocol: Dict[str, Any], labware: str) -> float:
    """Total volume the IR aspirates from `labware` across all steps (all channels)."""
    return sum(
        float(s.get("volume_ul", 0)) * len(s.get("channels", [0]))
        for s in protocol.get("steps", [])
        if s.get("action") == "aspirate" and s.get("labware") == labware
    )


def capture_state(lh, res: Dict[str, Any], deck_config: Dict[str, Any], step: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Snapshot the parts of the deck relevant to diagnosing a failure."""
    state: Dict[str, Any] = {
        "tips_mounted": {ch: lh.head[ch].has_tip for ch in range(lh.backend.num_channels)},
        "container_volumes_ul": {},
        "unused_tip_columns": {},
    }
    for lid, spec in deck_config["labware"].items():
        if spec["kind"] == "container":
            state["container_volumes_ul"][lid] = round(res[lid].tracker.get_used_volume(), 2)
        elif spec["kind"] == "tip_rack":
            rack = res[lid]
            state["unused_tip_columns"][lid] = [
                c for c in range(1, 13)
                if all(rack.get_item(f"{r}{c}").tracker.has_tip for r in ROWS)
            ]
    if step and step.get("column") and deck_config["labware"].get(step.get("labware"), {}).get("kind") == "plate":
        plate = res[step["labware"]]
        state["plate_column_volumes_ul"] = {
            f"{ROWS[ch]}{step['column']}": round(plate.get_item(f"{ROWS[ch]}{step['column']}").tracker.get_used_volume(), 2)
            for ch in step.get("channels", [0])
        }
    return state


# ---------- knowledge base ----------
# The wording, matching rules and fixes for each error live in knowledge/diagnostics.json, so a
# scientist can review them without reading code. This module only matches an exception to an
# entry and fills in the numbers.

EXCEPTIONS = {
    cls.__name__: cls
    for cls in (ChannelsDoNotFitError, CrossContaminationError, DeviceError, HasTipError, NoTipError,
                TooLittleLiquidError, TooLittleVolumeError, ValueError)
}
CONDITIONS = {"error", "message_contains", "device_code", "action", "action_is_not", "reagent_loaded"}
ENTRY_FIELDS = {"id", "code", "title", "when", "facts", "explanation", "fixes", "notes", "observed"}
# Placeholders every entry can use, and the ones each fact adds.
ALWAYS_FIELDS = ("n", "action", "labware", "column", "channels", "n_channels", "last_channel", "volume_ul",
                 "speed_rpm", "temperature_c", "error", "raw")
FACT_FIELDS = {
    "container_fit": ("width", "pitch", "fit"),
    "liquid_levels": ("requested", "available"),
    "reagent_plan": ("start", "needed", "load"),
    "free_tip_columns": ("free",),
}


def exception_class(name: str) -> Optional[type]:
    """The exception class with this name: a common one above, or any exception class loaded in
    this process (so an entry proposed from a run can name whatever PyLabRobot raised)."""
    if name in EXCEPTIONS:
        return EXCEPTIONS[name]
    todo = [BaseException]
    while todo:
        cls = todo.pop()
        if cls.__name__ == name:
            return cls
        todo.extend(cls.__subclasses__())
    return None


@dataclass
class Failure:
    """Everything an entry's conditions and facts can look at."""

    err: BaseException
    step: Dict[str, Any]
    protocol: Dict[str, Any]
    res: Dict[str, Any]
    state: Dict[str, Any]

    @property
    def labware(self) -> Optional[str]:
        return self.step.get("labware")

    def reagent_loaded(self) -> bool:
        return self.labware is not None and self.labware in self.protocol.get("initial_volumes_ul", {})

    def fields(self) -> Dict[str, Any]:
        """Placeholders every entry can use."""
        channels = self.step.get("channels", [0])
        return {
            "n": self.step.get("step"),
            "action": self.step.get("action"),
            "labware": self.labware,
            "column": self.step.get("column"),
            "channels": channels,
            "n_channels": len(channels),
            "last_channel": channels[-1],
            "volume_ul": self.step.get("volume_ul"),
            "speed_rpm": self.step.get("speed_rpm"),
            "temperature_c": self.step.get("temperature_c"),
            "error": str(self.err),
            "raw": f"{type(self.err).__name__}: {self.err}",
        }


# Facts: numbers an entry needs that come from the deck or the whole protocol. Entries list
# the facts they use by name; each returns extra placeholders.

def container_fit(f: Failure) -> Dict[str, Any]:
    width = f.res[f.labware].get_size_y() if f.labware in f.res else 0.0
    return {"width": width, "pitch": CHANNEL_PITCH_MM, "fit": max(1, math.floor(width / CHANNEL_PITCH_MM))}


def liquid_levels(f: Failure) -> Dict[str, Any]:
    available = f.state["container_volumes_ul"].get(f.labware)
    requested = re.findall(r"([\d.]+)uL", str(f.err))
    return {
        "requested": requested[0] if requested else f.step.get("volume_ul"),
        "available": available if available is not None else "too little",
    }


def reagent_plan(f: Failure) -> Dict[str, Any]:
    needed = planned_aspirate_ul(f.protocol, f.labware)
    return {
        "start": f.protocol["initial_volumes_ul"][f.labware],
        "needed": needed,
        "load": math.ceil(needed * 1.1 / 50) * 50,  # 10% margin, rounded up to 50 uL
    }


def free_tip_columns(f: Failure) -> Dict[str, Any]:
    return {"free": f.state["unused_tip_columns"].get(f.labware, [])}


FACTS = {fn.__name__: fn for fn in (container_fit, liquid_levels, reagent_plan, free_tip_columns)}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else [value]


def _matches(cond: Dict[str, Any], f: Failure) -> bool:
    if "error" in cond and not {c.__name__ for c in type(f.err).__mro__} & set(_as_list(cond["error"])):
        return False
    if "message_contains" in cond and cond["message_contains"] not in str(f.err):
        return False
    if "device_code" in cond and getattr(f.err, "code", None) != cond["device_code"]:
        return False
    if "action" in cond and f.step.get("action") not in _as_list(cond["action"]):
        return False
    if "action_is_not" in cond and f.step.get("action") in _as_list(cond["action_is_not"]):
        return False
    if "reagent_loaded" in cond and f.reagent_loaded() != cond["reagent_loaded"]:
        return False
    return True


def _text(value: Any) -> str:
    """Entry text is a string or a list of sentences, joined with spaces."""
    return " ".join(value) if isinstance(value, list) else value


def _is_text(value: Any) -> bool:
    return isinstance(value, str) or (isinstance(value, list) and bool(value) and all(isinstance(s, str) for s in value))


def _check_entry(i: int, entry: Dict[str, Any], last: bool) -> None:
    where = f"{KNOWLEDGE_BASE.name} entry {i + 1} ({entry.get('id', 'no id')})"
    if not all(isinstance(entry.get(k), str) for k in ("id", "code")) or not _is_text(entry.get("explanation")):
        raise ValueError(f"{where}: needs an id, a code and an explanation")
    if unknown := set(entry) - ENTRY_FIELDS:
        raise ValueError(f"{where}: unknown field(s) {sorted(unknown)}")
    if not isinstance(entry.get("fixes", []), list) or not all(_is_text(f) for f in entry.get("fixes", [])):
        raise ValueError(f"{where}: fixes must be a list of strings (or of lists of sentences)")
    if "when" not in entry and not last:
        raise ValueError(f"{where}: only the last entry may leave out 'when'")
    for cond in _as_list(entry.get("when", {})):
        if unknown := set(cond) - CONDITIONS:
            raise ValueError(f"{where}: unknown condition(s) {sorted(unknown)}")
        if missing := [e for e in _as_list(cond.get("error", [])) if exception_class(e) is None]:
            raise ValueError(f"{where}: unknown error class(es) {missing}")
    if missing := [name for name in entry.get("facts", []) if name not in FACTS]:
        raise ValueError(f"{where}: unknown fact(s) {missing}")


def check_entries(entries: Any, name: str = KNOWLEDGE_BASE.name) -> None:
    """Raise ValueError describing the first problem in a list of entries."""
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{name}: expected a list of entries under 'entries'")
    for i, entry in enumerate(entries):
        _check_entry(i, entry, last=i == len(entries) - 1)
    if "when" in entries[-1] and entries[-1]["when"]:
        raise ValueError(f"{name}: the last entry must leave out 'when' so every error is covered")
    ids = [e["id"] for e in entries]
    if dupes := sorted({x for x in ids if ids.count(x) > 1}):
        raise ValueError(f"{name}: duplicate id(s) {dupes}")


@functools.lru_cache(maxsize=None)
def knowledge_base(path: Path = KNOWLEDGE_BASE) -> List[Dict[str, Any]]:
    """Load and check the knowledge base; typos in a hand-edited entry fail here, not mid-run."""
    entries = json.loads(path.read_text()).get("entries")
    check_entries(entries, path.name)
    return entries


def lookup(f: Failure) -> Dict[str, Any]:
    """The first knowledge-base entry whose conditions match this failure."""
    return next(e for e in knowledge_base() if any(_matches(c, f) for c in _as_list(e.get("when", {}))))


def translate(
    exc: BaseException,
    step: Optional[Dict[str, Any]],
    protocol: Dict[str, Any],
    res: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a lab-concept diagnostic for an exception raised while running `step`."""
    f = Failure(unwrap(exc), step or {}, protocol, res, state)
    entry = lookup(f)
    fields = f.fields()
    for name in entry.get("facts", []):
        fields.update(FACTS[name](f))
    return {
        "step": fields["n"],
        "step_ir": f.step,
        "raw_error": fields["raw"],
        "deck_state": state,
        "kb_entry": entry["id"],
        "error_code": entry["code"],
        "explanation": _text(entry["explanation"]).format(**fields),
        "suggested_fixes": [_text(fix).format(**fields) for fix in entry.get("fixes", [])],
        # This failure's placeholder values, so a proposed fix can be shown filled in for review.
        "fields": {k: v if isinstance(v, (int, float, str, list, type(None))) else str(v) for k, v in fields.items()},
        # What a new entry for this failure would match on (used by knowledge proposals).
        "match": {
            "error": type(f.err).__name__,
            "message": str(f.err),
            "device_code": getattr(f.err, "code", None),
            "action": f.step.get("action"),
            "labware": f.labware,
            "reagent_loaded": f.reagent_loaded(),
        },
    }


# ---------- learning across runs ----------
# After each self-healing run, every entry that diagnosed a failure gets its `observed` block
# updated: how often it came up, how often the model's repair made it go away and with which
# edits, and why edits were rejected. People read this to improve the entry; it is never sent
# to the model, so recording does not change what the model sees.

MAX_EXAMPLES = 5
REJECTION_KINDS = [  # (text in the harness's rejection message, how it is tallied)
    ("changes how much liquid is moved", "intent guard: moves a different volume"),
    ("changes the experiment", "intent guard: changes a hold or an empty"),
    ("which does not exist", "replace_step names a step that does not exist"),
    ("Only the failing step", "edits a step other than the failing one"),
    ("is replaced twice", "replaces the same step twice"),
    ("set_initial_volume needs", "set_initial_volume on something that is not a container"),
    ("Unknown edit op", "unknown edit op"),
    ("no edits were proposed", "no edits proposed"),
]
_write_lock = threading.Lock()


def rejection_kind(error: str) -> str:
    return next((kind for text, kind in REJECTION_KINDS if text in error), "a new step does not compile")


def _outcome(r: Dict[str, Any], nxt: Optional[Dict[str, Any]]) -> Optional[str]:
    """How a failed round's repair went: the edit ops that resolved it, or None if it did not.
    Resolved means the next round passed, or failed in the simulator at a different entry or step."""
    applied = [r["edits"][i] for i in r.get("edits_applied", [])]
    if not applied or nxt is None:
        return None
    moved_on = nxt["passed"] or (nxt.get("kb_entry") and (nxt["kb_entry"], nxt.get("step")) != (r["kb_entry"], r.get("step")))
    return "+".join(sorted({e.get("op", "?") for e in applied})) if moved_on else None


def update_knowledge(path: Path, change: Callable[[Dict[str, Any]], Any]) -> Any:
    """Read the knowledge base, apply `change` to it, and write it back atomically. If `change`
    raises, nothing is written. Returns what `change` returned."""
    with _write_lock:
        kb = json.loads(path.read_text())
        result = change(kb)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(kb, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)  # never leave a half-written knowledge base
    knowledge_base.cache_clear()
    return result


def decisions_path(path: Path) -> Path:
    """The decision log kept next to a knowledge base."""
    return path.parent / "decisions.jsonl"


def record_run(rounds: List[Dict[str, Any]], protocol: str, model: str, path: Path = KNOWLEDGE_BASE,
               today: Optional[datetime.date] = None) -> List[str]:
    """Add what a self-healing run learned to the knowledge base, and append one line per repair
    decision to decisions.jsonl next to it. `rounds` is HealResult.rounds. Returns the ids of the
    entries that were updated."""
    date = (today or datetime.date.today()).isoformat()
    status = "HEALED" if rounds and rounds[-1]["passed"] else "GAVE_UP"
    decisions: List[Dict[str, Any]] = []

    def change(kb: Dict[str, Any]) -> List[str]:
        by_id = {e["id"]: e for e in kb["entries"]}
        updated = []
        for i, r in enumerate(rounds):
            entry = by_id.get(r.get("kb_entry"))
            if entry is None:
                continue  # passed, failed before the simulator, or the entry was renamed since
            obs = entry.setdefault("observed", {
                "seen": 0, "repair_attempts": 0, "resolved": 0, "resolved_by": {}, "rejected": {},
                "protocols": [], "models": [], "first_seen": date, "last_seen": date, "examples": [],
            })
            nxt = rounds[i + 1] if i + 1 < len(rounds) else None
            resolved_by = _outcome(r, nxt)
            escalated = r.get("mode") == "escalated"
            if "edits" in r:
                decisions.append(_decision(r, entry, obs, resolved_by, status, protocol, model, date))
            obs["seen"] += 1
            if r.get("edits_applied"):
                obs["repair_attempts"] += 1
            if resolved_by:
                obs["resolved"] += 1
                obs["resolved_by"][resolved_by] = obs["resolved_by"].get(resolved_by, 0) + 1
            if escalated:
                obs["escalations"] = obs.get("escalations", 0) + 1
                obs["escalations_resolved"] = obs.get("escalations_resolved", 0) + bool(resolved_by)
            for err in r.get("edit_errors", []):
                kind = rejection_kind(err)
                obs["rejected"][kind] = obs["rejected"].get(kind, 0) + 1
            for key, value in (("protocols", protocol), ("models", model)):
                if value and value not in obs[key]:
                    obs[key].append(value)
            obs["last_seen"] = date
            if resolved_by:
                outcome = f"resolved by {resolved_by}"
            elif "edits" not in r:
                outcome = "no repair attempted (out of rounds)"
            elif not r.get("edits_applied"):
                outcome = "all edits rejected"
            else:
                outcome = "edits applied, failure remained"
            if escalated:
                outcome += " (model reasoned past the knowledge base)"
            obs["examples"] = (obs["examples"] + [{
                "date": date, "protocol": protocol, "model": model, "step": r.get("step"),
                "raw_error": r.get("raw_error"), "outcome": outcome,
            }])[-MAX_EXAMPLES:]
            updated.append(entry["id"])
        return updated

    updated = update_knowledge(path, change)
    if decisions:
        with _write_lock, decisions_path(path).open("a") as log:
            for d in decisions:
                log.write(json.dumps(d) + "\n")
    return updated


def _decision(r: Dict[str, Any], entry: Dict[str, Any], obs: Dict[str, Any], resolved_by: Optional[str],
              status: str, protocol: str, model: str, date: str) -> Dict[str, Any]:
    """One repair decision, for a future policy that chooses between following the knowledge base
    and asking the model to reason past it. Features are what was known before the decision
    (the entry's history is read before this round is added to it); the rest is the outcome."""
    match = r.get("match", {})
    return {
        "date": date, "protocol": protocol, "model": model, "round": r["round"],
        # features
        "kb_entry": entry["id"], "code": entry["code"], "error": match.get("error"), "action": match.get("action"),
        "reagent_loaded": match.get("reagent_loaded"), "repeats": r.get("repeats", 0),
        "entry_has_fixes": bool(entry.get("fixes")), "entry_seen_before": obs["seen"],
        "entry_attempts_before": obs["repair_attempts"], "entry_resolved_before": obs["resolved"],
        "previous_rejections": r.get("previous_rejections", []),
        # action taken: follow the knowledge base, or reason past it
        "mode": r.get("mode", "knowledge_base"), "policy": r.get("policy", "none"),
        # outcome
        "edits_applied": len(r.get("edits_applied", [])),
        "rejections": sorted({rejection_kind(e) for e in r.get("edit_errors", [])}),
        "resolved": bool(resolved_by), "resolved_by": resolved_by, "run_status": status,
        "proposal": bool(r.get("knowledge_proposal")),
    }
