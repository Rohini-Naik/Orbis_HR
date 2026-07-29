#!/usr/bin/env python3
"""Orbis — run the backend and frontend together.

    Linux / macOS :  ./start.sh     (or: python3 start.py)
    Windows       :  start.bat      (or: py start.py)

Ctrl-C stops both. Run setup first if you haven't.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"
VENV_BIN = ROOT / "venv" / ("Scripts" if IS_WINDOWS else "bin")
VENV_PY = VENV_BIN / ("python.exe" if IS_WINDOWS else "python")

if IS_WINDOWS:
    os.system("")
BOLD, GREEN, RED, DIM, OFF = "\033[1m", "\033[32m", "\033[31m", "\033[2m", "\033[0m"

def main() -> None:
    setup_cmd = "setup.bat" if IS_WINDOWS else "./setup.sh"
    for path, what in (
        (VENV_PY, "venv/"),
        (ROOT / ".env", ".env"),
        (ROOT / "Frontend" / "node_modules", "Frontend/node_modules"),
    ):
        if not path.exists():
            print(f"{RED}{what} not found — run {setup_cmd} first.{OFF}", file=sys.stderr)
            sys.exit(1)

    npm = shutil.which("npm") or (shutil.which("npm.cmd") if IS_WINDOWS else None)
    if npm is None:
        print(f"{RED}npm not found on PATH.{OFF}", file=sys.stderr)
        sys.exit(1)

    procs: list[subprocess.Popen] = []
    try:
        print(f"{BOLD}Starting backend{OFF}  {DIM}http://localhost:8000/docs{OFF}")
        procs.append(subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--port", "8000"], cwd=ROOT
        ))

        print(f"{BOLD}Starting frontend{OFF} {DIM}http://localhost:5173{OFF}")
        procs.append(subprocess.Popen(
            [npm, "run", "dev"], cwd=ROOT / "Frontend", shell=IS_WINDOWS
        ))

        print(f"\n{GREEN}{BOLD}Orbis is starting — open http://localhost:5173{OFF}")
        print(f"{DIM}Invitation links for new hires appear in this terminal. "
              f"Ctrl-C to stop.{OFF}\n")

        # Exit as soon as either half dies, so a crashed backend doesn't leave a
        # frontend serving a dead API.
        while all(proc.poll() is None for proc in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n{DIM}Shutting down…{OFF}")
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


# Guarded so importing this module (tooling, tests) never launches servers.
if __name__ == "__main__":
    main()
