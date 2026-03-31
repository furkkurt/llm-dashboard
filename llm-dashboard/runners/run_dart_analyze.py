#!/usr/bin/env python3
import subprocess
import sys
r = subprocess.run(["dart", "analyze", "--format=machine", "main.dart"], capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="", file=sys.stderr)
sys.exit(r.returncode)
