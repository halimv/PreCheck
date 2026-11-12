"""Knowledge-base proposals: the model's suggested additions to knowledge/diagnostics.json.

When the same simulator failure comes back round after round, the self-healing loop stops
relying on the knowledge base's suggestions and asks the model to reason past them (an
"escalated" round). Besides its edits, the model then proposes a change to the knowledge base:
a new fix for the entry, a replacement for fixes that do not work, or a new entry for an error
the knowledge base does not cover.

A proposal is only kept when its own edits fixed the failure and the protocol then passed every
stage. It is stored under "proposals" in the knowledge base with status "pending"; nothing reaches
the entries the model sees until a person approves it (demo Library page, or this module's CLI).

    python -m pipeline.proposals list
    python -m pipeline.proposals approve <id>
    python -m pipeline.proposals reject <id> [comment]
"""

import datetime
import json
import re
import string
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline import diagnostics
from pipeline.diagnostics import KNOWLEDGE_BASE

KINDS = ("add_fix", "replace_fixes", "new_entry")
UNRECOGNIZED = "unrecognized"


def placeholders_for(entry_id: Optional[str]) -> List[str]:
    """Placeholders a fix for this entry may use: the ones every entry has, plus its facts'."""
    entry = next((e for e in diagnostics.knowledge_base() if e["id"] == entry_id), {})
    names = list(diagnostics.ALWAYS_FIELDS)
    for fact in entry.get("facts", []):
        names.extend(diagnostics.FACT_FIELDS.get(fact, ()))
    return names


def _template(text: str, allowed: List[str], labware: Optional[str], step: Optional[int]) -> str:
    """Turn the model's fix into knowledge-base template text. Braces that are not known
    placeholders are kept as literal text; this run's labware ID and step number become
    {labware} and {n}, so the fix reads for any protocol."""
    try:
        names = {f for _, f, _, _ in string.Formatter().parse(text) if f is not None}
        ok = all(n.split(":")[0].split("!")[0] in allowed for n in names)
    except ValueError:
        ok = False
    if not ok:
        text = text.replace("{", "{{").replace("}", "}}")
    if labware:
        text = re.sub(rf"(?<![\w{{]){re.escape(labware)}(?![\w}}])", "{labware}", text)
    if step is not None:
        text = re.sub(rf"\b([Ss]tep) {step}\b", r"\1 {n}", text)
    return text


def _problems(kind: str, target: Optional[str], p: Dict[str, Any], match: Dict[str, Any]) -> List[str]:
    problems = []
    if not str(p.get("fix", "")).strip():
        problems.append("no fix text")
    if kind == "new_entry":
        if not re.fullmatch(r"[A-Z][A-Z0-9_]+", str(p.get("code", ""))):
            problems.append("a new entry needs a code in UPPER_SNAKE_CASE")
        if not str(p.get("title", "")).strip() or not str(p.get("explanation", "")).strip():
            problems.append("a new entry needs a title and an explanation")
        text = str(p.get("match_text", "")).strip()
        if text and text not in match.get("message", ""):
            problems.append(f"match_text {text!r} does not appear in the error message")
    return problems


def _warnings(kind: str, target: Optional[str], record: Dict[str, Any], proposed: Dict[str, Any]) -> List[str]:
    """Things a reviewer should look at; they don't stop a proposal from being kept. Also fills in
    the fix with this run's values (proposed["fix_example"]) so a misused placeholder shows."""
    warnings = []
    try:
        proposed["fix_example"] = proposed["fix"].format(**record.get("fields", {}))
    except (KeyError, IndexError, ValueError):
        pass  # a fact's placeholder this record has no value for; the reviewer sees the template
    entry = next((e for e in diagnostics.knowledge_base() if e["id"] == target), {}) if kind != "new_entry" else {}
    existing = " ".join(diagnostics._text(f) for f in entry.get("fixes", []))
    ops = sorted({record["edits"][i].get("op") for i in record.get("edits_applied", [])})
    if existing and ops and all(op in existing for op in ops):
        warnings.append(f"the edits that worked ({', '.join(ops)}) are what this entry already suggests: the model "
                        "may have needed the existing fix followed, not a new one")
    if re.search(r"\d{3,}", proposed["fix"]):
        warnings.append("the fix contains numbers from this run; check they hold for other protocols")
    return warnings


