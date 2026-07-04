# Step2 位移/访问次数辅助报表 TODO

更新时间: 2026-07-04

## 当前状态

- 当前报表: `data/reports/step2_mobility_visit_rankings_zh.html`
- 当前脚本: `pipeline/analysis/write_mobility_visit_rankings.py`
- 数据来源: `data/step1_db/skill_facts.jsonl`
- 状态: 已生成基础候选表，并挂入 `docs/reports/index.html`。

## 当前分类

| 页签 | 用途 |
|---|---|
| 追加访问/再次访问 | 直接增加访问回数，回数活动价值最高 |
| 随机/远程/思い出し访问 | 固定地点、回国、行动受限时补访问机会 |
| 范围/链接转移 | 扩大可触达范围，或转移/保留 link 成果 |
| 今日新駅奖励 | 不增加访问次数，但放大开图收益 |

## 已知口径

- “粗略期望”只按数值和发动概率估算，不模拟 cooldown 覆盖、站点可用性、移动路线和活动规则。
- `today_new_station_bonus` 单独列出，避免和真正增加访问回数的技能混排。
- `link_transfer` / `station_link_transfer` 主要改变 link 成果，不应直接当作访问回数增加。

## 下一步

1. 为回数活动定义专门评分: 追加访问次数、触发概率、CD、持续时间、触发前置条件分别加权。
2. 区分“人在原地”“通勤中”“长距离开图”“回国/海外只能访问少量站”的场景。
3. 把位移候选转为 solver 可读 role profile，与攻击/经验/PT/防御候选一起参与配队。
