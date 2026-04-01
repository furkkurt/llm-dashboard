import hashlib
import json
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

from backend.models import PaperScores
from backend.paper_scoring import DEFAULT_WEIGHTS, composite_with_weights

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
    /* Hide Streamlit header “running” indicator next to Stop (in-page progress is enough). */
    [data-testid="stStatusWidget"] {
        display: none !important;
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
            help="AI 0–100 from OpenRouter when Compare uses AI commentary; else neutral **50** in composite.",
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


def _snippet_json_for_download() -> str:
    return json.dumps(
        {
            "version": 1,
            "snippet_id": str(st.session_state.get("snippet_id_input", "")).strip(),
            "target_language": str(st.session_state.get("target_language_sel", "Kotlin")),
            "prompt": str(st.session_state.get("prompt_area", "")),
            "code_chatgpt": str(st.session_state.get("code_chatgpt", "")),
            "code_claude": str(st.session_state.get("code_claude", "")),
            "code_gemini": str(st.session_state.get("code_gemini", "")),
        },
        ensure_ascii=False,
        indent=2,
    )


def _parse_snippet_upload(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    lang = data.get("target_language")
    if lang is not None and lang not in ("Kotlin", "Flutter"):
        raise ValueError("target_language must be Kotlin or Flutter if set")
    out = {
        "prompt": str(data.get("prompt", "")),
        "code_chatgpt": str(data.get("code_chatgpt", data.get("code_gpt", ""))),
        "code_claude": str(data.get("code_claude", "")),
        "code_gemini": str(data.get("code_gemini", "")),
    }
    if "snippet_id" in data and data["snippet_id"] is not None:
        out["snippet_id"] = str(data["snippet_id"])
    if lang in ("Kotlin", "Flutter"):
        out["target_language"] = lang
    return out


tab_compare, tab_history = st.tabs(["Compare models", "History & winner"])

with tab_compare:
    if "_pending_snippet_id" in st.session_state:
        st.session_state["snippet_id_input"] = st.session_state.pop("_pending_snippet_id")
    if "_pending_compare_snippet" in st.session_state:
        d = st.session_state.pop("_pending_compare_snippet")
        if isinstance(d, dict):
            st.session_state["prompt_area"] = str(d.get("prompt", ""))
            st.session_state["code_chatgpt"] = str(d.get("code_chatgpt", ""))
            st.session_state["code_claude"] = str(d.get("code_claude", ""))
            st.session_state["code_gemini"] = str(d.get("code_gemini", ""))
            if "snippet_id" in d:
                st.session_state["snippet_id_input"] = str(d["snippet_id"])
            if d.get("target_language") in ("Kotlin", "Flutter"):
                st.session_state["target_language_sel"] = d["target_language"]
    # Apply AI text *before* the text_area widget mounts (same-run writes after widget are forbidden).
    if "_pending_ai_commentary" in st.session_state:
        st.session_state["ai_commentary_summary"] = st.session_state.pop("_pending_ai_commentary")

    left_col, middle_col, right_col = st.columns([1, 2, 2], gap="large")

    with left_col:
        st.subheader("Settings")
        target_language = st.selectbox(
            "Target Language", ["Kotlin", "Flutter"], key="target_language_sel"
        )
        snippet_id = st.text_input(
            "Snippet ID",
            placeholder="e.g. notepad_compare_01 (shared across models for this run)",
            key="snippet_id_input",
        )
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
                "Save or restore all four inputs (and snippet id / language) with **Download** / **Upload**."
            )
            du1, du2 = st.columns(2)
            with du1:
                st.download_button(
                    label="Download snippet (.json)",
                    data=_snippet_json_for_download(),
                    file_name="llm-eval-snippet.json",
                    mime="application/json",
                    width="stretch",
                    help="Saves prompt, ChatGPT / Claude / Gemini code, snippet id, and target language.",
                )
            with du2:
                up = st.file_uploader(
                    "Upload snippet (.json)",
                    type=["json"],
                    key="snippet_json_upload",
                    help="Restores the four text areas (and optional snippet id / language).",
                )
                if up is not None:
                    digest = hashlib.sha256(up.getvalue()).hexdigest()
                    if digest != st.session_state.get("_snippet_json_digest"):
                        try:
                            parsed = _parse_snippet_upload(json.loads(up.getvalue().decode("utf-8")))
                            st.session_state["_snippet_json_digest"] = digest
                            st.session_state["_pending_compare_snippet"] = parsed
                            st.rerun()
                        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
                            st.error(f"Could not load snippet file: {e}")
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
                to_run: list[tuple[str, str]] = []
                for model_name, key in MODEL_ORDER:
                    code = str(st.session_state.get(key, "")).strip()
                    if code:
                        to_run.append((model_name, code))
                if not to_run:
                    st.error("Paste code in at least one model box (ChatGPT, Claude, or Gemini).")
                else:
                    new_results: dict[str, dict] = {}
                    n = len(to_run)
                    with loading_slot:
                        prog = st.progress(0.0, text="Starting…")
                        for i, (model_name, code) in enumerate(to_run):
                            prog.progress(
                                i / max(n, 1),
                                text=f"Analyzing {model_name} ({i + 1}/{n})…",
                            )
                            payload = {
                                "llm_source": model_name,
                                "target_language": target_language,
                                "snippet_id": sid,
                                "prompt": prompt_text,
                                "code": code,
                            }
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
            st.dataframe(_arrow_safe_dataframe(cmp_rows), width="stretch", hide_index=True)

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
        "Load past runs, then pick weights to declare a winner per snippet."
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
        st.dataframe(_arrow_safe_dataframe(display_rows), width="stretch", hide_index=True)

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
                                    "note": "missing paper_scores; re-run Compare / analyze",
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
                    st.dataframe(_arrow_safe_dataframe(win_rows), width="stretch", hide_index=True)
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
