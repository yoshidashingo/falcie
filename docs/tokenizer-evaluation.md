# Tokenizer Evaluation

fal'Cie needs a tokenizer that is strong for Japanese, English, code, and mixed-language documents. Tokenizer selection must happen before non-smoke model training, because it affects training cost, context efficiency, and downstream model quality.

## Goals

- Reduce token count for Japanese without harming English or code.
- Keep code symbols, indentation, and common identifiers usable.
- Handle mixed Japanese-English technical text naturally.
- Reserve stable special tokens for chat, system messages, tools, and future multimodal markers.
- Make tokenizer comparisons reproducible.

## Required Candidate Metadata

Each tokenizer candidate should document:

- Candidate name
- Training corpus manifest
- Vocabulary size
- Special tokens
- Normalization rules
- Pre-tokenization rules
- Training command
- Training commit SHA
- License and artifact ownership

## Evaluation Dimensions

### Compression

Measure tokens per character and tokens per byte for:

- Japanese prose
- English prose
- Mixed Japanese-English technical text
- Python code
- TypeScript code
- Markdown
- JSON/YAML-like config

### Fertility

Track average tokens per word-like unit where applicable.

For Japanese, use character and byte-level proxies until a robust morphological analysis dependency is introduced.

### Code Friendliness

Inspect whether the tokenizer preserves useful programming structure:

- Common keywords
- Indentation
- Braces and punctuation
- Snake case and camel case identifiers
- Import paths
- Markdown code fences

### Special Token Discipline

Required special-token categories:

- Beginning/end of sequence
- Chat role markers
- System message marker
- Tool call marker
- Tool result marker
- Padding, if needed by the training stack

Special tokens must be stable before instruction tuning.

### Robustness

Probe:

- Long repeated text
- URLs
- Japanese punctuation
- Emoji and symbols
- Full-width and half-width characters
- Mixed scripts
- Malformed JSON snippets

## Probe Set

The initial probe set lives at `evals/tokenizer/probes.jsonl`.

The probe set is not training data. It is a small evaluation fixture used to keep tokenizer comparisons stable.

## Compression Scoring

A dependency-free baseline scorer measures tokens-per-character and
tokens-per-byte over the probe set:

```bash
python3 scripts/tokenizer/score_tokenizer.py --format md
```

It ships with reference tokenizers (`byte`, `char`, `whitespace`) that bound the
compression space. The `byte` tokenizer is the canonical reference a real
candidate must beat. Baseline results are recorded in
[`tokenizers/baseline-reference.md`](tokenizers/baseline-reference.md). A real
subword candidate is added by registering its encoder in the scorer's
`TOKENIZERS` map, after which the same report applies to it.

## Candidate Report Format

Each candidate report should include:

```markdown
# Tokenizer Candidate: <name>

## Metadata

## Compression Table

## Code Friendliness Notes

## Special Tokens

## Known Issues

## Decision
```

## Selection Gate

A tokenizer can be selected for M2 experiments only when:

- Probe set results are published.
- Japanese and English compression are both acceptable.
- Code probes have no severe fragmentation issue.
- Special tokens are finalized.
- Training and evaluation commands are reproducible.

## Immediate Implementation Tasks

1. Keep `evals/tokenizer/probes.jsonl` small and stable.
2. Add candidate-specific reports under `docs/tokenizers/`.
3. Add tokenizer training configs under `configs/tokenizer/`.
4. Add automated tokenizer scoring once a tokenizer library is selected.
