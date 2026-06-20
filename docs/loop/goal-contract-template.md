# Goal Contract — `<short-task-name>`

Copy this file to open a loop, fill every field, then paste it into the PR
description (or a ledger entry). The contract is the **scope anchor**: "done" is
exactly what is written here and nothing more. Do not expand scope mid-loop.

> Status: `draft | running | passed | rolled-back | handed-off | timed-out`
> Owner: `<who is accountable>`
> Opened: `YYYY-MM-DD`   Closed: `YYYY-MM-DD`

## 1. Goal (one sentence)

`<what changes and why — outcome, not steps>`

## 2. Inputs

- Source of work: `<roadmap milestone / ADR / failing check / issue>`
- Relevant context: `<docs, files, configs to attach>`

## 3. Acceptance criteria (must be checkable, prefer numbers)

- [ ] `<criterion 1 — e.g. python3 scripts/run_checks.py exits 0>`
- [ ] `<criterion 2 — e.g. new unit covers round-trip property>`
- [ ] `<criterion 3 — e.g. ADR-00X moved Proposed -> Accepted with evidence>`

## 4. Forbidden zones (out of scope / do not touch)

- `<files, behaviors, or decisions this loop must not change>`

## 5. Evidence format (what proves each criterion)

- `<gate output pasted / test names / eval numbers / diff summary>`

## 6. Stop conditions

- **Pass:** all of §3 checked and the gate is green.
- **Rollback if:** `<concrete risk that means revert>`
- **Handoff if:** `<the human decision that forces escalation>`
- **Timeout:** max `<N>` iterations, or stop if the same error repeats twice.

## 7. Verification (separate pass — author does not self-approve)

- [ ] Gate run and output pasted: `python3 scripts/run_checks.py`
- [ ] Independent reviewer/verifier signed off: `<agent or fresh context>`

## 8. Lessons (fold back after closing)

- `<what to add to CLAUDE.md / a skill / this template so it persists>`
