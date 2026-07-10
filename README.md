# Ekimemo Planner

Ekimemo 综合配队助手的数据、候选索引和求解器项目。

- 用户界面和说明使用中文。
- wiki/游戏事实保留日文原文。
- schema、JSON key 和索引使用英文。

AI/开发者读取顺序：

1. `cache/project_rules.json`
2. `ROADMAP.md`
3. 当前阶段的 `steps/<step>/README.md`
4. 当前阶段的 TODO/manifest 和任务需要的 schema、记录或脚本

只有在清理目录、判断文件归属或路径不明确时再读 `PROJECT_STRUCTURE.md`。

当前权威数据是 `data/step1_db/`。批次记录保留在 `data/records/`，历史复查材料位于 `archive/`。

Reports:

- Local report index: [docs/reports/index.html](docs/reports/index.html)
- GitHub Pages: https://xsky123.github.io/ekimemo_planner/docs/reports/
- Rebuild Step2 reports: `python pipeline/analysis/build_step2_reports.py`
