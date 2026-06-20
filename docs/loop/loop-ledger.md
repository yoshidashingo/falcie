# Loop Ledger

Append-only record of every loop run, newest first. One entry per loop. This is
the repo's persistent memory of *what was attempted, what proved it, and what we
learned* — so the project does not repeat the same accident twice.

Entry format: see [`goal-contract-template.md`](goal-contract-template.md). Keep
entries short; link to PRs/commits/ADRs for detail.

---

## L-008 — Needle-in-a-haystack long-context eval

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-21 / 2026-06-21
- **Goal:** Add the long-context retrieval evaluation axis the roadmap, `m2-plan.md`,
  and ADR-004 all call for (context extension must be validated with needle-in-a-
  haystack). Dependency-free: synthesize NIAH tasks (a unique "needle" fact embedded
  in filler at a given depth, with a retrieval question) and score a predictor across
  a length × depth grid, producing a retrieval matrix. Ready for a real model (M2+) to
  plug into; reference predictors validate it without a model.
- **Inputs:** `scripts/evals/metrics.py` (includes/exact), `scripts/evals/harness.py`,
  `docs/evaluation-plan.md`, `docs/architecture-decisions.md` (ADR-004), `docs/m2-plan.md`.
- **Acceptance criteria:**
  - [x] `scripts/evals/niah.py` (stdlib): deterministic NIAH task generation over a
        length × depth grid (needle embedded at the right depth; answer retrievable),
        and a runner aggregating retrieval accuracy **by length and by depth**.
  - [x] Reference predictors validate the harness without a model: **gold** retrieves
        every needle (accuracy 1.0), **empty** retrieves none (0.0), and a
        **prefix-window** stand-in shows real structure (retrieves short/shallow,
        misses long/deep) — proving the matrix isn't trivially flat.
  - [x] `python3 scripts/run_checks.py` exits 0 with a NIAH smoke wired in (gold=1.0).
  - [x] Unit tests: task-gen correctness (needle present, answer retrievable),
        gold=1.0 / empty=0.0, window predictor's length×depth structure, determinism.
  - [x] `evals/README.md` / `docs/evaluation-plan.md` note the long-context (NIAH) layer.
- **Forbidden zones:** committing large generated corpora; claiming model capability;
  any third-party dependency.
- **Evidence:** the retrieval matrix (gold=1.0, empty=0.0, window structured); gate;
  reviewer pass.
- **Stop conditions:** pass per criteria; timeout as usual.
- **Verification:** gate green (`all 13 checks passed`, incl. `niah_smoke` asserting
  gold accuracy 1.0; 9 NIAH tests). Independent code-reviewer (separate context, ran
  the eval + adversarial tautology/false-positive probes): **APPROVE-WITH-NITS** —
  both required gates PASS: the matrix has real length×depth structure (window stand-in
  0.8, long-context degrades by depth) and there are no false-positive needle matches
  from filler; the eval is anti-tautological (the answer is in the prompt and vanishes
  when the needle is removed). Its MEDIUM (id collision on sub-1% depths) + LOWs
  (duplicate-cell overwrite, unused ROOT) were then fixed: lossless depth ids +
  dedup/sort of the grid, with regression tests.
- **Lessons:**
  - A NIAH eval is only worth anything if it is (1) **anti-tautological** — the answer
    is embedded in the prompt and provably absent once the needle is removed — and
    (2) **non-flat** — a model-free `window` predictor must show real length×depth
    structure, so the gate would catch a regression that flattened the eval.
  - Deterministic synthesis (sha1, no RNG) keeps the eval reproducible in the gate.
  - When a grid is parameterized, make cell ids lossless and dedup the grid, or two
    near-equal coordinates silently conflate.

---

