# Conference paper draft (IEEE-style layout) — research framing

**Note:** Structured for the IEEE-style Word template (`Başlıksız.docx`): apply **Paper title** / **Heading 1–5**, remove gray template boilerplate before submission.

**Naming note (important):** All experiments reported here used **DeepSeek** as the second commercial model alongside **ChatGPT** and **Gemini**. Exported JSON under `results/` may still show the legacy UI column label **`Claude`** in keys and in `llm_source` fields; in this manuscript, that lane is referred to consistently as **DeepSeek**.

**Artifacts:** `results/compare-analysis-Instagram_Clone_Level1 (1).json`, `…Level2…`, `…Level3…` (plus matching snippet JSON files).

---

## Paper title *(Word style: paper title)*

**Comparing LLM-Generated Native and Cross-Platform Mobile Code: A Three-Level Instagram-Clone Prompt Study with Tool-Grounded Metrics**

---

## Authors and affiliations *(replace)*

Line 1: First Author Name  
Line 2: Department, Organization  
Line 3: City, Country  
Line 4: email / ORCID  

---

## Abstract—

Large language models (LLMs) are now embedded across software workflows from authoring to debugging, yet it remains poorly understood how they behave when targeting **Kotlin** (OS-tight, native Android stacks) versus **Flutter/Dart** (hybrid, single codebase across divergent device ecosystems). Hybrid stacks must reconcile Android’s vast hardware heterogeneity with iOS’s more constrained environment; whether LLMs produce **optimized, “aware”** code in that tension is still an open question. This paper reports a controlled **coding-exam** design: the same three frontier models—**ChatGPT**, **DeepSeek**, and **Gemini**—answer a **three-level**, progressively harder **Instagram-clone** prompt family (Level 1: feed UI, scrolling, and refresh; Level 2: added hardware-oriented and structural demands; Level 3: richer data and interaction complexity). To reduce evaluator subjectivity, outputs were scored with our **LLM Dashboard** pipeline: **compilability**, **static analysis** (Dart analyzer / Detekt), cross-language **maintainability proxies**, and optional **prompt-faithfulness** commentary. Early aggregated scores show **level-dependent divergence**: simple UI tasks remain largely analyzable across stacks, while deeper prompts depress maintainability indices and composites—especially on Flutter at Level 2–3—consistent with the hypothesis that **cross-platform abstraction** invites **shallower** fixes unless the model invests in dependency and architecture detail. The **scientific aim** is not only to rank models, but to **institutionalize evidence** about which stack (Kotlin vs Flutter) pairs better with which LLM under transparent, repeatable measurement—supporting a grounded debate on the place of next-generation AI coding assistants.

---

## Keywords—

Large language models, Kotlin, Flutter, mobile development, static analysis, maintainability, Instagram clone, comparative study, reproducible evaluation, hybrid platforms

---

## I. INTRODUCTION

### A. Motivation and problem

LLMs are no longer optional accessories in software engineering; they shape how developers draft UI, wire networking, and iterate on bugs. For **mobile**, two dominant idioms coexist: **native Kotlin** (often Jetpack Compose) with **direct platform APIs**, and **Flutter**, which trades some platform specificity for a **shared abstraction layer**. Prior work benchmarks code LLMs heavily on **Python-centric** completion or repository tasks with hidden tests [7], [8]; less is published on **paired, cross-stack** generation from **identical natural-language briefs**, especially when prompts deliberately escalate from **UI** to **hardware-adjacent** concerns and **non-trivial state**. We argue that gap matters for practitioners choosing **where** to deploy an LLM—native versus hybrid—and for researchers who need **traceable** evidence rather than anecdote.

### B. Gap and research questions

**RQ1:** Under identical prompts, how do **ChatGPT**, **DeepSeek**, and **Gemini** differ in **tool-visible quality** (compile/analyze outcomes, MI-like metrics, composite score) on **Flutter vs Kotlin**?  
**RQ2:** Does **prompt difficulty** (three Instagram-clone levels) interact with **language choice**—e.g., does Flutter encourage **shallower** dependency or scaffold choices when complexity rises, as hypothesized for abstraction-heavy stacks?  
**RQ3:** Can a small, open **dashboard** turn ad-hoc model comparisons into **auditable** runs suitable for longitudinal or classroom study?

### C. Contributions

We contribute (1) a **three-level Instagram-clone** benchmark narrative grounded in real exports; (2) **quantitative snapshots** from the dashboard on **compilability**, **static health**, and **research composite** scores; (3) explicit **limitations** (heuristic composite, optional AI judge, Android-aware compile caveats); (4) a **reproducibility path** via the public codebase and `results/` JSON.

**Organization:** Section II positions related work. Section III describes the prompt ladder, apparatus, and metrics. Section IV reports measured outcomes from stored runs. Section V interprets results against hypotheses. Section VI concludes.

---

## II. RELATED WORK

### A. Maintainability and static analysis

Cyclomatic complexity [1], MI variants [2], and static-warning taxonomies [3] underpin many industrial quality gates. Surveys link metrics to defect prediction [4], [5]; we borrow **measurement discipline** without claiming predictive validity on LLM snippets.

### B. LLM code evaluation

Large-scale studies stress functional correctness [7], [8]; naturalness arguments motivate statistical models of code [6], [9]. Our work is **complementary**: we foreground **IDE-grade** signals on **short, pasted** multi-language outputs.

### C. Positioning

**TABLE I.** *Contrast (illustrative).*

| Tradition | Unit | This study |
|-----------|------|------------|
| Repo-scale benchmarks [7] | Functions / repos | Single-file / snippet Instagram tasks |
| MI literature [2] | Mature modules | LLM-generated greenfield paste |
| **Our dashboard** | Prompt × model × language × level | Tool traces + composite |

---

## III. METHODOLOGY

### A. Prompt ladder (Instagram clone, three levels)

**Level 1 (`Instagram_Clone_Level1`):** Flutter or Kotlin single-artifact Instagram-style **feed**: generic images (e.g., Picsum), **endless scroll** with pagination, **pull-to-refresh** from top—minimal but non-trivial UI and networking.  
**Level 2 (`Instagram_Clone_Level2`):** Same product theme with **escalated** requirements (hardware-adjacent features and richer structure per the study protocol—exact wording is preserved in repository JSON `inputs.prompt`).  
**Level 3 (`Instagram_Clone_Level3`):** **Complex data and interaction** demands (again, canonical text in JSON exports).

Each level was executed in **Both** language mode: six cells (Flutter + Kotlin × three models). **Models:** ChatGPT, **DeepSeek** (second column), Gemini.

### B. Instrumentation (LLM Dashboard)

