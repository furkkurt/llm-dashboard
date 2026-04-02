# LLM evaluation dashboard

A small research tool for **comparing LLM-generated code** (e.g. ChatGPT, Claude, Gemini) on the same prompt. It runs **real toolchains** where possible—compile/analyze steps for **Kotlin** and **Flutter**—and turns the outcome into **structured scores** aligned with an evaluation narrative (compilability, static analysis, tooling efficiency, prompt faithfulness). A **Streamlit** UI drives day-to-day use; a **FastAPI** backend performs analysis and persists results.

**This is not a benchmark suite with ground-truth labels.** Scores are **heuristic** (tunable constants, subjective faithfulness). The goal is a **repeatable, auditable workflow**: same snippet id, same prompt, comparable metrics across models, exportable history.

---

## Goals

- **Compare models fairly on the same task** using one prompt and side-by-side outputs.
- **Measure what the toolchain actually sees**: does it compile? what do static analyzers report? how long did the run take?
- **Support human judgment** on prompt adherence (faithfulness sliders + optional AI-assisted commentary).
- **Persist runs** in SQLite so you can revisit results, patch faithfulness later, and explore “history & winner” style views in the UI.
- **Stay local-first**: you control API keys, data stays on disk under `results/` unless you export.

**Non-goals:** proving statistical significance, replacing security review, or treating optional AI commentary as authoritative.

---

## How it is built (architecture)

| Piece | Role |
|--------|------|
| **`backend/main.py`** | FastAPI app: `/analyze`, `/generate`, `/results`, `/health/commentary`, etc. |
| **`backend/analyzer.py`** | Orchestrates Kotlin/Flutter temp projects, compile/analyze, timing metrics. |
| **`backend/database.py`** | SQLite (`results/results.db` by default); upsert on same logical run key. |
| **`backend/paper_scoring.py`** | Builds 0–100 dimension scores + default composite from analyzer output. |
| **`backend/commentary.py`** | Optional OpenRouter chat → JSON when `auto_commentary=true`. |
| **`backend/openrouter_client.py`** | OpenAI-compatible client pointed at OpenRouter’s base URL. |
| **`frontend/app.py`** | Streamlit UI: paste prompt/code, call API, show scores, history, compare. |
| **`runners/`** | Helpers (e.g. Detekt invocation). |
| **`temp/runs/`** | Ephemeral project trees per analysis. |
| **`tools/detekt-cli.jar`** | Required for Kotlin static analysis (you download the JAR; not bundled). |

The UI talks to the API over HTTP (`API_BASE_URL`, default `http://127.0.0.1:8000`). If the API is down, analyze actions fail until it is back up.

---

## Project root

Use the directory that contains **`setup.sh`**, **`backend/main.py`**, and **`frontend/app.py`**.

In this repository that path is:

`llm-eval/llm-dashboard/`

There is **no** nested `llm-dashboard/llm-dashboard` in source control. If your machine shows a different layout, always `cd` into the folder that contains `setup.sh`.

---

## Prerequisites

