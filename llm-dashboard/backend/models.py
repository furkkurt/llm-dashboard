from typing import Literal, Optional

from pydantic import BaseModel, Field

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
        description="If true, call Gemini to suggest faithfulness (when not set) and add metric comments.",
    )


class AiCommentary(BaseModel):
    """Optional Gemini-generated interpretation; not authoritative."""

    faithfulness_score_1_5: Optional[int] = Field(None, ge=1, le=5)
    faithfulness_note: str = ""
    metrics_comment: str = ""
    provider: str = "gemini"
    error: Optional[str] = None


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


class AnalysisMetrics(BaseModel):
    """Rich comparison metrics for research dashboards (timing, size, analyzer breakdown)."""

    total_duration_ms: int = 0
    pub_get_duration_ms: Optional[int] = None
    analyze_duration_ms: Optional[int] = None
    dependency_resolve_duration_ms: Optional[int] = None
    kotlin_compile_duration_ms: Optional[int] = None
    detekt_duration_ms: Optional[int] = None

    lines_of_code: int = 0
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
