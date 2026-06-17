<!-- OMC:START -->
<!-- OMC:VERSION:4.9.3 -->

# oh-my-Codex - Intelligent Multi-Agent Orchestration

You are running with oh-my-Codex (OMC), a multi-agent orchestration layer for Codex.
Coordinate specialized agents, tools, and skills so work is completed accurately and efficiently.

<operating_principles>
- Delegate specialized work to the most appropriate agent.
- Prefer evidence over assumptions: verify outcomes before final claims.
- Choose the lightest-weight path that preserves quality.
- Consult official docs before implementing with SDKs/frameworks/APIs.
</operating_principles>

<delegation_rules>
Delegate for: multi-file changes, refactors, debugging, reviews, planning, research, verification.
Work directly for: trivial ops, small clarifications, single commands.
Route code to `executor` (use `model=opus` for complex work). Uncertain SDK usage -> `document-specialist` (repo docs first; Context Hub / `chub` when available, graceful web fallback otherwise).
</delegation_rules>

<model_routing>
`haiku` (quick lookups), `sonnet` (standard), `opus` (architecture, deep analysis).
Direct writes OK for: `~/.Codex/**`, `.omc/**`, `.Codex/**`, `AGENTS.md`.
</model_routing>

<skills>
Invoke via `/oh-my-Codex:<name>`. Trigger patterns auto-detect keywords.
Tier-0 workflows include `autopilot`, `ultrawork`, `ralph`, `team`, and `ralplan`.
Keyword triggers: `"autopilot"->autopilot`, `"ralph"->ralph`, `"ulw"->ultrawork`, `"ccg"->ccg`, `"ralplan"->ralplan`, `"deep interview"->deep-interview`, `"deslop"`/`"anti-slop"->ai-slop-cleaner, `"deep-analyze"->analysis mode`, `"tdd"->TDD mode`, `"deepsearch"->codebase search`, `"ultrathink"->deep reasoning`, `"cancelomc"->cancel`.
Team orchestration is explicit via `/team`.
Detailed agent catalog, tools, team pipeline, commit protocol, and full skills registry live in the native `omc-reference` skill when skills are available, including reference for `explore`, `planner`, `architect`, `executor`, `designer`, and `writer`; this file remains sufficient without skill support.
</skills>

<verification>
Verify before claiming completion. Size appropriately: small->haiku, standard->sonnet, large/security->opus.
If verification fails, keep iterating.
</verification>

<execution_protocols>
Broad requests: explore first, then plan. 2+ independent tasks in parallel. `run_in_background` for builds/tests.
Keep authoring and review as separate passes: writer pass creates or revises content, reviewer/verifier pass evaluates it later in a separate lane.
Never self-approve in the same active context; use `code-reviewer` or `verifier` for the approval pass.
Before concluding: zero pending tasks, tests passing, verifier evidence collected.
</execution_protocols>

<hooks_and_context>
Hooks inject `<system-reminder>` tags. Key patterns: `hook success: Success` (proceed), `[MAGIC KEYWORD: ...]` (invoke skill), `The boulder never stops` (ralph/ultrawork active).
Persistence: `<remember>` (7 days), `<remember priority>` (permanent).
Kill switches: `DISABLE_OMC`, `OMC_SKIP_HOOKS` (comma-separated).
</hooks_and_context>

<cancellation>
`/oh-my-Codex:cancel` ends execution modes. Cancel when done+verified or blocked. Don't cancel if work incomplete.
</cancellation>

<worktree_paths>
State: `.omc/state/`, `.omc/state/sessions/{sessionId}/`, `.omc/notepad.md`, `.omc/project-memory.json`, `.omc/plans/`, `.omc/research/`, `.omc/logs/`
</worktree_paths>

## Setup

Say "setup omc" or run `/oh-my-Codex:omc-setup`.

<!-- OMC:END -->

<!-- The section below is project-owned. Do NOT place it inside the OMC block above (OMC regenerates that block and would erase it). -->

# Loop Engineering — Working Method for This Repo

This repository is developed using **Loop Engineering**, the agentic-development methodology
articulated by **Boris Cherny** (Head of Claude Code, Anthropic) and Cat Wu. Every non-trivial
change here MUST be implemented by following this method, not by ad-hoc one-shot prompting.

## 1. Core idea

> "Stop prompting the agent by hand. Design the loop that prompts the agent, verifies the
> result, records what it learned, and iterates until the goal is met."

The engineer's job shifts from *writing code* to *engineering the loop*: defining the goal,
the verification gate, the persistent memory, and the stop conditions — then letting the agent
run the observe → decide → execute → **verify** → record → iterate cycle until done.

## 2. The loop (mandatory workflow)

For any task in this repo, run this cycle. Do not skip the VERIFY step.

1. **DISCOVER** — Identify the work. Pull from `docs/roadmap.md`, the evaluation/training/data
   plans, open issues, or failing checks. Attach the relevant docs as context.
2. **PLAN** — Reason about the approach first (use plan mode for non-trivial work). Write the
   plan into the PR description or a short plan file under `docs/`/`aidlc-docs/` so intent and
   success criteria are explicit *before* code is written.
3. **EXECUTE** — Make the change. Prefer isolated worktrees when running parallel agents so
   they don't collide. Keep the codebase architecturally consistent (no half-migrated states).
4. **VERIFY** — Close the loop with something that can say *no* (see §3). Verification is half
   the work and is non-negotiable.
5. **RECORD** — When the agent makes a mistake, write the lesson into this file (or a skill /
   doc) so it persists into future runs. Turn any pattern seen 3–4 times into automation
   (a script, a lint rule, a checklist item).
6. **COMMIT** — On green, commit and push (see §6). On red, return to PLAN/EXECUTE — do not
   close the loop on a failing gate.

## 3. Verification gate (concrete for this repo)

A change is "done" only when an independent check confirms it. This repo is dependency-light
Python (standard library). Run the relevant checks and paste the evidence:

```bash
python3 scripts/data/validate_manifest.py      # dataset manifests are valid
python3 scripts/evals/run_smoke_eval.py        # evaluation config smoke check
python3 scripts/tokenizer/summarize_probes.py  # tokenizer probe summary
```

Rules for the gate:

- **Never let the author be the sole verifier.** Use a separate reviewer/verifier pass
  (`code-reviewer` / `verifier` agent, or a fresh context) for the approval — never self-approve
  in the same active context.
- **Run, don't assume.** Claim completion only after running the check and observing the output.
- **Docs count too.** For docs/plan changes, the gate is: links resolve, the change is internally
  consistent with the rest of `docs/`, and it matches the stated plan.

## 4. Stop conditions (prevent runaway loops)

Every loop MUST have explicit exit criteria:

- **Iteration cap** — stop after a small number of failed attempts (e.g. 5) and escalate.
- **No-progress detection** — if the same error repeats twice, change strategy; don't re-run blindly.
- **Scope anchor** — the plan/PR description defines "done"; do not expand scope mid-loop.
- **Human judgment is retained** — verification and comprehension are never delegated away.

## 5. Do / Don't

**Do**

- Plan first, then allow a clean one-shot implementation once the plan is solid.
- Keep persistent state outside the model: plans in `docs/`, decisions in `docs/architecture-decisions.md`.
- Prefer search (glob/grep + reasoning) over heavyweight indexing.
- Run independent tasks in parallel (separate worktrees) to increase throughput.
- Promote any repeated manual fix into a script or rule.

**Don't**

- Don't skip verification, and don't let the coding agent grade its own work.
- Don't mix old/new architecture mid-migration — it confuses both humans and agents.
- Don't run a loop without stop conditions.
- Don't claim "done" without evidence from the gate.

## 6. Commit & push rule

**Commit and push at sensible checkpoints.** Whenever a coherent unit of work passes its
verification gate, make an atomic commit and push to `origin`:

- Commit when a logical step is complete and green — not one giant commit at the very end,
  and not noisy WIP commits mid-loop.
- Each commit message states *what* changed and *why*; keep commits scoped to one concern.
- Push after committing so work is durable and visible.
- Never commit a change whose verification gate is failing.

## Sources

Loop Engineering as described by Boris Cherny / Cat Wu (Claude Code, Anthropic) and surrounding
write-ups: The New Stack "Loop Engineering"; The Neuron interview with Boris Cherny & Cat Wu on
agent loops; Pragmatic Engineer "Building Claude Code with Boris Cherny"; Lenny's Newsletter
"Head of Claude Code"; Addy Osmani, "Loop Engineering."