## L-007 — Decontamination wiring (M2 data prerequisite)

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-21
- **Goal:** Make "decontaminate the training corpus against the eval set" a real,
  runnable, gated step before any M2 training. `data-policy.md` and
  `evaluation-plan.md` both require it; today `contamination.py` only defaults to the
  tokenizer probe fixture and reads a single `text` field, so the scored-suite
  prompts/answers aren't protected and there is no canonical "do-not-train-on-these"
  set. This is a framework-agnostic, fully-unblocked M2 prerequisite (chosen over
  speculative model configs, which depend on the still-open framework decision).
- **Inputs:** `scripts/data/contamination.py`, `evals/tokenizer/probes.jsonl`,
  `evals/suites/smoke-scored.jsonl`, `docs/data-policy.md`, `docs/data-pipeline.md`,
  `docs/evaluation-plan.md`.
- **Acceptance criteria:**
  - [x] `scripts/data/build_benchmark_index.py` (stdlib): gathers every eval text
        that must stay out of training (probe texts + scored-suite **prompts and
        answers**) into a canonical `evals/benchmark-index.jsonl` (one `{text,...}`
        per line), with a `--check` mode that verifies it is in sync with the suites.
  - [x] `evals/benchmark-index.jsonl` committed (small eval reference, not training
        data), kept in sync by a test (regenerate == committed).
  - [x] A test proves end-to-end decontamination: a planted copy of a benchmark text
        is **flagged/removed** by `contamination.py` against the index, while a clean
        doc survives.
  - [x] `python3 scripts/run_checks.py` exits 0 with a decontamination check wired in.
  - [x] `data-pipeline.md` / `data-policy.md` / `evaluation-plan.md` document the
        canonical benchmark index + the decontamination command.
- **Forbidden zones:** committing training data; weakening the existing contamination
  thresholds; any third-party dependency.
- **Evidence:** the index + sync test + planted-contamination test; gate output; reviewer pass.
- **Stop conditions:** pass per criteria; timeout as usual.
- **Verification:** gate green (`all 12 checks passed`, incl. `benchmark_index`
  asserting the committed index is in sync with the suites; 6 decontamination tests
  incl. a planted-prompt removal and a short-token safety regression). Independent
  code-reviewer (separate context, ran the gate + adversarial over-removal probes):
  **APPROVE** — both required gates PASS (decontamination works end-to-end; in-sync
  gate is real). Its two MEDIUM follow-ups were then fixed: a min-length floor on
  answer rows (drops generic ≤4-char tokens; index 21 -> 16) and a `_rel` helper so
  out-of-repo `--output` errors print cleanly, plus the recommended safety test.
- **Lessons:**
  - Decontamination is a hard pre-training prerequisite — a canonical, in-sync-gated
    benchmark index (`evals/benchmark-index.jsonl`) makes "decontaminate vs the eval
    set" runnable, reviewable, and drift-proof before M2 ever trains.
  - For a contamination index, short/generic answer tokens ("7", "東京") are a
    false-positive hazard: floor answer-row inclusion at the n-gram window so only
    meaningful items are protected; prompts are always included.
  - A step that *deletes* data needs an adversarial worst-case review (the reviewer's
    short-answer over-removal analysis) and a regression test pinning the safety
    property — done here before it can touch a real corpus.

---

## L-006 — M2 implementation plan (owner decision artifact)

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-20
- **Goal:** Turn the M2 "go/no-go" into "approve this plan." Synthesize the
  committed evidence (L-002 recipe research, L-003 tokenizer/vocab, L-005 BPB eval)
  + the ADRs + roadmap M2 into a concrete, research-grounded **proposal** for the
  first real (sub-1B / 1B dense) models: architecture, tokenizer, data curriculum,
  training recipe, eval, checkpointing — and the explicit owner decisions and
  resources M2 *execution* requires (it leaves the dependency-free phase).
