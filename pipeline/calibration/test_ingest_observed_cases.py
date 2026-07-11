from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.calibration.ingest_observed_cases import media_kind, scan_archive  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        archive_path = Path(directory) / "observed.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("notes/team.md", "example team")
            archive.writestr("cases/team.json", json.dumps({"scene": "capture"}))
            archive.writestr("screenshots/example.png", b"not-a-real-png-but-a-stable-test-payload")
        first = scan_archive(archive_path, {})
        prior = {row["case_id"]: {**row, "parse_status": "parsed", "record_meta": {"review_reasons": []}} for row in first}
        second = scan_archive(archive_path, prior)
    checks = [
        ("entry_count", len(first) == 3),
        ("media_kinds", {row["media_kind"] for row in first} == {"text", "structured", "image"}),
        ("stable_ids", [row["case_id"] for row in first] == [row["case_id"] for row in second]),
        ("resume_status", all(row["parse_status"] == "parsed" for row in second)),
        ("no_fact_authority", all(row["source_kind"] == "observed_case" and row["calibration_only"] for row in second)),
        ("classification", media_kind("anything.JSONL") == "structured" and media_kind("no_extension") == "other"),
    ]
    failures = [name for name, ok in checks if not ok]
    print(json.dumps({"checks": len(checks), "failures": len(failures), "details": failures}, ensure_ascii=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
