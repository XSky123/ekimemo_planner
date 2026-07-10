from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "data" / "reports"
OUT_HTML = REPORT_DIR / "step2_all_reports_zh.html"


REPORTS = [
    {
        "id": "attack",
        "kind": "ranking",
        "title": "攻击辅助排行",
        "file": "step2_attack_support_rankings_zh.html",
        "description": "给自己/队友加 ATK、固定伤害、降低对手 DEF。",
    },
    {
        "id": "defense",
        "kind": "ranking",
        "title": "防御/守站辅助排行",
        "file": "step2_defense_support_rankings_zh.html",
        "description": "DEF、减伤、HP 回复、无效化/保命、降低对手输出、link 保持。",
    },
    {
        "id": "exp-pt",
        "kind": "ranking",
        "title": "经验/PT 辅助排行",
        "file": "step2_exp_pt_support_rankings_zh.html",
        "description": "固定经验/score、倍率、ねこぱんち经验、收益技能效果量强化。",
    },
    {
        "id": "utility",
        "kind": "ranking",
        "title": "技能工具索引",
        "file": "step2_skill_utility_reports_zh.html",
        "description": "无效化、效果量强化、CD/概率操作、条件索引、活动访问与雷达范围。",
    },
    {
        "id": "prototype",
        "kind": "prototype",
        "title": "原型线路/站点反查",
        "file": "step2_prototype_lookup_zh.html",
        "description": "按线路、车辆、公司、都道府县、生日、声优等反查でんこ。",
    },
]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def extract_style(text: str) -> str:
    match = re.search(r"<style>(.*?)</style>", text, flags=re.S | re.I)
    return match.group(1).strip() if match else ""


def extract_body(text: str) -> str:
    match = re.search(r"<body[^>]*>(.*?)</body>", text, flags=re.S | re.I)
    body = match.group(1) if match else text
    body = re.sub(r"<script\b[^>]*>.*?</script>", "", body, flags=re.S | re.I)
    return body.strip()


def script_text(value: str) -> str:
    return value.replace("</script", "<\\/script")


def read_report(report: dict[str, str]) -> tuple[str, str]:
    text = (REPORT_DIR / report["file"]).read_text(encoding="utf-8")
    return extract_style(text), extract_body(text)


