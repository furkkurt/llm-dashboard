# LLM evaluation metrics (research abstract alignment)

This dashboard scores model outputs along dimensions discussed in the evaluation abstract (compilability, static analysis, tooling efficiency, and manual prompt faithfulness). The formulas below are **heuristic** research aids, not statistical tests.

## 1. Compilability (0–100)

Binary: **100** if the project compiles (or the analyzer pipeline accepts the snippet as valid for the target toolchain), **0** otherwise. This matches “kodun derlenebilirliği” as a pass/fail gate.

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

If you **do not** rate faithfulness, the default composite uses a **neutral 50** on that axis (`faithfulness_rated: false` in API responses). The optional `faithfulness_0_100` field is then omitted.

### Optional Gemini commentary (`auto_commentary`)

When `POST /analyze` is called with `auto_commentary: true` and `GOOGLE_API_KEY` is set, the API runs a separate **Gemini** call (same model family as `GOOGLE_MODEL`, default `gemini-2.0-flash`) that returns JSON: an estimated `faithfulness_score_1_5`, a short `faithfulness_note`, and a plain-language `metrics_comment` on compile/static/timing signals.

- If you **did not** set a manual faithfulness score, the AI estimate is used for `build_paper_scores` and persistence.
- If you **did** set a manual score, that value wins for scoring; the AI may still return an estimate for transparency.
- This is **not** a ground-truth judge; it is a cheap assist subject to model bias and quota limits. Failures (missing key, parse errors) populate `ai_commentary.error` without failing the analyze request.

Tune timeout with `COMMENTARY_TIMEOUT_SEC` (default 60). Commentary is stored under `metrics_json.ai_commentary`.

## 5. Composite score (default weights)

Weighted average of the four dimensions. Default weights (sum = 1.0):

| Dimension        | Weight |
|-----------------|--------|
| Compilability   | 0.30   |
| Static analysis | 0.35   |
| Efficiency      | 0.15   |
| Faithfulness    | 0.20   |

The **History & winner** tab lets you choose different weights; scores are renormalized if your weights do not sum to 1.

`composite_default_0_100` in the API uses these defaults and is persisted inside `metrics_json.paper_scores`.

## API and storage

- `POST /analyze` accepts optional `faithfulness_score_1_5`, `faithfulness_notes`, and `auto_commentary` (boolean).
- `PATCH /results/{id}` updates faithfulness and recomputes `paper_scores` in `metrics_json`.
- `GET /results` and `GET /results/{id}` return rows including `metrics.paper_scores` when present.
- Re-submitting the same `(llm_source, language, snippet_id, prompt, code)` **updates** the existing database row (same `id`) instead of failing, so you can re-run Compare on unchanged inputs.

## Limitations

- Faithfulness is subjective; use notes for auditability.
- Static penalties are tunable constants, not calibrated on a labeled dataset.
- Efficiency rewards speed without conditioning on correctness beyond what static analysis captures.
