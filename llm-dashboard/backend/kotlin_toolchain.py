"""Resolve kotlinc: KOTLIN_HOME, bundled tools/kotlin (from setup), then PATH. Requires a JDK on PATH."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_DASHBOARD_ROOT = Path(__file__).resolve().parent.parent


def kotlin_home_candidates() -> list[Path]:
    homes: list[Path] = []
    env = os.getenv("KOTLIN_HOME", "").strip()
    if env:
        homes.append(Path(env))
    homes.append(_DASHBOARD_ROOT / "tools" / "kotlin")
    return homes


def resolve_kotlinc_argv() -> list[str]:
    """
    Executable path for the Kotlin compiler CLI (first element of argv).
    Caller adds ``Main.kt`` and uses cwd=snippet dir.
    """
    for home in kotlin_home_candidates():
        if os.name == "nt":
            bat = home / "bin" / "kotlinc.bat"
            if bat.is_file():
                return [str(bat.resolve())]
        exe = home / "bin" / "kotlinc"
        if exe.is_file():
            return [str(exe.resolve())]
    for name in ("kotlinc", "kotlinc.bat"):
        found = shutil.which(name)
        if found:
            return [found]
    return ["kotlinc"]
