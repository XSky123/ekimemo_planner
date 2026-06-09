# Ekimemo Report 校对事项清单

这份清单沉淀用户在多轮人工 review 中指出的问题。用途是让 report review agent、manual semantic fill agent、以及后续接管的 AI 在看 HTML report / JSONL records 时，不只检查 `blocking_item_count`，还要检查报告是否真的适合人读、适合后续配队算法使用。

## 速查表

| No. | 类别 | 校对事项 | 触发/异常表现 | 处理方式 |
| --- | --- | --- | --- | --- |
| 1 | 编码 | HTML/JSONL 中日文和中文必须正常显示 | 出现 `????`、`HP?30%`、`銇/銈/鐧/鍔/鏅` | 先用 Python UTF-8 复查；坏数据重跑或重写 patch |
| 2 | 编码 | 不用 PowerShell literal 写日文 | 手动 patch 里日文变成 `?` | patch 用 UTF-8 文件或 `ensure_ascii=True` 生成 |
| 3 | 报告结构 | 主表一行一个 `skill_component` | 固定 5-slot 导致大片空白 | 不展开空 slot，改用 component 长表 |
| 4 | 报告结构 | report 顶部先列可疑项目 | 可疑点藏在大表里 | 顶部列 `denko_id / component / 中文理由` |
| 5 | 报告结构 | VU-only 不应看起来空白 | Lv30/Lv50 空，用户误以为漏抓 | 显示 `※VU生效`，并列出 Lv92/96/100 |
| 6 | 等级 | Lv30/Lv50 必须优先可见 | 非 VU component 缺 Lv30 或 Lv50 | 进入可疑项，复查技能等级表 |
| 7 | 等级 | Lv92/Lv96/Lv100 必须可见 | VU 追加效果无法在 report 看出 | report 加 VU 三列，JSON 标 `vu_only` |
| 8 | ID | ID 与 wiki 行必须确认 | 列表页合并单元格错位 | 展开 rowspan/colspan；详情页优先 |
| 9 | 编号拆分 | `(1)/(2)/(3)` 通常拆成独立 component | 检测到编号但只产出一个 component | 可疑；脚本修或 LLM 片段复查 |
| 10 | 编号顺序 | 第一个编号 component 应是 `(1)` | slot1/第一行直接 `(2)` | 可疑；检查是否漏了主效果 |
| 11 | 编号一致 | label 与 component_id 编号一致 | `label=(2)` 但 component_id 是 `_1` | 可疑；重排或重建 component |
| 12 | VU 错位 | `(1)` 主效果不应只 VU 生效 | `_1` 只有 Lv92/96/100 | 通常是基础效果漏抓，必须复查 |
| 13 | 句中引用 | 不把句中 `(1)` 当新 label | `(2)...(1)の発動率UP` 被拆错 | 只识别段首 label 或按 `/` 分段 |
| 14 | 概率 | probability 必须按 label 拆分 | `(1)` 组件里同时有 `発動率(1)/(2)` | `(1)` 只留自身概率，`(2)` 独立 |
| 15 | 概率 | 概率增量是 modifier | `(1)+5%` 被当回復量/效果值 | 建 `activation_probability_boost` |
| 16 | 概率 | `確定発動` 记录为 100% | VU 追加概率空白 | 填 `activation_probability: 100%` |
| 17 | 概率 | `(2)` 依赖 `(1)` 时要记录依赖 | `(1)が発動した上で30%` 写成普通 30% | 写 `depends_on_component` |
| 18 | 对象 | target 与 condition 分开 | 条件词被写进 target_scope | target 写受益/受害对象，条件写 filters/trigger |
| 19 | 对象 | 自己/全队/访问者/被访问者分清 | “访问中的でんこ”写成 team_all | 复查 raw，修 target_scope |
| 20 | 对象 | “自己以外”不能写成自己 | `自身を除く` 解析成 `self` | target_filters 写 `exclude_self` |
| 21 | 位置 | 先头车/前一辆/相邻车要结构化 | `先頭車両`、`前の一両` 丢失 | 写 `front_car` / relative position |
| 22 | 属性 | 自己队伍属性与对手属性分开 | `相手がeco` 写成 own eco 限制 | 写 `opponent_attribute` |
| 23 | 方向 | access/accessed 分清 | 被攻击触发写成主动访问 | trigger 写 `access` 或 `accessed` |
| 24 | 条件 | film/theme/name/weather/time 等保留 | 奇怪条件被省略或硬猜 | 结构化能拆就拆，不能拆保留 raw |
| 25 | 效果类型 | 不把特殊效果塞进 ATK/DEF | HP0/スキル無効化 变成 DEF modifier | 改 `force_hp_zero` / `skill_disable` |
| 26 | 效果类型 | EXP 分配不是 EXP gain | `経験値分配` 写成 self exp_gain | 用 `exp_distribution` |
| 27 | 效果类型 | HP1 生存和固定减伤分开 | `HP1で耐える` 混入 damage_reduction | 用 `survive_hp1` + `damage_reduction` |
| 28 | 效果类型 | link/随机访问/传送单独建模 | link transfer 被写成 DEF | 用 `link_transfer` / `random_access` |
| 29 | 数值 | 正负号和单位不能丢 | `DEF -10%` 变 `10` | 保留 `value_raw`、`value_numeric=-10`、unit |
| 30 | 数值 | scaling 条件必须保留 | `n×%`、`0～+x%`、`最大5駅` 丢失 | 写 `scaling_conditions` |
| 31 | 时间 | duration/CD 按等级排序 | Lv5/Lv15 被放到底部 | 按关键等级顺序输出 |
| 32 | 分支 | 属性/季节/星期/时间分支进入可疑项 | 只出一个 component 或 effect_kind 矛盾 | LLM/manual fill 或截图复查 |
| 33 | fallback | fallback component 必须可疑 | `component_01_*` 出现在 report | 复查原文，替换成语义 component |
| 34 | 重复 | 两个 component 完全一样要报错 | `(1)/(2)` 值、条件、对象都相同 | 检查错位或重复复制 |
| 35 | LLM | 只把最小片段交给 LLM | 整页 wiki 丢给模型 | 片段包含条件表、等级表、remarks |
| 36 | patch | manual patch 必须可追溯 | 无 reason/source 的改动 | 必填 evidence、problem_zh、reason_zh |
| 37 | 批次复盘 | 每 20～30 个复盘一次 | 同类错反复出现 | 共性问题进 parser/report rule |
| 38 | 验收 | `blocking_item_count=0` 不等于通过 | report 仍难读或概率混合 | 必须跑本表和自动验收脚本 |

