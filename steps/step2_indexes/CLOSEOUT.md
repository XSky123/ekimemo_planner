# Step2 Closeout

Updated: 2026-07-11

## Current State

| Area | Status | Deferred modeling work |
|---|---|---|
| Attack | Candidate report stable | uptime, condition match and opportunity cost belong in role profiles |
| Defense | Candidate report stable | survival/hold-time composition must not be a simple sum |
| EXP/PT | Candidate report stable | separate farming, score, 育成 and activity goals |
| Utility/conditions | Audited; includes mobility/visit indexes; retain maintenance watch | recipient/trigger semantics and category boundaries remain high impact |
| Prototype lookup | Full report available | maintain incrementally when new denko arrive |

Shared numeric, probability, range, behavioral-effect and VU rules are implemented in the report generators and `cache/project_rules.json`. Stable semantic corrections are written back to Step1 records/DB.

All remaining scoring work moved to `steps/step3_role_profiles/TODO.md`. When Step1 facts change, rerun `python pipeline/analysis/build_step2_reports.py` and keep the utility classifier audit green.
