# Release Checklist

No fal'Cie weights should be published until this checklist is complete for the target checkpoint.

## 1. Repository Readiness

- [ ] README links to the release.
- [ ] Model card is complete.
- [ ] License is present and compatible with release assets.
- [ ] Evaluation report is published.
- [ ] Data policy compliance is documented.
- [ ] Training config and metadata are available.
- [ ] Known limitations are documented.

## 2. Artifact Readiness

- [ ] Model weights are uploaded.
- [ ] Tokenizer files are uploaded.
- [ ] Config files are uploaded.
- [ ] Generation config is uploaded.
- [ ] Checksums are published.
- [ ] File names are versioned and stable.
- [ ] Quantized variants are clearly labeled, if provided.

## 3. Evaluation Gate

- [ ] Public benchmark suite completed.
- [ ] Private regression suite completed.
- [ ] Japanese evaluation completed.
- [ ] Code evaluation completed.
- [ ] Math evaluation completed.
- [ ] Long-context evaluation completed.
- [ ] Safety evaluation completed.
- [ ] No unresolved critical regressions.

## 4. Data and Legal Gate

- [ ] Dataset manifest is frozen.
- [ ] License review completed.
- [ ] PII filtering completed.
- [ ] Benchmark contamination check completed.
- [ ] Excluded data sources are documented.
- [ ] Third-party attribution requirements are satisfied.

## 5. Safety Gate

- [ ] Misuse analysis completed.
- [ ] Refusal behavior reviewed.
- [ ] Dangerous capability risks documented.
- [ ] Known jailbreak weaknesses documented.
- [ ] Reporting channel is available.
- [ ] Release notes include safety limitations.

## 6. Distribution Gate

- [ ] Hugging Face repository prepared.
- [ ] GitHub Release prepared.
- [ ] Mirror or fallback distribution considered for large files.
- [ ] Download instructions tested.
- [ ] Example inference script tested.
- [ ] Fine-tuning example tested, if promised.

## 7. Final Approval

- [ ] Release owner:
- [ ] Evaluation owner:
- [ ] Data owner:
- [ ] Safety owner:
- [ ] Date:
- [ ] Commit SHA:
- [ ] Tag:

## Release Notes Template

```markdown
# fal'Cie <version>

## Summary

## What's Included

## Evaluation Results

## Known Limitations

## Safety Notes

## Download

## Checksums

## Citation
```