- **Inputs:** `docs/roadmap.md` (M2), `docs/architecture-decisions.md`
  (ADR-001..006), `docs/research/open-weight-recipes.md`,
  `docs/tokenizers/vocab-bakeoff-report.md`, `docs/evals/lm-baseline-report.md`,
  `docs/training-plan.md`, `docs/data-pipeline.md`, `docs/evaluation-plan.md`.
- **Acceptance criteria:**
  - [x] `docs/m2-plan.md` exists: a concrete M2 plan (recommended dense architecture
        + the OLMo-2 stability stack, ~3 model sizes, tokenizer/vocab, 2-stage data
        curriculum, AdamW recipe, context strategy, BPB+scored eval cadence,
        safetensors checkpoints) — every recommendation cites the ADR/research that
        backs it.
  - [x] A clear **"Decisions required"** section (framework/ADR-001, dependency
        adoption/ADR-006, compute & budget) and a rough compute estimate, so the
        owner can approve or redirect.
  - [x] A staged **task breakdown** mapping to roadmap M2 exit criteria
        (resume-from-checkpoint, automatic eval, model-card draft).
  - [x] It is a **proposal**, not a decision: it does not flip any ADR; M2 execution
        stays an explicit owner go/no-go.
  - [x] Internally consistent with the rest of `docs/`; relative links resolve;
        `python3 scripts/run_checks.py` exits 0 (docs-only change is safe).
- **Forbidden zones:** flipping ADRs or starting M2 *execution* (no framework/deps/
  training); overstating the baseline or any capability.
- **Evidence:** the doc; gate output; link/consistency check; independent critic pass.
- **Stop conditions:** pass per criteria; **handoff** — M2 execution is the owner's
  go/no-go after this plan; timeout as usual.
- **Verification:** gate green (`all 11 checks passed`); all 10 relative links
  resolve; internally consistent with `roadmap.md`/`training-plan.md`/the ADRs.
  Independent critic (separate context) = **APPROVE-WITH-NITS**: grounding,
  consistency, scope-discipline, and honesty all PASS; it independently recomputed
  the compute estimate (908–1333 GPU-h, confirming ~1000). Three objective nits
  fixed: falcie-1b param count (~1.2B -> ~0.9B, matching its own dims), GPU-hours/days
  alignment, and ADR-006's "Accepted-for-dependency-free-phase" status; added a
  divergence-recovery note and the rationale for the full stability stack at small scale.
- **Lessons:**
  - Plan-as-decision-artifact: synthesizing the committed evidence (L-002/L-003/L-005
    + ADRs) into one concrete proposal turns an open "go/no-go" into an approvable
    artifact and cleanly isolates the genuinely owner-gated calls (framework, deps,
    compute). A proposal must *recommend* ADR promotion, never flip the ADR.
  - Even a docs/plan benefits from an independent pass that **recomputes the numbers** —
    the critic caught a param-count-vs-dimensions mismatch and a GPU-hours/days slip
    that internal review would likely have waved through.
  - **The dependency-free loop has reached its productive ceiling.** Foundation,
    research, tokenizer, eval harness, baseline model, and the M2 plan are all
    shipped. The next substantive step — M2 *execution* (real neural models) — is the
    owner's go/no-go (framework + dependency adoption + compute), and cannot be made
    autonomously. Further dependency-free loops would be motion, not progress.

---

## L-005 — Baseline n-gram LM + bits-per-byte eval (first end-to-end evaluable member)

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-20
- **Goal:** Close the data -> tokenizer -> model -> eval loop for the first time
  with a *trivial, honest* baseline: a dependency-free byte n-gram language model
  and the base-LM metric every real base model is judged on — **bits-per-byte
  (BPB)** and perplexity on held-out text. This gives the eval harness a real
  (non-reference) model and gives the project its first evaluable series member.
  Explicitly **not** a capability claim — an n-gram is a floor, not "high
  performance"; the value is the metric + the closed loop.
- **Inputs:** `docs/evaluation-plan.md`, `scripts/tokenizer/bpe.py`,
  `scripts/data/fetch_corpus.py` (held-out corpus), `data-policy.md` (no raw data
  / no large model committed).
