# LLM Evaluation Dashboard — IDEE Blueprint (Linux / Void Linux Edition)

This blueprint refactors the current dashboard into an **Integrated Development & Evaluation Environment (IDEE)** tailored to the paper's workflow.

It keeps the original stack choice — **FastAPI + Streamlit + SQLite** — but changes the UX, request/response model, storage model, and local setup to match the research flow.

---

## 1. Research Framing

The dashboard is not just a code upload form. It is a **structured evaluation workstation** for comparing **ChatGPT, Claude, and Gemini** across **three prompt-complexity levels** and **two target languages: Kotlin and Flutter**.

### Research Levels

Based on the abstract, the 3 research levels should be encoded explicitly in both UI and backend logic:

- **Level 1 — Basic UI**
  - Simple interface construction
  - Low logic complexity
  - Expected to be the easiest category for all models

- **Level 2 — Hardware / Native Access**
  - Camera or similar device / platform capability access
  - Intended to test how well the model handles platform-linked or native concerns
  - Especially important for Kotlin vs Flutter comparison

- **Level 3 — Complex Data / State Management**
  - More complex logic, state flow, data handling, or architecture-heavy tasks
  - Intended to expose depth, correctness, and maintainability limits

### Evaluation Goals

The dashboard should help the paper evaluate:

- **Compilability**
- **Static analysis quality**
- **Prompt faithfulness / instruction adherence**
- **Cross-language effectiveness** for Kotlin vs Flutter
- **Cross-model effectiveness** for ChatGPT vs Claude vs Gemini

---

## 2. UX Vision — 3-Column IDEE Layout

The UI should behave like a horizontal **developer workstation**, not a report page.

### Layout Ratios

Use:

```python
st.columns([1, 2, 2])
```

Recommended mapping:

- **Left = Control & Context**
- **Middle = Terminal / Editor**
- **Right = Live Analysis Results**

---

## 3. Updated Streamlit UX Specification

### Left Column — Control & Context

Purpose: metadata, experiment context, and run configuration.

**Widgets**
- `LLM Source` → `ChatGPT`, `Claude`, `Gemini`
- `Research Level` → `1`, `2`, `3`
- `Target Language` → `Kotlin`, `Flutter`
- `Snippet ID` → free-text input
- Optional future fields:
  - `notes`
  - `paper_tag`
  - `reviewer`

**Behavior**
- This column is always visible.
- It acts like the settings pane for each experiment run.
- Changes do **not** trigger analysis automatically.

### Middle Column — Terminal / Editor

Purpose: single workspace for the actual experimental artifact.

**Components**
- Large text area labeled:
  - **Terminal - Input Prompt & Code**
- The researcher pastes:
  1. the exact prompt given to the LLM
  2. the code produced by the LLM

Because the backend must store prompt and code separately, the UI should expose **two large editors inside the terminal pane**:

- `Prompt` text area
- `Code` text area

This still fits the user's workflow because both inputs live in the same central terminal-like workspace.

**Call to Action**
- Primary button at the bottom:
  - **RUN ANALYSIS**

**Styling**
- Dark background
- Monospace typography
- Strong editor framing
- Make the middle column visually dominant

### Right Column — Live Analysis Results

Purpose: immediate post-run feedback.

#### Before Run
The panel must remain empty-ish and show:

- `Waiting for input...`

#### After Run
Render three stacked sections:

1. **KPI Cards**
   - Compilable: Yes / No
   - Error Count
   - Static Analysis Issues

2. **Detailed Error Log**
   - Raw or normalized compile/analyzer errors
   - Parsed from:
     - `kotlinc`
     - `dart analyze`

3. **Static Analysis Flags**
   - Parsed rule findings
   - For Kotlin: Detekt findings
   - For Flutter/Dart: `dart analyze` findings or lints

---

## 4. Updated Information Architecture

### Recommended Linux Folder Structure

This replaces the previous Windows path structure.

```text
/home/furkan/projects/llm-eval/
├── research-data/
│   ├── level-1-basic-ui/
│   │   ├── chatgpt/
│   │   │   ├── kotlin/
│   │   │   │   └── snippet_01.kt
│   │   │   └── flutter/
│   │   │       └── snippet_01.dart
│   │   ├── claude/
│   │   └── gemini/
│   ├── level-2-hardware-access/
│   └── level-3-data-state/
│
├── llm-dashboard/
│   ├── backend/
│   │   ├── main.py
│   │   ├── analyzer.py
│   │   ├── models.py
│   │   ├── database.py
│   │   └── parsers.py
│   ├── frontend/
│   │   └── app.py
│   ├── runners/
│   │   ├── run_kotlin_compile.py
│   │   ├── run_detekt.py
│   │   └── run_dart_analyze.py
│   ├── tools/
│   │   └── detekt-cli.jar
│   ├── temp/
│   │   └── runs/
│   ├── results/
│   │   ├── results.db
│   │   ├── exports/
│   │   └── raw-logs/
│   ├── .env
│   ├── requirements.txt
│   ├── setup.sh
│   └── start.sh
│
├── paper/
└── README.md
```

