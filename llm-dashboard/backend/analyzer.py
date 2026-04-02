import asyncio
import os
import re
import subprocess
import time
import uuid
from pathlib import Path as P

from backend.flutter_extract import (
    missing_packages_from_diagnostics,
    prepare_flutter_project,
)
from backend.kotlin_toolchain import resolve_kotlinc_argv
from backend.metrics_util import build_metrics
from backend.models import AnalyzeRequest, AnalysisSummary, ErrorItem, StaticFlagItem
from backend.parsers import (
    parse_dart_machine_output,
    parse_detekt_json,
    parse_kotlinc_stderr,
)

_ROOT = P(__file__).resolve().parent.parent
TEMP_RUNS = os.getenv("TEMP_RUNS_DIR", str(_ROOT / "temp" / "runs"))
RAW_LOGS = os.getenv("RAW_LOGS_DIR", str(_ROOT / "results" / "raw-logs"))
DETEKT_JAR = os.getenv("DETEKT_JAR", str(_ROOT / "tools" / "detekt-cli.jar"))

_MAX_PUB_RESOLVE_ROUNDS = 10
_MAX_AUTO_PACKAGES = 24

# Standalone kotlinc has no android.jar / Compose on the classpath.
_ANDROID_KOTLIN_IMPORT = re.compile(
    r"^\s*import\s+((android|androidx)(\.|\s|$)|com\.google\.android\.)",
    re.MULTILINE | re.IGNORECASE,
)


def _kotlin_snippet_needs_android_sdk(code: str) -> bool:
    return bool(_ANDROID_KOTLIN_IMPORT.search(code or ""))


def _write_raw_log(run_id: str, text: str) -> None:
    try:
        d = P(RAW_LOGS)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{run_id}.log").write_text(text, encoding="utf-8", errors="replace")
    except OSError:
        pass


def _run(cmd: list[str], cwd: P, timeout: int = 180) -> tuple[str, str, int]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.stdout or "", p.stderr or "", p.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except FileNotFoundError as e:
        return "", str(e), -1


def _package_in_pubspec(pubspec: str, pkg: str) -> bool:
    return any(
        line.strip().startswith(f"{pkg}:")
        or line.strip().startswith(f"{pkg} :")
        for line in pubspec.splitlines()
    )


def _pub_get(project: P, log_parts: list[str]) -> tuple[str, str, int, str | None]:
    for cmd in (["flutter", "pub", "get"], ["dart", "pub", "get"]):
        o, e, r = _run(cmd, project, timeout=300)
        log_parts.append(f"=== {' '.join(cmd)} stdout ===\n{o}\n=== stderr ===\n{e}\n")
        if r == 0:
            return o, e, r, " ".join(cmd)
    return o, e, r, None


