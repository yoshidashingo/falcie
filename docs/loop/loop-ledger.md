# Loop Ledger

Append-only record of every loop run, newest first. One entry per loop. This is
the repo's persistent memory of *what was attempted, what proved it, and what we
learned* — so the project does not repeat the same accident twice.

Entry format: see [`goal-contract-template.md`](goal-contract-template.md). Keep
entries short; link to PRs/commits/ADRs for detail.

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
