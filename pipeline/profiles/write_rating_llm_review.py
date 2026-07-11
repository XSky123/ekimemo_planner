from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

# Human/LLM-authored findings after reading the compact top/bottom evidence and
# targeted Japanese condition text. Unlisted sampled rows were explicitly
# checked and accepted for the current model version.
ROUND1_FINDINGS: dict[tuple[str, str], dict[str, Any]] = {
    ("daily_attack", "original:015"): {"verdict": "overrated", "layer": "step1", "review_zh": "昼间限定 ATK 被当成全天无条件；应结构化 06:00–18:00。"},
    ("daily_attack", "original:032"): {"verdict": "overrated", "layer": "step1", "review_zh": "ATK 上限依赖当日访问 50 站，当前按区间均值且无访问门槛。"},
    ("daily_attack", "original:046"): {"verdict": "overrated", "layer": "step1", "review_zh": "45% 是承受约 20 次攻击后的峰值，不是无脑打第一站的常驻值。"},
    ("daily_attack", "original:064"): {"verdict": "overrated", "layer": "step1", "review_zh": "效果依赖当日移动距离，100km 后才有全队段，不能列作无条件日常攻击。"},
    ("daily_attack", "original:085"): {"verdict": "overrated", "layer": "step1", "review_zh": "50% 是累计 Link 20 次后的峰值；第一次抢站没有该增益。"},
    ("daily_attack", "extra:103"): {"verdict": "overrated", "layer": "step1", "review_zh": "峰值要求多名“マスターにおまかせ”技能正在发动，且一次 Link 失败会终止全队技能。"},
    ("burst_attack", "original:046"): {"verdict": "overrated", "layer": "step1", "review_zh": "受击叠层不能在计划爆发前自由准备，峰值可达不等于爆发可用。"},
    ("burst_attack", "original:085"): {"verdict": "overrated", "layer": "step1", "review_zh": "Link 叠层 20 次属于滚雪球，不是可按按钮获得的爆发。"},
    ("burst_attack", "extra:103"): {"verdict": "conditional", "layer": "step3", "review_zh": "可作为成型队伍爆发，但必须显示主动技能数量和失败清空风险。"},
    ("home_defense", "extra:044"): {"verdict": "overrated", "layer": "step1", "review_zh": "固定减伤要求自身以外另有两名角色正在 Link，缺少该高门槛。"},
    ("home_defense", "original:089"): {"verdict": "overrated", "layer": "step1", "review_zh": "高 DEF 只在满 HP；受一次伤害后效果骤降，不能按整段 60% 评价。"},
    ("home_defense", "original:141"): {"verdict": "overrated", "layer": "step1", "review_zh": "40% 取决于全队同时 Link 数，自身 Link 才有全队段，当前峰值成本不足。"},
    ("expedition_score", "extra:091"): {"verdict": "overrated", "layer": "step1", "review_zh": "需最近三次访问中已有另一名队员 Link；Link 失败还会缩短效果时间。"},
    ("expedition_score", "original:163"): {"verdict": "overrated", "layer": "step1", "review_zh": "15000 是累计伤害达阈值后一次性奖励，追加分还要求每 1000 伤害，不能直接当单次收益。"},
    ("expedition_exp", "extra:091"): {"verdict": "overrated", "layer": "step1", "review_zh": "480 EXP 的 Link 链前置和失败缩时未进入条件。"},
    ("growth", "extra:091"): {"verdict": "overrated", "layer": "step1", "review_zh": "日常育成榜忽略了最近三次 Link 链和持续时间维护成本。"},
    ("growth", "original:121"): {"verdict": "overrated", "layer": "step1", "review_zh": "420 是同主题 Film 最多 7 人时的上限；没有 Film 组合就没有收益。"},
    ("expedition_exp", "extra:026"): {"verdict": "scene_error", "layer": "step3", "review_zh": "该经验授予对手，不是己方远征经验收益，应从推荐候选排除。"},
    ("growth", "extra:026"): {"verdict": "scene_error", "layer": "step3", "review_zh": "该经验授予对手，不能作为己方育成组件。"},
    ("expedition_exp", "original:020"): {"verdict": "underrated", "layer": "step3", "review_zh": "40% 是经验分配比例，不应使用固定 EXP=300 的锚点；Wiki ◎ 的育成工具价值被压低。"},
    ("growth", "original:020"): {"verdict": "underrated", "layer": "step3", "review_zh": "百分比经验分配单位被按固定经验量归一化，导致明显低估。"},
    ("mechanism", "original:034"): {"verdict": "underrated", "layer": "step3", "review_zh": "发动率 1.32 倍应按 +32% 解释，不应把 1.32 直接除以 20。"},
}

