import math
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.env_bootstrap import load_dashboard_env

# Same as API: `.env` then `local.env` (override); never written by setup.sh.
load_dashboard_env()

from backend.flutter_extract import split_compare_transcript
from backend.models import PaperScores
from backend.paper_scoring import DEFAULT_WEIGHTS, composite_with_weights

# Minimal 3-way sheet so Compare works without pasting (smoke test).
_SMOKE_COMPARE_SHEET = """PROMPT:
create a basic notepad app using flutter.
GEMINI:
import 'package:flutter/material.dart';

void main() {
  runApp(const MaterialApp(home: Scaffold(body: Center(child: Text('Gemini')))));
}
GPT:
import 'package:flutter/material.dart';

void main() {
  runApp(const MaterialApp(home: Scaffold(body: Center(child: Text('GPT')))));
}
CLAUDE:
import 'package:flutter/material.dart';

void main() {
  runApp(const MaterialApp(home: Scaffold(body: Center(child: Text('Claude')))));
}
"""

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ANALYZE_URL = f"{API_BASE}/analyze"
RESULTS_URL = f"{API_BASE}/results"
REQUEST_TIMEOUT_SEC = 600

MODEL_ORDER = [
    ("ChatGPT", "code_chatgpt"),
    ("Claude", "code_claude"),
    ("Gemini", "code_gemini"),
]

st.set_page_config(page_title="LLM Evaluation Dashboard", layout="wide")

