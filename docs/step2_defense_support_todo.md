# Step2 防御/守站辅助报表 TODO

更新时间: 2026-07-03

## 当前状态

- 当前报表: `data/reports/step2_defense_support_rankings_zh.html`
- 当前脚本: `pipeline/analysis/write_defense_support_rankings.py`
- 数据来源: `data/step1_db/skill_facts.jsonl`

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

## 已知风险

- 已在 2026-07-03 抽查并回写一批稳定目标/数值修正：
  - `original:102` 曜日表 ATK / DEF / 固定ダメージ / ダメージ軽減。
  - `extra:052 def_buff_1` 目标修为 `self`。
  - `original:024 damage_reduction_2` 目标修为 `self`。
  - `extra:011 hp_recovery_1/2` 目标修为 `accessed_denko`。
  - `extra:082 hp_recovery_1`、`extra:122 hp_recovery_2` 目标修为 `self`。
  - `original:048`、`original:082`、`original:092` 的先头车 DEF 目标修为 `own_front_car`。
  - `original:035 def_buff_1` 的 `n駅×倍率%` 范围回写为 `0～上限5駅×倍率`，Lv50 为最大 40、平均 20。
- 剩余 `自身以外` 类型通常以 `target_scope=team_all` 加 `exclude_self` filter 表示，报告中应显示“不含自己”。
- 部分 DB 的 `target_scope` 仍可能偏粗，后续发现稳定问题时继续回写 DB，并保留 manual/stable lock。
- `n駅×倍率%`、`倍率×n%` 这类公式已加入 `backfill_per_unit_ranges.py` 幂等回写；横向扫描当前未发现仍缺少范围的同类公式。
- `skill_disable` 在防御中暂归入“降低对手输出”，但实际还要区分主动访问无效化、被访问防御、对双方/己方是否有副作用。
- 布尔型防御效果当前用发动概率作为可靠性分数；还没有纳入持续/CD 的 uptime。
- 尚未实现“守站时间/生存率”模拟，当前只是候选 ranking，不是最终 solver 分数。

## 下一步

1. 随机抽查每个页签 3-5 个候选，重点确认对象、触发方向、队伍属性条件。
2. 对确认稳定的 target/数值问题回写 Step1 DB，避免只在报表层修。
3. 为 defense ranking 增加 uptime: `duration / (duration + cooldown)`，常驻近似 1。
4. 设计守站场景评分: DEF/减伤/回复/无效化/对手 ATK debuff 的边际收益不要简单相加。
