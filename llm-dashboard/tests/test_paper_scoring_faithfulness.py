from backend.models import AnalysisSummary, ErrorItem, StaticFlagItem
from backend.paper_scoring import (
    build_paper_scores,
    faithfulness_1_5_from_0_100,
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
