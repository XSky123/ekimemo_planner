# Original 040-080 LLM Semantic Review

generated_at: 2026-06-09 JST

Patch file:

- `data/manual_fills/original_040_080_semantic_patches.jsonl`

## Summary

本次只复查 controller 留下的 4 个 blocking denko：

- `original:041` 南郷にちな
- `original:061` 深遊ちとせ
- `original:076` 上ノ山ゆのか
- `original:078` 海部なる

共写入 7 条 proposed manual patches。没有直接改 `data/records/`。

## Findings

### original:041 南郷にちな

主效果不是 DEF，而是：

- 自身リブート时，把最もリンク時間が長い 1 駅转交给先頭車両のでんこ
- 自身在先头时转交给 2 両目
- リブート時にアクセスされた駅は対象外
- 接收方等级高于自身时不发动

VU 追加效果是另一个组件：

- 自身最长 link 时间 1 小时以内时，自身 DEF 增加
- Lv92/96/100: DEF +6% / +12% / +18%

### original:061 深遊ちとせ

`(2)` 明确写着 `Lv.92以降で発動`，所以当前 parser 把 `duration_extension_2` 铺到 Lv5-80 是错的。

但是当前 JSONL 没有可靠抽到 `(2)` 的 Lv92/96/100 具体延长量，所以 patch 只设置 VU-only 并保留 `screenshot_needed`。

### original:076 上ノ山ゆのか

`(2)` 是相手 HP 回復，不是 DEF debuff。

DEF 減少属于 `(3)`，且 `（3）はLv.92以降で発動`。Lv100 raw cell 写成 `(2)DEF -12%`，但表头 `効果(1)(3)`、条件 `(3)相手のDEF減少`、概率 `(3)75%` 都指向它应归入 `(3)`。

### original:078 海部なる

漏掉了核心 `(1)` score 随机增减分支：

- Lv30: +700% or -50%，增加 28%，减少 72%
- Lv50: +750% or -50%，增加 31%，减少 69%
- Lv80: +900% or -50%，增加 40%，减少 60%

`(2)` ATK +5% 是依赖 `(1)` 发生 score decrease 时触发，概率 100%。

## Acceptability

可直接作为 manual semantic patch 接受：

- `original_040_080_041_replace_vu_def_buff`
- `original_040_080_076_merge_lv100_def_debuff_3`
- `original_040_080_076_supersede_def_debuff_2`
- `original_040_080_078_add_score_random_modifier_1`
- `original_040_080_078_fix_atk_buff_2_dependency`

建议先确认 solver effect model 后接受：

- `original_040_080_041_add_link_transfer_1`

建议截图或详情页片段确认数值后再接受：

- `original_040_080_061_set_duration_extension_2_vu_only`
