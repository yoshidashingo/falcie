# Loop Engineering — Foundation

This directory is the **operational foundation** that every non-trivial task in
fal'Cie rides on. It does not restate the method — `CLAUDE.md` ("Loop
Engineering — Working Method for This Repo") is the method-of-record. This
directory provides the *reusable artifacts* that method calls for:

| Artifact | File | Purpose |
| --- | --- | --- |
| Goal contract template | [`goal-contract-template.md`](goal-contract-template.md) | Copy once per loop. Makes the goal, acceptance criteria, evidence, and stop conditions explicit *before* code is written. |
| Loop ledger | [`loop-ledger.md`](loop-ledger.md) | Append-only record of every loop run: goal, evidence, outcome, lessons. The repo's persistent memory — "the model forgets, the repo does not." |

## How a loop runs here

```
DISCOVER -> PLAN -> EXECUTE -> VERIFY -> RECORD -> COMMIT
   |          |        |          |         |         |
   |          |        |          |         |         on green: atomic commit + push
   |          |        |          |         lessons -> CLAUDE.md / skills / this ledger
   |          |        |          the gate (below) must say PASS with pasted evidence
   |          |        isolated worktree for parallel agents (see below)
   |          goal contract filled in + ledger entry opened
   pulled from docs/roadmap.md, ADRs, failing checks, or open issues
```

## The verification gate (the thing that can say "no")

One command runs every gate and exits non-zero on any failure:

```bash
python3 scripts/run_checks.py
```

It is the canonical Loop-Engineering gate for the repo. As of this writing it
runs these 8 checks (the labels `scripts/run_checks.py` prints): `validate_manifest`,
`smoke_eval`, `summarize_probes`, `score_tokenizer`, `select_tokenizer`,
`special_tokens`, `mock_eval`, and `unit_tests` (the `unittest discover` suite).

Rules (from `CLAUDE.md` §3):

- **Run, don't assume.** Claim completion only after running the gate and pasting
  the output as evidence.
- **The author is never the sole verifier.** A separate reviewer/verifier pass
  (`code-reviewer` / `verifier` agent or a fresh context) signs off — never
  self-approve in the same active context.
- **Docs-only changes** still need a gate: links resolve, the change is
  internally consistent with the rest of `docs/`, and it matches the stated plan.

## Stop conditions (every loop must declare these up front)

| Outcome | Trigger | Next action |
| --- | --- | --- |
| **Pass** | All acceptance criteria met, gate green | Deliver: commit + push |
| **Rollback** | A risk materialized (broken gate, wrong direction) | Revert the change; record why |
| **Handoff** | A human decision is required | Escalate to the owner with context |
| **Timeout** | Iteration cap hit, or the same error repeats twice | Stop, report, change strategy — do not re-run blindly |

## Worktrees (parallel agents)

Run independent loops in isolated git worktrees so parallel agents never collide
or leave a half-migrated tree:

```bash
git worktree add ../falcie-<short-task> -b loop/<short-task>
# ... run the loop in that worktree; gate must pass there ...
git worktree remove ../falcie-<short-task>
```

One concern per worktree/branch; one atomic commit per green checkpoint.

## Suitability (from the method)

- **Good loops:** failing-check repair, test backfill, tokenizer/data probes,
  doc sync, dependency bumps, eval harness runs.
- **Not loops (human-led):** broad refactors, production-credential actions,
  safety-sensitive changes, purely aesthetic judgment.

Priority order when in doubt: **verifiable > automatable > extensible.**
