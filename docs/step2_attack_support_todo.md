# Step2 ATK Support Report TODO

更新时间: 2026-06-28

## 当前状态

- 最近已提交: `3f26ab8 Refine attack ranking data quality`
- 提交后又发现并修正了若干问题，当前工作区仍有未提交变更。
- 当前报表: `data/reports/step2_attack_support_rankings_zh.html`
- 当前生成脚本: `pipeline/analysis/write_attack_support_rankings.py`
- 当前 DB 构建脚本: `pipeline/ingest/build_step1_db.py`
- 临时 batch review 文件不要提交；只保留最终总报表。

## 必做 1: 再随机抽查 10 个

目的: 当前错误率仍偏高，commit 前必须再抽查 10 个 Step2 报表实际候选。

重点检查:

- `target_scope` 是否把对手/访问者/队伍对象混淆。
- `target_filters` 是否残留合并单元格误读，例如把己方全属性条件显示成对象属性。
- `trigger_conditions` 是否把累计条件误显示成主动访问/被访问触发。
- `0%～+N%`、`n×N%`、公式型范围是否被截断或按单次值排序。
- VU-only 项是否显示了有意义的 Lv92/Lv100 基准，而不是无意义 `+0%`。
- 固定伤害必须确认对象是否为 `opponent_denko`。
- DEF debuff 只保留“降低对手 DEF”，不列自降或队友降防。

建议抽查命令:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import random
from pathlib import Path
import pipeline.analysis.write_attack_support_rankings as w
rows=w.read_jsonl(Path('data/step1_db/skill_facts.jsonl'))
meta=w.denko_metadata()
all_candidates=[]
for tab in w.TABS:
    for c in w.build_candidates(tab, rows, meta):
        c=dict(c); c['tab']=tab; all_candidates.append(c)
r=random.Random(2026062803)
for i,c in enumerate(r.sample(all_candidates,10),1):
    print(f"{i}. [{c['tab']}] {c['denko_id']} {c['name']} / {c['component_id']}")
    print(f"   target={c['target']} filters={c['filters']} Lv{c['basis_level']}={c['lv50']} max={c['max_text']} avg={c['avg_text']} prob={c['probability']} dur={c['duration']} cd={c['cooldown']}")
    print(f"   condition={c['condition']}")
'@ | python -
```

## 必做 2: 增加等级基准切换

当前报表以 Lv50 为基准，显示理论最大和平均值。

需要扩展为:

- 非 VU 段位可选: `Lv30` / `Lv50` / `Lv80`
- VU 段位可选: `Lv92` / `Lv100`
- 默认仍用 `Lv50`，仅 VU-only 项默认按当前逻辑使用较高 VU 基准。
- 切换段位时，理论最大、平均值、Lv 显示、排序值都要跟着切换。
- 范围型效果继续提供两个排序指标: 理论最大、平均值。
- VU-only 默认隐藏逻辑保留，但用户打开 VU 时，应按选定 VU 段位显示。

实现提示:

- 在 `write_attack_support_rankings.py` 中把候选数据预计算成多个 level basis，不要在前端临时解析文本。
- 前端增加固定 select/button，不使用大规模动态搜索下拉。
- `basis_value()` 目前只返回单个基准，需要扩展为按 requested level 取值。
- 报表仍然保持中文展示，DB 日文事实不改写。

## 验证

每次修正后按顺序执行:

```powershell
$env:PYTHONIOENCODING='utf-8'
python pipeline\ingest\build_step1_db.py
python pipeline\analysis\write_attack_support_rankings.py
python -m py_compile pipeline\analysis\write_attack_support_rankings.py pipeline\ingest\apply_manual_semantic_patches.py
```

期望:

- `denko_total = 290`
- `skill_total = 290`
- `issue_count = 0`
- HTML 无 `????`
- Lv30 列不作为固定表列回归；Lv30/Lv80/Lv92/Lv100 应作为基准切换。

## 收尾顺序

1. 删除 apply 脚本生成的临时 batch review 文件。
2. `git status --short` 确认只剩真正成果物。
3. commit。
4. push `main`。
5. 构建/更新 web 发布物。
6. 更新并 push `pages` 分支。注意: `pages` 分支应保持最小静态发布分支，不要镜像完整 repo。