## 0. 基本原则

- 展示层必须是中文，必要日语游戏术语保留原文。
- raw/wiki/game 事实字段保留日语原文，不能为了展示而覆盖事实字段。
- schema/key/index/cache 使用 English key。
- report 是给人看的，不要出现无意义 CSS class、空白 skill 槽、大段机器噪音。
- DB 是给 solver 和后续 agent 接管的，每条记录必须保留 `source_url`、`content_hash`、`parser_version`、`confidence`、`needs_review`、`review_reasons`。
- wiki 详情页是事实权威；推荐页只是 prior；实战队伍/截图只是 case/calibration；manual patch 必须带 source/reason。

## 1. 编码与乱码

- HTML report 必须能在本地浏览器正常显示中文和日文。
- report 物理文件建议输出 ASCII-only HTML entities，避免 Windows 本地查看器误判 UTF-8。
- JSONL/DB 内容必须用 UTF-8 读写，不要通过 PowerShell 命令 literal 直接写日文。
- PowerShell 控制台显示日文乱码时，不得据此判断源数据坏掉；必须用 Python UTF-8 读文件或用 `ensure_ascii=True` 检查。
- 禁止 report/record 出现批量 `????`、`HP?30%`、`銇/銈/鐧/鍔/鏅` 这类 mojibake 痕迹。
- 技能名里原本存在的单个 `?` 可以保留，但连续 `??` 或日文全变 `?` 必须视为数据损坏。

## 2. 报告结构

- 主报告应该是一行一个 `skill_component` 的长表，不要把固定 5 个 skill slot 当主视图。
- 不要展开空 skill slot；空槽会让人误以为有空白技能或 parser 漏项。
- 每行至少包含：`denko_id`、`name`、`type`、`attribute`、`color`、`skill_name`、`component_id`、`condition_label`、`effect_kind`、`target_scope`、`condition/trigger/scaling`、`Lv30/Lv50/Lv92/Lv96/Lv100 内容`、`probability`、`duration`、`CD`、`review_reasons`。
- report 顶部必须先列可疑项目和可疑理由，理由用中文。
- VU-only component 在 Lv30/Lv50 不要显示成纯空白，应显示 `※VU生效` 或在 Lv92/Lv96/Lv100 列显示实际值。
- 对用户最关心的刚抽一只上限 50 的情况，Lv30/Lv50 必须优先可见。
- 对 VU 技能，Lv92/Lv96/Lv100 必须可见，否则会误判成“空白技能”。

