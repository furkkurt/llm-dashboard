from backend.cross_language_metrics import compute_cross_language_metrics


def test_empty_code_returns_nulls() -> None:
    out = compute_cross_language_metrics("")
    assert out["avg_cyclomatic_complexity"] is None


def test_simple_kotlin_has_reasonable_values() -> None:
    code = """
fun main() {
  // greet
  if (true) {
    println("hi")
  }
}
"""
    out = compute_cross_language_metrics(code)
    assert out["loc"] is not None and out["loc"] >= 1
    assert out["comment_lines"] is not None
    assert out["code_lines"] is not None
    assert out["avg_cyclomatic_complexity"] is not None
    assert out["avg_cyclomatic_complexity"] >= 1.0
    assert out["maintainability_index"] is not None
    assert out["comment_ratio"] is not None
