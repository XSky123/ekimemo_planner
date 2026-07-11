from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(script: str) -> None:
    subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild and validate Step3 role profiles from canonical Step1 facts.")
    parser.add_argument(
        "--refresh-priors",
        action="store_true",
        help="Fetch the two beginner recommendation pages before rebuilding the Step3 report. Requires network access.",
    )
    args = parser.parse_args()
    if args.refresh_priors:
        run("pipeline/ingest/recommendation_prior_audit.py")
    elif not (ROOT / "data/audits/recommendation_prior_audit.json").exists():
        raise SystemExit("recommendation prior audit is missing; rerun with --refresh-priors when network access is available")
    run("pipeline/profiles/build_role_profiles.py")
    run("pipeline/profiles/validate_role_profiles.py")
    run("pipeline/profiles/test_role_profile_regressions.py")
    run("pipeline/profiles/audit_external_strategy_priors.py")
    run("pipeline/profiles/audit_role_profile_samples.py")
    run("pipeline/profiles/score_denko_ratings.py")
    run("pipeline/profiles/validate_denko_ratings.py")
    run("pipeline/profiles/test_denko_rating_regressions.py")
    run("pipeline/profiles/write_role_profile_report.py")
    run("pipeline/profiles/write_denko_rating_report.py")
    run("pipeline/profiles/audit_rating_llm_reviews.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
