"""The run store: every run leaves a folder in the working folder, so it can be reopened and traced later.

    runs/<timestamp>-<protocol>/
        manifest.json     what the run was, its result, the models used, and where everything came from
        input.txt         what the scientist gave (the text, or a copy of the file)
        protocol.json     the protocol as it was checked (the passing one, or the last attempt)
        script.py         the standalone PyLabRobot script (passing runs only)
        layout.yaml       the AHC layout (passing runs only)
        summary.md        the summary: result, design, review list
        report.json       the design review and suggestions, as data
        heal_log.json     every repair round: the failure, the model's edits, the verdict

The manifest's `provenance` records the files and versions the run depended on, as hashes and version strings, so a
run can be compared with the lab's files as they are later.
"""

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline import paths

RUNS = paths.WORK / "runs"


def _sha256(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _library_fingerprint(library: Path) -> Optional[str]:
    """One hash over the library's file names and sizes (hashing 141 MB of files on every run would be slow)."""
    if not library.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(library.rglob("*")):
        if path.is_file():
            digest.update(f"{path.relative_to(library)} {path.stat().st_size}\n".encode())
    return digest.hexdigest()


def _commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.PLUGIN, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def provenance() -> Dict[str, Any]:
    """The versions and the ground-truth files a run depends on, as hashes and version strings."""
    config = paths.PLUGIN / "config"
    try:
        pylabrobot = importlib.metadata.version("pylabrobot")
    except importlib.metadata.PackageNotFoundError:
        pylabrobot = "unknown"
    return {
        "precheck_commit": _commit(),
        "pylabrobot": pylabrobot,
        "python": platform.python_version(),
        "instrument_file_sha256": _sha256(config / "instrument" / "starlet_F553.json"),
        "firmware_report_sha256": _sha256(config / "instrument" / "starlet_F553_configuration.json"),
        "deck_layout_sha256": _sha256(config / "instrument" / "ahc_deck.lay"),
        "venus_map_sha256": _sha256(config / "venus_labware.json"),
        "policy_sha256": _sha256(config / "precheck_policy.json"),
        "labware_library_fingerprint": _library_fingerprint(config / "Labware"),
    }


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)[:60] or "protocol"


def record(stem: str, source: Optional[str], protocol: Dict[str, Any], rounds: List[Dict[str, Any]],
           tiers: List[Dict[str, Any]], passed: bool, summary_md: str, report: Optional[Dict[str, Any]],
           script: Optional[str] = None, layout: Optional[Path] = None, runs_dir: Path = RUNS) -> Path:
    """Write one run's folder and return it. `source` is the protocol text, or the path of the file given."""
    created = datetime.now()
    folder = runs_dir / f"{created.strftime('%Y%m%d-%H%M%S')}-{_slug(stem)}"
    folder.mkdir(parents=True, exist_ok=True)

    if source is not None:
        given = Path(source)
        if given.is_file():
            shutil.copyfile(given, folder / f"input{given.suffix or '.txt'}")
        else:
            (folder / "input.txt").write_text(source)
    (folder / "protocol.json").write_text(json.dumps(protocol, indent=2))
    (folder / "summary.md").write_text(summary_md)
    (folder / "heal_log.json").write_text(json.dumps({"tiers": [{"model": t["model"], "status": t["status"]} for t in tiers],
                                                     "rounds": rounds}, indent=2))
    files = ["input*", "protocol.json", "summary.md", "heal_log.json"]
    if report is not None:
        (folder / "report.json").write_text(json.dumps(report, indent=2))
        files.append("report.json")
    if script is not None:
        (folder / "script.py").write_text(script)
        files.append("script.py")
    if layout is not None and layout.exists():
        shutil.copyfile(layout, folder / "layout.yaml")
        files.append("layout.yaml")

    manifest = {
        "id": folder.name,
        "created": created.isoformat(timespec="seconds"),
        "protocol_name": protocol.get("protocol_name") or stem,
        "stem": stem,
        "passed": passed,
        "status": "PASSED" if passed else "NOT READY",
        "steps": len(protocol.get("steps", [])),
        "repair_rounds": max(len(rounds) - 1, 0),
        "models": [{"model": t["model"], "rounds": max(len(t["rounds"]) - 1, 0), "status": t["status"]} for t in tiers],
        "simulated_on": "PyLabRobot's STAR model, configured as this instrument",
        "files": files,
        "review": {"items": (report or {}).get("needs_review", []), "acknowledged": {}},
        "provenance": provenance(),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return folder


def list_runs(runs_dir: Path = RUNS) -> List[Dict[str, Any]]:
    """Every run's manifest, newest first."""
    if not runs_dir.is_dir():
        return []
    manifests = []
    for path in runs_dir.glob("*/manifest.json"):
        manifests.append(json.loads(path.read_text()))
    return sorted(manifests, key=lambda m: m["created"], reverse=True)


def load(run_id: str, runs_dir: Path = RUNS) -> Optional[Dict[str, Any]]:
    path = runs_dir / Path(run_id).name / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else None


def run_file(run_id: str, name: str, runs_dir: Path = RUNS) -> Optional[Path]:
    """A file inside one run's folder. Names that leave the folder are refused."""
    folder = (runs_dir / Path(run_id).name).resolve()
    target = (folder / Path(name).name).resolve()
    if target.parent != folder or not target.is_file():
        return None
    return target


def acknowledge(run_id: str, item_index: int, name: str, note: str = "", runs_dir: Path = RUNS) -> Dict[str, Any]:
    """A person's review of one item, with their typed name and an optional note. Stored in the manifest."""
    path = runs_dir / Path(run_id).name / "manifest.json"
    manifest = json.loads(path.read_text())
    items = manifest["review"]["items"]
    if not 0 <= item_index < len(items):
        raise IndexError(f"the run has {len(items)} review items")
    manifest["review"]["acknowledged"][str(item_index)] = {
        "by": name.strip()[:80], "note": note.strip()[:500],
        "at": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(manifest, indent=2))
    return manifest