- **Acceptance criteria:**
  - [x] `scripts/model/ngram_lm.py`: dependency-free byte n-gram LM with smoothing
        that yields a **valid normalized distribution** (probabilities over the 256
        bytes sum to 1, never zero) so BPB/perplexity are finite; deterministic.
  - [x] `scripts/evals/lm_eval.py`: trains an n-gram on a train split, computes
        **BPB + perplexity overall and per language** on a disjoint held-out slice,
        emits a report; higher order must not increase training BPB (the model learns).
  - [x] A committed BPB report under `docs/evals/` (the trained model + raw corpus
        are **not** committed — regenerable via the scripts), like the L-003 pattern.
  - [x] `python3 scripts/run_checks.py` exits 0 with a fast LM smoke wired in (runs
        on a tiny committed fixture, not the big corpus).
  - [x] Unit tests: valid distribution (sums to ~1), finite positive BPB,
        order monotonicity on training text, determinism.
  - [x] `docs/evaluation-plan.md` / `evals/README.md` note the base-LM (BPB) layer.
- **Forbidden zones:** committing the raw corpus or a large trained model; claiming
  the baseline is high-performance; any third-party dependency.
- **Evidence:** the BPB report (finite numbers, order trend), gate output, reviewer pass.
- **Stop conditions:** pass per criteria; handoff if it would need a neural framework
  (it must not — n-gram is pure stdlib); timeout as usual.
- **Verification:** gate green (`all 11 checks passed`, incl. `lm_eval_smoke`
  asserting best BPB < 8.0; 17 LM unit tests). Held-out report reproduces
  byte-for-byte (deterministic). Independent code-reviewer (separate context, ran
  the gate + adversarial probes itself): first APPROVE-WITH-NITS, then **APPROVE**
  after the fixes — confirmed the distribution sums to 1 within one float ULP, all
  probabilities > 0, and BPB always finite. Result: held-out BPB 5.71 -> 2.18 across
  orders 0..3 (best order 3 = 2.1766, perplexity ~4.5), vs uniform 8.0.
- **Lessons:**
  - Closing data -> tokenizer -> model -> eval end-to-end — even with a trivial
    n-gram — is high-value: it validates the whole pipeline, gives the eval harness
    a real (non-reference) model, and establishes the base-LM metric (BPB) a real
    model will reuse. The n-gram is an honest floor, not a capability claim.
  - The normalization invariant (probs sum to 1, all > 0) is what makes BPB finite —
    make it **structural** (reject floor_weight <= 0 at construction), not a
    convention a future caller could break.
  - When holding out for eval, dedup held vs train by exact text (short boilerplate
    evades corpus dedup) — and capture the train set *before* dropping held rows, or
    the fix itself becomes a leak.
  - Next is the owner's call: M2 (a neural model + a training framework + compute) is
    the big step that leaves the dependency-free phase. The base-LM metric and
    harness are ready for whatever model lands.

---

## L-004 — Scored evaluation harness ("evaluable" core)

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-20
- **Goal:** Make the model series *evaluable*: today the eval scaffolding only
  validates config shape (`run_smoke_eval`) and runs a trivial "non-empty output"
  metric (`run_mock_eval`). Add a real scored harness that compares a predictor's
  output to a known answer with real metrics and aggregates per area/language —
  the roadmap's "build the evaluation harness before training the first model."
- **Inputs:** `docs/evaluation-plan.md` (layers, reporting format, anti-contamination),
  `evals/README.md`, existing `scripts/evals/*`, `configs/evals/smoke.yaml`.