def main() -> None:
    styles: list[str] = []
    templates: list[str] = []
    for report in REPORTS:
        style, body = read_report(report)
        if style and style not in styles:
            styles.append(style)
        templates.append(
            f'<script type="text/plain" id="report-template-{esc(report["id"])}">{script_text(body)}</script>'
        )

    report_data = json.dumps(
        [
            {
                "id": report["id"],
                "kind": report["kind"],
                "title": report["title"],
                "file": report["file"],
                "description": report["description"],
            }
            for report in REPORTS
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    nav_buttons = "\n".join(
        f'<button type="button" class="report-tab" data-report-id="{esc(report["id"])}">{esc(report["title"])}</button>'
        for report in REPORTS
    )
    style_text = "\n\n".join(styles)
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ekimemo Step2 综合报表</title>
  <style>
    body {{ margin: 24px; color: #1f2328; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.5; background: #ffffff; }}
    #top {{ max-width: 1440px; margin: 0 auto; }}
    .all-header h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .all-header p {{ margin: 6px 0 0; color: #57606a; }}
    .report-nav {{ position: sticky; top: 0; z-index: 20; display: flex; gap: 8px; flex-wrap: wrap; padding: 12px 0; margin: 16px 0; background: white; border-bottom: 1px solid #d8dee4; }}
    .report-tab {{ border: 1px solid #d0d7de; border-radius: 4px; padding: 7px 10px; background: #f6f8fa; color: #0969da; font-weight: 600; cursor: pointer; }}
    .report-tab.active {{ background: #0969da; border-color: #0969da; color: white; }}
    .report-shell {{ border-top: 1px solid #d8dee4; padding-top: 16px; }}
    .report-shell header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 10px; }}
    .report-shell h2 {{ margin: 0; font-size: 20px; }}
    .report-shell p {{ margin: 6px 0 0; color: #57606a; }}
    .open-link {{ white-space: nowrap; border: 1px solid #d0d7de; border-radius: 4px; padding: 6px 9px; color: #0969da; text-decoration: none; font-weight: 600; background: white; }}
    .report-content {{ min-height: 420px; }}
    .report-loading {{ padding: 40px 0; color: #57606a; }}
    .embedded-report > h1:first-child {{ display: none; }}
    .embedded-report .toolbar {{ top: 52px; }}
    .embedded-report th {{ top: 105px; }}
    {style_text}
  </style>
</head>
<body>
  <main id="top">
    <section class="all-header">
      <h1>Ekimemo Step2 综合报表</h1>
      <p>真正合并成一个 HTML。为提高性能，报表内容按需加载到当前页面，不使用 iframe，也不会一次性把所有大表展开进 DOM。</p>
    </section>
    <nav class="report-nav">{nav_buttons}</nav>
    <section class="report-shell">
      <header>
        <div>
          <h2 id="active-title"></h2>
          <p id="active-description"></p>
        </div>
        <a id="active-open-link" class="open-link" href="#">单独打开</a>
      </header>
      <div id="report-content" class="report-content"><div class="report-loading">加载中...</div></div>
    </section>
    {"".join(templates)}
  </main>
  <script>
    const REPORTS = {report_data};
    const reportById = new Map(REPORTS.map(report => [report.id, report]));
    const loadedReports = new Map();
    const content = document.getElementById('report-content');
    const title = document.getElementById('active-title');
    const description = document.getElementById('active-description');
    const openLink = document.getElementById('active-open-link');
    const buttons = [...document.querySelectorAll('[data-report-id]')];

    function templateHTML(id) {{
      const node = document.getElementById(`report-template-${{id}}`);
      return node ? node.textContent : '<p class="report-loading">报表模板不存在。</p>';
    }}

    function loadReport(id) {{
      const report = reportById.get(id) || REPORTS[0];
      buttons.forEach(button => button.classList.toggle('active', button.dataset.reportId === report.id));
      title.textContent = report.title;
      description.textContent = report.description;
      openLink.href = report.file;

      if (!loadedReports.has(report.id)) {{
        const wrapper = document.createElement('div');
        wrapper.className = 'embedded-report';
        wrapper.dataset.reportKind = report.kind;
        wrapper.innerHTML = templateHTML(report.id);
        loadedReports.set(report.id, wrapper);
        if (report.kind === 'ranking') setupRankingReport(wrapper);
        if (report.kind === 'prototype') setupPrototypeReport(wrapper);
      }}
      content.replaceChildren(loadedReports.get(report.id));
      history.replaceState(null, '', `#${{report.id}}`);
    }}

    function setupRankingReport(root) {{
      const state = {{ activeTab: root.querySelector('.tab-button')?.dataset.tab || '', sortKey: 'avg', sortDirection: 'desc' }};
      const q = root.querySelector('#q');
      const levelMode = root.querySelector('#levelMode');
      const activation = root.querySelector('#activation');
      const attr = root.querySelector('#attr');
      const type = root.querySelector('#type');
      const tabButtons = [...root.querySelectorAll('.tab-button')];
      const panels = [...root.querySelectorAll('[data-tab-panel]')];
      const rowCache = new Map();
      const sortKeyByHeader = {{
        '排行': 'rank', '排名': 'rank', 'でんこ': 'name', '属性': 'attr', '类型': 'type', '效果': 'effect',
        '理论最大': 'max', '平均值': 'avg', '期望值': 'avg', '等级值': 'level', '概率': 'probability',
        '持续': 'duration', 'CD': 'cooldown', '发动': 'activation', '访问方向': 'direction',
        '对象/限制': 'target', '触发与条件': 'condition'
      }};
      const missingText = '未记载';

      for (const panel of panels) {{
        const rows = [...panel.querySelectorAll('tbody tr')];
        rows.forEach((row, index) => {{
          row.dataset.originalIndex = String(index);
          try {{ row.levels = JSON.parse(row.dataset.levels || '{{}}'); }}
          catch (_error) {{ row.levels = {{}}; }}
        }});
        rowCache.set(panel.dataset.tabPanel, rows);
      }}

      function activeRows() {{ return rowCache.get(state.activeTab) || []; }}
      function hasAnyVuLevel(row) {{ return Boolean(row.levels['92'] || row.levels['96'] || row.levels['100']); }}
      function shouldShowMissingVu(row) {{
        return !row.levels[levelMode?.value] && ['92', '100'].includes(levelMode?.value) && (row.dataset.vuOnly === 'true' || hasAnyVuLevel(row));
      }}
      function applyLevel(row) {{
        if (!levelMode) return;
        const data = row.levels[levelMode.value];
        const missingVu = shouldShowMissingVu(row);
        row.dataset.hasLevel = data || missingVu ? 'true' : 'false';
        row.dataset.sortMax = data && data.sort_max !== null ? data.sort_max : -1;
        row.dataset.sortAvg = data && data.sort_avg !== null ? data.sort_avg : -1;
        row.querySelector('.max-cell').textContent = data ? data.max_text : (missingVu ? missingText : '-');
        row.querySelector('.avg-cell').textContent = data ? data.avg_text : (missingVu ? missingText : '-');
        row.querySelector('.level-cell').textContent = data ? data.value_text : (missingVu ? missingText : '-');
        row.querySelector('.probability-cell').textContent = data ? data.probability : '-';
        row.querySelector('.duration-cell').textContent = data ? data.duration : '-';
        row.querySelector('.cooldown-cell').textContent = data ? data.cooldown : '-';
      }}
      function textAt(row, index) {{ return (row.children[index]?.textContent || '').trim().toLowerCase(); }}
      function numberFromText(text) {{
        const match = String(text || '').replace(/,/g, '').match(/-?\\d+(?:\\.\\d+)?/);
        return match ? Number(match[0]) : Number.NEGATIVE_INFINITY;
      }}
      function columnIndex(row, key) {{
        const headers = [...row.closest('table').querySelectorAll('thead th')];
        return headers.findIndex(th => th.dataset.sortKey === key);
      }}
      function sortValue(row, key) {{
        if (key === 'rank') return Number(row.dataset.originalIndex);
        if (key === 'max') return Number(row.dataset.sortMax);
        if (key === 'avg') return Number(row.dataset.sortAvg);
        const index = columnIndex(row, key);
        if (key === 'probability') return numberFromText(textAt(row, index));
        return textAt(row, index);
      }}
      function sortActiveRows() {{
        const rows = activeRows();
        for (const row of rows) applyLevel(row);
        if (state.sortKey) {{
          const direction = state.sortDirection === 'asc' ? 1 : -1;
          rows.sort((a, b) => {{
            const av = sortValue(a, state.sortKey);
            const bv = sortValue(b, state.sortKey);
            if (typeof av === 'number' && typeof bv === 'number') {{
              return (av - bv) * direction || Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex);
            }}
            return String(av).localeCompare(String(bv), 'ja') * direction || Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex);
          }});
        }} else {{
          rows.sort((a, b) => Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex));
        }}
        const tbody = root.querySelector(`#panel-${{CSS.escape(state.activeTab)}} tbody`);
        for (const row of rows) tbody.appendChild(row);
      }}
      function updateSortHeaders() {{
        for (const th of root.querySelectorAll('th[data-sort-key]')) {{
          th.classList.remove('sort-asc', 'sort-desc');
          if (th.dataset.sortKey === state.sortKey && th.closest('[data-tab-panel]')?.dataset.tabPanel === state.activeTab) {{
            th.classList.add(state.sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
          }}
        }}
      }}
      function applyFilter() {{
        const needle = q?.value.trim().toLowerCase() || '';
        sortActiveRows();
        let visibleRank = 1;
        for (const row of activeRows()) {{
          const okText = !needle || row.dataset.search.includes(needle);
          const okActivation = !activation?.value || row.dataset.activation === activation.value || (activation.value === 'non_probability' && ['always', 'manual'].includes(row.dataset.activation));
          const okAttr = !attr?.value || row.dataset.attr === attr.value;
          const okType = !type?.value || row.dataset.type === type.value;
          const okLevel = row.dataset.hasLevel !== 'false';
          const visible = okText && okActivation && okAttr && okType && okLevel;
          row.style.display = visible ? '' : 'none';
          if (visible) row.querySelector('.rank').textContent = visibleRank++;
        }}
        updateSortHeaders();
      }}
      function setActiveTab(tabId) {{
        state.activeTab = tabId;
        for (const button of tabButtons) button.classList.toggle('active', button.dataset.tab === tabId);
        for (const panel of panels) panel.classList.toggle('active', panel.dataset.tabPanel === tabId);
        applyFilter();
      }}
      function initSortableHeaders() {{
        for (const panel of panels) {{
          const headers = [...panel.querySelectorAll('th')];
          headers.forEach(th => {{
            const key = sortKeyByHeader[th.textContent.trim()];
            if (!key) return;
            th.classList.add('sortable');
            th.dataset.sortKey = key;
            let clickTimer = null;
            th.addEventListener('click', () => {{
              clearTimeout(clickTimer);
              clickTimer = setTimeout(() => {{
                if (state.sortKey === key) state.sortDirection = state.sortDirection === 'desc' ? 'asc' : 'desc';
                else {{ state.sortKey = key; state.sortDirection = ['max', 'avg', 'probability'].includes(key) ? 'desc' : 'asc'; }}
                applyFilter();
              }}, 180);
            }});
            th.addEventListener('dblclick', event => {{
              event.preventDefault();
              clearTimeout(clickTimer);
              state.sortKey = null;
              state.sortDirection = 'desc';
              applyFilter();
            }});
          }});
        }}
      }}
      for (const button of tabButtons) button.addEventListener('click', () => setActiveTab(button.dataset.tab));
      for (const input of [q, levelMode, activation, attr, type]) if (input) input.addEventListener('input', applyFilter);
      initSortableHeaders();
      if (state.activeTab) setActiveTab(state.activeTab);
    }}

    function setupPrototypeReport(root) {{
      const normalizeQuery = value => value.trim().toLowerCase()
        .replace(/[ァ-ヶ]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0x60))
        .replace(/[ ・＝=]/g, '');
      const scrollWithinList = (list, target, block = 'center') => {{
        let current = 0;
        let node = target;
        while (node && node !== list) {{
          current += node.offsetTop || 0;
          node = node.offsetParent;
        }}
        if (node !== list) current = list.scrollTop + target.getBoundingClientRect().top - list.getBoundingClientRect().top;
        let offset = block === 'center' ? (list.clientHeight - target.offsetHeight) / 2 : 0;
        if (block === 'start') {{
          const section = target.previousElementSibling?.classList.contains('directory-section') ? target.previousElementSibling : null;
          offset = section ? section.offsetHeight + 6 : 8;
        }}
        list.scrollTo({{ top: Math.max(0, current - offset), behavior: 'smooth' }});
      }};
      const jumpInCard = card => {{
        const input = card.querySelector('[data-directory-search]');
        const list = card.querySelector('.directory-list');
        if (!input || !list) return;
        const q = normalizeQuery(input.value);
        if (!q) return;
        const items = [...list.querySelectorAll('[data-directory-item]')];
        const target = items.find(item => (item.dataset.key || '').includes(q));
        if (!target) return;
        list.querySelectorAll('.directory-hit').forEach(item => item.classList.remove('directory-hit'));
        target.classList.add('directory-hit');
        scrollWithinList(list, target);
      }};
      root.querySelectorAll('.directory-card').forEach(card => {{
        const button = card.querySelector('[data-directory-jump]');
        const expandButton = card.querySelector('[data-directory-expand]');
        const input = card.querySelector('[data-directory-search]');
        if (button) button.addEventListener('click', () => jumpInCard(card));
        if (expandButton) expandButton.addEventListener('click', () => {{
          const expanded = card.classList.toggle('is-expanded');
          expandButton.textContent = expanded ? '收起' : '展开';
          expandButton.setAttribute('aria-pressed', expanded ? 'true' : 'false');
        }});
        if (input) input.addEventListener('keydown', event => {{
          if (event.key === 'Enter') {{
            event.preventDefault();
            jumpInCard(card);
          }}
        }});
      }});
      root.querySelectorAll('.directory-quick [data-directory-section]').forEach(button => {{
        button.addEventListener('click', event => {{
          const id = button.dataset.directorySection;
          if (!id) return;
          const card = button.closest('.directory-card');
          const list = card?.querySelector('.directory-list');
          const target = root.querySelector(`#${{CSS.escape(id)}}`);
          if (!list || !target) return;
          event.preventDefault();
          scrollWithinList(list, target, 'start');
        }});
      }});
    }}

    for (const button of buttons) button.addEventListener('click', () => loadReport(button.dataset.reportId));
    const initial = location.hash ? location.hash.slice(1) : REPORTS[0].id;
    loadReport(reportById.has(initial) ? initial : REPORTS[0].id);
  </script>
</body>
</html>
"""
    OUT_HTML.write_text("\n".join(line.rstrip() for line in html_text.splitlines()) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "reports": len(REPORTS), "mode": "single_html_lazy"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