def _analyze_kotlin_sync(payload: AnalyzeRequest, run_dir: P, run_id: str) -> dict:
    kt = run_dir / "Main.kt"
    kt.write_text(payload.code, encoding="utf-8")

    static_flags: list[StaticFlagItem] = []
    if _kotlin_snippet_needs_android_sdk(payload.code):
        compile_out = ""
        compile_err = (
            "kotlinc skipped: snippet imports Android/AndroidX. "
            "Standalone JVM compile is not supported (requires Android SDK / Gradle module)."
        )
        compile_rc = 0
        kotlinc_ms = 0
        error_log: list[ErrorItem] = []
        compilable = True
        error_count = 0
        static_flags.append(
            StaticFlagItem(
                tool="kotlin_pipeline",
                severity="info",
                message=(
                    "JVM kotlinc not run: Android or AndroidX imports detected. "
                    "Detekt still runs on source; treat compilability as unverified vs a device build."
                ),
            )
        )
    else:
        t0 = time.perf_counter()
        compile_out, compile_err, compile_rc = _run([*resolve_kotlinc_argv(), "Main.kt"], run_dir)
        kotlinc_ms = int((time.perf_counter() - t0) * 1000)

        error_log = parse_kotlinc_stderr(compile_err + "\n" + compile_out)
        if not error_log and compile_rc != 0:
            error_log = [
                ErrorItem(
                    tool="kotlinc",
                    severity="error",
                    file="Main.kt",
                    message=(compile_err or compile_out or "kotlinc failed").strip()[:2000],
                )
            ]
        compilable = compile_rc == 0 and not any(e.severity == "error" for e in error_log)
        error_count = len([e for e in error_log if e.severity == "error"])
    analyzer_out, analyzer_err = "", ""

    t1 = time.perf_counter()
    jar = P(DETEKT_JAR)
    if jar.is_file():
        report = run_dir / "detekt.json"
        ao, ae, arc = _run(
            [
                "java",
                "-jar",
                str(jar),
                "analyze",
                "-i",
                str(run_dir),
                "--report",
                f"json:{report}",
            ],
            run_dir,
        )
        analyzer_out, analyzer_err = ao, ae
        detekt_flags = parse_detekt_json(report)
        static_flags.extend(detekt_flags)
        if arc != 0 and not detekt_flags:
            static_flags.append(
                StaticFlagItem(
                    tool="detekt",
                    severity="warning",
                    message=(ae or ao or "detekt exited non-zero")[:2000],
                )
            )
    else:
        static_flags.append(
            StaticFlagItem(
                tool="detekt",
                severity="info",
                message="detekt-cli.jar not found; skipped static analysis.",
            )
        )
    detekt_ms = int((time.perf_counter() - t1) * 1000)

    log_blob = (
        f"=== kotlinc stdout ===\n{compile_out}\n=== kotlinc stderr ===\n{compile_err}\n"
        f"=== detekt stdout ===\n{analyzer_out}\n=== detekt stderr ===\n{analyzer_err}\n"
    )
    _write_raw_log(run_id, log_blob)

    summary = AnalysisSummary(
        compilable=compilable,
        error_count=error_count,
        static_issue_count=len(static_flags),
    )
    return {
        "summary": summary,
        "error_log": error_log,
        "static_flags": static_flags,
        "compile_stdout": compile_out,
        "compile_stderr": compile_err,
        "analyzer_stdout": analyzer_out,
        "analyzer_stderr": analyzer_err,
        "_code_sample": payload.code,
        "_pubspec_sample": None,
        "_timing": {
            "kotlinc_ms": kotlinc_ms,
            "detekt_ms": detekt_ms,
            "pub_get_ms": None,
            "analyze_ms": None,
            "resolve_ms": None,
            "packages_added": [],
            "pub_cmd": None,
        },
    }


