from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "reports"

RANKING_GENERATORS = [
    ("attack", ["pipeline/analysis/write_attack_support_rankings.py"]),
    ("defense", ["pipeline/analysis/write_defense_support_rankings.py"]),
    ("exp_pt", ["pipeline/analysis/write_exp_pt_support_rankings.py"]),
    ("mobility", ["pipeline/analysis/write_mobility_visit_rankings.py"]),
    ("utility", ["pipeline/analysis/write_skill_utility_reports.py"]),
]

PROTOTYPE_GENERATOR = (
    "prototype",
    ["pipeline/prototype/write_prototype_sample_report.py", "--all", "--render-only"],
)

FINAL_GENERATORS = [
    (
        "all_reports",
        ["pipeline/analysis/write_step2_all_reports.py"],
    ),
    ("semantic_audit", ["pipeline/analysis/audit_step2_reports.py"]),
]

STEP2_REPORTS = [
    "step2_attack_support_rankings_zh.html",
    "step2_defense_support_rankings_zh.html",
    "step2_exp_pt_support_rankings_zh.html",
    "step2_mobility_visit_rankings_zh.html",
    "step2_skill_utility_reports_zh.html",
    "step2_prototype_lookup_zh.html",
    "step2_all_reports_zh.html",
]

UTILITY_WARNING = (
    "提醒：技能工具索引仍按用户标记为风险报表。下次改动/发布前，需要复查分类边界："
    "无效化、效果量强化、CD/概率操作、条件索引、访问次数。"
)


def run_step(name: str, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    command = [sys.executable, *args]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} failed with exit code {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    summary: Any = None
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            summary = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    return {
        "name": name,
        "command": " ".join(args),
        "summary": summary,
        "stdout_tail": completed.stdout.splitlines()[-3:],
    }


def smoke_check_reports() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for filename in STEP2_REPORTS:
        path = REPORT_DIR / filename
        if not path.exists():
            issues.append({"file": filename, "issue": "missing"})
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        if b"\r\n" in data:
            issues.append({"file": filename, "issue": "crlf"})
        if "\ufffd" in text or "????" in text:
            issues.append({"file": filename, "issue": "mojibake_marker"})
    all_report = (REPORT_DIR / "step2_all_reports_zh.html").read_text(encoding="utf-8")
    template_count = all_report.count('type="text/plain" id="report-template-')
    if "<iframe" in all_report.lower():
        issues.append({"file": "step2_all_reports_zh.html", "issue": "iframe_present"})
    if template_count != 6:
        issues.append(
            {
                "file": "step2_all_reports_zh.html",
                "issue": f"unexpected_template_count:{template_count}",
            }
        )
    return {
        "files": len(STEP2_REPORTS),
        "all_report_templates": template_count,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-prototype",
        action="store_true",
        help="Also render the prototype lookup report from the existing JSONL. This changes generated_at.",
    )
    args = parser.parse_args()

    print(UTILITY_WARNING)
    generators = [*RANKING_GENERATORS]
    if args.include_prototype:
        generators.append(PROTOTYPE_GENERATOR)
    generators.extend(FINAL_GENERATORS)
    steps = [run_step(name, command) for name, command in generators]
    smoke = smoke_check_reports()
    if smoke["issues"]:
        raise RuntimeError(json.dumps({"smoke_check": smoke}, ensure_ascii=False, indent=2))
    result = {
        "steps": steps,
        "smoke_check": smoke,
        "warning": UTILITY_WARNING,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
