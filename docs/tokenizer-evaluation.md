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

## BPE Candidates and Selection

A dependency-free, clean-room **byte-level BPE** tokenizer
(`scripts/tokenizer/bpe.py`) provides the first real subword candidate. It trains,
encodes, decodes, and serializes with the standard library only; the byte-level
base alphabet makes encoding lossless (`decode(encode(x)) == x` for all text),
which is verified by property-based tests (`tests/test_bpe_pbt.py`).

Train a candidate:

```bash
python3 scripts/tokenizer/train_bpe.py evals/tokenizer/probes.jsonl \
    --vocab-size 1024 --output /tmp/falcie-bpe.json
```

Produce a selection report comparing the reference baselines against BPE
candidates over the probe set:

```bash
python3 scripts/tokenizer/select_tokenizer.py
```

With the default corpus the BPE candidates are trained on the same probe texts
they are scored on, so the report runs in **smoke mode**: it recommends *nothing*
and explicitly discloses that each probe is memorized to ~1 token. This proves the
selection pipeline end to end without overstating it. Pass `--corpus <held-out
corpus>` to train on data disjoint from the probes — only then does the report emit
an evidence-based recommendation and reach the M1 exit criterion ("tokenizer
candidate is selected with evidence"). Output is written to
[`tokenizers/selection-report.md`](tokenizers/selection-report.md) (and a JSON sibling).

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
2. ~~Add candidate-specific reports under `docs/tokenizers/`.~~ Done: baseline
   reference + generated `selection-report.md`.
3. Add tokenizer training configs under `configs/tokenizer/`.
4. ~~Add automated tokenizer scoring once a tokenizer library is selected.~~ Done:
   dependency-free byte-level BPE library + scorer + selection harness.
5. ~~Next: acquire a held-out training corpus and re-run selection on it~~ Done
   (L-003): `scripts/data/fetch_corpus.py` builds a held-out public-domain corpus
   (Aozora JP + Gutenberg EN + CPython code; raw corpus not committed per
   `data-policy.md`), and `scripts/tokenizer/vocab_bakeoff.py` measures Japanese
   fertility vs embedding cost across vocab sizes — see
   [`tokenizers/vocab-bakeoff-report.md`](tokenizers/vocab-bakeoff-report.md).
6. Next: finalize the special-token scheme (unit U-T4) and the vocabulary size. The
   in-phase bakeoff shows the fertility/cost trend at small scale; the full
   64k/128k/256k decision is deferred to M2 (real corpus + a faster, dependency-
   managed trainer).