- **Acceptance criteria:**
  - [x] `scripts/evals/metrics.py`: dependency-free metric registry (exact_match,
        normalized_match, multiple_choice, numeric_match, includes) with unit tests.
  - [x] `scripts/evals/harness.py` + `run_eval.py`: run a predictor over a scored
        suite, aggregate accuracy overall + by area + by language, emit a report
        (model id, harness version, commit, score table, per-task pass/fail).
  - [x] `evals/suites/smoke-scored.jsonl`: a small scored multi-area suite (JP / EN
        / code / math / instruction), clearly labeled **harness fixtures, not
        benchmarks**, with an anti-contamination note.
  - [x] Built-in reference predictors prove the harness scores correctly: a **gold**
        predictor scores 1.0, an **empty** predictor scores 0.0, with per-area
        breakdown — the harness is validated without a real model.
  - [x] `python3 scripts/run_checks.py` exits 0 with a fast scored-smoke wired in.
  - [x] `evals/README.md` + `docs/evaluation-plan.md` updated (tasks marked done).
- **Forbidden zones:** committing private/benchmark datasets; claiming real model
  capability (no model exists yet); any third-party dependency.
- **Evidence:** the harness report (gold=1.0 / empty=0.0), gate output, reviewer pass.
- **Stop conditions:** pass per criteria; handoff if it turns out to need a real
  model (it must not — reference predictors stand in); timeout as usual.
- **Verification:** gate green (`all 10 checks passed`, incl. `scored_eval_gold`
  asserting accuracy 1.0 and `scored_eval_empty` asserting 0.0; 32 harness/metric
  tests). Independent code-reviewer (separate context, ran the gate itself): first
  APPROVE-WITH-NITS (2 MEDIUM + 5 LOW), then **APPROVE** after the fixes —
  adversarial metric probing confirmed no false-positive path remains.
- **Lessons:**
  - The harness's value is the *gold→1.0 / empty→0.0* self-check: it proves a
    scorer is wired correctly **without a model**. Make such invariants structural
    (load_suite rejects empty answers) rather than incidental, so they can't
    silently weaken as suites grow.
  - Automated scoring metrics must be *precision-first*: the reviewer caught a
    classic multiple-choice extraction trap (prose "A quick fox" scored as choosing
    A). The fix refuses to guess (single-letter / explicit cue / paren only) — for
    answer-checking, a false negative is far safer than a false positive.
  - Validate at ingestion, not at scoring time (choices membership checked in
    load_suite), so a malformed suite fails fast.
  - Next: when a real model exists (M2+), register its `predict(task) -> str` in
    place of a reference predictor — scoring/aggregation/report are already in
    place. Expand suites (public benchmarks where licensing permits + a private
    regression set per `evaluation-plan.md`).

---

## L-003 — Tokenizer vocab-size bakeoff (JP fertility evidence for ADR-003)

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-20
- **Goal:** Give ADR-003 real evidence on vocabulary size by measuring Japanese
  fertility vs embedding-parameter cost across vocab sizes on a held-out
  public-domain corpus — the measurement the L-002 research said was the open
  tokenizer decision.
- **Scope reality (logged, not silent):** a literal 64k/128k/256k *real-merge*
  bakeoff is **not feasible in this dependency-free phase** — (a) no large corpus
  may be committed (`data-policy.md`: store retrieval scripts, not raw data), and
  (b) the pure-Python BPE trainer is O(merges x corpus), so 256k merges over MBs
  is intractable here. The full sweep is **deferred to M2** (real corpus + a
  faster, dependency-managed trainer). This loop builds the harness + metrics and
  runs a real, non-collapsing *small-scale* fertility curve as the in-phase proxy.
- **Inputs:** `docs/research/open-weight-recipes.md` (Tokenizer), ADR-003,
  `scripts/tokenizer/*`, `docs/tokenizers/baseline-reference.md` (byte JP baseline
  = 2.7255 tokens/char), `data-policy.md`.
