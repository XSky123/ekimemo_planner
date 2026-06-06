# Cache Directory

This directory currently contains two kinds of files:

- Active handoff/config files:
  - `project_rules.json`
  - `cache_manifest.json`
- Legacy/prototype cache from the previous agent phase:
  - `01_reverse_index/`
  - `02_denko_profile/`
  - `03_skill_parsed/`
  - `04_solver_results/`
  - `manual_overrides/`

For the new Step 1 pipeline, write generated records to `data/`, not to these old prototype cache folders.

Old prototype cache can be used as reference only after checking source authority, confidence, and `needs_review`.

