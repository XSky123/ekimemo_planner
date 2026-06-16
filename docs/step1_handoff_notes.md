# Step1 Handoff Notes

Date: 2026-06-16

Step1 is closed as the first ingestion and cleanup phase. The canonical output is `data/step1_db/`.

## Final Status

- Denko total: 290
- Skill total: 290
- Original: 163
- Extra: 127
- Step1 validation: 0 issues
- Original checklist audit: 0 issues
- Extra checklist audit: 0 issues
- Recommendation prior audit: 288 checked, 2 info findings, 0 warn/error findings

The remaining recommendation prior findings are intentionally not applied to DB facts:

- `extra:118` recommendation prior mentions `atk_buff`; detail page facts do not confirm it.
- `extra:125` recommendation prior mentions `def_buff`; detail page facts do not confirm it.

## Canonical Artifacts

- `data/step1_db/denko_facts.jsonl`
- `data/step1_db/skill_facts.jsonl`
- `data/step1_db/denko_index.json`
- `data/step1_db/manifest.json`
- `data/step1_db/validation.json`
- `data/reports/step1_final_report_zh.html`

Batch records under `data/records/` are retained as inspectable intermediate facts. They are useful when checking how canonical rows were normalized.

## Project Rules To Preserve

- User-facing explanations, report labels, and review reasons are Chinese.
- Wiki/game source facts remain Japanese.
- JSON/schema/parser keys remain English.
- Do not trust Japanese text rendered through Windows PowerShell if it looks garbled. Re-check with Python UTF-8 output or direct UTF-8 reads.
- Detail wiki pages are fact authority.
- Beginner recommendation pages are priors and QA checks only. They do not override detail page facts.
- Observed teams/screenshots are future case/calibration data, not correctness labels.

## Parser Lessons

- Numbered effects like `(1)/(2)/(3)` are high-risk. If detected labels and emitted components do not match, treat the row as suspicious.
- Label-specific probabilities must be extracted from raw probability text. Do not let `(2)` inherit `(1)` probability.
- Wiki merged cells often put attributes at the end, for example `編成内の の数 ... cool属性でんこ`. Normalize these placeholders in `condition_raw` while preserving original Japanese facts in raw fields.
- Distinguish own-team constraints from opponent constraints. `相手がheat属性` and `heat属性のでんこからアクセスされる` should become opponent filters, not own-team filters.
- Distinguish active access and passive accessed triggers.
- Negative/exclusion text is not a positive effect. For example, `リンクボーナスを増加するスキルは効果の対象外` is not `link_bonus_zero`.
- Only explicit zero-link-bonus text such as `リンクボーナスが0` should create `link_bonus_zero`.
- Cooldown reduction is not always fixed `-5%`. Only specific source text/value should create fixed `cooldown_reduction`.
- VU-only and Lv92/96/100 rows need explicit availability semantics. Lv30 and Lv50 remain the most important practical checkpoints.

## Main Scripts

- `pipeline/ingest/parse.py`: detail page table parser.
- `pipeline/ingest/normalize_skill_facts.py`: semantic normalization and common cleanup.
- `pipeline/ingest/report_checklist_audit.py`: batch/report consistency audit.
- `pipeline/ingest/recommendation_prior_audit.py`: beginner recommendation prior audit.
- `pipeline/ingest/build_step1_db.py`: canonical Step1 DB builder and validation.

## Cleanup Policy

For Step1 close, keep canonical DB, retained batch source records, audit JSON, code, docs, and one browsable final report. Remove old exploration samples, split batch HTML reports, old full HTML reports, and Python bytecode caches.