## 3. ID 与列表页映射

- `でんこ ID` 与 wiki 列表页行必须确认，不得只靠顺序猜。
- 原创/Extra 列表页存在合并单元格，必须正确展开 row/colspan。
- 列表页字段至少确认：编号、名字、type、attribute、color、skill_name、detail_url。
- 如果列表页字段与详情页冲突，以详情页为事实权威，并把冲突写入 review reason。

## 4. 详情页表格解析

- 详情页也可能有合并单元格，必须展开后再解析。
- 技能条件表和技能等级表模板不统一，不能假设固定列。
- 必须识别关键等级：`1/15/30/50/60/70/80/92/96/100`。
- `92/96/100` 只适用于有 VU 的でんこ；VU-only 内容必须在 JSON 中用 `availability.vu_only=true` 或同等 key 表示。
- 如果截图或视觉布局能确认 row/colspan，但 HTML parser 结果可疑，应截图确认。
- 如果详情页 parser 无法稳定处理，只把最小相关日文片段交给 LLM/manual fill，不要整页塞进模型。

## 5. 技能拆分

- 检测到 `(1)/(2)/(3)` 时，必须拆成独立 component，除非有明确证据表明只是同一效果的说明文本。
- 检测到编号但只产出一个 component，必须可疑。
- 第一个带编号 component 不是 `(1)`，必须可疑。
- component 的 `condition_label` 与 `component_id` 编号不一致，必须可疑。
- `(1)` 主效果被解析成仅 VU 生效，通常是错位，必须可疑。
- VU 追加效果不能覆盖基础效果；应作为 additional component 或 conditional modifier。
- `(2)` 有时是 `(1)` 的补充条件/追加效果，不是独立主动技能；也要拆出来，但 `effect_role` 应标注为 `additional_effect` / `conditional_modifier`。
- 文本中出现“(1)の発動率UP”这类句中引用时，不要把句中 `(1)` 当作新 label；优先按斜线分段或只识别段首 label。
- 如果两个 component 解析结果完全相同，必须怀疑拆分错位或重复复制。

## 6. 条件与对象

- 必须区分访问方向：自己アクセス、被アクセス、リンク中、リブート時、ログイン時、通勤随手访问、传送/随机访问。
- 必须区分对象：自己、队伍全员、访问中的でんこ、被访问的でんこ、先头车、自己前一辆、自己以外、对手、对手队伍。
- “限制自身/队伍属性”与“限制对手属性”不能混淆，例如 eco 限制可能是 opponent attribute，不是 formation attribute。
- “自己以外”不能解析成自己。
- “自己前面的一辆/先头车両/編成内访问的でんこ”要明确落到 `target_scope` 或 `target_filters`。
- 名字、主题、film、属性、type、颜色、位置、link 状态、站名/路线名关键词等条件都要保留结构化字段或 raw 条件。
- 条件在 raw 中看起来奇怪时，不要硬填错；宁可进入 LLM/manual semantic fill。

## 7. 效果类型

必须尽量把 effect_kind 语义化，而不是都塞进 ATK/DEF：

- `atk_buff` / `def_buff` / `atk_debuff` / `def_debuff`
- `fixed_damage` / `damage_reduction` / `force_hp_zero` / `counter_damage`
- `hp_recovery` / `hp_recovery_bonus` / `survive_hp1`
- `exp_gain` / `exp_distribution` / `exp_distribution_bonus`
- `score_gain` / `additional_score_gain`
- `skill_disable` / `supporter_disable` / `probability_boost`
- `cooldown_reduction` / `duration_extension` / `skill_continue`
- `link_transfer` / `extra_access` / `random_access` / `previous_station_access`
- `item_gain`，例如 `フットバース`
- `friend_slot_increase` 等账号级效果

如果 parser 把“相手HPを0にする”解析成 `def_modifier`，必须报错并改为 `force_hp_zero`。

如果 parser 把“スキル一部無効化”解析成 ATK/DEF modifier，必须报错并改为 `skill_disable`。

## 8. 数值、单位与等级