def candidate(record: Dict[str, Any], resolved: bool, healed: bool) -> Dict[str, Any]:
    """Build a proposal from an escalated round's record (HealResult.rounds item)."""
    p = record.get("knowledge_proposal") or {}
    target = record.get("kb_entry")
    match = record.get("match", {})
    kind = p.get("kind") if p.get("kind") in KINDS else "add_fix"
    # Only the catch-all can grow a new entry; anywhere else a new fix belongs to the entry itself.
    if target == UNRECOGNIZED:
        kind = "new_entry"
    elif kind == "new_entry":
        kind = "add_fix"
    allowed = placeholders_for(target) if kind != "new_entry" else list(diagnostics.ALWAYS_FIELDS)
    proposed = {
        "fix": _template(str(p.get("fix", "")), allowed, match.get("labware"), record.get("step")),
        "why": str(p.get("why", "")),
        "fix_as_written": str(p.get("fix", "")),
    }
    if kind == "new_entry":
        when: Dict[str, Any] = {"error": match.get("error")}
        if p.get("match_text"):
            when["message_contains"] = str(p["match_text"]).strip()
        if match.get("device_code"):
            when["device_code"] = match["device_code"]
        if match.get("action"):
            when["action"] = match["action"]
        proposed.update(code=str(p.get("code", "")), title=str(p.get("title", "")),
                        explanation=_template(str(p.get("explanation", "")), allowed, match.get("labware"), record.get("step")),
                        when=when)
    problems = _problems(kind, target, p, match)
    if record.get("edit_errors"):
        # Part of the reply was rejected, so the proposal may describe edits that never ran.
        problems.append("part of the model's reply was rejected, so the fix it describes was not what ran")
    if not resolved:
        problems.append("its edits did not fix the failure")
    elif not healed:
        problems.append("the protocol did not pass every stage afterwards")
    return {
        "kind": kind, "target": target, "proposed": proposed, "problems": problems,
        "warnings": _warnings(kind, target, record, proposed),
        "evidence": {
            "round": record["round"], "step": record.get("step"), "raw_error": record.get("raw_error"),
            "repeats": record.get("repeats", 0), "reasoning": record.get("model_reasoning", ""),
            "edits_applied": [record["edits"][i] for i in record.get("edits_applied", [])],
        },
    }


def collect(rounds: List[Dict[str, Any]], status: str) -> List[Dict[str, Any]]:
    """Every proposal made in a run; a proposal with no problems is ready for review."""
    out = []
    for i, r in enumerate(rounds):
        if r.get("mode") != "escalated" or not r.get("knowledge_proposal"):
            continue
        nxt = rounds[i + 1] if i + 1 < len(rounds) else None
        out.append(candidate(r, diagnostics._outcome(r, nxt) is not None, status == "HEALED"))
    return out


