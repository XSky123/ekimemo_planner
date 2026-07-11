from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "observed_cases"
DEFAULT_QUEUE = DEFAULT_INPUT / "ingest_queue.jsonl"
DEFAULT_MANIFEST = DEFAULT_INPUT / "manifest.json"
JST = timezone(timedelta(hours=9))
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv"}
STRUCTURED_SUFFIXES = {".json", ".jsonl", ".yaml", ".yml"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def media_kind(entry_path: str) -> str:
    suffix = Path(entry_path).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in TEXT_SUFFIXES:
        return "text"
    if suffix in STRUCTURED_SUFFIXES:
        return "structured"
    return "other"


def display_path(path: Path) -> str:
    """Keep the default handoff path relative, while allowing a safe custom input directory."""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def read_queue(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {
        row["case_id"]: row
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8", newline="\n")


def scan_archive(path: Path, prior_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    archive_hash = sha256_file(path)
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for info in sorted((item for item in archive.infolist() if not item.is_dir()), key=lambda item: item.filename):
            payload = archive.read(info)
            entry_hash = sha256_bytes(payload)
            entry_identity = sha256_bytes(f"{info.filename}\0{entry_hash}".encode("utf-8"))
            case_id = f"observed:{archive_hash[:16]}:{entry_identity[:16]}"
            current = prior_rows.get(case_id) or {}
            rows.append({
                "case_id": case_id,
                "source_kind": "observed_case",
                "archive_path": display_path(path),
                "archive_hash": archive_hash,
                "entry_path": info.filename,
                "entry_hash": entry_hash,
                "media_kind": media_kind(info.filename),
                "parse_status": current.get("parse_status", "queued"),
                "calibration_only": True,
                "record_meta": {
                    "source_authority": "observed_case",
                    "source_url": None,
                    "content_hash": entry_hash,
                    "parser_version": "observed_case_manifest.v1",
                    "confidence": "unverified",
                    "needs_review": current.get("parse_status", "queued") in {"queued", "needs_review"},
                    "review_reasons": current.get("record_meta", {}).get("review_reasons") or ["observed_case_requires_separate_parse"],
                    "ingested_at": datetime.now(JST).isoformat(),
                },
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a resumable metadata queue for observed-case ZIP attachments.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    input_dir = args.input_dir.resolve()
    queue_path = args.queue.resolve()
    manifest_path = args.manifest.resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    prior = read_queue(queue_path)
    rows: list[dict[str, Any]] = []
    archives: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for path in sorted(input_dir.glob("*.zip")):
        try:
            archive_rows = scan_archive(path, prior)
            rows.extend(archive_rows)
            archives.append({"path": display_path(path), "hash": sha256_file(path), "entries": len(archive_rows)})
        except (OSError, zipfile.BadZipFile) as exc:
            issues.append({"archive": display_path(path), "reason_zh": f"无法读取 ZIP：{exc}"})
    rows.sort(key=lambda row: row["case_id"])
    write_jsonl(queue_path, rows)
    manifest = {
        "artifact": "observed_case_manifest",
        "parser_version": "observed_case_manifest.v1",
        "generated_at": datetime.now(JST).isoformat(),
        "archives": archives,
        "queue_count": len(rows),
        "issues": issues,
        "policy_zh": "案例只用于校准与解释，不覆盖 wiki 详情事实；此阶段不解压落盘、不 OCR、不推断队伍含义。",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"archives": len(archives), "queue_count": len(rows), "issues": len(issues)}, ensure_ascii=True))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
