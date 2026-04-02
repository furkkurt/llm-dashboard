"""Optional OpenRouter pass: task adherence 0-100 + notes on toolchain metrics (JSON-only reply)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from backend.env_bootstrap import load_dashboard_env
from backend.models import AiCommentary, AnalysisMetrics, AnalysisSummary
from backend.openrouter_client import openrouter_chat_completion


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    head = max_len // 2 - 20
    tail = max_len - head - 30
    return s[:head] + "\n\n/* ... truncated ... */\n\n" + s[-tail:]


_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def run_metrics_commentary(
    *,
    user_prompt: str,
    code: str,
    summary: AnalysisSummary,
    metrics: Optional[AnalysisMetrics],
    llm_source: str,
    manual_faithfulness_set: bool,
) -> AiCommentary:
    load_dashboard_env()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return AiCommentary(
            error="OPENROUTER_API_KEY not set; skipping AI commentary.",
            provider="openrouter",
        )

    try:
        timeout = float(os.getenv("COMMENTARY_TIMEOUT_SEC", "60"))
    except ValueError:
        timeout = 60.0

    model_id = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()

    metrics_blob: dict[str, Any] = {}
    if metrics:
        metrics_blob = {
            "total_duration_ms": metrics.total_duration_ms,
            "pub_get_duration_ms": metrics.pub_get_duration_ms,
            "analyze_duration_ms": metrics.analyze_duration_ms,
            "dependency_resolve_duration_ms": metrics.dependency_resolve_duration_ms,
            "kotlin_compile_duration_ms": metrics.kotlin_compile_duration_ms,
            "detekt_duration_ms": metrics.detekt_duration_ms,
            "lines_of_code": metrics.lines_of_code,
            "characters_code": metrics.characters_code,
            "analyzer_errors": metrics.analyzer_errors,
            "analyzer_warnings": metrics.analyzer_warnings,
            "analyzer_infos": metrics.analyzer_infos,
            "packages_auto_added": metrics.packages_auto_added,
            # metrics.md — cross-language code-quality proxies (see metrics.md / metricguide.md)
            "loc": metrics.loc,
            "comment_lines": metrics.comment_lines,
            "lines_of_code_non_comment": metrics.lines_of_code,
            "avg_cyclomatic_complexity": metrics.avg_cyclomatic_complexity,
            "comment_ratio": metrics.comment_ratio,
            "halstead_volume": metrics.halstead_volume,
            "halstead_difficulty": metrics.halstead_difficulty,
            "maintainability_index": metrics.maintainability_index,
            "avg_nesting_depth": metrics.avg_nesting_depth,
        }

    summary_blob = {
        "compilable": summary.compilable,
        "error_count": summary.error_count,
        "static_issue_count": summary.static_issue_count,
    }

    user_block = f"""You grade ONE model submission for a research code-evaluation dashboard.

=== TASK PROMPT (the user’s request — this is the bar you grade against) ===
{_truncate(user_prompt, 4000)}

=== WHICH OUTPUT YOU ARE GRADING ===
The submission below is labeled as: **{llm_source}** (for context only).
Judge only whether the **code** fulfills the **TASK PROMPT** above — not generic code quality in isolation.

=== SUBMITTED CODE ===
{_truncate(code, 12000)}

=== TOOLCHAIN RESULTS (measured by our Kotlin/Flutter pipeline — cite these in metrics_comment) ===
Summary: {json.dumps(summary_blob)}
Metrics: {json.dumps(metrics_blob)}

Manual faithfulness already chosen in the UI: {manual_faithfulness_set!s}
(If true, still output your scores for transparency; the UI may prefer the human rating for ranking.)

---

Respond with **one JSON object only** (no markdown fences, no text outside JSON), keys:

1) "faithfulness_score_0_100" (integer, required): 0–100 how completely and correctly this submission satisfies the **TASK PROMPT**.
   - Use the **full range**. Do **not** default to ~20 or cluster scores unless every submission truly deserves that.
   - 0–20: largely misses or contradicts the task; 21–40: partial attempt with major gaps; 41–60: addresses core ask but incomplete or flawed;
     61–80: solid match with minor gaps; 81–100: fulfills stated requirements well (allow <100 if metrics show serious compile/static issues that block the task).

2) "faithfulness_note" (string): 1–3 sentences referencing **specific** parts of the TASK PROMPT vs what the code actually does.

3) "metrics_comment" (string): 3–7 sentences interpreting **compilable**, **error_count**, **static_issue_count**, analyzer error/warning/info counts, durations, and LOC. Also briefly relate **avg_cyclomatic_complexity**, **comment_ratio**, **halstead_volume** / **halstead_difficulty**, **maintainability_index**, and **avg_nesting_depth** (when present) to readability, maintainability, and cognitive load as in software-engineering research — not as ground truth, but as structured hints. Say when a metric is missing or null."""

    system_msg = (
        "You output only a single valid JSON object. No markdown code fences, no preamble or postfix."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_block},
    ]

    try:
        try:
            mt = int(os.getenv("COMMENTARY_MAX_TOKENS", "4096"))
        except ValueError:
            mt = 4096
        mt = max(256, min(8192, mt))
        text, used_model = openrouter_chat_completion(
            messages=messages,
            model=model_id,
            timeout=timeout,
            max_tokens=mt,
            temperature=0.25,
        )
        m = _JSON_BLOCK.search(text)
        if not m:
            return AiCommentary(
                error="Model returned no parseable JSON.",
                provider=used_model,
            )
        data = json.loads(m.group(0))

        score_100 = data.get("faithfulness_score_0_100")
        score_15 = data.get("faithfulness_score_1_5")
        out_100: Optional[int] = None
        out_15: Optional[int] = None

        if score_100 is not None:
            try:
                v = int(float(score_100))
                out_100 = max(0, min(100, v))
            except (TypeError, ValueError):
                out_100 = None
        if out_100 is None and score_15 is not None:
            try:
                v5 = int(score_15)
                v5 = max(1, min(5, v5))
                out_15 = v5
                out_100 = v5 * 20
            except (TypeError, ValueError):
                out_15 = None

        return AiCommentary(
            faithfulness_score_0_100=out_100,
            faithfulness_score_1_5=out_15,
            faithfulness_note=str(data.get("faithfulness_note") or "")[:2000],
            metrics_comment=str(data.get("metrics_comment") or "")[:6000],
            provider=used_model,
        )
    except Exception as e:
        msg = str(e).strip() or type(e).__name__
        return AiCommentary(error=msg[:500], provider=model_id)
