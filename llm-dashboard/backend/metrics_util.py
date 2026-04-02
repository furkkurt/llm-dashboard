"""Build structured AnalysisMetrics from analyzer outputs."""

import re
from collections import Counter
from typing import Optional

from backend.cross_language_metrics import compute_cross_language_metrics
from backend.models import AnalysisMetrics, ErrorItem, StaticFlagItem


def count_lines_of_code(source: str) -> int:
    return sum(1 for line in source.splitlines() if line.strip())


def count_pubspec_dependencies(pubspec_yaml: str) -> int:
    """Count direct keys under dependencies: (e.g. flutter, shared_preferences)."""
    m = re.search(
        r"^dependencies:\s*\n((?:^[ \t]+[^\n]+\n)+)",
        pubspec_yaml,
        re.MULTILINE,
    )
    if not m:
        return 0
    block = m.group(1)
    n = 0
    for line in block.splitlines():
        if re.match(r"^[ \t]{2}\w[\w_]*\s*:", line):
            n += 1
    return n


def severities_from_flags(static_flags: list[StaticFlagItem]) -> tuple[int, int, int]:
    """Analyzer-style warnings/infos (dart + detekt) and scaffold notes."""
    w = i = s = 0
    for f in static_flags:
        if f.tool == "flutter_scaffold":
            s += 1
            continue
        if f.tool == "dart_analyze":
            sev = (f.severity or "").lower()
            if sev == "warning":
                w += 1
            elif sev != "error":
                i += 1
        elif f.tool == "detekt":
            sev = (f.severity or "").lower()
            if sev in ("warning", "error"):
                w += 1
            else:
                i += 1
    return w, i, s


def rule_histogram(static_flags: list[StaticFlagItem], tool: str = "dart_analyze") -> dict[str, int]:
    c: Counter[str] = Counter()
    for f in static_flags:
        if f.tool != tool:
            continue
        c[f.rule or "GENERAL"] += 1
    return dict(c.most_common(40))


def build_metrics(
    *,
    total_duration_ms: int,
    pub_get_duration_ms: Optional[int] = None,
    analyze_duration_ms: Optional[int] = None,
    dependency_resolve_duration_ms: Optional[int] = None,
    kotlin_compile_duration_ms: Optional[int] = None,
    detekt_duration_ms: Optional[int] = None,
    code_source: str,
    pubspec_yaml: Optional[str] = None,
    error_log: list[ErrorItem],
    static_flags: list[StaticFlagItem],
    packages_auto_added: Optional[list[str]] = None,
    pub_get_command_used: Optional[str] = None,
) -> AnalysisMetrics:
    warn, info, scaffold = severities_from_flags(static_flags)
    dep_count = count_pubspec_dependencies(pubspec_yaml) if pubspec_yaml else 0

    cross = compute_cross_language_metrics(code_source)
    cl = cross.get("code_lines")
    lines_non_comment = int(cl) if cl is not None else count_lines_of_code(code_source)

    return AnalysisMetrics(
        total_duration_ms=total_duration_ms,
        pub_get_duration_ms=pub_get_duration_ms,
        analyze_duration_ms=analyze_duration_ms,
        dependency_resolve_duration_ms=dependency_resolve_duration_ms,
        kotlin_compile_duration_ms=kotlin_compile_duration_ms,
        detekt_duration_ms=detekt_duration_ms,
        lines_of_code=lines_non_comment,
        loc=cross.get("loc"),
        comment_lines=cross.get("comment_lines"),
        characters_code=len(code_source),
        dependency_declaration_count=dep_count,
        analyzer_errors=len([e for e in error_log if e.severity == "error"]),
        analyzer_warnings=warn,
        analyzer_infos=info,
        scaffold_notes=scaffold,
        packages_auto_added=packages_auto_added or [],
        pub_get_command_used=pub_get_command_used,
        analyzer_rule_histogram=rule_histogram(static_flags, "dart_analyze"),
        detekt_rule_histogram=rule_histogram(static_flags, "detekt"),
        avg_cyclomatic_complexity=cross.get("avg_cyclomatic_complexity"),
        comment_ratio=cross.get("comment_ratio"),
        halstead_volume=cross.get("halstead_volume"),
        halstead_difficulty=cross.get("halstead_difficulty"),
        maintainability_index=cross.get("maintainability_index"),
        avg_nesting_depth=cross.get("avg_nesting_depth"),
    )
