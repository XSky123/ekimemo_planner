# 数据读取阶段执行规则

这份文档是 Phase 1 数据入库与清洗的执行总纲。后续 AI、脚本或人工 reviewer 接手时，先读这里，再读 manifest 和 schema。

## 目标

- 只做数据读取、缓存、清洗、索引和复查队列。
- 不做配队 solver，不训练模型，不导入 Excel。
- 当前范围只覆盖 `original` + `extra`。
- 所有产物必须能被其他 AI 接管，不依赖对话记忆。

## 语言与存储

- 用户展示层使用中文，保留必要日语术语。
- wiki / 游戏事实按日语原文入库。
- schema、manifest、index、record key 使用 English keys。
- 如需中文说明，使用 `summary_zh`、`review_note_zh` 等展示字段，不覆盖日语事实。

## Source Authority

- `detail_page`: 事实最高权威，负责技能对象、触发、条件、数值、VU 差异、例外。
- `denko_list`: ID、名称、详情页 URL、类型、属性、颜色、技能名、VU 标记的 canonical first-pass source。
- `manual_override`: 修正自动解析错误，必须带 `reason` 和 `source`；冲突未解决时保持 `needs_review = true`。
- `skill_list_or_reverse_index`: 候选发现和粗分类，不直接确认最终事实。
- `recommendation_prior`: 初心者おすすめ度等参考评价，只写 prior，不覆盖事实。
- `observed_team_case`: 大佬队伍、截图、实战观察，只作案例和校准，不变成技能事实。

## 必须记录的元数据

每条结构化记录必须包含：

- `source_url`
- `source_authority`
- `content_hash`
- `parser_version`
- `parsed_at`
- `confidence`
- `needs_review`
- `review_reasons`

hash 未变化且置信度足够时复用缓存，不重复抓取和解析。

## 入口与输出

执行入口：

- `cache/project_rules.json`
- `cache/cache_manifest.json`
- `data/ingestion_manifest.json`

主要输出：

- `data/records/denko_facts.jsonl`
- `data/records/skill_facts.jsonl`
- `data/records/recommendation_priors.jsonl`
- `data/records/observed_team_cases.jsonl`
- `data/indexes/denko_index.json`
- `data/review_queue/review_queue.jsonl`

## ID 映射规则

- Original / Extra 列表页是 `wiki_no -> detail_url` 的 canonical source。
- Original 数字 ID 规范化为 `original:000`、`original:006`。
- Extra `EXxx` 规范化为 `extra:001`、`extra:035`。
- 同时保留 `wiki_no` 原文和 `denko_id` 规范 key。
- 不用 name 当稳定 key。
- 列表页一阶段读取字段：`wiki_no`、`name`、`detail_url`、`type`、`attribute`、`color`、`skill_name`、`vu_marker`、`remarks`。

## 表格解析规则

wiki 表格不能按 raw `<td>` 位置解析。

已确认经验：

- Original 列表页 `備考` 列存在 `rowspan`。
- 已检查的详情页存在多个 table、`rowspan`、`colspan` 和折叠区域。

硬要求：

- HTML DOM 解析优先。
- 所有列表页和详情页表格都必须先展开为 table matrix。
- 必须支持 `rowspan` 和 `colspan`。
- 重复 header row 要跳过。
- 详情页按 section heading 和局部 label 定位，不按 table 顺序硬猜。
- 折叠区域如果存在于 HTML 中，视为正常来源内容。
- skill level、ステータス、ラッピング、VU、probability、duration、cooldown 表都走同一矩阵逻辑。
- 无法证明正确的行或字段进入 `review_queue`，不要猜。

## 截图与证据

截图不是事实，截图是 review evidence。

需要截图确认的情况：

- 矩阵展开后 header/列仍不确定。
- raw HTML text order 与渲染布局可能不一致。
- 技能等级、VU、概率、持续、CD、数值列有歧义。
- 一个字段可能来自多个 section。
- 人工 reviewer 要求确认视觉布局。

截图路径：

- `data/review_evidence/screenshots/`

review item 至少保留一种证据：

- `raw_html_snippet`
- `text_snippet`
- `source_section`
- `screenshot_path`

## 先验使用规则

推荐页经验可以帮助排序或提示 reviewer，但只能写入 `recommendation_priors.jsonl`：

- `wiki_beginner_rating`
- `beginner_comment_summary`
- `rating_context`
- `rating_source_url`
- `rating_confidence = prior_only`

不要让推荐页覆盖 `skill_fact`、`denko_fact` 或详情页确认的条件。

实战队伍 / 截图队伍只能写入 `observed_team_cases.jsonl`：

- 用于发现组合、校准评分、生成案例解释。
- 不能作为技能对象、倍率、触发条件的事实来源。

## Token 与请求策略

- 默认 `fill` 模式：只补缺失、stale、low confidence、needs_review、用户明确要求刷新。
- 先读 manifest / index，再读单条 record。
- 不把整页 wiki 或全库交给 LLM。
- 确定性 parser 能处理的内容不交给 LLM。
- LLM 只处理最小的日语歧义片段。
- 网络失败时记录 retry / review 状态，不阻塞全批。

## 维度自检与自动修正规则

采集过程中，agent / parser 可以判断当前 key 是否足够，并自动补充或修正字段维度，但必须可追踪。

允许自动补充：

- 页面中稳定出现、且现有 schema 没有承接字段的事实。
- 解析必要的定位信息，例如 `source_section`、`table_index`、`row_index`、`cell_origin_by_column`。
- 能降低后续歧义的可选字段，例如 `wiki_page_title`、`vu_marker`、`raw_label_ja`。

必须进入 review：

- 改动 required field。
- 改动会影响 solver 语义。
- 列表页与详情页冲突。
- 新字段来自低置信解析或截图确认。

每次自动修正都要记录：

- `change_reason`
- `source_url`
- `source_section`
- `evidence`
- `confidence`
- `needs_review`

不要静默覆盖日语原文事实。

## 报告输出规则

- 人类可读报告默认导出 HTML。
- 报告语言使用中文，保留必要日语术语。
- HTML 报告写入 `data/reports/`。
- 报告必须区分：结构化事实、中文解释、review queue、prior-only、case-only。
- Markdown 只可作为临时草稿，不作为默认最终报告。

## Review Queue 触发条件

以下情况必须进入 `review_queue`：

- 表格矩阵展开失败。
- required field 缺失。
- 列表页和详情页事实冲突。
- 技能说明有多阶段、多对象、ただし、条件により、特殊。
- 涉及 VU 差异、天气、气温、时间、地点、リンク、发动顺序。
- 自动解析无法确定对象、触发、概率、持续、CD、条件。
- 需要截图确认。

## 执行顺序

1. 读取 `cache/project_rules.json` 和 `data/ingestion_manifest.json`。
2. 抓取或复用 Original / Extra 列表页。
3. 用 table matrix 解析 ID 映射，生成/更新 `denko_index.json`。
4. 抓取或复用目标详情页 raw HTML/text。
5. 按 section + table matrix 解析 `denko_fact` 和 `skill_fact`。
6. 抓取或复用推荐页，只写 `recommendation_prior`。
7. 生成 `review_queue`。
8. 校验 JSON / JSONL。
9. 不启动 solver。

## 执行前 Checklist

- `data/ingestion_manifest.json` 可解析。
- `schemas/*.schema.json` 可解析。
- `data/review_evidence/screenshots/` 已存在。
- `parser_requirements.must_expand_rowspan = true`。
- `parser_requirements.must_expand_colspan = true`。
- `parser_requirements.screenshot_when_needed = true`。
- Git 状态已知；旧 agent 已归档。
