# Tokenizer Candidate: baseline-reference

Reference baselines, not a selectable production tokenizer. These dependency-free
tokenizers establish the compression floor and ceiling that every real subword
candidate must be measured against. The **byte** tokenizer is the canonical
reference: it never compresses, so its token count is the upper bound a real
candidate must beat. `char` and `whitespace` bracket the space from the other side.

Reproduce this report with:

```bash
python3 scripts/tokenizer/score_tokenizer.py --format md
```

## Metadata

- Candidate name: baseline-reference (byte / char / whitespace)
- Training corpus manifest: none — these tokenizers are not trained
- Vocabulary size: byte = 256; char = open Unicode; whitespace = open
- Special tokens: none (baselines reserve no special tokens)
- Normalization rules: none (raw text)
- Pre-tokenization rules: byte = UTF-8 bytes; char = Unicode codepoints; whitespace = `str.split()`
- Training command: not applicable
- Training commit SHA: not applicable
- License and artifact ownership: project-owned, Apache-2.0

## Compression Table

Measured on `evals/tokenizer/probes.jsonl` (7 probes, 660 chars, 780 bytes).

### Overall

| tokenizer | tokens | chars | bytes | tokens/char | tokens/byte |
| --- | ---: | ---: | ---: | ---: | ---: |
| byte | 780 | 660 | 780 | 1.1818 | 1.0 |
| char | 660 | 660 | 780 | 1.0 | 0.8462 |
| whitespace | 59 | 660 | 780 | 0.0894 | 0.0756 |

### byte — by language

| language | tokens | chars | bytes | tokens/char | tokens/byte |
| --- | ---: | ---: | ---: | ---: | ---: |
| code | 204 | 204 | 204 | 1.0 | 1.0 |
| config | 93 | 93 | 93 | 1.0 | 1.0 |
| en | 229 | 229 | 229 | 1.0 | 1.0 |
| ja | 139 | 51 | 139 | 2.7255 | 1.0 |
| ja-en | 115 | 83 | 115 | 1.3855 | 1.0 |

### byte — by domain

| domain | tokens | chars | bytes | tokens/char | tokens/byte |
| --- | ---: | ---: | ---: | ---: | ---: |
| configuration | 93 | 93 | 93 | 1.0 | 1.0 |
| english_prose | 134 | 134 | 134 | 1.0 | 1.0 |
| japanese_prose | 139 | 51 | 139 | 2.7255 | 1.0 |
| markdown | 95 | 95 | 95 | 1.0 | 1.0 |
| mixed_technical | 115 | 83 | 115 | 1.3855 | 1.0 |
| python_code | 107 | 107 | 107 | 1.0 | 1.0 |
| typescript_code | 97 | 97 | 97 | 1.0 | 1.0 |

A byte tokenizer spends ~2.7 tokens per Japanese character versus 1.0 per ASCII
character. This quantifies the core tokenizer goal in `tokenizer-evaluation.md`:
a good candidate must cut Japanese token cost well below the byte baseline
without inflating English or code cost.

## Code Friendliness Notes

The baselines do not model subword structure, so they cannot fragment identifiers
or keywords — `char` and `byte` are loss-free by construction, and `whitespace`
splits only on spaces. These references therefore say nothing about code
friendliness; that dimension only becomes meaningful once a real subword
candidate is scored. The `code` probes (Python, TypeScript) are included so the
same fixture carries over to that future comparison.

## Special Tokens

None. Special-token discipline (BOS/EOS, chat roles, system, tool call/result,
padding) is a requirement for production candidates and is out of scope for these
references.

## Known Issues

- Not a usable production tokenizer; provided only as a measurement floor/ceiling.
- The probe fixture is intentionally tiny, so absolute counts are illustrative,
  not statistically representative of training-scale corpora.
- `whitespace` undercounts on scripts without spaces (Japanese collapses to ~1
  token per sentence), so it is a loose lower bound, not a realistic target.

## Decision

Adopted as the permanent reference baseline. Real subword candidates are accepted
only when they beat the `byte` Japanese tokens/char (2.7255) materially while
keeping English and code tokens/char close to or below `char` (1.0), per the
Selection Gate in `tokenizer-evaluation.md`.
