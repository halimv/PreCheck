"""Setting PreCheck up: the plugin's own requirements, and the working folder a task runs in.

`precheck --setup` (run it in the task folder) checks what PreCheck needs and makes the folders a run writes into:
healed/, drafts/, decks/, build/ and knowledge/ (the knowledge base, copied from the plugin's seed). Nothing else is
created. Installing the plugin can't do the folder part, because a working folder is a task folder the scientist
chooses; the first setup in that folder does it, and every run also creates whatever it needs on the way.
"""

import shutil
from pathlib import Path
from typing import List, Tuple

from pipeline import paths

FOLDERS = (paths.HEALED, paths.DRAFTS, paths.DECKS, paths.BUILD, paths.WORK / "runs")


def checks() -> List[Tuple[str, bool, str]]:
    """(check, passed, what to do) for everything PreCheck needs."""
    venus = paths.PLUGIN / "config" / "Labware"
    venus_ok = (venus / "ML_STAR").is_dir()
    instrument = paths.PLUGIN / "config" / "instrument" / "starlet_F553.json"
    writable = paths.WORK.is_dir() and _writable(paths.WORK)
    claude = shutil.which("claude")
    uv = shutil.which("uv")
    return [
        ("VENUS labware library", venus_ok,
         f"Copy the VENUS library's Labware folder (from the lab's VENUS install) to {venus}." if not venus_ok else str(venus)),
        ("instrument file and deck", instrument.exists(),
         str(instrument) if instrument.exists() else "The STARlet's instrument file is missing from the plugin's config/instrument/."),
        ("Claude Code CLI (drafting and repairs)", claude is not None,
         "Install it with `npm install -g @anthropic-ai/claude-code`, then run `claude` once to log in."
         if claude is None else claude),
        ("uv (installs PreCheck's Python packages)", uv is not None,
         "Install uv (https://docs.astral.sh/uv/), or set PRECHECK_PYTHON to a Python that has the packages."
         if uv is None else uv),
        ("working folder writable", writable,
         str(paths.WORK) if writable else f"{paths.WORK} is not writable; run PreCheck from a folder you own."),
    ]


def _writable(folder: Path) -> bool:
    probe = folder / ".precheck_write_test"
    try:
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


def setup() -> List[Tuple[str, bool, str]]:
    """Make the working folder's folders and seed the knowledge base. Returns the checks, after setup."""
    if paths.WORK.is_dir() and _writable(paths.WORK):
        for folder in FOLDERS:
            folder.mkdir(parents=True, exist_ok=True)
        paths.ensure_knowledge()
    return checks()


def report(results: List[Tuple[str, bool, str]]) -> str:
    lines = [f"PreCheck working folder: {paths.WORK}", f"PreCheck plugin folder:  {paths.PLUGIN}", ""]
    for name, passed, detail in results:
        lines.append(f"  [{'ok' if passed else 'missing'}] {name}: {detail}")
    folders = [f"{f.name}/" for f in FOLDERS + (paths.KNOWLEDGE.parent,) if f.exists()]
    lines += ["", "Working folders present: " + (", ".join(folders) if folders else "none yet")]
    lines.append("Ready." if all(ok for _, ok, _ in results) else "Fix the items marked missing, then run --setup again.")
    return "\n".join(lines)
