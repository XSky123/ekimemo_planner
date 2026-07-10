# Cache Directory

Tracked file:

- `project_rules.json`: compact project-wide language, authority, handoff, model-routing and report rules.

Ignored runtime caches may appear here:

- `prototype_pages/`
- `prototype_reference_pages/`
- `prototype_extract/`

They are reproducible web caches, not facts or handoff artifacts. Current facts belong in `data/step1_db/`; raw Step1 page cache remains in ignored `data/raw_pages/` because active parsers read that path.