A **Streamlit** client sends `POST /analyze` to **FastAPI**; the backend materializes ephemeral Flutter/Kotlin projects, runs **`flutter pub get` / `dart analyze`** or **`kotlinc` + Detekt`**, merges **cross-language metrics** (LOC, cyclomatic complexity, Halstead proxies, MI, nesting), and computes **`quality_composite_0_100`** (MI, nesting, analyzer cleanliness, optional faithfulness with renormalization). Runs persist to **SQLite**; exports used here are **`compare-analysis-*.json`** under `results/`. Optional OpenRouter commentary supplied **faithfulness_0_100** hints; those values are **auxiliary**, not ground truth [10].

### C. Ethics and threats

No human subjects; prompts and code are **researcher-supplied**. Threats include: (i) **API version drift** between collection dates; (ii) **single-shot** generations (no temperature sweep); (iii) Android-heavy Kotlin may skip standalone `kotlinc`—interpret **compilability** cautiously; (iv) **DeepSeek** mis-tagged as `Claude` in legacy exports (see header note).

---

## IV. RESULTS (from archived `compare-analysis` exports)

All numbers below are **recomputed from** `results/compare-analysis-Instagram_Clone_Level*.json` (April 2026 exports). **“DeepSeek”** denotes the second lane (legacy key `Claude` in files).

### A. Level 1 — baseline UI feed

| Model (lane) | Flutter: composite (0–100) | Flutter: MI | Kotlin: composite | Kotlin: MI | Notes |
|--------------|-----------------------------|---------------|---------------------|------------|--------|
| ChatGPT | 86.71 | 72.24 | 77.05 | 55.00 | Both stacks analyzable |
| **DeepSeek** | **80.28** | **52.85** | **70.00** | **30.29** | Kotlin MI lowest in row |
| Gemini | 75.62 | 57.88 | 71.07 | 28.13 | Flutter **not** compilable (`compilable=false`, 1 analyzer error) |

*Interpretation (descriptive):* At the easiest level, **Flutter** remains largely **compilable** for two models; **Gemini’s Flutter** already fails compile in this snapshot. **Kotlin MI** for **DeepSeek** and **Gemini** is **well below** ChatGPT, foreshadowing native-stack variance.

### B. Level 2 — escalated complexity

| Model | Flutter: composite | Flutter: MI | Flutter: errors | Kotlin: composite | Kotlin: MI | Kotlin: errors |
|-------|---------------------|-------------|-----------------|---------------------|------------|----------------|
| ChatGPT | 65.73 | 11.81 | 0 | 63.11 | 8.46 | 0 |
| **DeepSeek** | **57.68** | **47.33** | **4** | **67.65** | **22.50** | **0** |
| Gemini | 86.55 | 72.65 | 0 | 69.20 | 47.33 | 1 |

*Interpretation:* **DeepSeek Flutter** becomes **non-compilable** with **four** analyzer errors; composites and MI **collapse** for ChatGPT Flutter (MI ≈ 11.8) despite `compilable=true`, showing **static-health / MI tension** with the composite. **Gemini** recovers strongly on Flutter this level—**level–model interaction** is evident.

### C. Level 3 — high complexity

| Model | Flutter: composite | Flutter: MI | Kotlin: composite | Kotlin: MI |
|-------|---------------------|-------------|---------------------|------------|
| ChatGPT | 56.03 | **−7.11** | 58.30 | **−8.44** |
| **DeepSeek** | **49.59** | **34.42** | **65.17** | **21.98** |
| Gemini | **83.73** | 73.03 | **79.05** | 60.98 |

*Interpretation:* **Negative MI** for ChatGPT on **both** stacks indicates **extreme** size/complexity trade-offs under the heuristic MI clamping—not “better than zero maintainability” in an absolute sense, but a **warning flag** for readers. **Gemini** leads composites at this level; **DeepSeek Flutter** again fails compile (`compilable=false`, four errors in export).

### D. Synthesis vs hypotheses

**H1 (simple UI):** Mostly supported—all lanes produced analyzable or near-analyzable artifacts at Level 1 except **Gemini Flutter**.  
**H2 (native advantage under stress):** Partially supported: **Kotlin** sometimes preserves **higher composite** than **Flutter** for the same model (e.g., **DeepSeek** Level 3: 65.17 vs 49.59), but **counterexamples** (Gemini Level 3 Flutter highest) show **model×level** dominates naive “native always wins.”  
**H3 (Flutter shallowness):** Partially supported via **compile failures** and **error spikes** on Flutter for **DeepSeek** at Levels 2–3 and **MI collapses** for ChatGPT when prompts deepen—not exclusively a “Flutter problem,” but consistent with **abstraction-layer** risk.

---

## V. DISCUSSION

The **primary objective** is **not** a leaderboard slogan (“best LLM”) but an **evidence workflow**: identical briefs, frozen exports, and **multi-signal** scoring. **DeepSeek’s** Flutter regressions illustrate how **dependency and API choices** explode under pressure—exactly where human review and CI must catch gaps the composite only **summarizes** [11].

**Limitations:** (1) **Single** generation per cell (no variance bands); (2) **Faithfulness** scores come from an **auxiliary** LLM judge when enabled—report separately from toolchain facts; (3) **MI** on tiny or extreme snippets can go **negative**—caption carefully; (4) **Labeling debt** in JSON (`Claude` vs DeepSeek) must be cleaned in a repository pass to avoid confusion.

---

## VI. CONCLUSION

We framed LLM evaluation as a **mobile, cross-stack research problem**, executed a **three-level Instagram-clone** prompt ladder across **ChatGPT**, **DeepSeek**, and **Gemini**, and quantified outcomes with a **tool-grounded dashboard**. Results show **strong level and model interactions**; native Kotlin is **not** universally superior, but **DeepSeek’s Flutter path** documents concrete **compile/analyze failure modes** under escalation—useful data for teams weighing **hybrid vs native** LLM workflows. Future work: repeated trials with seeds, Gradle-integrated Android builds, cleaned **export provenance**, and user studies correlating composite scores with **post-merge defect** rates.

---

## ACKNOWLEDGMENT *(optional)*

*(Omit or add funding / compute credits per venue.)*

---

## REFERENCES

[1] T. J. McCabe, “A complexity measure,” *IEEE Trans. Softw. Eng.*, vol. SE-2, no. 4, pp. 308–320, Dec. 1976, doi: 10.1109/TSE.1976.233838.

[2] D. Coleman *et al.*, “Using metrics to evaluate software system maintainability,” *Computer*, vol. 27, no. 8, pp. 44–49, Aug. 1994, doi: 10.1109/2.303623.

[3] N. Ayewah *et al.*, “Using static analysis to find bugs,” *IEEE Softw.*, vol. 25, no. 5, pp. 22–29, 2008, doi: 10.1109/MS.2008.130.

[4] T. Menzies *et al.*, “Data mining static code attributes to learn defect predictors,” *IEEE Trans. Softw. Eng.*, vol. 33, no. 1, pp. 2–13, Jan. 2007, doi: 10.1109/TSE.2007.256946.

[5] D. Radjenović *et al.*, “Software fault prediction metrics: A systematic literature review,” *Inf. Softw. Technol.*, vol. 55, no. 8, pp. 1397–1418, 2013, doi: 10.1016/j.infsof.2013.02.009.

[6] A. Hindle *et al.*, “On the naturalness of software,” *Commun. ACM*, vol. 59, no. 5, pp. 122–131, 2016, doi: 10.1145/2902362.

[7] M. Chen *et al.*, “Evaluating large language models trained on code,” arXiv:2107.03374, 2021.

[8] J. Austin *et al.*, “Program synthesis with large language models,” arXiv:2108.07732, 2021.

[9] M. Allamanis *et al.*, “A survey of machine learning for big code and naturalness,” *ACM Comput. Surv.*, vol. 51, no. 4, 2018, doi: 10.1145/3212695.

[10] E. M. Bender and T. Gebru, “On the dangers of stochastic parrots,” in *Proc. FAccT*, 2021, doi: 10.1145/3442188.3445922.

[11] N. Brown *et al.*, “Managing technical debt in software engineering,” *ACM SIGSOFT SEN*, vol. 35, no. 5, pp. 51–60, 2010, doi: 10.1145/1838687.1838701.

---

## APPENDIX

**Data path:** `llm-eval/results/` — `compare-analysis-Instagram_Clone_Level{1,2,3}*.json` and companion snippet JSON files.  
**Repository (placeholder):** `https://github.com/<your-org>/llm-eval`  

**Housekeeping:** Re-export or post-process JSON to set `llm_source` to **DeepSeek** for the second lane and regenerate AI commentary labels for consistency with this manuscript.

---

## Template compliance checklist *(delete before submission)*

- [ ] Remove IEEE template help text from Word  
- [ ] Figures: architecture from `yontem.md` + example UI screenshots if allowed  
- [ ] Table captions explain MI negative values  
- [ ] References complete; citation style `[n]` throughout  

---

*End of draft.*
