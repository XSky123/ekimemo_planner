# Step2 防御/守站辅助报表 TODO

更新时间: 2026-07-04

## 当前状态

- 当前报表: `data/reports/step2_defense_support_rankings_zh.html`
- 当前脚本: `pipeline/analysis/write_defense_support_rankings.py`
- 数据来源: `data/step1_db/skill_facts.jsonl`
- 状态: 已生成、已抽查、已回写一批稳定目标/数值修复，并已发布到 GitHub Pages。

## 当前分类

| 页签 | 用途 |
|---|---|
| 守站本体：自己DEF | 单体守站核心的 DEF 增加 |
| DEF辅助：队友/队伍 | 给自身以外、队伍、被访问者或条件对象加 DEF |
| 伤害减轻/上限 | `damage_reduction` / `damage_cap` |
| HP回复/续航 | `hp_recovery` / `hp_recovery_bonus` |
| 无效化/保命 | `damage_nullification` / `survive_hp1` / `damage_substitution` |
| 降低对手输出 | `atk_debuff` / `skill_disable` / `battery_disable` |
| link保持 | `link_continue` / `link_retention` |
| 反击/惩罚 | `counter` / `counter_damage` / `reboot` / `force_hp_zero` |

## 已完成清理

- 已回写 `original:102` 曜日表 ATK / DEF / 固定ダメージ / ダメージ軽減。
- 已修正并回写多处防御目标: `extra:052`、`original:024`、`extra:011`、`extra:082`、`extra:122`、`original:048`、`original:082`、`original:092`。
- 已处理 `original:035 def_buff_1` 的 `n駅×倍率%`，Lv50 为最大 40、平均 20。
- 已将 `extra:002` / `extra:003` / `extra:004` 标为属性技能无效化，并显示自身同属性技能冲突；不再和普通减伤/DEF排行混为一类。
- 已将 `original:033 賢島エリア` 的技能无效化标为“部分伤害增加技能无效化”，和 EX2/3/4 的属性技能无效化分开。
- 已为 `original:162 福住みぞれ` 的 DEF 正负效果增加温度带显示。
- 已加入 `pipeline/ingest/backfill_per_unit_ranges.py`，用于幂等回写 `n駅×倍率%` / `倍率×n%` 这类公式范围。
- 横向扫描当前未发现仍缺少范围的同类公式。

## 保留风险

- `自身以外` 类型通常以 `target_scope=team_all` 加 `exclude_self` filter 表示，报告中应显示“不含自己”。
- `skill_disable` 暂归入“降低对手输出”，但后续需要区分主动访问无效化、被访问防御、对双方/己方是否有副作用。
- 布尔型防御效果当前用发动概率作为可靠性分数，还没有纳入持续时间和 CD 的覆盖率。
- 当前只是候选 ranking，不是“守站时间/生存率”模拟。

## 下一步

1. 为 defense ranking 增加 uptime: `duration / (duration + cooldown)`，常驻近似 1。
2. 设计守站场景评分: DEF、减伤、HP回复、无效化、对手 ATK debuff 不要简单相加。
3. 抽查每个页签少量高排名候选，重点确认对象、触发方向、队伍属性条件。