- **Acceptance criteria:**
  - [x] `scripts/data/fetch_corpus.py` (stdlib-only) fetches public-domain text
        (Aozora JP + Gutenberg EN [+ permissive code]), cleans it, writes a
        held-out corpus to an **uncommitted** local path, and prints sizes + sha256.
  - [x] A provenance manifest (per `data-policy.md` schema) is committed; the raw
        corpus is **not** committed (gitignored).
  - [x] The selection harness reports, per candidate, **Japanese tokens/char +
        whether it beats the byte JP baseline (2.7255)** and **embedding cost
        (vocab x d_model)**.
  - [x] A real, non-collapsing bakeoff (>=3 vocab sizes) runs on the held-out
        corpus; report committed under `docs/tokenizers/`.
  - [x] Evidence shows BPE beats the byte JP baseline materially; the full
        64k/128k/256k run is documented as deferred to M2.
  - [x] `python3 scripts/run_checks.py` exits 0 (new metric has a unit test; gate
        stays fast on the tiny probe corpus).
- **Forbidden zones:** committing the raw corpus; changing the byte/char/whitespace
  baselines; claiming the full 64k+ run was performed.
- **Evidence:** the committed bakeoff report; gate output; independent reviewer pass.
- **Stop conditions:** pass per criteria above; **handoff** if network is
  unavailable (fall back / escalate); **timeout** — if a vocab size does not finish
  in a few minutes, cap it and log the cap (no silent truncation).
- **Verification:** gate green (`all 8 checks passed`, 230 unit tests); the held-out
  bakeoff ran on a real public-domain corpus (raw corpus gitignored; only script +
  manifest-with-hashes + report committed). Independent code-reviewer (separate
  context, web/exec-enabled): first APPROVE-WITH-NITS (4 MEDIUM), then **APPROVE**
  after the fixes — every ADR-003 number machine-cross-checked equal to the report
  JSON. Measured: Japanese tokens/char 1.36 @512 -> 0.62 @8192 (54.6% -> 79.5%
  better than the byte baseline), all non-collapsing.
- **Lessons:**
  - A second adversarial review after the first APPROVE-WITH-NITS still found 4
    MEDIUM issues — for *measurement* code the methodology critique (single-work
    eval, paragraph granularity, recommendation-vs-prose) matters as much as
    claim-checking. Re-review after non-trivial edits, don't assume the first pass
    caught everything.
  - Honest "no knee in this range" beats a rigged recommendation: when fertility is
    monotonic over the tested sizes, say the cost knee is *expected at larger scale*
    rather than implying one the small-scale data doesn't show. `choose()` encodes
    this (cost-knee detection), and the prose was corrected to match.
  - `data-policy.md`'s "no raw data committed" pattern worked cleanly: gitignore the
    corpus, commit the retrieval script + manifest (with sha256) + the report. The
    fetch was deterministic (byte-identical corpus across re-runs), so a flag-only
    code fix didn't invalidate the committed report.
  - Pure-Python BPE is O(merges x corpus): the in-phase bakeoff caps at small vocab
    (~8k in ~2min). Next: owner to promote ADR-003 Proposed -> Testing; the full
    64k/128k/256k run waits for M2 (real corpus + a faster, dependency-managed
    trainer).

---