### Why this structure

- `research-data/` preserves your paper dataset
- `temp/runs/` isolates generated temporary files for compilation / analysis
- `results/raw-logs/` stores raw shell outputs for reproducibility
- `results.db` remains the structured source of truth for dashboard history

---

## 5. Updated Database Schema

The original schema was missing the actual prompt. That must be fixed.

### Required table

```sql
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
);
```

### Notes

- `prompt` is mandatory because it is a first-class research artifact.
- `code` is stored too, so each run is reproducible.
- `error_log_json` and `static_flags_json` should contain normalized parsed data.
- `prompt_faithfulness_notes` is optional now, but should exist because the abstract explicitly mentions fidelity to prompts.

---

## 6. Updated API Contract

### POST `/analyze`

The endpoint must now accept **both prompt and code as strings**.

#### Request body

```json
{
  "llm_source": "ChatGPT",
  "research_level": 2,
  "target_language": "Kotlin",
  "snippet_id": "camera_test_01",
  "prompt": "Build an Android camera preview screen...",
  "code": "class MainActivity : AppCompatActivity() { ... }"
}
```

#### Response body

```json
{
  "status": "success",
  "summary": {
    "compilable": false,
    "error_count": 3,
    "static_issue_count": 5
  },
  "error_log": [
    {
      "tool": "kotlinc",
      "severity": "error",
      "file": "Main.kt",
      "line": 12,
      "column": 18,
      "message": "Unresolved reference: CameraX"
    }
  ],
  "static_flags": [
    {
      "tool": "detekt",
      "rule": "LongMethod",
      "severity": "warning",
      "message": "Function exceeds recommended length"
    }
  ],
  "raw": {
    "compile_stdout": "",
    "compile_stderr": "...",
    "analyzer_stdout": "...",
    "analyzer_stderr": ""
  }
}
```

### GET `/results`

Should return recent runs for reporting and paper charts.

Useful optional filters:

- `llm_source`
- `research_level`
- `target_language`
- `snippet_id`
- `limit`

---

## 7. Execution Model

### Kotlin flow

1. Write code to temp file, for example:
   - `/home/furkan/projects/llm-eval/llm-dashboard/temp/runs/<uuid>/Main.kt`
2. Run compile check with `kotlinc`
3. Run static analysis with Detekt
4. Parse outputs
5. Persist result

### Flutter/Dart flow

1. Write code to temp file, for example:
   - `/home/furkan/projects/llm-eval/llm-dashboard/temp/runs/<uuid>/main.dart`
2. Run `dart analyze`
3. Parse output
4. Persist result

### Important implementation note

Pure compilation for arbitrary Flutter snippets is more context-sensitive than Kotlin because many snippets assume a full Flutter project structure. For that reason:

- for **Kotlin**, `compilable` can map directly to `kotlinc` success
- for **Flutter**, `compilable` should be interpreted as:
  - analysis succeeded without blocking errors, or
  - snippet compiles inside a generated temp project scaffold

For the first refactor, the simpler and more stable approach is:

- **Kotlin** → `kotlinc` + `detekt`
- **Flutter** → `dart analyze`

If you later need strict Flutter build validation, add a temp project scaffold runner.

---

## 8. Linux / Void Linux Setup

This replaces the earlier Windows-only instructions.

### Runtime install

On Void Linux:

```bash
sudo xbps-install -Su
sudo xbps-install -y python3 python3-pip python3-virtualenv openjdk17 curl unzip git kotlin flutter
```

If the `flutter` package is unavailable or outdated on your repo, install Flutter manually under:

```text
/opt/flutter
```

and add it to `PATH`.

### Verify tools

```bash
python3 --version
java -version
kotlinc -version
dart --version
flutter --version
```

### Python environment

```bash
cd /home/furkan/projects/llm-eval/llm-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Example `.env`

```env
APP_ENV=dev
API_HOST=127.0.0.1
API_PORT=8000
STREAMLIT_PORT=8501
PROJECT_ROOT=/home/furkan/projects/llm-eval/llm-dashboard
RESULTS_DB=/home/furkan/projects/llm-eval/llm-dashboard/results/results.db
DETekt_JAR=/home/furkan/projects/llm-eval/llm-dashboard/tools/detekt-cli.jar
TEMP_RUNS_DIR=/home/furkan/projects/llm-eval/llm-dashboard/temp/runs
RAW_LOGS_DIR=/home/furkan/projects/llm-eval/llm-dashboard/results/raw-logs
```

Use `DETEKT_JAR` in code, not `DETekt_JAR`; the mixed-case line above is only a typo example to avoid in implementation.

Correct version:

```env
DETEKT_JAR=/home/furkan/projects/llm-eval/llm-dashboard/tools/detekt-cli.jar
```

### `setup.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p tools results results/exports results/raw-logs temp/runs

