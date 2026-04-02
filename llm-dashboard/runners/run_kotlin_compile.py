#!/usr/bin/env python3
"""CLI helper: kotlinc in cwd. Expects Main.kt in current directory."""
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.kotlin_toolchain import resolve_kotlinc_argv

r = subprocess.run([*resolve_kotlinc_argv(), "Main.kt"], capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="", file=sys.stderr)
sys.exit(r.returncode)
