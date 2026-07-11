# Step 5: UI / Agent

Status: local prototype available.

Start only after Step 4 solver behavior is stable enough to explain.

Goal:

- User-facing display in Chinese.
- Preserve key Japanese game terms.
- Read indexes and targeted records first to control token use.
- Explain active skills, inactive skills, priors, and observed cases.

## Local Prototype

Run `python pipeline/ui/serve_solver.py` and open `http://127.0.0.1:8765`.
The UI calls the same Step4 request schema and solver as the report pipeline; it
does not contain its own scoring logic. It is a local work surface, not a
published recommendation UI yet.
