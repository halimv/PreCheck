"""Setting precheck up: the plugin's own requirements, and the working folder a task runs in.

`precheck --setup` (run it in the task folder) checks what precheck needs and makes the folders a run writes into:
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
    """(check, passed, what to do) for everything precheck needs."""
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
        ("uv (installs precheck's Python packages)", uv is not None,
         "Install uv (https://docs.astral.sh/uv/), or set PRECHECK_PYTHON to a Python that has the packages."
         if uv is None else uv),
        ("working folder writable", writable,
         str(paths.WORK) if writable else f"{paths.WORK} is not writable; run precheck from a folder you own."),
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
    lines = [f"precheck working folder: {paths.WORK}", f"precheck plugin folder:  {paths.PLUGIN}", ""]
    for name, passed, detail in results:
        lines.append(f"  [{'ok' if passed else 'missing'}] {name}: {detail}")
    folders = [f"{f.name}/" for f in FOLDERS + (paths.KNOWLEDGE.parent,) if f.exists()]
    lines += ["", "Working folders present: " + (", ".join(folders) if folders else "none yet")]
    lines.append("Ready." if all(ok for _, ok, _ in results) else "Fix the items marked missing, then run --setup again.")
    return "\n".join(lines)


def _library_ok(folder: Path) -> bool:
    return folder.is_dir() and (folder / "ML_STAR").is_dir()


def _ask(prompt: str) -> str:
    """A question to the person. No answer (end of input, Ctrl+C) counts as pressing Enter: the default."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def interactive_setup(ask=_ask, out=print) -> List[Tuple[str, bool, str]]:
    """`precheck --setup` in a terminal: show what is missing, and ask for what the person can give. Asks for the
    VENUS labware library's folder (linked into the plugin, so the library stays where the lab keeps it), and for a
    task folder to create if this one is not usable. Returns the checks after setup."""
    out(report(checks()))
    venus = paths.PLUGIN / "config" / "Labware"
    if not _library_ok(venus):
        given = ask("\nWhere is the VENUS Labware folder (the one with ML_STAR inside)? Press Enter to skip: ").strip()
        if given:
            source = Path(given).expanduser().resolve()
            if _library_ok(source):
                if venus.is_symlink() or not venus.exists():
                    venus.parent.mkdir(parents=True, exist_ok=True)
                    if venus.is_symlink():
                        venus.unlink()
                    venus.symlink_to(source, target_is_directory=True)
                    out(f"Linked {venus} to {source}.")
            else:
                out(f"{source} has no ML_STAR folder, so it is not a VENUS Labware folder. Not linked.")
    if not (paths.WORK.is_dir() and _writable(paths.WORK)):
        out(f"\nThis folder ({paths.WORK}) is not usable for results.")
    else:
        choice = ask(f"\nPress Enter to keep results in {paths.WORK}, or type the path of a new folder to create: ").strip()
        if choice:
            target = Path(choice).expanduser().resolve()
            target.mkdir(parents=True, exist_ok=True)
            out(f"Created {target}.\nRun setup there:  cd {target} && precheck --setup")
            return checks()
    return setup()
