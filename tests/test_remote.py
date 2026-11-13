"""Remote stage 5 (pipeline/remote.py and `python -m pipeline.stage5_executor serve`), without SSH: the
`serve` side runs as a local subprocess, so these check the protocol between the two sides, abort and
disconnect handling, the STARlet lock shared with the AHC bridge, and what blocks a run on the Pi.
Only ChatterBox runs; nothing here opens USB."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pipeline import remote as remote_module
from pipeline.deck import load_deck_config
from pipeline.remote import RemoteExecutor, code_digest, refusal
from pipeline.stage5_executor import ExecutionError, lock_holder, take_lock

ROOT = Path(__file__).resolve().parent.parent
LOCAL = {"name": "test", "host": "localhost", "dir": ".", "python": sys.executable, "star_lock": "unused"}


@pytest.fixture
def no_ssh(monkeypatch):
    """Run the remote command here, in the repo root, instead of over SSH."""
    monkeypatch.setattr(remote_module, "_ssh", lambda remote, command: ["sh", "-c", f"cd {ROOT} && {command}"])


def test_the_starlet_lock_is_exclusive_and_names_its_holder(tmp_path):
    lock = str(tmp_path / "lock")
    holder = subprocess.Popen([sys.executable, "-c", f"""
import sys, time; sys.path.insert(0, {str(ROOT)!r})
from pipeline.stage5_executor import take_lock
take_lock({lock!r}); print("held", flush=True); time.sleep(30)
"""], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        assert lock_holder(lock) == str(holder.pid)
        with pytest.raises(ExecutionError, match=f"pid {holder.pid}"):
            take_lock(lock)
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.1)
    assert lock_holder(lock) is None  # the lock goes with the process
    fd = take_lock(lock)
    assert (tmp_path / "lock").read_text() == str(os.getpid())
    os.close(fd)


def test_a_missing_lock_folder_is_an_error_not_a_new_folder(tmp_path):
    with pytest.raises(ExecutionError, match="does not exist"):
        take_lock(str(tmp_path / "nowhere" / "lock"))
    assert not (tmp_path / "nowhere").exists()


def test_what_blocks_a_run_on_the_pi():
    ready = {"host": "pi", "in_sync": True, "star_connected": True, "lock": {"path": "/l", "held_by": None}}
    assert refusal(ready, "star") is None
    assert "Sync" in refusal({**ready, "in_sync": False}, "chatterbox")
    assert "not on pi's USB" in refusal({**ready, "star_connected": False}, "star")
    assert refusal({**ready, "star_connected": False}, "chatterbox") is None
    held = {**ready, "lock": {"path": "/l", "held_by": "2735"}}
    assert "pid 2735" in refusal(held, "star")
    assert refusal(held, "chatterbox") is None  # a rehearsal does not touch the STARlet
    assert refusal({"error": "SSH failed"}, "chatterbox") == "SSH failed"


def test_the_code_digest_is_stable():
    assert code_digest(ROOT) == code_digest(ROOT)
    assert len(code_digest(ROOT)) == 16