if [ ! -f tools/detekt-cli.jar ]; then
  echo "Download detekt-cli.jar manually into tools/"
fi

echo "Setup complete. Activate with: source .venv/bin/activate"
```

### `start.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

streamlit run frontend/app.py --server.port 8501

kill $API_PID
```

---

## 9. Core FastAPI Models

File: `backend/models.py`

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

LLMSource = Literal["ChatGPT", "Claude", "Gemini"]
TargetLanguage = Literal["Kotlin", "Flutter"]


class AnalyzeRequest(BaseModel):
    llm_source: LLMSource
    research_level: int = Field(ge=1, le=3)
    target_language: TargetLanguage
    snippet_id: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1)
    code: str = Field(min_length=1)


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


class AnalyzeResponse(BaseModel):
    status: Literal["success", "error"]
    summary: AnalysisSummary
    error_log: list[ErrorItem]
    static_flags: list[StaticFlagItem]
    compile_stdout: str = ""
    compile_stderr: str = ""
    analyzer_stdout: str = ""
    analyzer_stderr: str = ""
    db_id: Optional[int] = None
```

---

## 10. Core FastAPI Endpoint

File: `backend/main.py`

```python
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisSummary,
)
from backend.analyzer import run_analysis
from backend.database import init_db, save_analysis_result

app = FastAPI(title="LLM Evaluation Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = await run_analysis(payload)

        db_id = save_analysis_result(
            llm_source=payload.llm_source,
            research_level=payload.research_level,
            target_language=payload.target_language,
            snippet_id=payload.snippet_id,
            prompt=payload.prompt,
            code=payload.code,
            compilable=result["summary"].compilable,
            error_count=result["summary"].error_count,
            static_issue_count=result["summary"].static_issue_count,
            compile_stdout=result.get("compile_stdout", ""),
            compile_stderr=result.get("compile_stderr", ""),
            analyzer_stdout=result.get("analyzer_stdout", ""),
            analyzer_stderr=result.get("analyzer_stderr", ""),
            error_log_json=json.dumps([item.model_dump() for item in result["error_log"]]),
            static_flags_json=json.dumps([item.model_dump() for item in result["static_flags"]]),
        )

        return AnalyzeResponse(
            status="success",
            summary=result["summary"],
            error_log=result["error_log"],
            static_flags=result["static_flags"],
            compile_stdout=result.get("compile_stdout", ""),
            compile_stderr=result.get("compile_stderr", ""),
            analyzer_stdout=result.get("analyzer_stdout", ""),
            analyzer_stderr=result.get("analyzer_stderr", ""),
            db_id=db_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

---

## 11. Core Database Layer

File: `backend/database.py`

```python
import os
import sqlite3
from datetime import datetime, UTC

