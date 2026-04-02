from backend.models import AnalysisMetrics, AnalysisSummary, ErrorItem, StaticFlagItem
from backend.paper_scoring import (
    attach_quality_composite,
    build_paper_scores,
    enrich_paper_scores_from_metrics,
    faithfulness_1_5_from_0_100,
    recompute_full_paper_scores,
)


def test_faithfulness_1_5_from_0_100() -> None:
    assert faithfulness_1_5_from_0_100(0) == 1
    assert faithfulness_1_5_from_0_100(19) == 1
    assert faithfulness_1_5_from_0_100(20) == 2
    assert faithfulness_1_5_from_0_100(100) == 5


def test_build_paper_scores_direct_0_100() -> None:
    summary = AnalysisSummary(compilable=True, error_count=0, static_issue_count=0)
    paper = build_paper_scores(
        summary,
        [],
        [],
        total_duration_ms=1000,
        faithfulness_score_1_5=None,
        faithfulness_0_100_direct=73.0,
        metrics_counts=(0, 0, 0),
    )
    assert paper.faithfulness_rated is True
    assert paper.faithfulness_0_100 == 73.0


def test_recompute_full_paper_scores_sets_quality_composite() -> None:
    summary = AnalysisSummary(compilable=True, error_count=0, static_issue_count=0)
    metrics = AnalysisMetrics(
        analyzer_errors=0,
        analyzer_warnings=0,
        analyzer_infos=0,
        maintainability_index=80.0,
        avg_nesting_depth=1.0,
    )
    paper = recompute_full_paper_scores(
        summary,
        [],
        [],
        total_duration_ms=1000,
        faithfulness_score_1_5=5,
        faithfulness_0_100_direct=None,
        metrics=metrics,
    )
    assert paper.quality_composite_0_100 is not None
    assert 0 <= paper.quality_composite_0_100 <= 100


def test_attach_quality_composite_prefers_high_mi_low_nesting() -> None:
    summary = AnalysisSummary(compilable=True, error_count=0, static_issue_count=0)
    base = build_paper_scores(
        summary,
        [],
        [],
        total_duration_ms=1000,
        faithfulness_score_1_5=3,
        metrics_counts=(0, 0, 0),
    )
    good = AnalysisMetrics(
        maintainability_index=90.0,
        avg_nesting_depth=0.5,
        analyzer_errors=0,
        analyzer_warnings=0,
        analyzer_infos=0,
    )
    bad = AnalysisMetrics(
        maintainability_index=50.0,
        avg_nesting_depth=4.0,
        analyzer_errors=2,
        analyzer_warnings=0,
        analyzer_infos=0,
    )
    p_good = attach_quality_composite(
        enrich_paper_scores_from_metrics(base, good),
        summary,
        [],
        [],
        good,
    )
    p_bad = attach_quality_composite(
        enrich_paper_scores_from_metrics(base, bad),
        summary,
        [],
        [],
        bad,
    )
    assert p_good.quality_composite_0_100 is not None
    assert p_bad.quality_composite_0_100 is not None
    assert p_good.quality_composite_0_100 > p_bad.quality_composite_0_100


def test_quality_composite_renormalizes_when_faithfulness_unrated() -> None:
    """No faithfulness score → only MI / nesting / analyzer weights, renormalized to 1.0."""
    summary = AnalysisSummary(compilable=True, error_count=0, static_issue_count=0)
    metrics = AnalysisMetrics(
        maintainability_index=100.0,
        avg_nesting_depth=0.0,
        analyzer_errors=0,
        analyzer_warnings=0,
        analyzer_infos=0,
    )
    unrated = recompute_full_paper_scores(
        summary,
        [],
        [],
        total_duration_ms=1,
        faithfulness_score_1_5=None,
        faithfulness_0_100_direct=None,
        metrics=metrics,
    )
    assert unrated.quality_composite_0_100 == 100.0
    low_faith = recompute_full_paper_scores(
        summary,
        [],
        [],
        total_duration_ms=1,
        faithfulness_score_1_5=1,
        faithfulness_0_100_direct=None,
        metrics=metrics,
    )
    assert low_faith.quality_composite_0_100 is not None
    assert low_faith.quality_composite_0_100 < unrated.quality_composite_0_100
