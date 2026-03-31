#!/usr/bin/env python3
"""CLI helper: run detekt if DETEKT_JAR and path provided."""
import os
import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: run_detekt.py <input_dir>", file=sys.stderr)
    sys.exit(2)

jar = os.environ.get("DETEKT_JAR", "")
if not jar or not os.path.isfile(jar):
    print("DETEKT_JAR not set or missing", file=sys.stderr)
    sys.exit(1)

out = os.path.join(sys.argv[1], "detekt.json")
cmd = ["java", "-jar", jar, "analyze", "-i", sys.argv[1], "--report", f"json:{out}"]
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="", file=sys.stderr)
sys.exit(r.returncode)
