"""Optional Gemini pass: faithfulness hint + short metrics narrative (JSON-only reply)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from backend.env_bootstrap import load_dashboard_env
from backend.models import AiCommentary, AnalysisMetrics, AnalysisSummary


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
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        return AiCommentary(
            error="GOOGLE_API_KEY not set; skipping AI commentary.",
            provider="gemini",
        )

    try:
        timeout = float(os.getenv("COMMENTARY_TIMEOUT_SEC", "60"))
    except ValueError:
        timeout = 60.0

    model_id = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash").strip()

    metrics_blob: dict[str, Any] = {}
    if metrics:
        metrics_blob = {
            "total_duration_ms": metrics.total_duration_ms,
            "pub_get_duration_ms": metrics.pub_get_duration_ms,
            "analyze_duration_ms": metrics.analyze_duration_ms,
            "dependency_resolve_duration_ms": metrics.dependency_resolve_duration_ms,
            "lines_of_code": metrics.lines_of_code,
            "analyzer_errors": metrics.analyzer_errors,
            "analyzer_warnings": metrics.analyzer_warnings,
            "analyzer_infos": metrics.analyzer_infos,
            "packages_auto_added": metrics.packages_auto_added,
        }

    summary_blob = {
        "compilable": summary.compilable,
        "error_count": summary.error_count,
        "static_issue_count": summary.static_issue_count,
    }

    user_block = f"""You evaluate one LLM code output for a research dashboard.

Claimed model label (for context only): {llm_source}
User task prompt:
{_truncate(user_prompt, 2500)}

Analyzer summary (machine): {json.dumps(summary_blob)}
Timing/size (machine): {json.dumps(metrics_blob)}

Code sample (may be truncated):
{_truncate(code, 8000)}

The human may have already set a manual faithfulness score in the UI. manual_faithfulness_already_set={manual_faithfulness_set!s}

Reply with ONE JSON object only, no markdown fences, keys:
- "faithfulness_score_1_5": integer 1-5 how well the code matches the task prompt, or null if you refuse
- "faithfulness_note": one short sentence explaining the score (or empty if null)
- "metrics_comment": 2-4 sentences interpreting static health, compile status, and efficiency signals for someone choosing between models; plain language

If manual_faithfulness_already_set is true, still output faithfulness_score_1_5 and faithfulness_note as your independent estimate for transparency, but the dashboard may not use your score for ranking."""

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        import google.generativeai as genai

    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        model_id,
        system_instruction=(
            "You output only valid JSON objects. No markdown, no prose outside JSON."
        ),
    )
    try:
        try:
            response = model.generate_content(
                user_block,
                request_options={"timeout": timeout},
            )
        except TypeError:
            response = model.generate_content(user_block)
        text = getattr(response, "text", None) or ""
        if not text and response.candidates:
            cand = response.candidates[0]
            content = getattr(cand, "content", None)
            if content and getattr(content, "parts", None):
                text = "".join(getattr(p, "text", "") for p in content.parts)
        text = (text or "").strip()
        m = _JSON_BLOCK.search(text)
        if not m:
            return AiCommentary(
                error="Model returned no parseable JSON.",
                provider=model_id,
            )
        data = json.loads(m.group(0))
        score = data.get("faithfulness_score_1_5")
        if score is not None:
            try:
                score = int(score)
                if score < 1 or score > 5:
                    score = None
            except (TypeError, ValueError):
                score = None
        return AiCommentary(
            faithfulness_score_1_5=score,
            faithfulness_note=str(data.get("faithfulness_note") or "")[:2000],
            metrics_comment=str(data.get("metrics_comment") or "")[:4000],
            provider=model_id,
        )
    except Exception as e:
        msg = str(e).strip() or type(e).__name__
        return AiCommentary(error=msg[:500], provider=model_id)