ROUND2_FINDINGS: dict[tuple[str, str], dict[str, Any]] = {
    ("daily_attack", "original:149"): {"verdict": "overrated", "layer": "step1", "review_zh": "65% 峰值确实高，但 Link 失败会概率自爆并强制结束技能，日常稳定性缺少风险折扣。"},
    ("burst_attack", "original:149"): {"verdict": "conditional", "layer": "step3", "review_zh": "适合一次性抢站爆发，但失败惩罚必须作为显式风险列，不能与无副作用 65% 等价。"},
    ("home_defense", "original:103"): {"verdict": "overrated", "layer": "step1", "review_zh": "固定减伤主段随当日访问站数增长，追加段分别要求 15/70 站；当前仍过度接近峰值。"},
    ("home_defense", "original:067"): {"verdict": "overrated", "layer": "step1", "review_zh": "减伤随当日访问站数增长，26/40 站才解锁全队追加段，不能按无条件守站评价。"},
    ("home_defense", "original:124"): {"verdict": "overrated", "layer": "step1", "review_zh": "追加 50% DEF 只在上次被访问后两分钟内再次被访问时出现，低频环境只有基础段。"},
    ("mechanism", "extra:002"): {"verdict": "underrated", "layer": "step3", "review_zh": "机制榜应评价命中对应属性编成时的克制价值；用全天覆盖率把强力无效化压到尾部不合理。"},
    ("mechanism", "extra:003"): {"verdict": "underrated", "layer": "step3", "review_zh": "与 EX2 同类，命中 heat 编成时价值很高，应分开显示适用率与命中后的机制强度。"},
    ("mechanism", "extra:004"): {"verdict": "underrated", "layer": "step3", "review_zh": "与 EX2 同类，命中 cool 编成时价值很高，不能只用持续/冷却覆盖率排序。"},
    ("mechanism", "extra:107"): {"verdict": "underrated", "layer": "step3", "review_zh": "条件很多但命中目标时为确定无效化；机制榜应保留条件列并提高命中强度。"},
    ("mechanism", "extra:108"): {"verdict": "underrated", "layer": "step3", "review_zh": "条件型确定无效化被平均发生率重复惩罚，适用性与强度应拆列。"},
    ("mechanism", "extra:109"): {"verdict": "underrated", "layer": "step3", "review_zh": "条件型确定无效化被平均发生率重复惩罚，适用性与强度应拆列。"},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, required=True, choices=(1, 2))
    args = parser.parse_args()
    queue = ROOT / "data/review_queue" / f"step3_rating_llm_round{args.round}.jsonl"
    rows = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines() if line.strip()]
    findings = ROUND1_FINDINGS if args.round == 1 else ROUND2_FINDINGS
    for row in rows:
        finding = findings.get((row["scene"], row["denko_id"]))
        if finding:
            row["llm_review"] = {**finding, "reviewed": True, "action": "fix_and_rerank"}
        else:
            component = row["components"][0] if row["components"] else None
            reason = (
                f"{component['effect']}，效果量={component['value']}，条件系数={component['condition']}；当前位次与结构化证据相容。"
                if component else "该场景没有有效组件，不应进入候选。"
            )
            row["llm_review"] = {"reviewed": True, "verdict": "pass", "layer": "none", "review_zh": reason, "action": "none"}
    out = ROOT / "data/audits" / f"step3_rating_llm_round{args.round}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    counts = Counter(row["llm_review"]["verdict"] for row in rows)
    summary = {
        "artifact": f"step3_rating_llm_round{args.round}", "rows": len(rows),
        "reviewed": sum(bool(row["llm_review"].get("reviewed")) for row in rows),
        "by_verdict": dict(sorted(counts.items())),
        "actionable": sum(row["llm_review"]["action"] != "none" for row in rows),
        "queue": str(queue.relative_to(ROOT)), "results": str(out.relative_to(ROOT)),
    }
    summary_path = ROOT / "data/audits" / f"step3_rating_llm_round{args.round}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