- 每个 component 的值必须按 denko level 分开保存，即使 report 合并展示。
- Lv30/Lv50 是优先校对等级；非 VU component 在这两个等级空白通常是错误。
- VU-only component 在 Lv30/Lv50 空白正常，但 report 必须说明 `※VU生效`。
- `n×%`、`0～+x%`、`最大n駅`、`上限n人`、`残り効果時間に応じて` 等必须保留 scaling 条件。
- 数值单位要区分 percent、percentage_point、flat_damage、percent_hp、percent_exp、station_count、item_count。
- 加成/减少的正负号不能丢，例如 `DEF -10%` 不能存成 `10%`。
- 固定伤害/固定减伤与百分比 ATK/DEF 不能混淆。
- 持续时间、CD、概率不能因为 rowspan 被错放到 Lv5/Lv15 或表尾；必须按等级排序。

## 9. 概率与触发

- probability 必须按 component label 拆分，不能把 `(1)` 与 `(2)` 合在一个 component 的概率里。
- 例如 #001 黄陽セリア：`hp_recovery_1` 只显示 `(1)` 的 20/25/30/35/40/45/50%，`activation_probability_boost_2` 显示 VU 后 `(1)+5/+10/+15%`。
- 如果原始概率列是 `(1)75% (2)100%`，`*_1` 只拿 75%，`*_2` 只拿 100%。
- 如果 `(2)` 是“(1)発動した上で30%”，要记录依赖关系，而不是写成普通 30%。
- `確定発動` 应记录为 100%。
- 概率 UP 是 modifier，不等同于技能本体概率。
- `発動率(2)` 为 `-` 时，不应显示成概率；可留空或表示不适用。

## 10. 特殊分支与时间条件

- 属性分支、季节分支、星期变化、日期变化、时间窗口、天气、气温、milage 等都应进入 review。
- 季节变化/星期变化这种 parser 不能稳定处理时，先保留 raw 与分支 key，不要猜。
- 如果 raw 里明显有多个分支但 report 只出一个 component，必须可疑。
- 如果 component 的条件是季节/属性分支，但 effect_kind 与日文效果词不一致，必须可疑。

## 11. 可疑项触发器

以下任一情况必须进入 report 顶部可疑项：

- `first_label_not_1`
- detected labels count > emitted component count
- condition label 与 component_id 编号不匹配
- `(1)` only VU
- 非 VU component 缺 Lv30 或 Lv50
- probability/value_raw 里残留其他 label，例如 `(1)` component 里还有 `(2)`
- duplicate labeled component values
- condition text 与 effect_kind 矛盾
- target_scope 与 raw 对象词矛盾
- formation attribute 与 opponent attribute 混淆
- `access` 与 `accessed` 混淆
- 解析出新 effect_kind 但 solver model 不知道如何用
- 出现大量 `?` 或 mojibake
- parser 从 fallback 生成 `component_01_*`

## 12. LLM/manual fill 触发规则

- 脚本能确定的共性问题先脚本修。
- 脚本不能可靠判断的，只把相关 denko 的技能条件表、技能等级表、remarks 最小片段交给 LLM。
- LLM/manual fill 输出必须是 patch，不得直接覆盖事实且无 reason。
- patch 必须包含：`patch_id`、`denko_id`、`source_authority`、`evidence.text_ja`、`problem_zh`、`reason_zh`、`confidence`。
- 用户已指出的 pattern 应进入 parser/review rule，而不是每批重复问用户。

## 13. 批次复盘

- 每 20～30 个でんこ做一次复盘。
- 复盘要统计：新增 effect_kind、blocking reason counts、manual patch 类型、重复错误模式。
- 如果同一错误模式出现 2 次以上，优先修 parser 或 report writer。
- 每批结束时必须输出：state、report、review queue、manual patches、self-review summary。
- `blocking_item_count=0` 不是最终验收，只是第一层验收；还必须跑本 checklist。

## 14. 最低自动验收脚本应检查

- 所有 report ASCII-only 或明确 UTF-8 且浏览器可正常显示。
- report 中无旧 `skill1_*` 主矩阵。
- report 中存在 `技能分量表`。
- report 中存在 `Lv92内容/Lv96内容/Lv100内容`。
- report 中无 `HP?30%`、无连续 `??`、无 mojibake pattern。
- skill facts 中无 `first_label_not_1`。
- skill facts 中无混合 probability label。
- skill facts 中非 VU component 不缺 Lv30/Lv50。
- 对 #001 这类样例，确认基础效果与概率 modifier 分开展示。

## 15. 当前已知残余

- `original_080_119` 仍有旧语义 blocking，主要是属性分支/效果类型复查，不属于 report 格式问题。
- 后续应把概率拆分、label 分段、VU-only 展示规则前置到 parser 生成阶段，减少后处理。
