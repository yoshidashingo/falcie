# Loop Ledger

Append-only record of every loop run, newest first. One entry per loop. This is
the repo's persistent memory of *what was attempted, what proved it, and what we
learned* — so the project does not repeat the same accident twice.

Entry format: see [`goal-contract-template.md`](goal-contract-template.md). Keep
entries short; link to PRs/commits/ADRs for detail.

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
