#!/usr/bin/env python3
"""CLI helper: kotlinc in cwd. Expects Main.kt in current directory."""
import subprocess
import sys
r = subprocess.run(["kotlinc", "Main.kt"], capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="", file=sys.stderr)
sys.exit(r.returncode)
