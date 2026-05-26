# fal'Cie Roadmap

fal'Cie aims to become a frontier-grade open-weight language model: no API gate, no usage lock-in, and weights that researchers, developers, and builders can run, inspect, fine-tune, and redistribute under Apache 2.0.

This roadmap turns that promise into measurable milestones. Dates are intentionally omitted until compute, data, and evaluation resources are secured.

## North Star

Build and release an open-weight large language model that is competitive with the strongest closed frontier systems on public and private evaluation suites, while preserving reproducibility, multilingual capability, and permissive downstream use.

## Principles

- Open weights first: release usable checkpoints, not only papers or APIs.
- Measured claims only: every capability claim must map to an evaluation result.
- Reproducible training: publish configs, data manifests, filtering rules, and evaluation harnesses.
- Multilingual strength: Japanese and English are first-class targets; code and math are core capabilities.
- Permissive release: Apache 2.0 remains the default unless a concrete safety or legal blocker is found.
- Safety by design: release requires model cards, known limitations, misuse analysis, and red-team results.

## Capability Targets

The phrase "most capable open-weight language model" must be earned through evidence. fal'Cie will track at least these dimensions:

- General reasoning
- Japanese language understanding and generation
- English language understanding and generation
- Code generation and repair
- Mathematical reasoning
- Long-context retrieval and synthesis
- Instruction following
- Tool-use readiness
- Safety, refusal quality, and hallucination resistance
- Inference efficiency and deployability

## Milestones

### M0: Public Research Foundation

- Publish roadmap, evaluation plan, data policy, training plan, model-card template, and release checklist.
- Define benchmark suites and release gates.
- Establish repository structure for future code, configs, and artifacts.

Exit criteria:

- Core planning docs are public.
- README links to the plan.
- Evaluation and release requirements are explicit.

### M1: Data and Tokenizer Prototype

- Build dataset manifest format.
- Implement data ingestion, deduplication, filtering, and contamination checks.
- Train and compare tokenizer candidates for Japanese, English, and code.
- Publish tokenizer evaluation notes.

Exit criteria:

- Reproducible data pipeline exists.
- Tokenizer candidate is selected with evidence.
- Dataset licenses and exclusions are documented.

### M2: Small Experimental Models

- Train sub-1B and 1B-class models to validate the pipeline.
- Run evaluation after fixed token intervals.
- Track scaling behavior, loss curves, and failure modes.

Exit criteria:

- Training pipeline can resume from checkpoint.
- Evaluation harness runs automatically.
- Model card draft exists for each experimental checkpoint.

### M3: Instruction and Alignment Stack

- Build supervised fine-tuning datasets.
- Evaluate DPO, RLAIF, and other preference optimization methods.
- Add refusal, safety, and tool-use evaluations.

Exit criteria:

- Instruction-following model beats base model across target suites.
- Safety regressions are tracked.
- Prompt templates and chat formatting are stable.

### M4: First Open-Weight Release Candidate

- Train a release-sized model with full provenance tracking.
- Freeze evaluation harness and release gates.
- Run external review where possible.
- Prepare Hugging Face, GitHub Release, and model-card publication assets.

Exit criteria:

- Release checklist is complete.
- Weights are ready for public distribution.
- Known limitations are disclosed.

### M5: Frontier-Scale Program

- Secure compute and funding for frontier-scale training.
- Expand multilingual and tool-use data.
- Establish independent evaluations and red-team review.
- Release stronger checkpoints iteratively.

Exit criteria:

- Scaling plan is backed by compute, data, and evaluation evidence.
- Release process remains reproducible and auditable.

## Repository Workstreams

- `docs/`: public plans, policies, release notes, and model cards.
- `configs/`: tokenizer, training, data, and evaluation configurations.
- `scripts/`: reproducible data, training, evaluation, and release automation.
- `evals/`: benchmark wrappers and private eval definitions where publishable.
- `model/`: architecture code when the implementation begins.
- `examples/`: inference, fine-tuning, and deployment examples.

## Immediate Next Steps

1. Convert this roadmap into issues or project milestones.
2. Add dataset manifest schema and tokenizer evaluation criteria.
3. Choose the first experimental scale and training framework.
4. Build the evaluation harness before training the first model.
