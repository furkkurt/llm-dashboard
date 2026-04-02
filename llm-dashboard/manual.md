# LLM Evaluation Dashboard — user guide

**Project root:** the folder that contains `setup.sh` / `setup.bat`, `backend/`, and `frontend/`. In this repository that is `llm-eval/llm-dashboard/`.

This document is the **main user guide**: what the tool is for, how it is built, how to install and run it on **Linux** and **Windows**, and which technologies it uses. **Score formulas and API details** start in [§ Metric definitions](#metric-definitions-research-abstract-alignment). For a Turkish **methodology** chapter (design, data, procedure, evaluation), see **`yontem.md`**.

---

## What this project aims to achieve

The dashboard helps you **compare outputs from different LLMs** (e.g. ChatGPT, Claude, Gemini) on the **same prompt** using:

- **Real toolchains** where possible: Kotlin and Flutter/Dart are analyzed with compile/analyze-style steps, not only text similarity.
- **Structured scores** along dimensions useful for research narratives: compilability, static analysis health, tooling efficiency, and prompt faithfulness (manual and/or optional AI-assisted).
- **Persistence** in a local SQLite database so runs are **repeatable and auditable** (shared `snippet_id`, history, optional “winner” views).

**This is not a benchmark with ground-truth labels.** Numbers are **heuristic** (tunable rules, subjective faithfulness). The goal is a **practical workflow**: paste prompt + code, run analysis, compare models, export or revisit runs later.

**Non-goals:** statistical proof of superiority, security certification, or treating optional AI commentary as an authoritative judge.

---

## How it works (high level)

1. You use the **Streamlit** web UI (`frontend/app.py`) to enter a **target language** (**Kotlin**, **Flutter**, or **Both**), a **snippet id** (logical label for the task), the **prompt**, and each model’s **code** (one row per stack when **Both**: Flutter/Dart and Kotlin for ChatGPT, Claude, Gemini — six boxes total; only the row(s) matching the setting are analyzed).
2. The UI sends **`POST /analyze`** to the **FastAPI** backend (`backend/main.py`).
3. The **analyzer** (`backend/analyzer.py`) builds a temporary project, runs the relevant tools (e.g. Dart analyzer, **kotlinc** for plain JVM Kotlin, **Detekt** for Kotlin, Flutter **pub get** rounds). Snippets that **import `android.*` / `androidx.*`** skip standalone **kotlinc** (no Android SDK in the temp sandbox); **Detekt** still runs. The backend then **scores** the run (`backend/paper_scoring.py`), including **`quality_composite_0_100`** for Compare/History winners.
4. Optional **AI commentary** (`backend/commentary.py`, **OpenRouter**) can add faithfulness-style scores and text when enabled and configured.
5. Results are stored under **`results/`** (SQLite by default) and shown in the UI; **History & winner** reads the same API.

| Component | Role |
|-----------|------|
| **FastAPI** (`backend/main.py`) | REST API: `/analyze`, `/results`, `/health/commentary`, etc. |
| **Streamlit** (`frontend/app.py`) | **LLM Dashboard** UI: Compare models, metrics tables, charts, history; snippet JSON in **Settings** (left column). |
| **SQLite** (`backend/database.py`) | Stores runs; same logical key **updates** an existing row instead of duplicating. |
| **Analyzer** (`backend/analyzer.py`) | Kotlin / Flutter temp projects, compile & static analysis, metrics JSON; Android-import Kotlin skips JVM `kotlinc`. |
| **Kotlin compiler** (`tools/kotlin/`, from `setup.sh` / `setup.bat`) | Bundled **kotlinc** for JVM Kotlin; override with **`KOTLIN_HOME`**. Requires **JDK** on `PATH`. |
| **Detekt** (`tools/detekt-cli.jar`) | Kotlin static analysis (JAR downloaded separately; see prerequisites). |
| **OpenRouter** (optional) | Chat completions for `auto_commentary` and health checks when `OPENROUTER_API_KEY` is set. |

The UI talks to the API over HTTP. Default base URL: **`http://127.0.0.1:8000`** (`API_BASE_URL` in env). If the API is not running, analyze actions fail until it is started.

---

## Streamlit UI layout

When you open the app (default **http://localhost:8501**):

1. **Title** — **LLM Dashboard** appears at the **top left**, above the tabs, with a short subtitle. The browser tab title is also **LLM Dashboard**. Title and subtitle colors follow the **Streamlit theme** (Settings → Theme): in **dark** mode the heading uses **light text** for contrast; in **light** mode it uses dark text.
2. **Tabs** — **Compare models** and **History & winner** sit directly under the title.
3. **Compare models** uses three columns:
   - **Left — Settings:** target language (**Kotlin** / **Flutter** / **Both**), **Snippet ID**, **Snippet bundle** (**Download snippet (.json)** and **Browse / upload snippet (.json)**), optional **Use AI for task faithfulness & commentary**, and the read-only AI output text area when enabled.
   - **Center — Prompt and model outputs:** shared prompt; **Flutter (Dart)** row (three columns: ChatGPT, Claude, Gemini) and/or **Kotlin** row (same), depending on the language setting; **COMPARE MODELS**.
   - **Right — Live analysis results:** comparison table, **Altair** bar charts (when **Both** is selected, **Flutter** bars use **blue**, **Kotlin** bars use **orange**), and expandable full reports per run key (e.g. `ChatGPT (Kotlin)`).

Snippet JSON is **version 2** by default: `version`, `snippet_id`, `target_language` (including **`Both`**), `prompt`, plus `code_flutter_*` and `code_kotlin_*` keys. **Version 1** files with `code_chatgpt` / `code_claude` / `code_gemini` still load (mapped by `target_language`). Use them to re-run the same inputs later without re-pasting. **Download** saves as **`<snippet_id>.json`** when **Snippet ID** is non-empty (characters outside `[A-Za-z0-9_.-]` are replaced with `_`; max length truncated for safety). If Snippet ID is empty, the file is named **`llm-eval-snippet.json`**.

---

## Technologies

| Layer | Technology |
|-------|------------|
| Language | **Python** 3.10+ (3.12+ recommended) |
| Web API | **FastAPI**, **Uvicorn** |
| UI | **Streamlit** |
| Data / tables | **Pandas** (UI tables), **SQLite** (persistence) |
| Charts (Compare) | **Altair** (grouped bars by language when comparing **Both**) |
| HTTP client | **Requests** (frontend → API) |
| Optional AI | **OpenRouter** (OpenAI-compatible HTTP API; model via `OPENROUTER_MODEL`) |
| Kotlin analysis | **kotlinc** (`tools/kotlin` after setup, or `KOTLIN_HOME` / `PATH`), **Detekt** (CLI JAR), **JDK** for `kotlinc` |
| Flutter analysis | **Flutter / Dart** SDK on `PATH` (`flutter`, `dart`) |

---

## Prerequisites

- **Python** 3.10+ with `pip` (on Windows the `python` launcher is used by `setup.bat`).
- **Git** (to clone the repo) — optional if you already have the sources.
- **Kotlin path:** run **`setup.sh`** or **`setup.bat`** to install the **Kotlin compiler** under **`tools/kotlin/`** (optional env **`KOTLIN_VERSION`** on Linux/macOS). A **JDK 17+** must be on `PATH` (`java`). Place **`detekt-cli.jar`** in `tools/` ([Detekt releases](https://github.com/detekt/detekt/releases)), or set **`DETEKT_JAR`** in `.env` / `local.env`. Optional **`KOTLIN_HOME`** overrides the bundled layout.
- **Flutter path:** install **Flutter/Dart** and ensure `flutter` and `dart` are on `PATH` when analyzing Flutter snippets.
- **Optional:** **[OpenRouter](https://openrouter.ai)** API key for AI commentary and `/health/commentary`.

---

## Installation — Linux and macOS

From a terminal:

```bash
cd /path/to/llm-eval/llm-dashboard
chmod +x setup.sh start.sh stop.sh   # if needed
./setup.sh
source .venv/bin/activate
```

`setup.sh`:

- Checks that `backend/main.py` exists (correct project root).
- Creates **`.venv`** if missing and installs **`requirements.txt`**.
- Creates **`tools/`**, **`results/`**, **`temp/runs/`**, **`scripts/`**, etc.
- Downloads the **Kotlin JVM compiler** into **`tools/kotlin/`** if **`bin/kotlinc`** is missing (see **README**; Windows uses **`scripts/install-kotlin.ps1`**).
- Does **not** create or modify **`.env`** / **`local.env`** (you add those yourself).

Then configure environment files:

```bash
cp .env.example .env
cp local.env.example local.env   # recommended for secrets (gitignored)
```

Edit paths (`PROJECT_ROOT`, `RESULTS_DB`, `DETEKT_JAR`, …) and API keys. Loader order: **`.env`** then **`local.env`** (second file wins on duplicate keys). **Save files to disk**; running processes only see files on disk.

---

## Installation — Windows

1. Open **Command Prompt** or **PowerShell**.
2. `cd` to the dashboard folder (the one that contains `backend\main.py` and `setup.bat`).

```bat
setup.bat
```

This creates `.venv`, installs dependencies, and creates the same folders as `setup.sh`. If `python` is not found, install Python from [python.org](https://www.python.org/downloads/) and ensure **“Add python.exe to PATH”** was selected (or use the **py** launcher).

Activate the venv for manual commands:

```bat
.venv\Scripts\activate
```

Copy and edit config (same idea as Linux):

```bat
copy .env.example .env
copy local.env.example local.env
```

Download **`detekt-cli.jar`** into **`tools\`** for Kotlin analysis.

---

## Running — Linux and macOS

**Option A — one command (API + UI)**

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
./start.sh
```

- Starts **Uvicorn** on **`127.0.0.1:8000`** (override with `API_HOST` / `API_PORT`).
- Starts **Streamlit** on **`8501`** (override with `STREAMLIT_PORT`).
- Stopping Streamlit (Ctrl+C) attempts to stop the API child process.

**Stop stray processes / free ports** (from another terminal):

```bash
./stop.sh
```

**Option B — two terminals (easier debugging)**

Terminal 1 — API:

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — UI:

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
streamlit run frontend/app.py --server.port 8501
```

Open **http://localhost:8501** for the UI. API docs: **http://127.0.0.1:8000/docs**.

---

## Running — Windows

From the project folder (after `setup.bat`):

```bat
start.bat
```

This starts **Uvicorn** in the background (`start /B`) and then **Streamlit** in the foreground. Open **http://localhost:8501** (or the URL Streamlit prints).

- Override ports like Linux: set **`API_HOST`**, **`API_PORT`**, **`STREAMLIT_PORT`** before running `start.bat` (e.g. in the same Command Prompt session).
- After you close Streamlit, a **background Uvicorn** may still be running. If port **8000** stays busy, end the **python** / **uvicorn** process via **Task Manager** or:

```bat
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

(There is no `stop.bat` in the repo; `./stop.sh` is Unix-oriented.)

**Manual two-terminal run (Windows)**

```bat
.venv\Scripts\activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```bat
.venv\Scripts\activate
streamlit run frontend\app.py --server.port 8501
```

---

## Typical workflow in the UI

1. Open the **Compare models** tab (under the **LLM Dashboard** title).
2. In the **left Settings** column: choose **Kotlin**, **Flutter**, or **Both** and enter a **Snippet ID** (shared label for this task across models).
3. In **Snippet bundle** (still on the left): **Download snippet (.json)** to save the current inputs (download name = **Snippet ID** + `.json` when the id field is set), or **Browse / upload snippet (.json)** to restore prompt, six code areas (when using v2), id, and language.
4. In the **center** column: paste the **prompt** and the active **Flutter** and/or **Kotlin** code cells; run **COMPARE MODELS** (each non-empty cell for the selected language(s) triggers one **`POST /analyze`**).
5. Optionally enable **Use AI for task faithfulness & commentary (OpenRouter)** in Settings if you want AI-assisted scores/text (requires API key).
6. Use **History & winner** to load stored runs and compute the composite-based winner for a snippet.

For metric meanings and formulas, see the next section. For a shorter overview and troubleshooting table, see **`README.md`**. Turkish versions of this guide and of **metrics.md** are **`manual.tr.md`** and **`metrics.tr.md`**. Turkish methodology (design, data, procedure, evaluation) for papers: **`yontem.md`**.

---

## Tests and health checks

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
pytest
```

With the API running: **GET** `http://127.0.0.1:8000/health/commentary` checks OpenRouter when configured. CLI: `python -m backend.openrouter_check` from the project root (venv activated).

---

## Security and data

- **`.env`** and **`local.env`** are gitignored; prefer **`local.env`** for secrets.
- Database and temp runs live under **`results/`** and **`temp/`** by default.

---

# Metric definitions (research abstract alignment)

The remainder of this file defines **how scores are computed** and how they relate to the API and storage. These formulas are **heuristic** research aids, not statistical tests.

## 1. Compilability (0–100)

Binary: **100** if the project compiles (or the analyzer pipeline accepts the snippet as valid for the target toolchain), **0** otherwise. This matches “kodun derlenebilirliği” as a pass/fail gate.

**Android / AndroidX Kotlin:** If the snippet **imports `android.*`, `androidx.*`, or `com.google.android.*`**, standalone **kotlinc** is **not** executed (no Android SDK in the sandbox). The run records an **info** static flag (`kotlin_pipeline`); **`compilable`** is still **true** for pipeline purposes, but this does **not** certify a full **Gradle/device** build. **Detekt** still runs on the source file.

## 2. Static analysis health (0–100)

Starts at 100 and applies penalties from analyzer output:

- Prefer **structured counts** from the run (`analyzer_errors`, `analyzer_warnings`, `analyzer_infos`) when present.
- Otherwise approximate from parsed error log entries (severity `error`) and static flags (warnings vs infos), excluding `flutter_scaffold` tool noise.

Penalty (illustrative):

`100 − 12×errors − 3.5×warnings − 0.8×infos`, clamped to `[0, 100]`.

This mirrors “dart analyze / detekt ile statik analiz” as a continuous quality signal.

## 3. Tool efficiency (0–100)

Uses total wall time for the analysis run vs a cap (default **300_000 ms** = 5 minutes):

`100 × (1 − min(1, duration_ms / cap_ms))`

Missing duration defaults to **50** (neutral). Zero duration maps to **100**. This is a simple proxy for “verimlilik” in the toolchain sense (faster analysis at equal quality is better).

## 4. Prompt faithfulness (manual or optional AI, 1–5 → 0–100)

You can rate **1 (weak)** … **5 (strong)** adherence to the prompt in the UI. Stored as `faithfulness_score` in the database and mapped to 0–100 as `score × 20`.

If you **do not** rate faithfulness, `faithfulness_rated: false` in API responses and the optional `faithfulness_0_100` field may be omitted. The research composite then **omits** the faithfulness weight and **renormalizes** MI, nesting, and analyzer weights to sum to 1.0 (see §5).

### Optional AI commentary via OpenRouter (`auto_commentary`)

When `POST /analyze` is called with `auto_commentary: true` and **`OPENROUTER_API_KEY`** is set, the API calls **[OpenRouter](https://openrouter.ai)**’s OpenAI-compatible **`POST /v1/chat/completions`** with **`OPENROUTER_MODEL`**. The assistant returns JSON: **`faithfulness_score_0_100`** (0–100 vs the user’s task prompt), **`faithfulness_note`**, and **`metrics_comment`** (interpretation of compilable / error counts / analyzer stats / timing). Legacy responses may still send `faithfulness_score_1_5` (mapped to ~0–100 as ×20). That 0–100 value is stored for display and `paper_scores` when present and feeds the **faithfulness** ingredient of the research composite (§5).

Put the key in **`llm-dashboard/local.env`** (recommended; gitignored, not touched by `setup.sh`) and/or **`.env`**. The loader reads `.env` then **`local.env`** (second wins). `override=True` so file values replace empty shell exports (e.g. `export OPENROUTER_API_KEY=`). Optional: `OPENROUTER_BASE_URL`, `OPENROUTER_HTTP_REFERER`, `OPENROUTER_APP_TITLE` for OpenRouter attribution. **Restart uvicorn** after edits.

**Setup script:** `setup.sh` / `setup.bat` does **not** mention or access your secrets file (no existence check, no copy). It only creates the venv, runs `pip install`, and creates `tools/` / `results/` / `temp/` dirs. Maintain `.env` yourself; `.env.example` lists variable names only.

- If you **did not** set a manual faithfulness score, the AI estimate is used for `build_paper_scores` and persistence.
- If you **did** set a manual score, that value wins for scoring; the AI may still return an estimate for transparency.
- This is **not** a ground-truth judge; it is a cheap assist subject to model bias and quota limits. Failures (missing key, parse errors) populate `ai_commentary.error` without failing the analyze request.

Tune timeout with `COMMENTARY_TIMEOUT_SEC` (default 60). Commentary is stored under `metrics_json.ai_commentary`.

## 5. Compare / History winner: research composite (`quality_composite_0_100`)

The Streamlit **Compare models** banner and **History & winner** tool declare a winner using **`paper_scores.quality_composite_0_100`** (0–100, higher better). It is a weighted blend of four 0–100 ingredients:

| Ingredient | Meaning | Default weight |
|------------|---------|----------------|
| **MI** | Maintainability Index from **metrics.md §4** (clamped to [0, 100]); missing → neutral **50** | 0.30 |
| **Nesting** | Lower **avg_nesting_depth** is better: `max(0, min(100, 100 − 15×depth))`; missing → **50** | 0.10 |
| **Analyzer cleanliness** | Same penalty structure as §2 static health: `100 − 12×errors − 3.5×warnings − 0.8×infos` (structured counts from the run when present); clamped to [0, 100] | 0.30 |
| **Faithfulness** | Higher **faithfulness_0_100** when **faithfulness_rated**; if unrated, this axis is **excluded** and the other three weights are renormalized | 0.30 |

Composite = weighted average (faithfulness included only when rated). Implemented in **`backend/paper_scoring.py`** (`QUALITY_COMPOSITE_WEIGHTS`, `attach_quality_composite`, `recompute_full_paper_scores`).

## 6. Legacy `paper_scores` dimensions (API / export)

The API still builds **`metrics_json.paper_scores`** with 0–100 dimensions (compilability, static analysis health, tool efficiency, faithfulness) and **`composite_default_0_100`** for backward compatibility and JSON export. The dashboard **does not** use that legacy composite for the winner.

## API and storage

- `GET /health/commentary` runs a tiny OpenRouter chat completion (same stack as AI commentary) using `OPENROUTER_API_KEY` / `OPENROUTER_MODEL`. Deprecated alias: `GET /health/gemini`. The API reads **the saved file on disk**, not unsaved editor buffers—**save** after editing. Do not define `OPENROUTER_API_KEY=` twice; the **last** occurrence wins (a trailing empty line clears the key). CLI: `python -m backend.openrouter_check`.
- `POST /analyze` accepts optional `faithfulness_score_1_5`, `faithfulness_notes`, and `auto_commentary` (boolean).
- `PATCH /results/{id}` updates faithfulness and recomputes `paper_scores` in `metrics_json`.
- `GET /results` and `GET /results/{id}` return rows including `metrics.paper_scores` when present.
- Re-submitting the same `(llm_source, language, snippet_id, prompt, code)` **updates** the existing database row (same `id`) instead of failing, so you can re-run Compare on unchanged inputs.

## Limitations

- Faithfulness is subjective; use notes for auditability.
- Static penalties are tunable constants, not calibrated on a labeled dataset.
- Efficiency rewards speed without conditioning on correctness beyond what static analysis captures.
- **JVM Kotlin** compile uses **kotlinc** without an Android classpath; **Android-dependent** snippets skip that step (see §1).
- **Compare / History winner** uses **`quality_composite_0_100`** (heuristic blend); it is **not** a statistical test of model superiority.

---

## Documentation map

| Document | Contents |
|----------|----------|
| **This file (`manual.md`)** | User guide (install/run Linux & Windows), UI layout, goals, architecture, technologies; metric formulas and API notes |
| **`manual.tr.md`** | Turkish translation of this user guide |
| **`metrics.md`** | Cross-language code-quality metrics (research definitions) |
| **`metrics.tr.md`** | Turkish translation of **metrics.md** |
| **`metricguide.md`** | Implementation hints for developers (Cursor / codebase) |
| **`README.md`** | Quick overview, troubleshooting table, links back here for formulas |
| **`yontem.md`** | Turkish methodology: architecture, data, procedure, evaluation (paper-oriented) |
