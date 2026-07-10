# Step1 Review Agent

Use this only for incremental Original/Extra ingestion or parser regression review.

## Controller

1. Run deterministic fetch/parse/normalize/audit first.
2. Group failures by shared parser pattern.
3. Fix repeated patterns and rerun before semantic review.
4. Keep transient state and prompts under `tmp/review_runs/`.

## Semantic Review

Review only suspicious records. Read denko id, component id, condition/remarks, relevant level rows, raw headers and source URL. Check label count/order, target, trigger actor/direction, opponent vs own-team constraints, VU availability, probability mapping and formula/range values.

Return a structured patch only when the detail-page evidence is sufficient. Keep Japanese evidence, Chinese reason, confidence, patch id and source authority.

## Acceptance

- Stable fixes are reapplied through parser/backfill/manual patch code.
- Manual fixes are locked against parser overwrite.
- Step1 validation and Step2 semantic audit both return zero issues.
- Remaining ambiguity goes to an active review queue; do not force-fill it.
