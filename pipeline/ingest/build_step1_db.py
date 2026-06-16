from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import parse as base


OUT_DIR = base.ROOT / "data" / "step1_db"
POOLS = ("original", "extra")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def pool_from_denko_id(denko_id: str) -> str:
    return denko_id.split(":", 1)[0]


def number_from_denko_id(denko_id: str) -> int:
    return int(denko_id.split(":", 1)[1])


def record_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    denko_id = row.get("denko_id") or row.get("identity", {}).get("denko_id")
    pool = pool_from_denko_id(denko_id)
    return (POOLS.index(pool), number_from_denko_id(denko_id))


def canonical_identity(row: dict[str, Any]) -> tuple[str, str]:
    denko_id = row.get("denko_id") or row.get("identity", {}).get("denko_id")
    content_hash = row.get("record_meta", {}).get("content_hash") or ""
    return denko_id, content_hash


def load_batch_rows(kind: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources: list[str] = []
    for pool in POOLS:
        for path in sorted(base.RECORD_DIR.glob(f"{pool}_*_ {kind}.jsonl")):
            raise AssertionError(f"unexpected spaced glob result: {path}")
        for path in sorted(base.RECORD_DIR.glob(f"{pool}_*_{kind}.jsonl")):
            sources.append(str(path.relative_to(base.ROOT)))
            rows.extend(read_jsonl(path))
    return rows, {"source_files": sources, "source_row_count": len(rows)}


def dedupe_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        denko_id = row.get("denko_id") or row.get("identity", {}).get("denko_id")
        if denko_id:
            grouped[denko_id].append(row)
    canonical: list[dict[str, Any]] = []
    duplicate_details: list[dict[str, Any]] = []
    for denko_id, candidates in sorted(grouped.items(), key=lambda item: (POOLS.index(pool_from_denko_id(item[0])), number_from_denko_id(item[0]))):
        identities = {json.dumps(canonical_identity(row), ensure_ascii=False, sort_keys=True) for row in candidates}
        chosen = candidates[-1]
        canonical.append(chosen)
        if len(candidates) > 1:
            duplicate_details.append(
                {
                    "denko_id": denko_id,
                    "candidate_count": len(candidates),
                    "identity_count": len(identities),
                    "content_hashes": sorted({canonical_identity(row)[1] for row in candidates}),
                    "resolution": "last_batch_row_selected",
                }
            )
    return sorted(canonical, key=record_sort_key), {
        "unique_count": len(canonical),
        "duplicate_denko_count": len(duplicate_details),
        "duplicate_details": duplicate_details,
    }


def build_denko_index(denko_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, Any] = {}
    by_pool: dict[str, list[str]] = {pool: [] for pool in POOLS}
    by_wiki_no: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for row in denko_rows:
        identity = row.get("identity") or {}
        denko_id = identity.get("denko_id")
        pool = identity.get("pool") or pool_from_denko_id(denko_id)
        entry = {
            "denko_id": denko_id,
            "pool": pool,
            "id_number": identity.get("id_number"),
            "wiki_no": identity.get("wiki_no"),
            "name": identity.get("name"),
            "full_name": identity.get("full_name"),
            "type": identity.get("type"),
            "attribute": identity.get("attribute"),
            "color": identity.get("color"),
            "detail_url": identity.get("detail_url"),
            "skill_name": (row.get("list_page_fields") or {}).get("skill_name"),
        }
        by_id[denko_id] = entry
        by_pool.setdefault(pool, []).append(denko_id)
        if entry["wiki_no"]:
            by_wiki_no[entry["wiki_no"]] = denko_id
        if entry["name"]:
            by_name[entry["name"]] = denko_id
    return {
        "schema_version": 1,
        "generated_at": datetime.now(base.JST).isoformat(),
        "by_id": by_id,
        "by_pool": by_pool,
        "by_wiki_no": by_wiki_no,
        "by_name": by_name,
    }


def component_counts(skill_rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in skill_rows:
        for component in row.get("skill_components") or []:
            counter[component.get("effect_kind") or "unknown"] += 1
    return dict(sorted(counter.items()))


def validate(denko_rows: list[dict[str, Any]], skill_rows: list[dict[str, Any]]) -> dict[str, Any]:
    denko_ids = [row.get("identity", {}).get("denko_id") for row in denko_rows]
    skill_ids = [row.get("denko_id") for row in skill_rows]
    denko_set = set(denko_ids)
    skill_set = set(skill_ids)
    issues: list[dict[str, Any]] = []
    if len(denko_ids) != len(denko_set):
        issues.append({"issue": "duplicate_denko_ids", "count": len(denko_ids) - len(denko_set)})
    if len(skill_ids) != len(skill_set):
        issues.append({"issue": "duplicate_skill_ids", "count": len(skill_ids) - len(skill_set)})
    if denko_set != skill_set:
        issues.append(
            {
                "issue": "denko_skill_id_mismatch",
                "missing_skill_ids": sorted(denko_set - skill_set),
                "missing_denko_ids": sorted(skill_set - denko_set),
            }
        )
    for pool, expected in {"original": 163, "extra": 127}.items():
        denko_count = sum(1 for denko_id in denko_ids if denko_id and pool_from_denko_id(denko_id) == pool)
        skill_count = sum(1 for denko_id in skill_ids if denko_id and pool_from_denko_id(denko_id) == pool)
        if denko_count != expected or skill_count != expected:
            issues.append(
                {
                    "issue": "unexpected_pool_count",
                    "pool": pool,
                    "expected": expected,
                    "denko_count": denko_count,
                    "skill_count": skill_count,
                }
            )
    review_blockers = []
    for row in skill_rows:
        if not row.get("skill_components"):
            review_blockers.append(
                {
                    "denko_id": row.get("denko_id"),
                    "component_id": None,
                    "review_reasons": ["skill_components_empty"],
                }
            )
        for component in row.get("skill_components") or []:
            reasons = component.get("review_reasons") or []
            blockers = [
                reason
                for reason in reasons
                if reason
                in {
                    "labeled_component_count_mismatch",
                    "duplicate_labeled_component_values_need_review",
                    "compound_labeled_effect_needs_manual_review",
                    "condition_effect_mismatch_needs_review",
                    "vu_label_level_mismatch_needs_review",
                    "component_values_not_parsed",
                    "skill_components_empty",
                }
            ]
            if blockers:
                review_blockers.append(
                    {
                        "denko_id": row.get("denko_id"),
                        "component_id": component.get("component_id"),
                        "review_reasons": blockers,
                    }
                )
    if review_blockers:
        issues.append({"issue": "blocking_review_reasons_present", "items": review_blockers})
    return {
        "issue_count": len(issues),
        "issues": issues,
        "counts": {
            "denko_total": len(denko_rows),
            "skill_total": len(skill_rows),
            "by_pool": {
                pool: {
                    "denko": sum(1 for denko_id in denko_ids if denko_id and pool_from_denko_id(denko_id) == pool),
                    "skill": sum(1 for denko_id in skill_ids if denko_id and pool_from_denko_id(denko_id) == pool),
                }
                for pool in POOLS
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    out_dir = args.out_dir

    denko_batch_rows, denko_source = load_batch_rows("denko_facts")
    skill_batch_rows, skill_source = load_batch_rows("skill_facts")
    denko_rows, denko_dedupe = dedupe_rows(denko_batch_rows)
    skill_rows, skill_dedupe = dedupe_rows(skill_batch_rows)
    validation = validate(denko_rows, skill_rows)

    write_jsonl(out_dir / "denko_facts.jsonl", denko_rows)
    write_jsonl(out_dir / "skill_facts.jsonl", skill_rows)
    write_json(out_dir / "denko_index.json", build_denko_index(denko_rows))

    manifest = {
        "schema_version": 1,
        "artifact": "step1_db",
        "generated_at": datetime.now(base.JST).isoformat(),
        "parser_version": base.PARSER_VERSION,
        "language_policy": {
            "display": "zh",
            "source_facts": "ja",
            "schema_keys": "en",
        },
        "scope": {
            "included_pools": list(POOLS),
            "excluded_pools": ["special", "collaboration"],
        },
        "outputs": {
            "denko_facts": "data/step1_db/denko_facts.jsonl",
            "skill_facts": "data/step1_db/skill_facts.jsonl",
            "denko_index": "data/step1_db/denko_index.json",
            "manifest": "data/step1_db/manifest.json",
            "validation": "data/step1_db/validation.json",
        },
        "source_batches": {
            "denko": denko_source,
            "skill": skill_source,
        },
        "dedupe": {
            "denko": denko_dedupe,
            "skill": skill_dedupe,
        },
        "metrics": {
            **validation["counts"],
            "skill_component_effect_kind_counts": component_counts(skill_rows),
        },
        "review_status": {
            "checklist_issue_count": validation["issue_count"],
            "original_audit": "data/reports/original_001_163_full_audit_zh.html",
            "extra_audit": "data/reports/extra_full_audit_zh.html",
        },
    }
    write_json(out_dir / "manifest.json", manifest)
    write_json(out_dir / "validation.json", validation)
    print(
        json.dumps(
            {
                "out_dir": str(out_dir.relative_to(base.ROOT)),
                "denko_total": len(denko_rows),
                "skill_total": len(skill_rows),
                "issue_count": validation["issue_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if validation["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