## L-002 — Open-weight recipe research log (fill ADR evidence)

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-20
- **Goal:** Turn the project premise ("don't train from scratch — research proven
  open-weight recipes and build our own series") into its first artifact: a
  cited comparison of how recent strong open-weight models are actually built,
  and use it to back-fill the still-"Proposed" ADR-001..005 with evidence.
- **Inputs:** docs/architecture-decisions.md (ADR-001..005), docs/roadmap.md,
  docs/training-plan.md, docs/tokenizer-evaluation.md. Reference models:
  Qwen3, Llama 3.x, DeepSeek-V3, Gemma 2/3, OLMo 2 (fully-open reproducibility ref).
- **Acceptance criteria:**
  - [x] `docs/research/open-weight-recipes.md` exists: a cross-model comparison
        over the ADR dimensions (model family, tokenizer+vocab, pretrain data mix
        & token budget, training recipe, context strategy, checkpoint/release).
  - [x] Every non-obvious quantitative claim carries a source URL; anything
        unverified is explicitly marked `[unverified]`.
  - [x] Each ADR-001..005 gets a "Research evidence (L-002)" annotation citing the
        log + a recommended direction.
  - [x] `python3 scripts/run_checks.py` still exits 0; docs links resolve.
- **Forbidden zones:** model/data/tokenizer **code**; do NOT flip any ADR to
  "Accepted" unilaterally — final acceptance is an owner **handoff**.
- **Evidence:** the cited doc; gate output; independent critic pass on claims.
- **Stop conditions:** pass when ≥4 reference models are covered with citations
  and ADRs are annotated; **handoff** for final ADR Accept/Reject; timeout if a
  model's recipe can't be sourced — mark `[unverified]` and move on.
- **Verification:** gate green (`all 8 checks passed`); 5 cited model profiles from
  primary sources; independent critic (separate context, web-enabled) first returned
  REQUEST-CHANGES on two mis-citations, then APPROVE-WITH-NITS after fixes were
  re-verified against the primary sources.
- **Lessons:**
  - The adversarial fact-check earned its keep: it caught two mis-cited claims
    (a Gemma CJK quote attributed to the wrong blog; a Llama "3.17→3.94 chars/token"
    figure absent from its cited page) that the sonnet research agents introduced and
    the synthesis carried over. Verification-death-zone is real — for any cited doc,
    a web-enabled critic that re-fetches sources is mandatory before commit.
  - When delegating cited research, require source URLs *and* mark unverified items;
    but do not trust the citation→claim mapping until an independent pass re-fetches.
  - ADRs were annotated, not flipped — Accept/Reject stays an owner handoff. Next:
    owner to promote ADR-002 (dense-first) and ADR-003/004 directions to Testing.

---

## L-001 — Loop Engineering foundation

- **Status:** passed
- **Owner:** Shingo YOSHIDA
- **Opened / Closed:** 2026-06-20 / 2026-06-20
- **Goal:** Establish the operational foundation (goal-contract template, stop
  conditions, worktree workflow, verifier pass, persistent ledger) so every
  later task rides on an explicit, verifiable loop instead of ad-hoc prompting.
- **Inputs:** project premise + the Loop Engineering method (CLAUDE.md;
  AcrossStudio Zenn article on Loop Engineering by Boris Cherny / Cat Wu).
- **Acceptance criteria:**
  - [x] `docs/loop/README.md`, `goal-contract-template.md`, `loop-ledger.md` exist.
  - [x] The canonical gate (`scripts/run_checks.py`) is referenced as the single
        command, not a stale subset of scripts.
  - [x] No duplication of CLAUDE.md's method narrative; docs only add artifacts.
  - [x] `python3 scripts/run_checks.py` still exits 0 (docs-only change is safe).
- **Forbidden zones:** model/data/tokenizer code; CLAUDE.md narrative (untouched).
- **Evidence:** gate output pasted in the PR; `docs/loop/` links resolve.
- **Stop conditions:** pass on green gate + resolving links; handoff if the
  foundation shape needs a product decision.
- **Verification:** gate run locally (`all 8 checks passed`, exit 0); independent
  verifier pass (separate context) = APPROVE-WITH-NITS, one cosmetic nit folded in.
- **Lessons:**
  - CLAUDE.md §3 lists three scripts as the gate, but the real single-command
    gate is `scripts/run_checks.py` (8 checks). Future loops cite run_checks.py;
    consider syncing CLAUDE.md §3 to match.
  - The "research proven open-weight recipes" premise has no artifact yet — ADRs
    001–005 are still "Proposed" with no evidence. Candidate next loop: a
    research log under `docs/research/` that fills those ADRs with citations.

---

<!-- New entries go ABOVE this line, newest first. -->
