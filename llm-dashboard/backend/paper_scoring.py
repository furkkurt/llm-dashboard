"""
Scores aligned with the research abstract (ÖZET): compilability, static analysis
(dart analyze / detekt), tooling efficiency, and manual prompt faithfulness.
"""

from __future__ import annotations

import math
from typing import Optional

from backend.models import AnalysisMetrics, AnalysisSummary, ErrorItem, PaperScores, StaticFlagItem

# Özetteki üç ana boyut + verimlilik; toplam 1.0 (manual.md)
DEFAULT_WEIGHTS = {
    "compilability": 0.30,
    "static_analysis": 0.35,
    "efficiency": 0.15,
    "faithfulness": 0.20,
}

# Dashboard winner: MI + nesting + analyzer + faithfulness when rated (faith weight omitted if unrated).
QUALITY_COMPOSITE_WEIGHTS = {
    "mi": 0.30,
    "nesting": 0.10,
    "analyzer_cleanliness": 0.30,
    "faithfulness": 0.30,
}

NEUTRAL_FAITHFULNESS_0_100 = 50.0
NEUTRAL_AXIS_0_100 = NEUTRAL_FAITHFULNESS_0_100


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


def faithfulness_1_5_from_0_100(score_0_100: float) -> int:
    """Coarse 1-5 for SQLite `faithfulness_score` when AI used 0-100."""
    s = max(0.0, min(100.0, float(score_0_100)))
    return max(1, min(5, (int(s) // 20) + 1))


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
    faithfulness_0_100_direct: float | None = None,
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
    if faithfulness_0_100_direct is not None:
        f_val = max(0.0, min(100.0, float(faithfulness_0_100_direct)))
        rated = True
    else:
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


def enrich_paper_scores_from_metrics(
    paper: PaperScores,
    metrics: AnalysisMetrics | None,
) -> PaperScores:
    """Copy metrics.md cross-language fields onto paper_scores for nested JSON / API consumers."""
    if metrics is None:
        return paper
    return paper.model_copy(
        update={
            "loc": metrics.loc,
            "comment_lines": metrics.comment_lines,
            "avg_cyclomatic_complexity": metrics.avg_cyclomatic_complexity,
            "comment_ratio": metrics.comment_ratio,
            "halstead_volume": metrics.halstead_volume,
            "halstead_difficulty": metrics.halstead_difficulty,
            "maintainability_index": metrics.maintainability_index,
            "avg_nesting_depth": metrics.avg_nesting_depth,
        }
    )


def mi_component_0_100(mi: float | None) -> float:
    """Higher MI is better; clamp to [0, 100]. Missing → neutral."""
    if mi is None:
        return NEUTRAL_AXIS_0_100
    return max(0.0, min(100.0, float(mi)))


def nesting_component_0_100(depth: float | None) -> float:
    """Lower average nesting depth is better. Missing → neutral."""
    if depth is None:
        return NEUTRAL_AXIS_0_100
    d = max(0.0, float(depth))
    return max(0.0, min(100.0, 100.0 - 15.0 * d))


def faithfulness_axis_when_present(paper: PaperScores) -> float | None:
    """0–100 faithfulness score only when rated; otherwise None (composite excludes that axis)."""
    if paper.faithfulness_rated and paper.faithfulness_0_100 is not None:
        return max(0.0, min(100.0, float(paper.faithfulness_0_100)))
    return None


def attach_quality_composite(
    paper: PaperScores,
    summary: AnalysisSummary,
    error_log: list[ErrorItem],
    static_flags: list[StaticFlagItem],
    metrics: AnalysisMetrics | None,
) -> PaperScores:
    """
    Single 0–100 research composite: MI, shallow nesting, low analyzer noise, optional faithfulness.
    Faithfulness uses its configured weight only when rated; otherwise MI/nesting/analyzer weights
    are renormalized to sum to 1.0.
    Uses structured analyzer counts from metrics when present (same penalty idea as static health).
    """
    w = QUALITY_COMPOSITE_WEIGHTS
    mi_c = mi_component_0_100(paper.maintainability_index)
    nest_c = nesting_component_0_100(paper.avg_nesting_depth)

    mc: tuple[int | None, int | None, int | None] | None = None
    if metrics is not None:
        mc = (metrics.analyzer_errors, metrics.analyzer_warnings, metrics.analyzer_infos)
    ana_c = static_analysis_health_score(
        summary,
        error_log,
        static_flags,
        analyzer_errors=mc[0] if mc else None,
        analyzer_warnings=mc[1] if mc else None,
        analyzer_infos=mc[2] if mc else None,
    )
    faith_c = faithfulness_axis_when_present(paper)
    core = (
        w["mi"] * mi_c
        + w["nesting"] * nest_c
        + w["analyzer_cleanliness"] * ana_c
    )
    if faith_c is not None:
        tw = w["mi"] + w["nesting"] + w["analyzer_cleanliness"] + w["faithfulness"]
        q = (core + w["faithfulness"] * faith_c) / tw
    else:
        tw = w["mi"] + w["nesting"] + w["analyzer_cleanliness"]
        q = core / tw
    return paper.model_copy(update={"quality_composite_0_100": round(q, 2)})


def recompute_full_paper_scores(
    summary: AnalysisSummary,
    error_log: list[ErrorItem],
    static_flags: list[StaticFlagItem],
    *,
    total_duration_ms: int | None,
    faithfulness_score_1_5: int | None,
    faithfulness_0_100_direct: float | None = None,
    metrics: AnalysisMetrics | None,
) -> PaperScores:
    """Build legacy paper_scores, attach cross-language metrics, then quality composite (analyze + PATCH)."""
    mc: tuple[int | None, int | None, int | None] | None = None
    if metrics is not None:
        mc = (metrics.analyzer_errors, metrics.analyzer_warnings, metrics.analyzer_infos)
    paper = build_paper_scores(
        summary,
        error_log,
        static_flags,
        total_duration_ms=total_duration_ms,
        faithfulness_score_1_5=faithfulness_score_1_5
        if faithfulness_0_100_direct is None
        else None,
        faithfulness_0_100_direct=faithfulness_0_100_direct,
        metrics_counts=mc,
    )
    paper = enrich_paper_scores_from_metrics(paper, metrics)
    return attach_quality_composite(paper, summary, error_log, static_flags, metrics)


def quality_composite_from_history_row(row: dict) -> float | None:
    """
    Cached `quality_composite_0_100` from stored paper_scores, or recompute from row payload
    (works for older rows saved before the field existed).
    """
    metrics_dict = row.get("metrics")
    if not isinstance(metrics_dict, dict):
        metrics_dict = {}
    ps = metrics_dict.get("paper_scores")
    if isinstance(ps, dict):
        q = ps.get("quality_composite_0_100")
        if isinstance(q, (int, float)) and math.isfinite(float(q)):
            return float(q)
    try:
        summary = AnalysisSummary(
            compilable=bool(row["compilable"]),
            error_count=int(row.get("error_count") or 0),
            static_issue_count=int(row.get("static_issue_count") or 0),
        )
        error_log = [ErrorItem.model_validate(x) for x in (row.get("error_log") or [])]
        static_flags = [StaticFlagItem.model_validate(x) for x in (row.get("static_flags") or [])]
        base = {k: v for k, v in metrics_dict.items() if k != "paper_scores"}
        am: AnalysisMetrics | None = None
        if base:
            try:
                am = AnalysisMetrics.model_validate(base)
            except Exception:
                am = None
        f_direct: float | None = None
        f_1_5: int | None = row.get("faithfulness_score")
        if isinstance(ps, dict) and ps.get("faithfulness_rated") and isinstance(
            ps.get("faithfulness_0_100"), (int, float)
        ):
            f_direct = float(ps["faithfulness_0_100"])
            f_1_5 = None
        paper = recompute_full_paper_scores(
            summary,
            error_log,
            static_flags,
            total_duration_ms=row.get("run_duration_ms"),
            faithfulness_score_1_5=f_1_5,
            faithfulness_0_100_direct=f_direct,
            metrics=am,
        )
        qc = paper.quality_composite_0_100
        return float(qc) if isinstance(qc, (int, float)) and math.isfinite(float(qc)) else None
    except Exception:
        return None


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
