# Pipeline

This directory is for implementation code.

Keep Step 1 simple:

- `ingest/`: fetch and cache raw pages.
- `parse/`: deterministic parsers and small LLM fallback hooks.
- `review/`: review queue generation and human correction helpers.

Do not put solver optimization here yet.