def _analyze_dart_sync(payload: AnalyzeRequest, run_dir: P, run_id: str) -> dict:
    """
    Flutter package from LLM paste; pub get; dart analyze with rounds of
    `dart pub add` when diagnostics report missing packages.
    """
    project = run_dir / "flutter_pkg"
    lib_dir = project / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    dart_src, pubspec_yaml, prep_notes = prepare_flutter_project(payload.code)
    (project / "pubspec.yaml").write_text(pubspec_yaml, encoding="utf-8")
    (lib_dir / "main.dart").write_text(dart_src, encoding="utf-8")

    scaffold_flags: list[StaticFlagItem] = [
        StaticFlagItem(tool="flutter_scaffold", severity="info", message=n) for n in prep_notes
    ]

    log_parts: list[str] = []
    t_pg0 = time.perf_counter()
    pub_out, pub_err, pub_rc, pub_cmd = _pub_get(project, log_parts)
    pub_get_ms = int((time.perf_counter() - t_pg0) * 1000)

    if pub_rc != 0:
        err_msg = (pub_err or pub_out or "pub get failed").strip()[:4000]
        error_log = [
            ErrorItem(
                tool="pub_get",
                severity="error",
                file="pubspec.yaml",
                message=err_msg,
            )
        ]
        summary = AnalysisSummary(
            compilable=False,
            error_count=len(error_log),
            static_issue_count=len(scaffold_flags),
        )
        _write_raw_log(run_id, "\n".join(log_parts))
        return {
            "summary": summary,
            "error_log": error_log,
            "static_flags": scaffold_flags,
            "compile_stdout": pub_out,
            "compile_stderr": pub_err,
            "analyzer_stdout": "",
            "analyzer_stderr": "",
            "_code_sample": dart_src,
            "_pubspec_sample": pubspec_yaml,
            "_timing": {
                "kotlinc_ms": None,
                "detekt_ms": None,
                "pub_get_ms": pub_get_ms,
                "analyze_ms": None,
                "resolve_ms": 0,
                "packages_added": [],
                "pub_cmd": pub_cmd,
            },
        }

    packages_added: list[str] = []
    tried: set[str] = set()
    resolve_ms_total = 0
    analyze_ms_total = 0

    final_out, final_err, final_rc = "", "", 0
    error_log: list[ErrorItem] = []
    dart_flags: list[StaticFlagItem] = []

    for _round in range(_MAX_PUB_RESOLVE_ROUNDS):
        t_a = time.perf_counter()
        out, err, rc = _run(
            ["dart", "analyze", "--format=machine"],
            project,
            timeout=300,
        )
        analyze_ms_total += int((time.perf_counter() - t_a) * 1000)
        log_parts.append(
            f"=== dart analyze (round {_round}) stdout ===\n{out}\n=== stderr ===\n{err}\n"
        )
        merged = out + "\n" + err
        error_log, dart_flags = parse_dart_machine_output(merged)
        final_out, final_err, final_rc = out, err, rc

        pubspec_now = (project / "pubspec.yaml").read_text(encoding="utf-8", errors="replace")
        candidates = missing_packages_from_diagnostics(error_log, out, err)
        to_add = [
            p
            for p in candidates
            if p not in tried
            and not _package_in_pubspec(pubspec_now, p)
            and len(packages_added) < _MAX_AUTO_PACKAGES
        ]
        if not to_add:
            break

        t_r = time.perf_counter()
        for pkg in to_add:
            tried.add(pkg)
            add_out, add_err, add_rc = _run(
                ["dart", "pub", "add", pkg],
                project,
                timeout=120,
            )
            log_parts.append(
                f"=== dart pub add {pkg} stdout ===\n{add_out}\n=== stderr ===\n{add_err}\n"
            )
            if add_rc == 0:
                packages_added.append(pkg)
            _pub_get(project, log_parts)
        resolve_ms_total += int((time.perf_counter() - t_r) * 1000)

    static_flags = scaffold_flags + dart_flags
    error_only = [e for e in error_log if e.severity == "error"]
    compilable = len(error_only) == 0 and final_rc == 0
    error_count = len(error_only)

    _write_raw_log(run_id, "\n".join(log_parts))

    summary = AnalysisSummary(
        compilable=compilable,
        error_count=error_count,
        static_issue_count=len(static_flags),
    )
    pubspec_final = (project / "pubspec.yaml").read_text(encoding="utf-8", errors="replace")
    return {
        "summary": summary,
        "error_log": error_log,
        "static_flags": static_flags,
        "compile_stdout": pub_out,
        "compile_stderr": pub_err,
        "analyzer_stdout": final_out,
        "analyzer_stderr": final_err,
        "_code_sample": dart_src,
        "_pubspec_sample": pubspec_final,
        "_timing": {
            "kotlinc_ms": None,
            "detekt_ms": None,
            "pub_get_ms": pub_get_ms,
            "analyze_ms": analyze_ms_total,
            "resolve_ms": resolve_ms_total,
            "packages_added": packages_added,
            "pub_cmd": pub_cmd,
        },
    }


def _run_analysis_sync(payload: AnalyzeRequest) -> dict:
    run_id = str(uuid.uuid4())
    run_dir = P(TEMP_RUNS) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    if payload.target_language == "Kotlin":
        result = _analyze_kotlin_sync(payload, run_dir, run_id)
    else:
        result = _analyze_dart_sync(payload, run_dir, run_id)

    total_ms = int((time.perf_counter() - t0) * 1000)
    timing = result.pop("_timing")
    code_s = result.pop("_code_sample")
    pubspec_s = result.pop("_pubspec_sample")

    result["metrics"] = build_metrics(
        total_duration_ms=total_ms,
        pub_get_duration_ms=timing["pub_get_ms"],
        analyze_duration_ms=timing["analyze_ms"],
        dependency_resolve_duration_ms=timing["resolve_ms"],
        kotlin_compile_duration_ms=timing["kotlinc_ms"],
        detekt_duration_ms=timing["detekt_ms"],
        code_source=code_s,
        pubspec_yaml=pubspec_s,
        error_log=result["error_log"],
        static_flags=result["static_flags"],
        packages_auto_added=timing["packages_added"],
        pub_get_command_used=timing["pub_cmd"],
    )
    result["run_duration_ms"] = total_ms
    return result


async def run_analysis(payload: AnalyzeRequest) -> dict:
    return await asyncio.to_thread(_run_analysis_sync, payload)
