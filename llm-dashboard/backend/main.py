import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.env_bootstrap import load_dashboard_env

# Path anchored to this package, not cwd; override=True beats empty shell exports.
load_dashboard_env()

from backend.analyzer import run_analysis
from backend.commentary import run_metrics_commentary
from backend.openrouter_check import run_openrouter_smoke_test
from backend.database import (
    fetch_result_by_id,
    fetch_results,
    init_db,
    save_analysis_result,
    update_faithfulness,
)
from backend.llm_clients import run_generation
from backend.models import (
    AiCommentary,
    AnalysisMetrics,
    AnalyzeRequest,
    AnalyzeResponse,
    FaithfulnessPatch,
    CommentaryHealthResponse,
    GenerateRequest,
    GenerateResponse,
)
from backend.paper_scoring import build_paper_scores, faithfulness_1_5_from_0_100

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="LLM Evaluation Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Browser-friendly root: this process is the JSON API, not the Streamlit UI."""
    return {
        "service": "LLM Evaluation Dashboard API",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "commentary_health": "/health/commentary",
        "commentary_health_legacy": "/health/gemini",
        "note": "Dashboard UI: run Streamlit (e.g. streamlit run frontend/app.py); default port 8501.",
    }


@app.get("/health/commentary", response_model=CommentaryHealthResponse)
async def health_commentary():
    """Live check that OPENROUTER_API_KEY can call the configured model (OpenRouter chat, tiny prompt)."""
    result = await asyncio.to_thread(run_openrouter_smoke_test)
    return CommentaryHealthResponse(**result)


@app.get("/health/gemini", response_model=CommentaryHealthResponse, include_in_schema=False)
async def health_commentary_legacy():
    """Deprecated alias; use GET /health/commentary."""
    result = await asyncio.to_thread(run_openrouter_smoke_test)
    return CommentaryHealthResponse(**result)


@app.post("/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest) -> GenerateResponse:
    result = await asyncio.to_thread(run_generation, payload)
    if result.status == "error":
        raise HTTPException(status_code=503, detail=result.detail or "Generation failed")
    return result


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = await run_analysis(payload)
        summary = result["summary"]
        error_log = result["error_log"]
        static_flags = result["static_flags"]
        metrics: AnalysisMetrics | None = result.get("metrics")

        ai_commentary: AiCommentary | None = None
        if payload.auto_commentary:
            ai_commentary = await asyncio.to_thread(
                run_metrics_commentary,
                user_prompt=payload.prompt,
                code=payload.code,
                summary=summary,
                metrics=metrics,
                llm_source=payload.llm_source,
                manual_faithfulness_set=payload.faithfulness_score_1_5 is not None,
            )

        faithfulness_final = payload.faithfulness_score_1_5
        faithfulness_0_100_direct: float | None = None
        if faithfulness_final is None and ai_commentary is not None:
            if ai_commentary.faithfulness_score_0_100 is not None:
                faithfulness_0_100_direct = float(ai_commentary.faithfulness_score_0_100)
                faithfulness_final = faithfulness_1_5_from_0_100(faithfulness_0_100_direct)
            elif ai_commentary.faithfulness_score_1_5 is not None:
                faithfulness_final = ai_commentary.faithfulness_score_1_5

        counts: tuple[int | None, int | None, int | None] | None = None
        if metrics:
            counts = (metrics.analyzer_errors, metrics.analyzer_warnings, metrics.analyzer_infos)
        paper = build_paper_scores(
            summary,
            error_log,
            static_flags,
            total_duration_ms=result.get("run_duration_ms"),
            faithfulness_score_1_5=faithfulness_final
            if faithfulness_0_100_direct is None
            else None,
            faithfulness_0_100_direct=faithfulness_0_100_direct,
            metrics_counts=counts,
        )
        base_m = metrics.model_dump() if metrics else {}
        merged_metrics: dict = {**base_m, "paper_scores": paper.model_dump()}
        if ai_commentary is not None:
            merged_metrics["ai_commentary"] = ai_commentary.model_dump()
        metrics_json = json.dumps(merged_metrics)

        notes_parts: list[str] = []
        if payload.faithfulness_notes:
            notes_parts.append(payload.faithfulness_notes.strip())
        if ai_commentary and ai_commentary.faithfulness_note.strip():
            notes_parts.append(f"[AI] {ai_commentary.faithfulness_note.strip()}")
        combined_notes = "\n\n".join(notes_parts) if notes_parts else None

        db_id = save_analysis_result(
            llm_source=payload.llm_source,
            research_level=1,
            target_language=payload.target_language,
            snippet_id=payload.snippet_id,
            prompt=payload.prompt,
            code=payload.code,
            compilable=summary.compilable,
            error_count=summary.error_count,
            static_issue_count=summary.static_issue_count,
            compile_stdout=result.get("compile_stdout", ""),
            compile_stderr=result.get("compile_stderr", ""),
            analyzer_stdout=result.get("analyzer_stdout", ""),
            analyzer_stderr=result.get("analyzer_stderr", ""),
            error_log_json=json.dumps([e.model_dump() for e in error_log]),
            static_flags_json=json.dumps([f.model_dump() for f in static_flags]),
            prompt_faithfulness_notes=combined_notes,
            run_duration_ms=result.get("run_duration_ms"),
            metrics_json=metrics_json,
            faithfulness_score=faithfulness_final,
        )

        return AnalyzeResponse(
            status="success",
            summary=summary,
            error_log=error_log,
            static_flags=static_flags,
            metrics=metrics,
            paper_scores=paper,
            ai_commentary=ai_commentary,
            compile_stdout=result.get("compile_stdout", ""),
            compile_stderr=result.get("compile_stderr", ""),
            analyzer_stdout=result.get("analyzer_stdout", ""),
            analyzer_stderr=result.get("analyzer_stderr", ""),
            db_id=db_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/results")
async def results(
    llm_source: str | None = None,
    target_language: str | None = None,
    snippet_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    return fetch_results(
        llm_source=llm_source,
        target_language=target_language,
        snippet_id=snippet_id,
        limit=limit,
    )


@app.patch("/results/{row_id}")
async def patch_result_faithfulness(row_id: int, payload: FaithfulnessPatch):
    if (
        payload.faithfulness_score_1_5 is None
        and payload.faithfulness_notes is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide faithfulness_score_1_5 and/or faithfulness_notes.",
        )
    updated = update_faithfulness(
        row_id,
        faithfulness_score_1_5=payload.faithfulness_score_1_5,
        faithfulness_notes=payload.faithfulness_notes,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return updated


@app.get("/results/{row_id}")
async def get_one_result(row_id: int):
    row = fetch_result_by_id(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return row