st.markdown(
    r"""
    <style>
    .terminal-pane {
        background: var(--st-secondary-background-color, #f0f2f6);
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .kpi-card {
        background: var(--st-secondary-background-color, #f0f2f6);
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 0.9rem;
        text-align: center;
    }
    .section-card {
        background: var(--st-secondary-background-color, #f0f2f6);
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    [data-testid="stSpinner"] svg {
        display: none !important;
    }
    [data-testid="stSpinner"] > div {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    [data-testid="stSpinner"] > div::before {
        content: "";
        display: inline-block;
        width: 1.1rem;
        height: 1.1rem;
        border: 2px solid rgba(128,128,128,0.35);
        border-top-color: var(--st-primary-color, #ff4b4b);
        border-radius: 50%;
        animation: compare-spin 0.75s linear infinite;
        flex-shrink: 0;
    }
    @keyframes compare-spin {
        to { transform: rotate(360deg); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "prompt_area" not in st.session_state:
    st.session_state.prompt_area = ""
for _label, key in MODEL_ORDER:
    if key not in st.session_state:
        st.session_state[key] = ""
if "model_results" not in st.session_state:
    st.session_state.model_results = {}
if "history_rows" not in st.session_state:
    st.session_state.history_rows = []
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


def render_metrics_table(metrics: dict | None) -> None:
    if not metrics:
        return
    rows = {
        "Total wall time": _fmt_ms(metrics.get("total_duration_ms")),
        "Pub get time": _fmt_ms(metrics.get("pub_get_duration_ms")),
        "Dependency resolve (pub add rounds)": _fmt_ms(metrics.get("dependency_resolve_duration_ms")),
        "Analyze time (dart / kotlin path)": _fmt_ms(metrics.get("analyze_duration_ms")),
        "Kotlin compile time": _fmt_ms(metrics.get("kotlin_compile_duration_ms")),
        "Detekt time": _fmt_ms(metrics.get("detekt_duration_ms")),
        "Lines of code (main snippet)": metrics.get("lines_of_code"),
        "Characters (main snippet)": metrics.get("characters_code"),
        "Pubspec dependency keys": metrics.get("dependency_declaration_count"),
        "Analyzer errors": metrics.get("analyzer_errors"),
        "Analyzer warnings": metrics.get("analyzer_warnings"),
        "Analyzer infos": metrics.get("analyzer_infos"),
        "Scaffold / setup notes": metrics.get("scaffold_notes"),
        "Packages auto-installed": ", ".join(metrics.get("packages_auto_added") or []) or "—",
        "Pub get command": metrics.get("pub_get_command_used") or "—",
    }
    st.dataframe(
        pd.DataFrame({"Metric": list(rows.keys()), "Value": list(rows.values())}),
        use_container_width=True,
        hide_index=True,
    )


def _faithfulness_choice(label: str, key: str) -> int | None:
    opts = ["- not rated", "1", "2", "3", "4", "5"]
    pick = st.selectbox(label, opts, index=0, key=key)
    if pick.startswith("-"):
        return None
    return int(pick)


def _paper_from_metrics(metrics: dict | None) -> PaperScores | None:
    if not metrics or not isinstance(metrics.get("paper_scores"), dict):
        return None
    try:
        return PaperScores.model_validate(metrics["paper_scores"])
    except Exception:
        return None


def render_ai_commentary_block(result: dict, metrics: dict | None) -> None:
    ac = result.get("ai_commentary") or (metrics or {}).get("ai_commentary")
    if not isinstance(ac, dict):
        return
    # API omits null fields; treat "any Gemini payload" as worth showing
    if not ac:
        return
    with st.expander("AI commentary (Gemini)", expanded=False):
        if ac.get("error"):
            st.warning(str(ac["error"]))
        fs = ac.get("faithfulness_score_1_5")
        if fs is not None:
            st.caption(
                f"AI-estimated prompt faithfulness: **{fs}** / 5 "
                "(used in composite only when manual faithfulness is left unrated)."
            )
        if ac.get("faithfulness_note"):
            st.markdown(str(ac["faithfulness_note"]))
        if ac.get("metrics_comment"):
            st.markdown(str(ac["metrics_comment"]))
        if not (
            ac.get("error")
            or fs is not None
            or ac.get("faithfulness_note")
            or ac.get("metrics_comment")
        ):
            st.info(
                "Commentary was requested but the model returned no usable text or score. "
                "Check quota, `GOOGLE_API_KEY` in `llm-dashboard/local.env` or `.env`, and restart the API after editing."
            )


def render_paper_scores(paper: PaperScores | None) -> None:
    if not paper:
        st.caption("No paper-aligned scores stored for this run.")
        return
    st.markdown("**Ozet metrics (0-100)**")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Compilability", paper.compilability_0_100)
    with c2:
        st.metric("Static health", paper.static_analysis_health_0_100)
    with c3:
        st.metric("Tool efficiency", paper.tool_efficiency_0_100)
    with c4:
        fv = paper.faithfulness_0_100
        st.metric(
            "Faithfulness",
            "—" if fv is None else fv,
            help="Manual 1-5 or AI estimate (if auto commentary on) mapped to 0-100 when set.",
        )
        if paper and not paper.faithfulness_rated:
            st.caption("Unrated: composite uses **50** on this axis.")
    with c5:
        st.metric("Composite (default weights)", paper.composite_default_0_100)


def render_rule_histogram(title: str, hist: dict) -> None:
    if not hist:
        return
    st.markdown(f"**{title}**")
    df = pd.DataFrame(
        [{"rule": k, "count": v} for k, v in sorted(hist.items(), key=lambda x: -x[1])[:25]]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


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
    render_ai_commentary_block(result, metrics)

    if metrics:
        with st.expander("Full timing and size metrics", expanded=False):
            render_metrics_table(metrics)
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
    """Prominent winner from default composite among successful compare runs."""
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
        cc = ps.get("composite_default_0_100")
        if cc is not None:
            try:
                scored.append((model_name, float(cc)))
            except (TypeError, ValueError):
                pass
    if not any_success:
        st.warning("No winner: all model runs failed.")
        return
    if not scored:
        st.info("No winner: no composite scores available for successful runs.")
        return
    best = max(s for _, s in scored)
    top_names = [n for n, s in scored if s == best]
    if len(top_names) == 1:
        st.markdown(f"## Winner: **{top_names[0]}**")
        st.success(f"Default composite **{best:.2f}** / 100 (weights: see caption under comparison table).")
    else:
        st.markdown(f"## Tie: **{', '.join(top_names)}**")
        st.success(f"Same default composite **{best:.2f}** / 100 for all tied models.")


tab_compare, tab_history = st.tabs(["Compare models", "History & winner"])

with tab_compare:
    if "_pending_snippet_id" in st.session_state:
        st.session_state["snippet_id_input"] = st.session_state.pop("_pending_snippet_id")

    left_col, middle_col, right_col = st.columns([1, 2, 2], gap="large")

    with left_col:
        st.subheader("Settings")
        target_language = st.selectbox("Target Language", ["Kotlin", "Flutter"])
        snippet_id = st.text_input(
            "Snippet ID",
            placeholder="e.g. notepad_compare_01 (shared across models for this run)",
            key="snippet_id_input",
        )
        st.markdown("**Optional faithfulness** (istemlere sadakati, 1-5)")
        st.caption("Leave unrated to use neutral faithfulness in the default composite.")
        fc = _faithfulness_choice("ChatGPT", "faith_chatgpt")
        fcl = _faithfulness_choice("Claude", "faith_claude")
        fg = _faithfulness_choice("Gemini", "faith_gemini")
        auto_commentary = st.checkbox(
            "Auto faithfulness + AI commentary (Gemini)",
            value=False,
            key="auto_commentary",
            help="Uses GOOGLE_API_KEY: estimates prompt adherence (1-5) when sliders are unrated, "
            "and adds a short metrics summary. Not a ground-truth judge.",
        )
        st.caption(
            "Set `GOOGLE_API_KEY` in **llm-dashboard/local.env** (recommended) or `.env`, then **restart uvicorn**."
        )
        st.caption("Paste one prompt and each model’s code in the middle column. API: " + API_BASE)

    with middle_col:
        st.markdown('<div class="terminal-pane">', unsafe_allow_html=True)
        st.subheader("Prompt and model outputs")
        if target_language == "Flutter":
            st.caption(
                "Paste the **full** model output when you can: fenced `main.dart` and `pubspec.yaml` "
                "are extracted. Missing packages are auto-added with **dart pub add** when the analyzer reports them."
            )
            st.caption(
                "**Compare sheet:** labels `PROMPT:`, `GEMINI:`, `GPT:`, `CLAUDE:` each on their own line "
                "are stripped from code; leading prose is cut before the first `import` / `void main`."
            )
            if st.button("Load smoke test sheet", help="Tiny valid Flutter in all 3 model boxes + prompt"):
                parts = split_compare_transcript(_SMOKE_COMPARE_SHEET)
                st.session_state.prompt_area = parts.get("prompt", "")
                st.session_state.code_gemini = parts.get("gemini", "")
                st.session_state.code_chatgpt = parts.get("gpt", "")
                st.session_state.code_claude = parts.get("claude", "")
                st.session_state["_pending_snippet_id"] = "notepad_smoke"
                st.rerun()
            bulk_sheet = st.text_area(
                "Optional: full PROMPT/GEMINI/GPT/CLAUDE sheet (paste once, then split)",
                height=100,
                placeholder="PROMPT:\n...\nGEMINI:\nimport ...\nGPT:\n...\nCLAUDE:\n...",
                key="bulk_compare_sheet",
            )
            if st.button("Split sheet into prompt + ChatGPT / Claude / Gemini boxes"):
                parts = split_compare_transcript(str(st.session_state.get("bulk_compare_sheet", "")))
                if not parts or len(parts) < 2:
                    st.warning(
                        "Could not parse sections. Put each label on its own line: "
                        "PROMPT:, GEMINI:, GPT:, CLAUDE: (case-insensitive)."
                    )
                else:
                    if "prompt" in parts:
                        st.session_state.prompt_area = parts["prompt"]
                    if "gemini" in parts:
                        st.session_state.code_gemini = parts["gemini"]
                    if "gpt" in parts:
                        st.session_state.code_chatgpt = parts["gpt"]
                    if "claude" in parts:
                        st.session_state.code_claude = parts["claude"]
                    if not str(st.session_state.get("snippet_id_input", "")).strip():
                        st.session_state["_pending_snippet_id"] = "compare_sheet"
                    st.success("Filled prompt and model boxes. Run COMPARE MODELS when ready.")
                    st.rerun()
        st.text_area(
            "Prompt (shared)",
            height=160,
            placeholder="Paste the exact prompt you used with each model...",
            key="prompt_area",
        )
        for model_name, key in MODEL_ORDER:
            st.text_area(
                f"{model_name} - paste code here",
                height=140,
                placeholder=f"Kotlin or Dart output from {model_name}...",
                key=key,
            )

        run_clicked = st.button("COMPARE MODELS", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    faith_by_model = {"ChatGPT": fc, "Claude": fcl, "Gemini": fg}

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
                to_run: list[tuple[str, str]] = []
                for model_name, key in MODEL_ORDER:
                    code = str(st.session_state.get(key, "")).strip()
                    if code:
                        to_run.append((model_name, code))
                if not to_run:
                    st.error("Paste code in at least one model box (ChatGPT, Claude, or Gemini).")
                else:
                    new_results: dict[str, dict] = {}
                    with loading_slot:
                        with st.spinner("Running analysis for each model..."):
                            for model_name, code in to_run:
                                payload = {
                                    "llm_source": model_name,
                                    "target_language": target_language,
                                    "snippet_id": sid,
                                    "prompt": prompt_text,
                                    "code": code,
                                }
                                fs = faith_by_model.get(model_name)
                                if fs is not None:
                                    payload["faithfulness_score_1_5"] = fs
                                if st.session_state.get("auto_commentary"):
                                    payload["auto_commentary"] = True
                                try:
                                    response = requests.post(
                                        ANALYZE_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC
                                    )
                                    if response.status_code != 200:
                                        new_results[model_name] = {
                                            "status": "error",
                                            "detail": _json_detail(response),
                                        }
                                    else:
                                        new_results[model_name] = {
                                            "status": "success",
                                            "data": response.json(),
                                        }
                                except requests.RequestException as e:
                                    new_results[model_name] = {
                                        "status": "error",
                                        "detail": str(e),
                                    }
                    st.session_state.model_results = new_results
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
            cmp_rows = []
            chart_time = {}
            chart_errors = {}
            chart_composite = {}
            for model_name, entry in results.items():
                if entry.get("status") != "success":
                    cmp_rows.append(
                        {
                            "Model": model_name,
                            "Compilable": "—",
                            "Compil. score": "—",
                            "Static score": "—",
                            "Eff. score": "—",
                            "Faith. score": "—",
                            "Composite*": "—",
                            "Errors": "—",
                            "Warnings": "—",
                            "Infos": "—",
                            "Total ms": "—",
                            "Pub get ms": "—",
                            "Analyze ms": "—",
                            "LOC": "—",
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
                cmp_rows.append(
                    {
                        "Model": model_name,
                        "Compilable": "Yes" if s["compilable"] else "No",
                        "Compil. score": ps.get("compilability_0_100", "—"),
                        "Static score": ps.get("static_analysis_health_0_100", "—"),
                        "Eff. score": ps.get("tool_efficiency_0_100", "—"),
                        "Faith. score": ps.get("faithfulness_0_100", "—"),
                        "Composite*": ps.get("composite_default_0_100", "—"),
                        "Errors": s["error_count"],
                        "Warnings": m.get("analyzer_warnings", "—"),
                        "Infos": m.get("analyzer_infos", "—"),
                        "Total ms": m.get("total_duration_ms", "—"),
                        "Pub get ms": m.get("pub_get_duration_ms", "—"),
                        "Analyze ms": m.get("analyze_duration_ms", "—"),
                        "LOC": m.get("lines_of_code", "—"),
                        "Deps": m.get("dependency_declaration_count", "—"),
                        "Auto packages": len(m.get("packages_auto_added") or []),
                        "API error": "",
                    }
                )
                chart_time[model_name] = int(m.get("total_duration_ms") or 0)
                chart_errors[model_name] = int(s.get("error_count") or 0)
                cc = ps.get("composite_default_0_100")
                if cc is not None:
                    chart_composite[model_name] = float(cc)

            st.caption("*Default weights: compilability 0.30, static 0.35, efficiency 0.15, faithfulness 0.20 (see manual.md).")
            st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True)

            if chart_composite:
                st.markdown("#### Default composite score by model")
                st.bar_chart(pd.Series(chart_composite, name="composite"))
            if chart_time:
                st.markdown("#### Total analysis time by model (ms)")
                st.bar_chart(pd.Series(chart_time, name="ms"))
            if chart_errors:
                st.markdown("#### Analyzer error count by model")
                st.bar_chart(pd.Series(chart_errors, name="errors"))

            st.divider()

            for model_name, entry in results.items():
                with st.expander(f"{model_name} - full report", expanded=False):
                    if entry.get("status") != "success":
                        st.error(entry.get("detail", "Unknown error"))
                    else:
                        render_one_model_panel(model_name, entry["data"])

with tab_history:
    st.markdown(
        "Metric definitions and formulas: **`manual.md`** in the `llm-dashboard` folder. "
        "Load past runs, adjust faithfulness, then pick weights to declare a winner per snippet."
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
            ps = m.get("paper_scores") or {}
            display_rows.append(
                {
                    "id": row["id"],
                    "created_at": str(row["created_at"])[:19],
                    "llm": row["llm_source"],
                    "snippet_id": row["snippet_id"],
                    "lang": row["target_language"],
                    "compilable": row["compilable"],
                    "composite": ps.get("composite_default_0_100", "—"),
                    "faith_1_5": row.get("faithfulness_score", "—"),
                }
            )
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

        st.subheader("Update faithfulness")
        default_id = int(display_rows[0]["id"]) if display_rows else 1
        patch_id = st.number_input("Result id", min_value=1, step=1, value=default_id, key="patch_id")
        score_choices = ["(unchanged)", "1", "2", "3", "4", "5"]
        patch_score_pick = st.selectbox("Faithfulness 1-5", score_choices, key="patch_score")
        patch_notes = st.text_area("Notes (optional)", key="patch_notes", height=80)
        if st.button("Apply PATCH", key="apply_patch"):
            body: dict = {}
            if patch_score_pick != "(unchanged)":
                body["faithfulness_score_1_5"] = int(patch_score_pick)
            if patch_notes.strip():
                body["faithfulness_notes"] = patch_notes.strip()
            if not body:
                st.warning("Choose a new score and/or enter notes.")
            else:
                try:
                    pr = requests.patch(
                        f"{API_BASE}/results/{int(patch_id)}",
                        json=body,
                        timeout=60,
                    )
                    if pr.status_code != 200:
                        st.error(_json_detail(pr))
                    else:
                        st.success("Updated. Reload history to refresh the table.")
                except requests.RequestException as e:
                    st.error(str(e))

        st.divider()
        st.subheader("Winner (latest row per model for one snippet)")
        win_snip = st.text_input(
            "Snippet ID",
            key="win_snip",
            help="Compared runs must share the same snippet_id from the Compare tab.",
        )
        wc1, wc2, wc3, wc4 = st.columns(4)
        with wc1:
            w_comp = st.slider(
                "w compilability",
                0.0,
                1.0,
                float(DEFAULT_WEIGHTS["compilability"]),
                0.05,
                key="w_comp",
            )
        with wc2:
            w_stat = st.slider(
                "w static",
                0.0,
                1.0,
                float(DEFAULT_WEIGHTS["static_analysis"]),
                0.05,
                key="w_stat",
            )
        with wc3:
            w_eff = st.slider(
                "w efficiency",
                0.0,
                1.0,
                float(DEFAULT_WEIGHTS["efficiency"]),
                0.05,
                key="w_eff",
            )
        with wc4:
            w_faith = st.slider(
                "w faithfulness",
                0.0,
                1.0,
                float(DEFAULT_WEIGHTS["faithfulness"]),
                0.05,
                key="w_faith",
            )
        weights = {
            "compilability": w_comp,
            "static_analysis": w_stat,
            "efficiency": w_eff,
            "faithfulness": w_faith,
        }
        tw = sum(weights.values())
        st.caption(f"Weight sum = {tw:.2f} (renormalized in the composite).")

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
                        m = r.get("metrics") or {}
                        ps = _paper_from_metrics(m)
                        if ps is None:
                            win_rows.append(
                                {
                                    "Model": lm,
                                    "custom composite": "—",
                                    "db id": r["id"],
                                    "note": "missing paper_scores; PATCH faithfulness or re-run analyze",
                                }
                            )
                            continue
                        try:
                            cust = composite_with_weights(ps, weights)
                        except Exception:
                            cust = float("nan")
                        win_rows.append(
                            {
                                "Model": lm,
                                "custom composite": round(cust, 2),
                                "default composite": ps.composite_default_0_100,
                                "db id": r["id"],
                                "note": "",
                            }
                        )
                    dfw = pd.DataFrame(win_rows)
                    st.dataframe(dfw, use_container_width=True, hide_index=True)
                    numeric = [
                        x
                        for x in win_rows
                        if isinstance(x.get("custom composite"), (int, float))
                        and math.isfinite(float(x["custom composite"]))
                    ]
                    if numeric:
                        best = max(numeric, key=lambda x: float(x["custom composite"]))
                        st.success(
                            f"**Winner:** {best['Model']} (custom composite **{best['custom composite']}**)"
                        )
    else:
        st.info("Click **Load history** to fetch saved analyses from the API.")
