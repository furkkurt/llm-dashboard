import hashlib
import json
import math
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.env_bootstrap import load_dashboard_env

# Same as API: `.env` then `local.env` (override); never written by setup.sh.
load_dashboard_env()

from backend.models import PaperScores
from backend.paper_scoring import QUALITY_COMPOSITE_WEIGHTS, quality_composite_from_history_row

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ANALYZE_URL = f"{API_BASE}/analyze"
RESULTS_URL = f"{API_BASE}/results"
REQUEST_TIMEOUT_SEC = 600

# (display name, Flutter session key, Kotlin session key)
MODEL_CODE_KEYS = [
    ("ChatGPT", "code_flutter_chatgpt", "code_kotlin_chatgpt"),
    ("Claude", "code_flutter_claude", "code_kotlin_claude"),
    ("Gemini", "code_flutter_gemini", "code_kotlin_gemini"),
]

_LEGACY_MODEL_CODE = {
    "ChatGPT": "code_chatgpt",
    "Claude": "code_claude",
    "Gemini": "code_gemini",
}

_CHART_COLOR_FLUTTER = "#3182ce"
_CHART_COLOR_KOTLIN = "#ed8936"

st.set_page_config(page_title="LLM Dashboard", layout="wide")

_theme_type = (st.context.theme.get("type") or "light").lower()
_is_dark = _theme_type == "dark"
_title_color = "#f8fafc" if _is_dark else "#111827"
_subtitle_color = "rgba(248, 250, 252, 0.78)" if _is_dark else "rgba(55, 65, 81, 0.92)"
_title_border = "rgba(250, 250, 250, 0.14)" if _is_dark else "rgba(49, 51, 63, 0.14)"