- **Python 3.10+** (3.12+ recommended; project uses a local `.venv`).
- **Kotlin path**: **`setup.sh`** / **`setup.bat`** download the **Kotlin JVM compiler** into **`tools/kotlin/`** (used as `kotlinc`). You still need a **JDK 17+** on `PATH` (`java`). For static analysis, add **`tools/detekt-cli.jar`** from [Detekt releases](https://github.com/detekt/detekt/releases) (and set `DETEKT_JAR` if needed—see `.env.example`). Optional: set **`KOTLIN_HOME`** to override the bundled compiler layout.
- **Flutter path**: a working **Flutter/Dart** SDK on `PATH` so `flutter` / `dart` can run (for Flutter snippets).
- **Optional**: **[OpenRouter](https://openrouter.ai)** API key (`OPENROUTER_API_KEY`) for AI commentary, `/health/commentary`, and the UI **Generate** lane labeled “Gemini” (still uses your chosen `OPENROUTER_MODEL`, often a Google model slug).

---

## First-time setup

```bash
cd /path/to/llm-eval/llm-dashboard
./setup.sh
source .venv/bin/activate
```

`setup.sh` will:

1. Verify you are in the real project root (`backend/main.py` exists).
2. Create **`.venv`** if missing and `pip install -r requirements.txt`.
3. Create **`tools/`**, **`results/`**, **`temp/runs/`**, etc.
4. Download **Kotlin `kotlinc`** into **`tools/kotlin/`** if missing (override version with env **`KOTLIN_VERSION`**). Warns if **`java`** is not on `PATH`.

Windows **`setup.bat`** does the same (Kotlin via **`scripts/install-kotlin.ps1`**).

It does **not** read, create, or delete **`.env`** or **`local.env`**. You add those yourself.

Copy examples and edit:

```bash
cp .env.example .env
# Recommended for secrets (gitignored; loaded after .env):
cp local.env.example local.env
```

Adjust paths in `.env` (`PROJECT_ROOT`, `RESULTS_DB`, `DETEKT_JAR`, …) to match your machine. Put **API keys** in **`local.env`** when possible so a regenerated `.env` does not wipe secrets.

---

## How to run (day to day)

### Option A — one command (API + UI)

From the project root, with venv activated:

```bash
./start.sh
```

This script:

1. Starts **uvicorn** on **`127.0.0.1:8000`** (override with `API_HOST` / `API_PORT`).
2. Starts **Streamlit** on **`8501`** (override with `STREAMLIT_PORT`).
3. When you stop Streamlit (Ctrl+C), it tries to kill the uvicorn child process.

To stop without leaving listeners (from another terminal):

```bash
./stop.sh
```

Uses **`fuser`** or **`lsof`** to free `API_PORT` and `STREAMLIT_PORT`, then `pkill` patterns for this app’s uvicorn/streamlit. Set the same env vars as `start.sh` if you use non-default ports.

### Option B — two terminals (easier debugging)

**Terminal 1 — API**

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — UI**

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
streamlit run frontend/app.py --server.port 8501
```

Open the Streamlit URL (usually **http://localhost:8501**). API docs: **http://127.0.0.1:8000/docs**.

### Environment loading

- Backend and Streamlit load **`.env`** then **`local.env`** (second file wins on duplicate keys). See `backend/env_bootstrap.py`.
- **Save files to disk** after editing; unsaved editor buffers are invisible to the processes.
- After changing env files, **restart uvicorn** (and Streamlit if you rely on env at its startup).

---

## Typical workflow in the UI

1. Choose target language (**Kotlin** or **Flutter**).
2. Set **LLM source** and **snippet id** (shared id lets you align the same task across models).
3. Paste the **prompt** and each model’s **code** (Flutter: full outputs help; fenced `main.dart` / `pubspec.yaml` are handled).
4. Optionally set **faithfulness** sliders or enable **auto faithfulness + AI commentary (OpenRouter)**.
5. **Analyze** / **Compare** — results go to SQLite and appear in metrics + **History & winner**.

Compare/History **winner** = highest **research composite** (MI + nesting + analyzer cleanliness + faithfulness; see `manual.md` §5).

---

## API overview

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Service metadata + links |
| GET | `/health/commentary` | Tiny OpenRouter chat; verifies `OPENROUTER_API_KEY` / model |
| POST | `/analyze` | Run toolchain + scoring; optional `auto_commentary` |
| POST | `/generate` | Optional LLM generation (OpenAI / Anthropic / OpenRouter for “Gemini” lane) |
| GET | `/results` | List stored runs (filters optional) |
| GET | `/results/{id}` | One row |
| PATCH | `/results/{id}` | Update faithfulness / notes; recompute paper scores |

Full metric definitions, weights, and limitations: **[manual.md](manual.md)**.

---

## Verify OpenRouter / keys

With the API running:

- Browser: **http://127.0.0.1:8000/health/commentary** — `ok: true` means OpenRouter returned a reply for `OPENROUTER_MODEL`. Legacy alias: `/health/gemini`.
- CLI from project root: `python -m backend.openrouter_check`  
  Response includes paths for `.env` / `local.env` presence (for debugging empty keys).

---

## Tests

```bash
cd /path/to/llm-eval/llm-dashboard
source .venv/bin/activate
pytest
```

`pytest.ini` sets `pythonpath` so `backend` imports resolve.

---

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| **Port 8000 in use** | Find process: `ss -ltnp \| grep 8000` or `lsof -i :8000`, then `kill <pid>`, or change `API_PORT`. |
| **Streamlit only, analyze fails** | Start uvicorn; UI calls the API over `API_BASE_URL`. |
| **Ports still busy after Ctrl+C** | Run `./stop.sh` (same `API_PORT` / `STREAMLIT_PORT` as `start.sh`). |
| **OPENROUTER_API_KEY “empty”** | Save `.env` / `local.env`; use `local.env` for keys; avoid a **second** empty `OPENROUTER_API_KEY=` line after a good one (last wins). |
| **`[Errno 2] kotlinc` / Kotlin won’t compile** | Run **`./setup.sh`** or **`setup.bat`** so **`tools/kotlin/bin/kotlinc`** exists; install a **JDK** and ensure **`java`** is on `PATH`. Optional **`KOTLIN_HOME`**. |
| **Kotlin analyze missing Detekt** | Place `detekt-cli.jar` under `tools/` or set `DETEKT_JAR`. |
| **`.env` “disappears”** | Nothing in `setup.sh` removes it; check for manual `cp .env.example .env`, sync tools, or other scripts. Prefer **`local.env`** for secrets. |

---

## Security & data

- **`.env`** and **`local.env`** are gitignored; **`local.env`** is recommended for secrets.
- **Rotate keys** if they were committed, pasted in chat, or exposed in screenshots.
- Database and logs live under **`results/`** and **`temp/`** by default—back up or purge according to your policy.

---

## Documentation map

| Doc | Contents |
|-----|----------|
| **This README** | Goals, architecture, run instructions, troubleshooting |
| **[manual.md](manual.md)** | Score formulas, MI winner rule, API/storage details, OpenRouter commentary behavior |
| **`.env.example` / `local.env.example`** | Variable names and layout hints |
