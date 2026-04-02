import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path as P

from backend.models import AnalysisMetrics, AnalysisSummary, ErrorItem, StaticFlagItem
from backend.paper_scoring import recompute_full_paper_scores

DB_PATH = os.getenv(
    "RESULTS_DB",
    str(P(__file__).resolve().parent.parent / "results" / "results.db"),
)


def get_conn() -> sqlite3.Connection:
    path = P(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                llm_source TEXT NOT NULL,
                research_level INTEGER NOT NULL,
                target_language TEXT NOT NULL,
                snippet_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                code TEXT NOT NULL,
                compilable INTEGER NOT NULL,
                error_count INTEGER NOT NULL DEFAULT 0,
                static_issue_count INTEGER NOT NULL DEFAULT 0,
                compile_stdout TEXT,
                compile_stderr TEXT,
                analyzer_stdout TEXT,
                analyzer_stderr TEXT,
                error_log_json TEXT,
                static_flags_json TEXT,
                prompt_faithfulness_notes TEXT,
                run_duration_ms INTEGER,
                UNIQUE(llm_source, research_level, target_language, snippet_id, prompt, code)
            )
            """
        )
        conn.commit()
        try:
            conn.execute("ALTER TABLE analysis_results ADD COLUMN metrics_json TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE analysis_results ADD COLUMN faithfulness_score INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def save_analysis_result(**kwargs) -> int:
    """
    Insert a new row or update the existing one on the natural key
    (llm_source, research_level, language, snippet_id, prompt, code) so
    re-running Compare with the same inputs succeeds instead of 409.
    """
    row = (
        datetime.now(UTC).isoformat(),
        kwargs["llm_source"],
        int(kwargs.get("research_level", 1)),
        kwargs["target_language"],
        kwargs["snippet_id"],
        kwargs["prompt"],
        kwargs["code"],
        int(kwargs["compilable"]),
        kwargs["error_count"],
        kwargs["static_issue_count"],
        kwargs.get("compile_stdout", ""),
        kwargs.get("compile_stderr", ""),
        kwargs.get("analyzer_stdout", ""),
        kwargs.get("analyzer_stderr", ""),
        kwargs.get("error_log_json", "[]"),
        kwargs.get("static_flags_json", "[]"),
        kwargs.get("prompt_faithfulness_notes"),
        kwargs.get("run_duration_ms"),
        kwargs.get("metrics_json"),
        kwargs.get("faithfulness_score"),
    )
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO analysis_results (
                created_at,
                llm_source,
                research_level,
                target_language,
                snippet_id,
                prompt,
                code,
                compilable,
                error_count,
                static_issue_count,
                compile_stdout,
                compile_stderr,
                analyzer_stdout,
                analyzer_stderr,
                error_log_json,
                static_flags_json,
                prompt_faithfulness_notes,
                run_duration_ms,
                metrics_json,
                faithfulness_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(llm_source, research_level, target_language, snippet_id, prompt, code)
            DO UPDATE SET
                created_at = excluded.created_at,
                compilable = excluded.compilable,
                error_count = excluded.error_count,
                static_issue_count = excluded.static_issue_count,
                compile_stdout = excluded.compile_stdout,
                compile_stderr = excluded.compile_stderr,
                analyzer_stdout = excluded.analyzer_stdout,
                analyzer_stderr = excluded.analyzer_stderr,
                error_log_json = excluded.error_log_json,
                static_flags_json = excluded.static_flags_json,
                prompt_faithfulness_notes = excluded.prompt_faithfulness_notes,
                run_duration_ms = excluded.run_duration_ms,
                metrics_json = excluded.metrics_json,
                faithfulness_score = excluded.faithfulness_score
            RETURNING id
            """,
            row,
        )
        out = cursor.fetchone()
        conn.commit()
        if out is None:
            return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return int(out[0])


def fetch_results(
    *,
    llm_source: str | None = None,
    target_language: str | None = None,
    snippet_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    limit = max(1, min(limit, 500))
    clauses: list[str] = []
    params: list[object] = []
    if llm_source:
        clauses.append("llm_source = ?")
        params.append(llm_source)
    if target_language:
        clauses.append("target_language = ?")
        params.append(target_language)
    if snippet_id:
        clauses.append("snippet_id = ?")
        params.append(snippet_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT * FROM analysis_results
        {where}
        ORDER BY created_at DESC
        LIMIT ?
    """
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    out: list[dict] = []
    for r in rows:
        out.append(_row_to_dict(r))
    return out


def _row_to_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["compilable"] = bool(d["compilable"])
    try:
        d["error_log"] = json.loads(d.pop("error_log_json") or "[]")
    except json.JSONDecodeError:
        d["error_log"] = []
    try:
        d["static_flags"] = json.loads(d.pop("static_flags_json") or "[]")
    except json.JSONDecodeError:
        d["static_flags"] = []
    mj = d.pop("metrics_json", None)
    if mj:
        try:
            d["metrics"] = json.loads(mj)
        except json.JSONDecodeError:
            d["metrics"] = None
    else:
        d["metrics"] = None
    if "faithfulness_score" not in d:
        d["faithfulness_score"] = None
    return d


def fetch_result_by_id(row_id: int) -> dict | None:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM analysis_results WHERE id = ?",
            (row_id,),
        ).fetchone()
    if r is None:
        return None
    return _row_to_dict(r)


def update_faithfulness(
    row_id: int,
    *,
    faithfulness_score_1_5: int | None = None,
    faithfulness_notes: str | None = None,
) -> dict | None:
    """
    Update optional manual faithfulness rating/notes and recompute paper_scores in metrics_json.
    None means leave that field unchanged.
    """
    row = fetch_result_by_id(row_id)
    if row is None:
        return None

    new_score = (
        faithfulness_score_1_5
        if faithfulness_score_1_5 is not None
        else row.get("faithfulness_score")
    )
    new_notes = (
        faithfulness_notes
        if faithfulness_notes is not None
        else row.get("prompt_faithfulness_notes")
    )

    summary = AnalysisSummary(
        compilable=row["compilable"],
        error_count=row["error_count"],
        static_issue_count=row["static_issue_count"],
    )
    error_log = [ErrorItem.model_validate(x) for x in row["error_log"]]
    static_flags = [StaticFlagItem.model_validate(x) for x in row["static_flags"]]
    metrics = row.get("metrics") or {}
    base_metrics = {k: v for k, v in metrics.items() if k != "paper_scores"}
    am: AnalysisMetrics | None = None
    if base_metrics:
        try:
            am = AnalysisMetrics.model_validate(base_metrics)
        except Exception:
            am = None
    paper = recompute_full_paper_scores(
        summary,
        error_log,
        static_flags,
        total_duration_ms=row.get("run_duration_ms"),
        faithfulness_score_1_5=new_score,
        faithfulness_0_100_direct=None,
        metrics=am,
    )
    merged = {**base_metrics, "paper_scores": paper.model_dump()}

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE analysis_results
            SET faithfulness_score = ?,
                prompt_faithfulness_notes = ?,
                metrics_json = ?
            WHERE id = ?
            """,
            (
                new_score,
                new_notes,
                json.dumps(merged),
                row_id,
            ),
        )
        conn.commit()
    return fetch_result_by_id(row_id)