st.markdown(
    f"""
    <style>
    /* Hide Streamlit header “running” indicator next to Stop (in-page progress is enough). */
    [data-testid="stStatusWidget"] {{
        display: none !important;
    }}
    .llm-dashboard-title-wrap {{
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        margin: 0 0 1.35rem 0;
        padding: 0.15rem 0 0.35rem 0;
        border-bottom: 1px solid {_title_border};
    }}
    .llm-dashboard-accent {{
        width: 5px;
        min-height: 3.25rem;
        border-radius: 4px;
        background: linear-gradient(180deg, #4361ee 0%, #7b68ee 55%, #a78bfa 100%);
        flex-shrink: 0;
        margin-top: 0.2rem;
    }}
    .llm-dashboard-title {{
        font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
        font-size: clamp(2.15rem, 4.2vw, 2.85rem);
        font-weight: 800;
        letter-spacing: -0.045em;
        line-height: 1.08;
        margin: 0;
        color: {_title_color};
    }}
    .llm-dashboard-subtitle {{
        font-size: 0.95rem;
        font-weight: 500;
        color: {_subtitle_color};
        margin: 0.35rem 0 0 0;
        letter-spacing: 0.01em;
    }}
    .kpi-card {{
        background: var(--st-secondary-background-color, #f0f2f6);
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 0.9rem;
        text-align: center;
    }}
    .section-card {{
        background: var(--st-secondary-background-color, #f0f2f6);
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

if "prompt_area" not in st.session_state:
    st.session_state.prompt_area = ""
for _label, fk, kk in MODEL_CODE_KEYS:
    if fk not in st.session_state:
        st.session_state[fk] = ""
    if kk not in st.session_state:
        st.session_state[kk] = ""
if not st.session_state.get("_legacy_code_keys_migrated"):
    for label, fk, kk in MODEL_CODE_KEYS:
        old = _LEGACY_MODEL_CODE[label]
        if old in st.session_state:
            legacy_val = str(st.session_state.get(old, "") or "")
            if legacy_val.strip():
                if not str(st.session_state.get(kk, "")).strip():
                    st.session_state[kk] = legacy_val
                if not str(st.session_state.get(fk, "")).strip():
                    st.session_state[fk] = legacy_val
    st.session_state["_legacy_code_keys_migrated"] = True
if "model_results" not in st.session_state:
    st.session_state.model_results = {}
if "history_rows" not in st.session_state:
    st.session_state.history_rows = []
if "ai_commentary_summary" not in st.session_state:
    st.session_state.ai_commentary_summary = ""
if "target_language_sel" not in st.session_state:
    st.session_state.target_language_sel = "Kotlin"
for legacy in ("analysis_result", "code_area"):
    st.session_state.pop(legacy, None)


def _json_detail(response: requests.Response) -> str:
    ct = response.headers.get("content-type", "")
    if ct.startswith("application/json"):
        body = response.json()
        if isinstance(body, dict) and "detail" in body:
            d = body["detail"]
            return str(d) if not isinstance(d, list) else "; ".join(str(x) for x in d)
    return response.text or response.reason


def _fmt_ms(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{int(v):,} ms"
    except (TypeError, ValueError):
        return "—"


def _cell_str(v) -> str:
    """Streamlit/Arrow rejects object columns that mix int and str; normalize for dataframes."""
    if v is None:
        return "—"
    if isinstance(v, float) and not math.isfinite(v):
        return "—"
    return str(v)


def _arrow_safe_dataframe(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([{k: _cell_str(v) for k, v in row.items()} for row in records])


def _float_metric(v: object) -> float | None:
    """Finite float or None (for MI / winner logic)."""
    if v is None:
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _active_languages_from_setting(sel: str) -> list[str]:
    if sel == "Both":
        return ["Flutter", "Kotlin"]
    return [sel]


def _snippet_codes_flat_from_session() -> dict[str, str]:
    out: dict[str, str] = {}
    for _label, fk, kk in MODEL_CODE_KEYS:
        out[fk] = str(st.session_state.get(fk, ""))
        out[kk] = str(st.session_state.get(kk, ""))
    return out


def _compare_lang_chart(
    df: pd.DataFrame,
    *,
    y_col: str,
    y_title: str,
    heading: str,
) -> None:
    if df.empty or y_col not in df.columns:
        return
    st.markdown(f"#### {heading}")
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=2)
        .encode(
            x=alt.X("model:N", title="Model", sort=None),
            y=alt.Y(f"{y_col}:Q", title=y_title),
            color=alt.Color(
                "language:N",
                title="Language",
                scale=alt.Scale(
                    domain=["Flutter", "Kotlin"],
                    range=[_CHART_COLOR_FLUTTER, _CHART_COLOR_KOTLIN],
                ),
            ),
            xOffset=alt.XOffset("language:N", sort=["Flutter", "Kotlin"]),
            tooltip=["model", "language", alt.Tooltip(f"{y_col}:Q", title=y_title)],
        )
    )
    st.altair_chart(chart, use_container_width=True)


def _fmt_ratio_as_percent(ratio: object) -> str:
    if ratio is None:
        return "—"
    try:
        x = float(ratio)
        if not math.isfinite(x):
            return "—"
        return f"{x * 100:.2f}%"
    except (TypeError, ValueError):
        return "—"


def render_cross_language_metrics_table(metrics: dict | None) -> None:
    """
    Present metrics.md § Selected Metrics in order: cyclomatic complexity, LOC & comments,
    Halstead, MI, nesting depth. Values come from the API `metrics` object.
    """
    if not metrics:
        st.info("No metrics payload for this run.")
        return

    loc = metrics.get("loc")
    cl = metrics.get("comment_lines")
    cr = metrics.get("comment_ratio")

    rows: list[dict[str, str]] = [
        {
            "#": "1",
            "Metric": "Average cyclomatic complexity",
            "Value": _cell_str(metrics.get("avg_cyclomatic_complexity")),
            "Definition (metrics.md)": (
                "Linearly independent paths through the code (file-level proxy: decisions ÷ "
                "estimated function count). Lower → simpler, more testable."
            ),
        },
        {
            "#": "2a",
            "Metric": "LOC (total physical lines)",
            "Value": _cell_str(loc),
            "Definition (metrics.md)": "Raw line count of the submitted snippet (total lines).",
        },
        {
            "#": "2b",
            "Metric": "Comment lines",
            "Value": _cell_str(cl),
            "Definition (metrics.md)": "Lines that are comments only (documentation effort).",
        },
        {
            "#": "2c",
            "Metric": "Comment ratio",
            "Value": (
                f"{_fmt_ratio_as_percent(cr)}  (comment_lines ÷ LOC)"
                if cr is not None
                else "—"
            ),
            "Definition (metrics.md)": "Comment lines divided by total lines; maintainability signal.",
        },
        {
            "#": "2d",
            "Metric": "Code lines (non-comment, non-empty)",
            "Value": _cell_str(metrics.get("lines_of_code")),
            "Definition (metrics.md)": "Lines containing code (excluding blank and comment-only lines).",
        },
        {
            "#": "3a",
            "Metric": "Halstead volume",
            "Value": _cell_str(metrics.get("halstead_volume")),
            "Definition (metrics.md)": "Size from operator/operand vocabulary (token heuristic).",
        },
        {
            "#": "3b",
            "Metric": "Halstead difficulty",
            "Value": _cell_str(metrics.get("halstead_difficulty")),
            "Definition (metrics.md)": "Mental effort proxy from Halstead counts.",
        },
        {
            "#": "4",
            "Metric": "Maintainability index (MI)",
            "Value": _cell_str(metrics.get("maintainability_index")),
            "Definition (metrics.md)": (
                "MI = 171 − 5.2·ln(Volume) − 0.23·CC − 16.2·ln(LOC) + 50·sin(√(2.4·perCM)); "
                "perCM = % comment lines. Higher → better maintainability (typical industry formula)."
            ),
        },
        {
            "#": "5",
            "Metric": "Average nesting depth",
            "Value": _cell_str(metrics.get("avg_nesting_depth")),
            "Definition (metrics.md)": (
                "Nesting proxy: max brace depth ÷ estimated function count. Lower → flatter structure."
            ),
        },
    ]
    st.dataframe(_arrow_safe_dataframe(rows), width="stretch", hide_index=True)


def render_toolchain_metrics_table(metrics: dict | None) -> None:
    """Analyzer counts, pubspec, total wall time only — per-step ms omitted (Kotlin vs Dart differ)."""
    if not metrics:
        return
    rows = {
        "Total wall time": _fmt_ms(metrics.get("total_duration_ms")),
        "Characters (snippet)": metrics.get("characters_code"),
        "Pubspec dependency keys": metrics.get("dependency_declaration_count"),
        "Analyzer errors": metrics.get("analyzer_errors"),
        "Analyzer warnings": metrics.get("analyzer_warnings"),
        "Analyzer infos": metrics.get("analyzer_infos"),
        "Scaffold / setup notes": metrics.get("scaffold_notes"),
        "Packages auto-installed": ", ".join(metrics.get("packages_auto_added") or []) or "—",
        "Pub get command": metrics.get("pub_get_command_used") or "—",
    }
    st.dataframe(
        pd.DataFrame(
            {"Metric": list(rows.keys()), "Value": [_cell_str(v) for v in rows.values()]}
        ),
        width="stretch",
        hide_index=True,
    )


def _paper_from_metrics(metrics: dict | None) -> PaperScores | None:
    if not metrics or not isinstance(metrics.get("paper_scores"), dict):
        return None
    try:
        return PaperScores.model_validate(metrics["paper_scores"])
    except Exception:
        return None


def _format_compare_ai_commentary(results: dict) -> str:
    """Aggregate AI commentary from a Compare `model_results` dict for the sidebar textbox."""
    chunks: list[str] = []
    for model_name, entry in results.items():
        if entry.get("status") != "success":
            continue
        data = entry.get("data") or {}
        ac = data.get("ai_commentary")
        if not isinstance(ac, dict):
            continue
        sub: list[str] = [f"━━ {model_name} ━━"]
        if ac.get("error"):
            sub.append(f"[Error] {ac['error']}")
        s100 = ac.get("faithfulness_score_0_100")
        s15 = ac.get("faithfulness_score_1_5")
        if s100 is not None:
            sub.append(f"Task adherence vs your prompt: {s100} / 100")
        elif s15 is not None:
            sub.append(f"Task adherence (legacy scale): {s15} / 5")
        fn = str(ac.get("faithfulness_note") or "").strip()
        if fn:
            sub.append("")
            sub.append("Prompt alignment:")
            sub.append(fn)
        mc = str(ac.get("metrics_comment") or "").strip()
        if mc:
            sub.append("")
            sub.append("Stats / toolchain:")
            sub.append(mc)
        if len(sub) > 1:
            chunks.append("\n".join(sub))
    if not chunks:
        return ""
    return "\n\n".join(chunks)


def render_paper_scores(paper: PaperScores | None) -> None:
    if not paper:
        st.caption("No paper-aligned scores stored for this run.")
        return
    qc = paper.quality_composite_0_100
    st.markdown("**Research composite (0–100, Compare winner)**")
    st.metric(
        "Composite",
        "—" if qc is None else qc,
        help="MI + nesting + analyzer cleanliness; faithfulness weighted only when rated (see comparison caption).",
    )
    st.markdown("**Faithfulness (0–100)**")
    fv = paper.faithfulness_0_100
    st.metric(
        "Faithfulness",
        "—" if fv is None else fv,
        help="From manual rating or OpenRouter AI commentary when Compare enables it.",
    )
    if not paper.faithfulness_rated:
        st.caption("Unrated: composite **excludes** the faithfulness weight; MI / nesting / analyzer are renormalized.")


def render_rule_histogram(title: str, hist: dict) -> None:
    if not hist:
        return
    st.markdown(f"**{title}**")
    df = pd.DataFrame(
        [{"rule": k, "count": _cell_str(v)} for k, v in sorted(hist.items(), key=lambda x: -x[1])[:25]]
    )
    st.dataframe(df, width="stretch", hide_index=True)


def render_one_model_panel(model_name: str, result: dict) -> None:
    summary = result["summary"]
    metrics = result.get("metrics")

    st.markdown("#### Summary metrics")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Compilable", "Yes" if summary["compilable"] else "No")
        st.markdown("</div>", unsafe_allow_html=True)
    with k2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Errors", summary["error_count"])
        st.markdown("</div>", unsafe_allow_html=True)
    with k3:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Static flags (all)", summary["static_issue_count"])
        st.markdown("</div>", unsafe_allow_html=True)
    with k4:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Total time", _fmt_ms(metrics.get("total_duration_ms") if metrics else None))
        st.markdown("</div>", unsafe_allow_html=True)

    render_paper_scores(_paper_from_metrics(metrics))

    if metrics:
        with st.container(border=True):
            st.markdown("##### Cross-language code metrics (metrics.md)")
            st.caption(
                "Five core measures from **metrics.md** / **metricguide.md**, computed from the "
                "submitted source (cross-language heuristic; comparable Kotlin ↔ Dart)."
            )
            render_cross_language_metrics_table(metrics)
        with st.expander("Toolchain runs, analyzer counts, and extras", expanded=False):
            render_toolchain_metrics_table(metrics)
        ah = metrics.get("analyzer_rule_histogram") or {}
        dh = metrics.get("detekt_rule_histogram") or {}
        if ah or dh:
            c1, c2 = st.columns(2)
            with c1:
                render_rule_histogram("Dart analyzer rules (top)", ah)
            with c2:
                render_rule_histogram("Detekt rules (top)", dh)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("#### Detailed error log")
    if result["error_log"]:
        for item in result["error_log"]:
            st.code(
                f"[{item['tool']}] {item['severity'].upper()} | "
                f"{item.get('file') or '-'}:{item.get('line') or '-'}:{item.get('column') or '-'}\n"
                f"{item['message']}",
                language="text",
            )
    else:
        st.success("No compile/runtime parseable errors found.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("#### Static analysis flags (all)")
    if result["static_flags"]:
        for flag in result["static_flags"]:
            st.code(
                f"[{flag['tool']}] {flag['severity'].upper()} | "
                f"{flag.get('rule') or 'General'}\n{flag['message']}",
                language="text",
            )
    else:
        st.success("No static analysis issues found.")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_compare_winner_banner(results: dict) -> None:
    """Winner = highest research composite (MI + nesting + analyzer + faithfulness) among successful runs."""
    if not results:
        return
    scored: list[tuple[str, float]] = []
    any_success = False
    for model_name, entry in results.items():
        if entry.get("status") != "success":
            continue
        any_success = True
        data = entry["data"]
        m = data.get("metrics") or {}
        ps = data.get("paper_scores") or m.get("paper_scores") or {}
        q = _float_metric(ps.get("quality_composite_0_100"))
        if q is not None:
            scored.append((model_name, q))
    if not any_success:
        st.warning("No winner: all model runs failed.")
        return
    if not scored:
        st.info(
            "No winner: **quality_composite_0_100** missing for all successful runs "
            "(re-run Compare with an up-to-date API)."
        )
        return
    best = max(s for _, s in scored)
    top_names = [n for n, s in scored if s == best]
    if len(top_names) == 1:
        st.markdown(f"## Winner: **{top_names[0]}**")
        st.success(
            f"Research composite **{best:.2f}** / 100 (higher is better; ingredients in caption under the table)."
        )
    else:
        st.markdown(f"## Tie: **{', '.join(top_names)}**")
        st.success(f"Same research composite **{best:.2f}** / 100 for all tied models.")


def _snippet_json_for_download() -> str:
    base = {
        "version": 2,
        "snippet_id": str(st.session_state.get("snippet_id_input", "")).strip(),
        "target_language": str(st.session_state.get("target_language_sel", "Kotlin")),
        "prompt": str(st.session_state.get("prompt_area", "")),
    }
    base.update(_snippet_codes_flat_from_session())
    return json.dumps(base, ensure_ascii=False, indent=2)


def _snippet_download_filename() -> str:
    """Save as `<snippet_id>.json`; safe for common filesystems."""
    sid = str(st.session_state.get("snippet_id_input", "")).strip()
    if not sid:
        return "llm-eval-snippet.json"
    safe = re.sub(r"[^\w\-.]+", "_", sid, flags=re.ASCII).strip("._")
    if not safe:
        safe = "snippet"
    safe = safe[:180]
    return f"{safe}.json"


def _compare_analysis_export_filename() -> str:
    sid = str(st.session_state.get("snippet_id_input", "")).strip()
    if not sid:
        return "llm-eval-compare-analysis.json"
    safe = re.sub(r"[^\w\-.]+", "_", sid, flags=re.ASCII).strip("._")
    if not safe:
        safe = "analysis"
    safe = safe[:160]
    return f"compare-analysis-{safe}.json"


def _compare_analysis_export_json(results: dict) -> str:
    """
    Serialize the current Compare run: per-model API payloads (metrics, paper_scores,
    ai_commentary when present), aggregate AI panel text, prompt, and submitted code.
    """
    flutter_row = {label: str(st.session_state.get(fk, "")) for label, fk, _kk in MODEL_CODE_KEYS}
    kotlin_row = {label: str(st.session_state.get(kk, "")) for label, _fk, kk in MODEL_CODE_KEYS}
    models_out: dict = {}
    for run_key, entry in results.items():
        row: dict = {
            "status": entry.get("status"),
            "llm_source": entry.get("llm_source"),
            "target_language": entry.get("target_language"),
        }
        if entry.get("status") == "success":
            row["data"] = entry.get("data")
        else:
            row["detail"] = entry.get("detail")
        models_out[run_key] = row
    payload = {
        "export_version": 2,
        "kind": "llm-dashboard_compare_analysis",
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "api_base": API_BASE,
        "compare": {
            "snippet_id": str(st.session_state.get("snippet_id_input", "")).strip(),
            "target_language": str(st.session_state.get("target_language_sel", "Kotlin")),
            "auto_commentary_enabled": bool(st.session_state.get("auto_commentary")),
            "ai_commentary_panel_summary": (
                str(st.session_state.get("ai_commentary_summary", "")).strip() or None
            ),
        },
        "inputs": {
            "prompt": str(st.session_state.get("prompt_area", "")),
            "code_flutter_by_model": flutter_row,
            "code_kotlin_by_model": kotlin_row,
        },
        "models": models_out,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_snippet_upload(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    lang = data.get("target_language")
    if lang is not None and lang not in ("Kotlin", "Flutter", "Both"):
        raise ValueError("target_language must be Kotlin, Flutter, or Both if set")
    out: dict = {"prompt": str(data.get("prompt", ""))}
    for label, fk, kk in MODEL_CODE_KEYS:
        out[fk] = str(data.get(fk, ""))
        out[kk] = str(data.get(kk, ""))
    ver = int(data.get("version", 1))
    if ver < 2:
        cg = str(data.get("code_chatgpt", data.get("code_gpt", "")))
        cc = str(data.get("code_claude", ""))
        cgm = str(data.get("code_gemini", ""))
        legacy_map = {"ChatGPT": cg, "Claude": cc, "Gemini": cgm}
        eff_lang = lang if lang in ("Kotlin", "Flutter", "Both") else "Kotlin"
        for label, fk, kk in MODEL_CODE_KEYS:
            text = legacy_map.get(label, "")
            if eff_lang == "Flutter":
                if not str(out.get(fk, "")).strip():
                    out[fk] = text
            elif eff_lang == "Kotlin":
                if not str(out.get(kk, "")).strip():
                    out[kk] = text
            else:
                if not str(out.get(kk, "")).strip():
                    out[kk] = text
    if "snippet_id" in data and data["snippet_id"] is not None:
        out["snippet_id"] = str(data["snippet_id"])
    if lang in ("Kotlin", "Flutter", "Both"):
        out["target_language"] = lang
    return out


st.markdown(
    """
<div class="llm-dashboard-title-wrap">
  <div class="llm-dashboard-accent" aria-hidden="true"></div>
  <div>
    <p class="llm-dashboard-title">LLM Dashboard</p>
    <p class="llm-dashboard-subtitle">Compare Kotlin & Flutter outputs from ChatGPT, Claude & Gemini</p>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tab_compare, tab_history = st.tabs(["Compare models", "History & winner"])

with tab_compare:
    if "_pending_snippet_id" in st.session_state:
        st.session_state["snippet_id_input"] = st.session_state.pop("_pending_snippet_id")
    if "_pending_compare_snippet" in st.session_state:
        d = st.session_state.pop("_pending_compare_snippet")
        if isinstance(d, dict):
            st.session_state["prompt_area"] = str(d.get("prompt", ""))
            for _label, fk, kk in MODEL_CODE_KEYS:
                st.session_state[fk] = str(d.get(fk, ""))
                st.session_state[kk] = str(d.get(kk, ""))
            if "snippet_id" in d:
                st.session_state["snippet_id_input"] = str(d["snippet_id"])
            if d.get("target_language") in ("Kotlin", "Flutter", "Both"):
                st.session_state["target_language_sel"] = d["target_language"]
    # Apply AI text *before* the text_area widget mounts (same-run writes after widget are forbidden).
    if "_pending_ai_commentary" in st.session_state:
        st.session_state["ai_commentary_summary"] = st.session_state.pop("_pending_ai_commentary")

    left_col, middle_col, right_col = st.columns([1, 2, 2], gap="large")

    with left_col:
        st.subheader("Settings")
        target_language = st.selectbox(
            "Target Language",
            ["Kotlin", "Flutter", "Both"],
            key="target_language_sel",
            help="**Both**: analyze Flutter and Kotlin rows per model (when pasted). Single stack: only that row.",
        )
        snippet_id = st.text_input(
            "Snippet ID",
            placeholder="e.g. notepad_compare_01 (shared across models for this run)",
            key="snippet_id_input",
        )
        st.markdown("**Snippet bundle**")
        st.caption(
            "Download or upload a JSON file to save or restore the prompt, six code boxes (Flutter + Kotlin rows), "
            "snippet id, and language."
        )
        st.download_button(
            label="Download snippet (.json)",
            data=_snippet_json_for_download(),
            file_name=_snippet_download_filename(),
            mime="application/json",
            width="stretch",
            help="Saves prompt, Flutter + Kotlin code rows, snippet id, and target language. "
            "Filename uses Snippet ID when set, else llm-eval-snippet.json.",
        )
        up_left = st.file_uploader(
            "Browse / upload snippet (.json)",
            type=["json"],
            key="snippet_json_upload",
            help="Restores prompt, six code areas, and optional snippet id / language.",
        )
        if up_left is not None:
            digest = hashlib.sha256(up_left.getvalue()).hexdigest()
            if digest != st.session_state.get("_snippet_json_digest"):
                try:
                    parsed = _parse_snippet_upload(json.loads(up_left.getvalue().decode("utf-8")))
                    st.session_state["_snippet_json_digest"] = digest
                    st.session_state["_pending_compare_snippet"] = parsed
                    st.rerun()
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
                    st.error(f"Could not load snippet file: {e}")
        st.divider()
        use_ai_faith = st.checkbox(
            "Use AI for task faithfulness & commentary (OpenRouter)",
            value=False,
            key="auto_commentary",
            help="Scores each model’s code vs your prompt (0–100) and comments on compile/analyzer stats. Requires OPENROUTER_API_KEY.",
        )
        st.text_area(
            "AI output (fills after Compare when option above is on)",
            height=260,
            key="ai_commentary_summary",
            disabled=True,
            help="Shows task scores and text from the last Compare run.",
        )
        if not use_ai_faith:
            st.caption("Turn on the checkbox and run **COMPARE MODELS** to populate this box.")
        st.caption(
            "Keys: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` in **local.env** or `.env`. API: " + API_BASE
        )

    run_clicked = False
    with middle_col:
        with st.container(border=True):
            st.subheader("Prompt and model outputs")
            st.caption(
                "Paste the shared prompt, then **Flutter** (Dart) and **Kotlin** rows. "
                "Only the row(s) matching **Target Language** in Settings are analyzed."
            )
            st.text_area(
                "Prompt (shared)",
                height=160,
                placeholder="Paste the exact prompt you used with each model...",
                key="prompt_area",
            )
            active_langs = _active_languages_from_setting(str(st.session_state.get("target_language_sel", "Kotlin")))
            if "Flutter" in active_langs:
                st.markdown("**Flutter (Dart)** — per model")
                fcols = st.columns(3)
                for i, (model_name, fk, _kk) in enumerate(MODEL_CODE_KEYS):
                    with fcols[i]:
                        st.text_area(
                            f"{model_name}",
                            height=130,
                            placeholder=f"Dart / Flutter output from {model_name}…",
                            key=fk,
                        )
            if "Kotlin" in active_langs:
                st.markdown("**Kotlin** — per model")
                kcols = st.columns(3)
                for i, (model_name, _fk, kk) in enumerate(MODEL_CODE_KEYS):
                    with kcols[i]:
                        st.text_area(
                            f"{model_name}",
                            height=130,
                            placeholder=f"Kotlin output from {model_name}…",
                            key=kk,
                        )

            run_clicked = st.button("COMPARE MODELS", type="primary", width="stretch")

    with right_col:
        loading_slot = st.empty()
        if run_clicked:
            prompt_text = str(st.session_state.prompt_area).strip()
            sid = snippet_id.strip()
            if not sid:
                st.error("Snippet ID is required.")
            elif not prompt_text:
                st.error("Prompt is required.")
            else:
                active = _active_languages_from_setting(str(target_language))
                to_run: list[tuple[str, str, str, str]] = []
                for model_name, fkey, kkey in MODEL_CODE_KEYS:
                    for lang in active:
                        ck = fkey if lang == "Flutter" else kkey
                        code = str(st.session_state.get(ck, "")).strip()
                        if code:
                            disp = f"{model_name} ({lang})"
                            to_run.append((disp, model_name, lang, code))
                if not to_run:
                    st.error(
                        "Paste code in at least one box for the active language row(s) "
                        "(ChatGPT / Claude / Gemini)."
                    )
                else:
                    new_results: dict[str, dict] = {}
                    n = len(to_run)
                    with loading_slot:
                        prog = st.progress(0.0, text="Starting…")
                        for i, (disp, llm_src, lang, code) in enumerate(to_run):
                            prog.progress(
                                i / max(n, 1),
                                text=f"Analyzing {disp} ({i + 1}/{n})…",
                            )
                            payload = {
                                "llm_source": llm_src,
                                "target_language": lang,
                                "snippet_id": sid,
                                "prompt": prompt_text,
                                "code": code,
                            }
                            if st.session_state.get("auto_commentary"):
                                payload["auto_commentary"] = True
                            err_entry = {
                                "status": "error",
                                "llm_source": llm_src,
                                "target_language": lang,
                            }
                            try:
                                response = requests.post(
                                    ANALYZE_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC
                                )
                                if response.status_code != 200:
                                    new_results[disp] = {
                                        **err_entry,
                                        "detail": _json_detail(response),
                                    }
                                else:
                                    new_results[disp] = {
                                        "status": "success",
                                        "data": response.json(),
                                        "llm_source": llm_src,
                                        "target_language": lang,
                                    }
                            except requests.RequestException as e:
                                new_results[disp] = {**err_entry, "detail": str(e)}
                        prog.progress(1.0, text="Done.")
                    st.session_state.model_results = new_results
                    if st.session_state.get("auto_commentary"):
                        txt = _format_compare_ai_commentary(new_results)
                        st.session_state["_pending_ai_commentary"] = (
                            txt
                            if txt.strip()
                            else "AI commentary was enabled but no text was returned. Check API keys and /health/commentary."
                        )
                    else:
                        st.session_state["_pending_ai_commentary"] = ""
                    st.rerun()

        results = st.session_state.model_results
        if results:
            _render_compare_winner_banner(results)

        st.subheader("Live Analysis Results")
        if not results:
            st.info(
                "Waiting for input... Run **COMPARE MODELS** after pasting a prompt and at least one code output."
            )
        else:
            st.markdown("### Cross-model comparison")
            st.download_button(
                label="Download analysis export (.json)",
                data=_compare_analysis_export_json(results),
                file_name=_compare_analysis_export_filename(),
                mime="application/json",
                width="stretch",
                help="Exports this compare run: metrics (incl. MI), paper_scores payload, per-model AI commentary "
                "if any, error/static flags, optional logs, plus prompt and pasted code. Filename uses Snippet ID when set.",
            )
            cmp_rows = []
            chart_rows: list[dict] = []
            wq = QUALITY_COMPOSITE_WEIGHTS
            w_caption = (
                f"MI {wq['mi']:.0%}, nesting {wq['nesting']:.0%}, "
                f"analyzer {wq['analyzer_cleanliness']:.0%}; faithfulness {wq['faithfulness']:.0%} **when rated**, "
                f"else the first three renormalize to 100%"
            )
            for run_key, entry in results.items():
                if entry.get("status") != "success":
                    cmp_rows.append(
                        {
                            "Model": run_key,
                            "Compilable": "—",
                            "Composite": "—",
                            "Faith. score": "—",
                            "Errors": "—",
                            "Warnings": "—",
                            "Infos": "—",
                            "Total ms": "—",
                            "LOC (phys)": "—",
                            "Comment %": "—",
                            "Avg CC": "—",
                            "MI": "—",
                            "Deps": "—",
                            "Auto packages": "—",
                            "API error": (entry.get("detail") or "")[:120],
                        }
                    )
                    continue
                data = entry["data"]
                s = data["summary"]
                m = data.get("metrics") or {}
                ps = data.get("paper_scores") or m.get("paper_scores") or {}
                cr = m.get("comment_ratio")
                llm = entry.get("llm_source") or run_key
                lang = entry.get("target_language") or ""
                cmp_rows.append(
                    {
                        "Model": run_key,
                        "Compilable": "Yes" if s["compilable"] else "No",
                        "Composite": ps.get("quality_composite_0_100", "—"),
                        "Faith. score": ps.get("faithfulness_0_100", "—"),
                        "Errors": s["error_count"],
                        "Warnings": m.get("analyzer_warnings", "—"),
                        "Infos": m.get("analyzer_infos", "—"),
                        "Total ms": m.get("total_duration_ms", "—"),
                        "LOC (phys)": m.get("loc", m.get("lines_of_code", "—")),
                        "Comment %": _fmt_ratio_as_percent(cr) if cr is not None else "—",
                        "Avg CC": m.get("avg_cyclomatic_complexity", "—"),
                        "MI": m.get("maintainability_index", "—"),
                        "Deps": m.get("dependency_declaration_count", "—"),
                        "Auto packages": len(m.get("packages_auto_added") or []),
                        "API error": "",
                    }
                )
                cq = _float_metric(ps.get("quality_composite_0_100"))
                chart_rows.append(
                    {
                        "model": llm,
                        "language": lang,
                        "composite": cq,
                        "total_ms": int(m.get("total_duration_ms") or 0),
                        "errors": int(s.get("error_count") or 0),
                    }
                )

            st.caption(
                f"**Winner** = highest **Composite** (0–100): high **MI** (metrics.md), **low nesting depth**, "
                f"**low analyzer errors/warnings/infos** (static-health-style penalties in manual.md), and "
                f"**high faithfulness** when a score exists (manual or AI). Weights: {w_caption}. "
                f"**Total ms** = full pipeline wall time (Kotlin vs Dart steps differ)."
            )
            st.dataframe(_arrow_safe_dataframe(cmp_rows), width="stretch", hide_index=True)

            df_ch = pd.DataFrame(chart_rows)
            if str(st.session_state.get("target_language_sel")) == "Both" and not df_ch.empty:
                st.caption(
                    f"**Both** mode charts: **Flutter** = blue, **Kotlin** = orange "
                    f"(`{_CHART_COLOR_FLUTTER}` / `{_CHART_COLOR_KOTLIN}`)."
                )
            if not df_ch.empty:
                sub = df_ch[df_ch["composite"].notna()].copy()
                if not sub.empty:
                    _compare_lang_chart(
                        sub,
                        y_col="composite",
                        y_title="Composite (0–100)",
                        heading="Research composite by model (winner axis)",
                    )
                _compare_lang_chart(
                    df_ch,
                    y_col="total_ms",
                    y_title="ms",
                    heading="Total analysis time by model (ms)",
                )
                _compare_lang_chart(
                    df_ch,
                    y_col="errors",
                    y_title="Errors",
                    heading="Analyzer error count by model",
                )

            st.divider()

            for run_key, entry in results.items():
                with st.expander(f"{run_key} — full report", expanded=False):
                    if entry.get("status") != "success":
                        st.error(entry.get("detail", "Unknown error"))
                    else:
                        render_one_model_panel(run_key, entry["data"])

with tab_history:
    st.markdown(
        "Metric definitions: **`manual.md`** and **`metrics.md`** in the `llm-dashboard` folder. "
        "Load past runs; winner per snippet is **highest research composite** (see Compare tab caption)."
    )
    f1, f2, f3 = st.columns(3)
    with f1:
        h_snip = st.text_input("Filter snippet_id", key="hist_snip")
    with f2:
        h_llm = st.selectbox("LLM", ["(any)", "ChatGPT", "Claude", "Gemini"], key="hist_llm")
    with f3:
        h_limit = st.number_input("Max rows", min_value=20, max_value=500, value=200, step=10)

    if st.button("Load history", key="load_hist"):
        params: dict = {"limit": int(h_limit)}
        if h_snip.strip():
            params["snippet_id"] = h_snip.strip()
        if h_llm != "(any)":
            params["llm_source"] = h_llm
        try:
            hr = requests.get(RESULTS_URL, params=params, timeout=120)
            if hr.status_code != 200:
                st.error(_json_detail(hr))
            else:
                st.session_state.history_rows = hr.json()
                st.success(f"Loaded {len(st.session_state.history_rows)} row(s).")
        except requests.RequestException as e:
            st.error(str(e))

    rows = st.session_state.history_rows
    if rows:
        display_rows = []
        for row in rows:
            m = row.get("metrics") or {}
            display_rows.append(
                {
                    "id": row["id"],
                    "created_at": str(row["created_at"])[:19],
                    "llm": row["llm_source"],
                    "snippet_id": row["snippet_id"],
                    "lang": row["target_language"],
                    "compilable": row["compilable"],
                    "MI": m.get("maintainability_index", "—"),
                    "Composite": quality_composite_from_history_row(row),
                    "faith_1_5": row.get("faithfulness_score", "—"),
                }
            )
        st.dataframe(_arrow_safe_dataframe(display_rows), width="stretch", hide_index=True)

        st.divider()
        st.subheader("Winner (latest row per model for one snippet)")
        win_snip = st.text_input(
            "Snippet ID",
            key="win_snip",
            help="Runs must share the same snippet_id from the Compare tab. Winner = highest research composite.",
        )

        if st.button("Compute winner from loaded history", key="win_btn"):
            sid = win_snip.strip()
            if not sid:
                st.error("Enter snippet_id.")
            else:
                pool = [r for r in rows if r.get("snippet_id") == sid]
                if not pool:
                    st.error("No rows for that snippet_id in the current history load.")
                else:
                    pool.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
                    by_llm: dict[str, dict] = {}
                    for r in pool:
                        lm = r.get("llm_source")
                        if lm and lm not in by_llm:
                            by_llm[lm] = r
                    win_rows = []
                    for lm, r in sorted(by_llm.items()):
                        qc = quality_composite_from_history_row(r)
                        note = "" if qc is not None else "could not compute composite; re-run analyze"
                        win_rows.append(
                            {
                                "Model": lm,
                                "Composite": round(qc, 2) if qc is not None else "—",
                                "db id": r["id"],
                                "note": note,
                            }
                        )
                    st.dataframe(_arrow_safe_dataframe(win_rows), width="stretch", hide_index=True)
                    numeric = [
                        x
                        for x in win_rows
                        if isinstance(x.get("Composite"), (int, float))
                        and math.isfinite(float(x["Composite"]))
                    ]
                    if numeric:
                        best = max(numeric, key=lambda x: float(x["Composite"]))
                        st.success(f"**Winner:** {best['Model']} (composite **{best['Composite']}** / 100)")
                    elif win_rows:
                        st.warning("No finite composite for this snippet; cannot pick a winner.")
    else:
        st.info("Click **Load history** to fetch saved analyses from the API.")