def submit(candidates: List[Dict[str, Any]], protocol: str, model: str, path: Path = KNOWLEDGE_BASE,
           today: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
    """Store the candidates that have no problems as pending proposals. Returns what was stored."""
    ready = [c for c in candidates if not c["problems"]]
    if not ready:
        return []
    date = (today or datetime.date.today()).isoformat()
    stored = [{"id": f"p-{date.replace('-', '')}-{uuid.uuid4().hex[:6]}", "status": "pending", "created": date,
               "protocol": protocol, "model": model, **c} for c in ready]
    for s in stored:
        s.pop("problems")
    diagnostics.update_knowledge(path, lambda kb: kb.setdefault("proposals", []).extend(stored))
    return stored


def _find(kb: Dict[str, Any], pid: str) -> Dict[str, Any]:
    p = next((p for p in kb.get("proposals", []) if p["id"] == pid), None)
    if p is None:
        raise KeyError(f"no proposal {pid}")
    if p["status"] != "pending":
        raise ValueError(f"proposal {pid} is already {p['status']}")
    return p


def _note(p: Dict[str, Any], date: str) -> str:
    return (f"Added {date} from proposal {p['id']} ({p['model']} on {p['protocol']}, approved by a person): "
            f"{p['proposed']['why']}")


def approve(pid: str, path: Path = KNOWLEDGE_BASE, comment: str = "",
            today: Optional[datetime.date] = None) -> Dict[str, Any]:
    """Merge a pending proposal into the entries. The whole knowledge base is checked first, so
    a proposal that would break it is refused and nothing changes. Returns the changed entry."""
    date = (today or datetime.date.today()).isoformat()

    def change(kb: Dict[str, Any]) -> Dict[str, Any]:
        p = _find(kb, pid)
        entries = kb["entries"]
        new = p["proposed"]
        if p["kind"] == "new_entry":
            ids = {e["id"] for e in entries}
            base = new["code"].lower()
            eid = base if base not in ids else next(f"{base}.{k}" for k in range(2, 99) if f"{base}.{k}" not in ids)
            entry = {"id": eid, "code": new["code"], "title": new["title"], "when": new["when"],
                     "explanation": new["explanation"], "fixes": [new["fix"]], "notes": [_note(p, date)]}
            entries.insert(len(entries) - 1, entry)  # just above the catch-all
        else:
            entry = next(e for e in entries if e["id"] == p["target"])
            notes = diagnostics._as_list(entry.get("notes", []))
            if p["kind"] == "replace_fixes":
                old = " | ".join(diagnostics._text(f) for f in entry.get("fixes", []))
                notes.append(f"Fixes before {date}: {old}")
                entry["fixes"] = [new["fix"]]
            else:
                entry["fixes"] = entry.get("fixes", []) + [new["fix"]]
            entry["notes"] = notes + [_note(p, date)]
        diagnostics.check_entries(entries)
        p.update(status="approved", reviewed={"date": date, "comment": comment, "entry": entry["id"]})
        return entry

    return diagnostics.update_knowledge(path, change)


def reject(pid: str, path: Path = KNOWLEDGE_BASE, comment: str = "",
           today: Optional[datetime.date] = None) -> None:
    """Mark a pending proposal rejected. It stays in the file as a record of what was turned down."""
    date = (today or datetime.date.today()).isoformat()
    diagnostics.update_knowledge(path, lambda kb: _find(kb, pid).update(
        status="rejected", reviewed={"date": date, "comment": comment}))


def pending(path: Path = KNOWLEDGE_BASE) -> List[Dict[str, Any]]:
    return [p for p in json.loads(path.read_text()).get("proposals", []) if p["status"] == "pending"]


def describe(p: Dict[str, Any]) -> str:
    what = {"add_fix": f"add a fix to {p['target']}", "replace_fixes": f"replace the fixes of {p['target']}",
            "new_entry": f"new entry {p['proposed'].get('code')}"}[p["kind"]]
    return f"{p['id']}: {what}\n  fix: {p['proposed']['fix']}\n  why: {p['proposed']['why']}"


def main(argv: List[str]) -> int:
    if not argv or argv[0] == "list":
        items = pending()
        print("\n".join(describe(p) for p in items) if items else "No pending proposals.")
        return 0
    if argv[0] in ("approve", "reject") and len(argv) >= 2:
        comment = " ".join(argv[2:])
        if argv[0] == "approve":
            entry = approve(argv[1], comment=comment)
            print(f"Approved {argv[1]}: {entry['id']} updated in {KNOWLEDGE_BASE.name}.")
        else:
            reject(argv[1], comment=comment)
            print(f"Rejected {argv[1]}.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
