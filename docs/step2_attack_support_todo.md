# Step2 攻击辅助报表 TODO

更新时间: 2026-07-04

## 当前状态

- 当前报表: `data/reports/step2_attack_support_rankings_zh.html`
- 当前脚本: `pipeline/analysis/write_attack_support_rankings.py`
- 数据来源: `data/step1_db/skill_facts.jsonl`
- 状态: 已生成、已抽查、已回写稳定语义修复，并已发布到 GitHub Pages。

## 已完成清理

- 已拆分页签: 自用 ATK、队友/队伍 ATK、固定伤害、降低对手 DEF。
- 已支持等级基准切换: `Lv30` / `Lv50` / `Lv80` / `Lv92` / `Lv100`。
- 已支持 VU-only 默认隐藏，并可在报表中打开。
- 已把范围型效果拆成理论最大和平均值排序。
- 已将稳定的 target/数值问题回写 Step1 DB，避免只在 HTML/report 层修。
- 已将 `original:059 嵯峨野もみじ` 的 ATK 增幅建模为“对手编成类型数 × 单位倍率，上限4类型”，不再当作固定 +15/+20%。
- 已为 `original:162 福住みぞれ` 增加温度带限制显示；详情页语义为己方编成内效果，30°C以上的 DEF-20% 不当作对手 DEF debuff。
- 已为 `extra:010 夕陽ケ丘ウシオ` 增加爆发按钮、长 CD、车位转移标签；`extra:094 クラウディア` 增加己方 heat 访问与对手 supporter≥3 条件。
- 已完成线上发布，报告目录可访问。

## 保留风险

- 公式型、天气/距离/站数等条件型效果仍是 ranking 候选，不等于最终组队评分。
- 部分 `target_scope` 仍可能偏粗；发现稳定语义问题时继续回写 DB，并保留 reason/source/lock。
- 自用 ATK 报表会结合 AP 估算结果，但 wiki 原页缺失 Lv92 AP/HP 时，Lv92 显示空值属于 source coverage 问题。
- 固定伤害和 DEF debuff 后续进入 solver 时，需要结合攻击对象、站点属性、队伍限制和触发方向二次评分。

## 下一步

1. 为攻击报表增加 uptime/覆盖率估算: 常驻为 1，手动技能按 `duration / (duration + cooldown)` 近似。
2. 把攻击候选转为 solver 可读的 role profile，不直接把报表排序当最终配队分数。
3. 设计“抢站场景”评分: AP/ATK%、固定伤害、对手 DEF debuff、概率、条件匹配度分开建模。
