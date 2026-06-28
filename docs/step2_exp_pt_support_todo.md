# Step2 经验/PT辅助报表 TODO

更新时间: 2026-06-28

## 当前状态

当前报表: `data/reports/step2_exp_pt_support_rankings_zh.html`

当前脚本: `pipeline/analysis/write_exp_pt_support_rankings.py`

本文件记录第一次生成后发现的基础问题。先不大改 parser；下次从这里继续做报表层修正，必要时再回写 Step1 DB。

## 基础筛查结果

| 类别 | 数量 | 例子 | 当前表现 | 问题 |
|---|---:|---|---|---|
| 概率 key 未展示成人话 | 2 | `original:091 exp_gain_2`, `original:091 score_gain_2` | `activation_probability 100%` | 应显示为 `発動率 100%` 或 `100%` |
| 等级值是内部 kind | 3 | `extra:048 score_gain_1`, `extra:090 score_gain_1`, `extra:091 score_gain_1` | `score_gain`，最大/平均为 `-` | 源值只有语义标签，没有数值；报告应显示“数值未明/条件型”，并降权排序 |
| スコア百分比/倍率型混入绝对值排序 | 5 | `original:078`, `extra:115`, `extra:073`, `extra:121 score_gain_2/3` | `+750%` 被排序成 `750` | 这不是固定 pt，而是访问スコア倍率/变动，应单独归类或明确单位 |
| 数值缺失但效果存在 | 12 | `original:102`, `extra:017`, `extra:046`, `extra:048`, `extra:087`, `extra:091` 等 | 最大/平均 `-` | 需要区分“数值未解析”“条件型无固定值”“随机/曜日/倍率” |

## 点名 case

| denko | component | 现状 | 判断 |
|---|---|---|---|
| `original:078` 海部なる | `score_random_modifier_1` | `スコア増減 +750% or -50%`，max `750`，avg `350` | 这是访问スコア的倍率/随机变动，不是绝对 pt。应该放入“スコア倍率/変動”分类，不应和固定スコア獲得直接排序。 |
| `original:091` 岩切よしの | `score_gain_2` / `exp_gain_2` | 概率显示 `activation_probability 100%` | 只是 probability dict 的 key 未规范显示，报表层即可修。 |
| `extra:048` エマ | `score_gain_1` | 等级值 `score_gain`，无最大/平均 | 条件写“与ダメージに応じスコア獲得＆経験値付与”，但数值未被解析。需要查详情页或保留为“与伤害联动，数值未明”。 |
| `extra:090` キャシー | `score_gain_1` | 等级值 `score_gain`，无最大/平均 | 与ダメージに応じてスコア獲得，属于条件型/公式型，不能当作普通固定スコア。 |
| `extra:091` ルーシー | `score_gain_1` | 等级值 `score_gain`，无最大/平均 | link获得时经验和スコア，但数值未解析；需要详情页复查或报告标为“数值未明”。 |

## 下次修正方向

1. 增加分类页签或筛选:
   - `固定経験値`
   - `経験値分配/倍率`
   - `固定スコア`
   - `スコア倍率/変動`
   - `条件型/数值未明`
   - `ボーナス/マイル`

2. 分离排序指标:
   - 固定值: 按 pt/exp 数值排序。
   - 百分比/倍率: 按倍率排序，但列名必须显示 `%/倍`，不要和固定值混排。
   - 条件型/数值未明: 默认靠后，显示 `数值未明`，不参与固定值排行。

3. 概率显示 normalization:
   - `activation_probability` -> `発動率`
   - 空 dict -> `-`
   - 保持日语原始值，不改 DB 原事实。

4. 对 `value_raw in {"score_gain", "exp_gain"}` 的记录:
   - 报告层显示 `数值未明`
   - `needs_metric_review` 或类似前端标记
   - 排序值设为 `-1`
   - 后续详情页/LLM 复查时再决定是否能解析公式或固定值。

5. 对 `スコア増加 +N%`、`スコア変動 +N%`、`受けたダメージのN%`:
   - 标记 metric_type=`percent_score_modifier`
   - 列名显示“倍率/比例最大”“倍率/比例平均”
   - 不要在固定スコア tab 里与 `スコア獲得 9000` 比大小。

## 最小复查命令

```powershell
$env:PYTHONIOENCODING='utf-8'
python pipeline\analysis\write_exp_pt_support_rankings.py
```

筛查样例:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from pipeline.analysis import write_exp_pt_support_rankings as w
rows=w.base.read_jsonl(Path('data/step1_db/skill_facts.jsonl'))
meta=w.base.denko_metadata()
all=[]
for tab in w.TABS:
    for c in w.build_candidates(tab, rows, meta):
        c=dict(c); c['tab']=tab; all.append(c)
for c in all:
    if c['probability'].startswith('activation_probability') or c['level_value'] in {'score_gain','exp_gain'} or c['max_text']=='-':
        print(c['tab'], c['denko_id'], c['name'], c['component_id'], c['level_value'], c['probability'], c['max_text'], c['condition'])
'@ | python -
```
