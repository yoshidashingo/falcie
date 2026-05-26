# Model Card Template

Use this template for every public fal'Cie checkpoint. Do not release weights without a completed model card.

## Model Summary

- Model name:
- Version:
- Release date:
- Model type:
- Parameter count:
- Context length:
- Tokenizer:
- Base or instruction-tuned:
- License:
- Repository:
- Weights URL:

## Intended Use

Describe intended users and use cases.

Examples:

- Research
- Local inference
- Fine-tuning
- Application prototyping
- Japanese and English language tasks
- Code assistance

## Out-of-Scope Use

List use cases the model is not designed for.

Examples:

- High-stakes medical, legal, or financial advice without expert review
- Autonomous harmful actions
- Credential extraction or malware generation
- Identity impersonation
- Any illegal or rights-violating use

## Training Data

Summarize the training corpus without exposing raw private or restricted data.

- Data manifest version:
- Languages:
- Domains:
- Training token count:
- License review status:
- PII filtering status:
- Deduplication method:
- Benchmark contamination check status:

## Training Procedure

- Training framework:
- Hardware:
- Precision:
- Optimizer:
- Learning-rate schedule:
- Batch size:
- Sequence length:
- Training duration:
- Checkpoint selection criteria:

## Evaluation

Include public and internal aggregate evaluations.

| Area | Benchmark | Score | Notes |
| --- | --- | --- | --- |
| General reasoning | TBD | TBD | TBD |
| Japanese | TBD | TBD | TBD |
| Code | TBD | TBD | TBD |
| Math | TBD | TBD | TBD |
| Long context | TBD | TBD | TBD |
| Safety | TBD | TBD | TBD |

## Known Limitations

Document observed weaknesses.

- Hallucination patterns:
- Weak domains:
- Language limitations:
- Reasoning limitations:
- Safety limitations:
- Inference constraints:

## Safety and Misuse

- Safety evaluation date:
- Red-team method:
- Refusal behavior summary:
- Known misuse risks:
- Mitigations:
- Reporting channel:

## Environmental and Compute Notes

- Estimated training compute:
- Energy or carbon estimate, if available:
- Inference hardware recommendations:

## Citation

Provide citation details for the model release.

```bibtex
@software{falcie_tbd,
  title = {fal'Cie},
  author = {TBD},
  year = {TBD},
  url = {https://github.com/yoshidashingo/falcie}
}
```

## Change Log

- Initial release:
- Updates:
- Deprecations:
