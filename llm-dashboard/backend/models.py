from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

LLMSource = Literal["ChatGPT", "Claude", "Gemini"]
TargetLanguage = Literal["Kotlin", "Flutter"]


class AnalyzeRequest(BaseModel):
    llm_source: LLMSource
    target_language: TargetLanguage
    snippet_id: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1)
    code: str = Field(min_length=1)
    faithfulness_score_1_5: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Manuel istem sadakati (1=zayıf … 5=mükemmel). Özetteki metrik.",
    )
    faithfulness_notes: Optional[str] = Field(None, max_length=4000)
    auto_commentary: bool = Field(
        False,
        description="If true, call OpenRouter (chat completions) for faithfulness hint + metric comments.",
    )


class AiCommentary(BaseModel):
    """Optional model-generated interpretation via OpenRouter; not authoritative."""

    faithfulness_score_0_100: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="How well this output fulfills the user task prompt (0-100).",
    )
    faithfulness_score_1_5: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Legacy 1-5 scale; ignored when faithfulness_score_0_100 is set.",
    )
    faithfulness_note: str = ""
    metrics_comment: str = ""
    provider: str = "openrouter"
    error: Optional[str] = None


class CommentaryHealthResponse(BaseModel):
    """Result of GET /health/commentary — does not expose the API key."""

    ok: bool
    model: Optional[str] = None
    error: Optional[str] = None
    preview: Optional[str] = Field(
        None,
        description="Short snippet of the model reply when the call succeeds.",
    )
    env_file: Optional[str] = Field(
        None,
        description="Absolute path to the .env file loaded before this check.",
    )
    env_file_present: Optional[bool] = Field(
        None,
        description="Whether `.env` exists on disk.",
    )
    local_env_file: Optional[str] = Field(
        None,
        description="Absolute path to optional `local.env` (loaded after `.env`, overrides it).",
    )
    local_env_present: Optional[bool] = Field(
        None,
        description="Whether `local.env` exists.",
    )


# Backward-compatible alias (older docs / links).
GeminiHealthResponse = CommentaryHealthResponse


class GenerateRequest(BaseModel):
    llm_source: LLMSource
    target_language: TargetLanguage
    prompt: str = Field(min_length=1)


class GenerateResponse(BaseModel):
    status: Literal["success", "error"]
    generated_text: str = ""
    code_suggestion: str = ""
    detail: Optional[str] = None


class ErrorItem(BaseModel):
    tool: str
    severity: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    message: str


class StaticFlagItem(BaseModel):
    tool: str
    rule: Optional[str] = None
    severity: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None


class AnalysisSummary(BaseModel):
    compilable: bool
    error_count: int
    static_issue_count: int


class PaperScores(BaseModel):
    """Özet (PDF) ile uyumlu 0–100 araştırma skorları."""

    compilability_0_100: float
    static_analysis_health_0_100: float
    tool_efficiency_0_100: float
    faithfulness_0_100: Optional[float] = None
    faithfulness_rated: bool = False
    composite_default_0_100: float
    quality_composite_0_100: Optional[float] = Field(
        default=None,
        description=(
            "0–100 research composite (dashboard winner): MI, shallow nesting, analyzer cleanliness, faithfulness."
        ),
    )
    # Cross-language code-quality measures (metrics.md / metricguide.md)
    loc: Optional[int] = None
    comment_lines: Optional[int] = None
    avg_cyclomatic_complexity: Optional[float] = None
    comment_ratio: Optional[float] = None
    halstead_volume: Optional[float] = None
    halstead_difficulty: Optional[float] = None
    maintainability_index: Optional[float] = None
    avg_nesting_depth: Optional[float] = None


class AnalysisMetrics(BaseModel):
    """Rich comparison metrics for research dashboards (timing, size, analyzer breakdown)."""

    model_config = ConfigDict(extra="ignore")

    total_duration_ms: int = 0
    pub_get_duration_ms: Optional[int] = None
    analyze_duration_ms: Optional[int] = None
    dependency_resolve_duration_ms: Optional[int] = None
    kotlin_compile_duration_ms: Optional[int] = None
    detekt_duration_ms: Optional[int] = None

    lines_of_code: int = Field(
        0,
        description="Non-empty lines that are not comment-only (code lines); metrics.md `loc` is total physical lines.",
    )
    loc: Optional[int] = Field(None, description="Total physical lines in snippet (metrics.md raw LOC).")
    comment_lines: Optional[int] = Field(None, description="Comment-only lines (metrics.md).")
    characters_code: int = 0
    dependency_declaration_count: int = 0

    analyzer_errors: int = 0
    analyzer_warnings: int = 0
    analyzer_infos: int = 0
    scaffold_notes: int = 0

    packages_auto_added: list[str] = Field(default_factory=list)
    pub_get_command_used: Optional[str] = None

    analyzer_rule_histogram: dict[str, int] = Field(default_factory=dict)
    detekt_rule_histogram: dict[str, int] = Field(default_factory=dict)

    # metrics.md — heuristic cross-language measures from source (see cross_language_metrics.py)
    avg_cyclomatic_complexity: Optional[float] = None
    comment_ratio: Optional[float] = None
    halstead_volume: Optional[float] = None
    halstead_difficulty: Optional[float] = None
    maintainability_index: Optional[float] = None
    avg_nesting_depth: Optional[float] = None


class FaithfulnessPatch(BaseModel):
    faithfulness_score_1_5: Optional[int] = Field(None, ge=1, le=5)
    faithfulness_notes: Optional[str] = Field(None, max_length=4000)


class AnalyzeResponse(BaseModel):
    status: Literal["success", "error"]
    summary: AnalysisSummary
    error_log: list[ErrorItem]
    static_flags: list[StaticFlagItem]
    metrics: Optional[AnalysisMetrics] = None
    paper_scores: Optional[PaperScores] = None
    ai_commentary: Optional[AiCommentary] = None
    compile_stdout: str = ""
    compile_stderr: str = ""
    analyzer_stdout: str = ""
    analyzer_stderr: str = ""
    db_id: Optional[int] = None