DB_PATH = os.getenv(
    "RESULTS_DB",
    "/home/furkan/projects/llm-eval/llm-dashboard/results/results.db",
)


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
                run_duration_ms INTEGER
            )
            """
        )
        conn.commit()


def save_analysis_result(**kwargs) -> int:
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
                static_flags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                kwargs["llm_source"],
                kwargs["research_level"],
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
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
```

---

## 12. Core Streamlit UI

File: `frontend/app.py`

```python
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/analyze"

st.set_page_config(page_title="LLM Evaluation Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0f1117;
        color: #e8eaed;
    }
    .terminal-pane {
        background: #0b0d12;
        border: 1px solid #2a2f3a;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 0 0 1px rgba(255,255,255,0.03) inset;
    }
    .kpi-card {
        background: #151922;
        border: 1px solid #2a2f3a;
        border-radius: 12px;
        padding: 0.9rem;
        text-align: center;
    }
    .section-card {
        background: #151922;
        border: 1px solid #2a2f3a;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

left_col, middle_col, right_col = st.columns([1, 2, 2], gap="large")

with left_col:
    st.subheader("Settings")
    llm_source = st.selectbox("LLM Source", ["ChatGPT", "Claude", "Gemini"])
    research_level = st.selectbox(
        "Research Level",
        [1, 2, 3],
        format_func=lambda x: {
            1: "1 — Basic UI",
            2: "2 — Hardware Access",
            3: "3 — Complex Data / State",
        }[x],
    )
    target_language = st.selectbox("Target Language", ["Kotlin", "Flutter"])
    snippet_id = st.text_input("Snippet ID", placeholder="e.g. level2_camera_chatgpt_01")

    st.caption("Use this pane to define the experiment context before each run.")

with middle_col:
    st.markdown('<div class="terminal-pane">', unsafe_allow_html=True)
    st.subheader("Terminal - Input Prompt & Code")
    prompt = st.text_area(
        "Prompt",
        height=220,
        placeholder="Paste the exact prompt given to the LLM...",
    )
    code = st.text_area(
        "Code",
        height=420,
        placeholder="Paste the generated Kotlin or Flutter code here...",
    )

    run_clicked = st.button("RUN ANALYSIS", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

if run_clicked:
    payload = {
        "llm_source": llm_source,
        "research_level": research_level,
        "target_language": target_language,
        "snippet_id": snippet_id.strip(),
        "prompt": prompt,
        "code": code,
    }

    if not payload["snippet_id"]:
        st.error("Snippet ID is required.")
    elif not prompt.strip():
        st.error("Prompt is required.")
    elif not code.strip():
        st.error("Code is required.")
    else:
        with st.spinner("Running analysis..."):
            response = requests.post(API_URL, json=payload, timeout=120)
            response.raise_for_status()
            st.session_state.analysis_result = response.json()

with right_col:
    st.subheader("Live Analysis Results")

    result = st.session_state.analysis_result

    if not result:
        st.info("Waiting for input...")
    else:
        summary = result["summary"]

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
            st.metric("Compilable", "Yes" if summary["compilable"] else "No")
            st.markdown('</div>', unsafe_allow_html=True)
        with k2:
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
            st.metric("Error Count", summary["error_count"])
            st.markdown('</div>', unsafe_allow_html=True)
        with k3:
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
            st.metric("Static Analysis Issues", summary["static_issue_count"])
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Detailed Error Log")
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
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Static Analysis Flags")
        if result["static_flags"]:
            for flag in result["static_flags"]:
                st.code(
                    f"[{flag['tool']}] {flag['severity'].upper()} | "
                    f"{flag.get('rule') or 'General'}\n{flag['message']}",
                    language="text",
                )
        else:
            st.success("No static analysis issues found.")
        st.markdown('</div>', unsafe_allow_html=True)
```

---

## 13. Analyzer Contract

The analyzer should return a normalized structure regardless of whether the source is Kotlin or Flutter.

Recommended internal shape:

```python
{
    "summary": AnalysisSummary(...),
    "error_log": [ErrorItem(...), ...],
    "static_flags": [StaticFlagItem(...), ...],
    "compile_stdout": "...",
    "compile_stderr": "...",
    "analyzer_stdout": "...",
    "analyzer_stderr": "...",
}
```

That normalization is what makes the right column stable and predictable.

---

## 14. Practical Parsing Rules

### Kotlin

- `kotlinc` output populates:
  - `compilable`
  - `error_log`
- `detekt` output populates:
  - `static_flags`
  - `static_issue_count`

### Flutter / Dart

- `dart analyze --format=machine` populates:
  - `error_log`
  - `static_flags`
- If no blocking errors appear, mark `compilable = True` for the first version of the dashboard

This is a research dashboard, not a production CI pipeline, so consistency and comparability matter more than pretending Flutter snippets can always be compiled standalone.

---

## 15. Changes Required vs Previous Blueprint

### Replace
- Windows path structure
- `setup.bat`
- `start.bat`
- upload-first UX
- charts-first main page

### Add
- 3-column IDEE layout
- prompt storage in database
- prompt+code request model
- right-side live results panel
- terminal-style central editor
- Linux shell scripts and Linux filesystem paths

### Keep
- FastAPI
- Streamlit
- SQLite
- subprocess-based analyzer architecture
- detekt / dart analyze toolchain

---

## 16. Recommended Next Step for Cursor

Tell Cursor to do the refactor in this order:

1. Update `backend/models.py`
2. Update `backend/database.py` with prompt column migration
3. Update `backend/main.py` request/response shape
4. Refactor analyzer to accept raw strings instead of uploaded files
5. Replace Streamlit app with 3-column IDEE layout
6. Add Linux `setup.sh` and `start.sh`
7. Verify Kotlin and Flutter analysis with one saved fixture each per level

---

## 17. Open Questions You Should Lock Before Final Paper Build

I made two implementation assumptions to keep this blueprint actionable:

1. **Prompt faithfulness is not yet auto-scored.**
   I left a schema field for notes, but not a scoring engine, because your abstract mentions faithfulness as a metric but does not define a formal scoring rubric.

2. **Flutter compilability is treated pragmatically in v1.**
   I used `dart analyze` as the stable baseline unless you explicitly want temporary full Flutter project generation for each run.

If you want, the next pass should define:

- the exact **prompt-faithfulness rubric**
- whether **Flutter should be analyzed only** or **fully scaffold-built** per snippet
