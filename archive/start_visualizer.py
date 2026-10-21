#!/usr/bin/env python3
"""Start Precheck Visualizer"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "viz_backend"

print("📥 Installing dependencies...")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
    cwd=BACKEND_DIR,
    check=True
)

print("🚀 Starting Precheck Visualizer...")
print("🌐 Open http://localhost:8000 in your browser\n")

subprocess.run(
    [sys.executable, "server.py"],
    cwd=BACKEND_DIR,
    check=True
)
