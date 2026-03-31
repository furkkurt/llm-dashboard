"""
Scores aligned with the research abstract (ÖZET): compilability, static analysis
(dart analyze / detekt), tooling efficiency, and manual prompt faithfulness.
"""

from __future__ import annotations

from typing import Optional

from backend.models import AnalysisSummary, ErrorItem, PaperScores, StaticFlagItem

# Özetteki üç ana boyut + verimlilik; toplam 1.0 (manual.md)
DEFAULT_WEIGHTS = {
    "compilability": 0.30,
    "static_analysis": 0.35,
    "efficiency": 0.15,
    "faithfulness": 0.20,
}

NEUTRAL_FAITHFULNESS_0_100 = 50.0


def compilability_score(summary: AnalysisSummary) -> float:
    return 100.0 if summary.compilable else 0.0


def static_analysis_health_score(
    summary: AnalysisSummary,
    error_log: list[ErrorItem],
    static_flags: list[StaticFlagItem],
    *,
    analyzer_errors: int | None = None,
    analyzer_warnings: int | None = None,
    analyzer_infos: int | None = None,
) -> float:
    if analyzer_errors is not None:
        err_n = analyzer_errors
    else:
        err_n = len([e for e in error_log if (e.severity or "").lower() == "error"])
    if analyzer_warnings is not None:
        warn_n = analyzer_warnings
    else:
        warn_n = _count_severity(static_flags, ("warning", "error"), exclude_tools={"flutter_scaffold"})
    if analyzer_infos is not None:
        info_n = analyzer_infos
    else:
        info_n = _count_severity(static_flags, ("info", "hint"), exclude_tools={"flutter_scaffold"})

    penalty = 12.0 * err_n + 3.5 * warn_n + 0.8 * info_n
    return max(0.0, min(100.0, 100.0 - penalty))


def _count_severity(
    flags: list[StaticFlagItem],
    severities: tuple[str, ...],
    exclude_tools: set[str],
) -> int:
    n = 0
    for f in flags:
        if f.tool in exclude_tools:
            continue
        if (f.severity or "").lower() in severities:
            n += 1
    return n


def tool_efficiency_score(total_duration_ms: int | None, cap_ms: int = 300_000) -> float:
    if total_duration_ms is None or total_duration_ms < 0:
        return 50.0
    if total_duration_ms == 0:
        return 100.0
    ratio = min(1.0, total_duration_ms / float(cap_ms))
    return max(0.0, 100.0 * (1.0 - ratio))


def faithfulness_score_0_100(score_1_to_5: int | None) -> tuple[Optional[float], bool]:
    if score_1_to_5 is None:
        return None, False
    s = max(1, min(5, score_1_to_5))
    return float(s) * 20.0, True


def composite_score(
    *,
    compilability: float,
    static_analysis: float,
    efficiency: float,
    faithfulness: Optional[float],
    weights: dict[str, float] | None = None,
    neutral_faithfulness: float = NEUTRAL_FAITHFULNESS_0_100,
) -> float:
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    f = faithfulness if faithfulness is not None else neutral_faithfulness
    total_w = w["compilability"] + w["static_analysis"] + w["efficiency"] + w["faithfulness"]
    if total_w <= 0:
        total_w = 1.0
    return (
        w["compilability"] * compilability
        + w["static_analysis"] * static_analysis
        + w["efficiency"] * efficiency
        + w["faithfulness"] * f
    ) / total_w


def build_paper_scores(
    summary: AnalysisSummary,
    error_log: list[ErrorItem],
    static_flags: list[StaticFlagItem],
    *,
    total_duration_ms: int | None,
    faithfulness_score_1_5: int | None,
    metrics_counts: tuple[int | None, int | None, int | None] | None = None,
) -> PaperScores:
    c = compilability_score(summary)
    if metrics_counts:
        s = static_analysis_health_score(
            summary,
            error_log,
            static_flags,
            analyzer_errors=metrics_counts[0],
            analyzer_warnings=metrics_counts[1],
            analyzer_infos=metrics_counts[2],
        )
    else:
        s = static_analysis_health_score(summary, error_log, static_flags)
    e = tool_efficiency_score(total_duration_ms)
    f_val, rated = faithfulness_score_0_100(faithfulness_score_1_5)
    comp = composite_score(
        compilability=c,
        static_analysis=s,
        efficiency=e,
        faithfulness=f_val,
        neutral_faithfulness=NEUTRAL_FAITHFULNESS_0_100,
    )
    return PaperScores(
        compilability_0_100=round(c, 2),
        static_analysis_health_0_100=round(s, 2),
        tool_efficiency_0_100=round(e, 2),
        faithfulness_0_100=round(f_val, 2) if f_val is not None else None,
        faithfulness_rated=rated,
        composite_default_0_100=round(comp, 2),
    )


def composite_with_weights(
    paper: PaperScores,
    weights: dict[str, float],
) -> float:
    """Seçilen ağırlıklarla birleşik skor (Streamlit Kazanan sekmesi)."""
    f = (
        paper.faithfulness_0_100
        if paper.faithfulness_rated and paper.faithfulness_0_100 is not None
        else None
    )
    return composite_score(
        compilability=paper.compilability_0_100,
        static_analysis=paper.static_analysis_health_0_100,
        efficiency=paper.tool_efficiency_0_100,
        faithfulness=f,
        weights=weights,
    )
