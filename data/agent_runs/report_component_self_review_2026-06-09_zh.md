# 报告与组件自检记录 2026-06-09

## 用户反馈

- 报告中仍能看到大量技能1位置直接出现 `(2)` 的观感。
- 报告存在固定 5 个技能槽导致的空白项目。
- #001 黄陽セリア 的概率把 `(1)` 与 `(2)` 合在一起显示。

## 自检结论

- 数据层没有发现真正的 `first_label_not_1` 残留。
- 主要问题是报告层仍使用固定 5-slot 调试矩阵，空槽和 VU-only 组件会让人误读为“技能1就是(2)”。
- 另一个真实数据问题是概率字段未按 component label 拆分，例如 `(1)` 组件继承了 `発動率(1)` 与 `発動率(2)` 的合并 dict。
- #001 的 `hp_recovery_1` 已修为只显示 `(1)` 概率，`activation_probability_boost_2` 独立表示 `(2)` 的 VU 発動率UP。

## 已执行修正

- 报告主表从固定 5-slot 矩阵改为“一行一个 skill component”的长表。
- 报告不再展开空 skill slot。
- 报告概率列按当前 component 的 `(1)/(2)/(3)` label 单独显示。
- 报告新增 `Lv92内容`、`Lv96内容`、`Lv100内容`，避免 VU-only component 在 Lv30/Lv50 视角下看起来像空白。
- 所有现有 `original_*_skill_facts.jsonl` 做了概率字段规范化。
- `value_raw` 中类似 `(1)... (2)-` 的合并文本按当前 component label 切分。
- #007 大月シーナ 的 VU ATK/DEF 追加效果按原文 `確定発動` 补为 `activation_probability: 100%`。

## 验收规则

- `first_label_not_1`: 0
- 非 VU component 的 Lv30/Lv50 空白: 0
- probability 中残留 `(1)/(2)` 混合标记: 0
- report 中旧 `skill1_*` 矩阵表头: 0
- report 中缺少 VU 内容列: 0
- report 中 `HP?30%` 或连续 `??`: 0

## 残余风险

- `original_080_119` 仍有 5 个旧语义 blocking item，属于之前批次的属性分支/效果类型复查问题，不是本轮报告格式或概率拆分问题。
- 后续 parser 应把本轮概率拆分规则前置到生成 skill component 阶段，而不是作为后处理。
