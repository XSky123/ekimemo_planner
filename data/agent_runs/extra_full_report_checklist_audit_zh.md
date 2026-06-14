# extra 全量报告校对审计

- generated_at: `2026-06-14T23:44:53.973912+09:00`
- issue_count: `87`
- skill_records: `127`
- severity_counts: `{'high': 75, 'medium': 12}`
- category_counts: `{'blocking_reason': 47, 'label': 9, 'summary': 6, 'probability': 7, 'level': 12, 'fallback': 6}`

## 可疑项目

| severity | batch | denko | component | issue | 理由 |
|---|---|---|---|---|---|
| high | extra_001_040 | extra:007 仰図まや | damage_reduction | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:008 阿下喜ケイ | atk_debuff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:008 阿下喜ケイ | def_debuff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:011 木屋はかり |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| medium | extra_001_040 | extra:011 木屋はかり |  | summary_mixed_labeled_probability | summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。 |
| high | extra_001_040 | extra:011 木屋はかり | duration_extension_3 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:013 花形ひかる | exp_gain_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:014 汐留いちご |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_001_040 | extra:014 汐留いちご | activation_probability_boost | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_001_040 | extra:016 天台ヤコ |  | summary_mixed_labeled_probability | summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。 |
| high | extra_001_040 | extra:016 天台ヤコ | atk_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:016 天台ヤコ | def_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | mixed_labeled_probability | probability 中仍混有多个 label。 |
| high | extra_001_040 | extra:016 天台ヤコ | score_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:020 エステル・サラ・パンクラス | extra_access | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:021 アンナ・チェルトナム | atk_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:022 レイラ・スコッツマン |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_001_040 | extra:022 レイラ・スコッツマン | atk_buff_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:024 アメリア・パウエル |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_001_040 | extra:024 アメリア・パウエル | def_debuff_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:025 ルース・ブルックリン | component_01_exp_gain | non_vu_missing_lv30 | 非 VU component 缺 Lv30。 |
| high | extra_001_040 | extra:025 ルース・ブルックリン | component_01_exp_gain | non_vu_missing_lv50 | 非 VU component 缺 Lv50。 |
| high | extra_001_040 | extra:025 ルース・ブルックリン | component_01_exp_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_001_040 | extra:025 ルース・ブルックリン | component_01_exp_gain | fallback_component | 出现 fallback component，语义不稳定。 |
| high | extra_001_040 | extra:026 ジン・ティエン | component_01_exp_gain | non_vu_missing_lv30 | 非 VU component 缺 Lv30。 |
| high | extra_001_040 | extra:026 ジン・ティエン | component_01_exp_gain | non_vu_missing_lv50 | 非 VU component 缺 Lv50。 |
| high | extra_001_040 | extra:026 ジン・ティエン | component_01_exp_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_001_040 | extra:026 ジン・ティエン | component_01_exp_gain | fallback_component | 出现 fallback component，语义不稳定。 |
| high | extra_001_040 | extra:028 ロン・リンファ | atk_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_001_040 | extra:030 ハリシャ・チャトラパティ | component_01_def_modifier | non_vu_missing_lv30 | 非 VU component 缺 Lv30。 |
| high | extra_001_040 | extra:030 ハリシャ・チャトラパティ | component_01_def_modifier | non_vu_missing_lv50 | 非 VU component 缺 Lv50。 |
| high | extra_001_040 | extra:030 ハリシャ・チャトラパティ | component_01_def_modifier | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_001_040 | extra:030 ハリシャ・チャトラパティ | component_01_def_modifier | fallback_component | 出现 fallback component，语义不稳定。 |
| high | extra_041_080 | extra:041 レニャ・サンモリッツ | reboot_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:046 五葉あこ | component_01_exp_gain | non_vu_missing_lv30 | 非 VU component 缺 Lv30。 |
| high | extra_041_080 | extra:046 五葉あこ | component_01_exp_gain | non_vu_missing_lv50 | 非 VU component 缺 Lv50。 |
| high | extra_041_080 | extra:046 五葉あこ | component_01_exp_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_041_080 | extra:046 五葉あこ | component_01_exp_gain | fallback_component | 出现 fallback component，语义不稳定。 |
| high | extra_041_080 | extra:048 エマ・ノアイユ |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_041_080 | extra:048 エマ・ノアイユ | atk_buff_3 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:058 ピン・ユートン | def_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:058 ピン・ユートン | hp_recovery | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:062 笛吹エイル |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_041_080 | extra:062 笛吹エイル | damage_reduction_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:062 笛吹エイル | damage_reduction_3 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:067 エドウィナ・プレトリア | atk_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:068 アダリヤ・ビクトリア | score_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:073 アチャラ・メークローン | def_debuff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_041_080 | extra:073 アチャラ・メークローン | reboot_3 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:081 ロッサ・ローマ | score_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:084 ネラ・クライストチャーチ | def_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:084 ネラ・クライストチャーチ | def_buff_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:091 ルーシー・ユニオン | score_gain | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:092 アリアナ・ジャスパー |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_081_120 | extra:092 アリアナ・ジャスパー | fixed_damage_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:097 殿ふじこ | component_01_def_modifier | non_vu_missing_lv30 | 非 VU component 缺 Lv30。 |
| high | extra_081_120 | extra:097 殿ふじこ | component_01_def_modifier | non_vu_missing_lv50 | 非 VU component 缺 Lv50。 |
| high | extra_081_120 | extra:097 殿ふじこ | component_01_def_modifier | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_081_120 | extra:097 殿ふじこ | component_01_def_modifier | fallback_component | 出现 fallback component，语义不稳定。 |
| high | extra_081_120 | extra:103 アイラ・ヒューストン | atk_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_081_120 | extra:107 ガブリエラ・アントワープ |  | summary_mixed_labeled_probability | summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。 |
| medium | extra_081_120 | extra:108 ジュリエット・ブリュッセル |  | summary_mixed_labeled_probability | summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。 |
| medium | extra_081_120 | extra:109 アンバー・デパンネ |  | summary_mixed_labeled_probability | summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。 |
| high | extra_081_120 | extra:110 ヨンサン・ソウ | exp_gain_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:111 トンタン・チェリン | exp_gain_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:112 ソウル・マウム | exp_gain_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_081_120 | extra:113 北乃ささら |  | summary_mixed_labeled_probability | summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。 |
| high | extra_081_120 | extra:115 アーイダ・ブルジュマーン |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_081_120 | extra:115 アーイダ・ブルジュマーン | additional_score_gain_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:118 リーガ・イマンタ | def_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:119 アニカ・タルトゥ | atk_buff_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_081_120 | extra:120 マルティナ・ヴィリニュス | exp_gain_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_121_127 | extra:121 コニー・クラークデール | score_gain_1 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_121_127 | extra:121 コニー・クラークデール | reboot_3 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_121_127 | extra:122 マリリン・マクリーン |  | first_label_not_1 | 第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。 |
| high | extra_121_127 | extra:122 マリリン・マクリーン | hp_recovery_2 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_121_127 | extra:122 マリリン・マクリーン | reboot_4 | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| high | extra_121_127 | extra:123 サブリナ・サンタバーバラ | component_01_hp_recovery | non_vu_missing_lv30 | 非 VU component 缺 Lv30。 |
| high | extra_121_127 | extra:123 サブリナ・サンタバーバラ | component_01_hp_recovery | non_vu_missing_lv50 | 非 VU component 缺 Lv50。 |
| high | extra_121_127 | extra:123 サブリナ・サンタバーバラ | component_01_hp_recovery | component_has_blocking_reason | component 仍带阻塞级 review reason。 |
| medium | extra_121_127 | extra:123 サブリナ・サンタバーバラ | component_01_hp_recovery | fallback_component | 出现 fallback component，语义不稳定。 |
