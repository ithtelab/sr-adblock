"""生成数据看板（SVG + JSON）。

**为什么不用第三方统计服务**：任何"安装量/调用量"都要求产物经过一个能记录请求的
服务器 —— 而这个项目的承诺就是"不采集、不回传"。两者不能兼得。
所以这里只画**真实可得**的数字：

  1. 规则规模 —— 每次构建从产物里数出来的，最准
  2. 工程质量 —— 修正了多少条上游缺陷，构建时统计
  3. GitHub 关注度 —— 星标/复刻/仓库访问，公开数据

「累计拦截了多少广告」这类数字**不存在**：规则在你手机上运行，不回传任何东西。
看板页脚会明确写这一点 —— 不编数字，也顺便告诉用户这是隐私设计的代价与好处。

嵌入方式：产物发布到 release 分支后，用 raw 链接嵌进 README。
（已验证 raw.githubusercontent 返回 Content-Type: image/svg+xml，能被 <img> 正常渲染）
"""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

from util import human, write_text

# 画布
W, H = 880, 348
PAD = 30
BG1, BG2 = "#0d1117", "#161b22"
BORDER = "#30363d"
FG = "#e6edf3"
MUTED = "#8b949e"
DIM = "#6e7681"

FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', "
        "'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', sans-serif")

ACCENTS = ["#3fb950", "#58a6ff", "#d29922", "#bc8cff",
           "#39c5cf", "#f778ba", "#ffa657", "#7ee787"]


def _num(x) -> str:
    return html.escape(str(x))


def build_stats_domains(domain_result: dict, module_result: dict,
                        conf_result: dict) -> list[tuple[str, str, str]]:
    """从各层构建结果里数出真实指标。返回 [(数值, 标签, 提示)]。"""
    m = (domain_result or {}).get("merged")
    mod = module_result or {}
    app = (mod.get("app_stats") or {})

    domains = m.total_domains() if m else 0
    exact = len(m.exact) if m else 0
    suffix = len(m.suffix) if m else 0
    lite = (domain_result or {}).get("lite")
    rules = len(m.rules) if m else 0
    scripts = len(mod.get("infos") or {})
    mitm = mod.get("mitm") or 0
    excluded = len(mod.get("mitm_excluded") or [])
    dupes = mod.get("rep").total_dupes_primary() if mod.get("rep") else 0
    apps = app.get("apps") or 0

    return [
        (human(domains), "广告域名", f"精确 {human(exact)} + 含子域 {human(suffix)}"),
        (human(apps), "覆盖 App", "每个 App 一个独立模块，可单独停用"),
        (human(rules + (mod.get("total") or 0)), "拦截规则", f"域名层 {human(rules)} + 模块层 {human(mod.get('total') or 0)}"),
        (human(lite[0]) if lite else "—", "高置信精简版", f"被 ≥{lite[1] if lite else 2} 个独立来源都认定"),
        (human(scripts), "本地化脚本", "抓进本仓库，上游删除也不失效"),
        (human(mitm), "MITM 主机名", "需要解密的域名总数"),
        (human(excluded), "排除解密域名", "银行/券商/支付/办公，默认不碰"),
        (human(dupes), "修正的重复规则", "上游合并脚本的 bug 产物"),
    ]


def build_stats_github(gh: dict) -> list[tuple[str, str, str]]:
    out = []
    if gh.get("stars") is not None:
        out.append((human(gh["stars"]), "GitHub 星标", "喜欢就给一个"))
    if gh.get("forks") is not None:
        out.append((human(gh["forks"]), "复刻", "自己改一份"))
    if gh.get("watchers") is not None:
        out.append((human(gh["watchers"]), "关注", ""))
    if gh.get("views") is not None:
        out.append((human(gh["views"]), "仓库访问（14 天）", f"独立访客 {human(gh.get('views_uniques') or 0)}"))
    return out


def render_svg(metrics: list[tuple[str, str, str]], gh_metrics: list[tuple[str, str, str]],
               *, repo: str, built_at: str) -> str:
    """画看板。纯字符串拼 SVG，无第三方依赖。"""
    cols = 4
    card_w = (W - PAD * 2) / cols
    rows = max(1, (len(metrics) + cols - 1) // cols)
    row_h = 74
    top = 96

    parts: list[str] = []
    add = parts.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="sr-adblock 数据看板">')
    add(f'''<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{BG1}"/><stop offset="100%" stop-color="{BG2}"/>
  </linearGradient>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#3fb950"/><stop offset="100%" stop-color="#58a6ff"/>
  </linearGradient>
</defs>''')
    add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" '
        f'fill="url(#bg)" stroke="{BORDER}"/>')
    add(f'<rect x="0" y="0" width="{W}" height="3" rx="1.5" fill="url(#accent)" opacity="0.85"/>')

    # 标题栏
    add(f'<text x="{PAD}" y="46" font-family="{FONT}" font-size="19" font-weight="700" '
        f'fill="{FG}">sr-adblock · 数据看板</text>')
    add(f'<text x="{PAD}" y="68" font-family="{FONT}" font-size="12.5" fill="{MUTED}">'
        f'{_num(repo)}　·　全部数字来自公开数据，产物不含任何埋点</text>')
    add(f'<text x="{W-PAD}" y="46" text-anchor="end" font-family="{FONT}" font-size="12.5" '
        f'fill="{DIM}">更新于 {_num(built_at)}</text>')
    add(f'<line x1="{PAD}" y1="82" x2="{W-PAD}" y2="82" stroke="{BORDER}"/>')

    # 指标网格
    for i, (value, label, hint) in enumerate(metrics):
        r, c = divmod(i, cols)
        x = PAD + c * card_w
        y = top + r * row_h
        color = ACCENTS[i % len(ACCENTS)]
        add(f'<rect x="{x+6:.0f}" y="{y+2}" width="3" height="34" rx="1.5" '
            f'fill="{color}" opacity="0.9"/>')
        add(f'<text x="{x+18:.0f}" y="{y+24}" font-family="{FONT}" font-size="30" '
            f'font-weight="700" fill="{FG}">{_num(value)}</text>')
        add(f'<text x="{x+18:.0f}" y="{y+44}" font-family="{FONT}" font-size="12.5" '
            f'fill="{MUTED}">{_num(label)}</text>')
        if hint:
            add(f'<text x="{x+18:.0f}" y="{y+60}" font-family="{FONT}" font-size="10.5" '
                f'fill="{DIM}">{_num(hint)}</text>')

    # GitHub 行
    gh_y = top + rows * row_h + 6
    add(f'<line x1="{PAD}" y1="{gh_y}" x2="{W-PAD}" y2="{gh_y}" stroke="{BORDER}"/>')
    if gh_metrics:
        seg = (W - PAD * 2) / max(1, len(gh_metrics))
        for i, (value, label, hint) in enumerate(gh_metrics):
            x = PAD + i * seg
            add(f'<text x="{x+8:.0f}" y="{gh_y+30}" font-family="{FONT}" font-size="20" '
                f'font-weight="600" fill="{FG}">{_num(value)}</text>')
            add(f'<text x="{x+8:.0f}" y="{gh_y+48}" font-family="{FONT}" font-size="11.5" '
                f'fill="{MUTED}">{_num(label)}</text>')

    add(f'<text x="{PAD}" y="{H-14}" font-family="{FONT}" font-size="10.5" fill="{DIM}">'
        f'「安装量」「拦截次数」这类数字<b>不存在</b>：规则在你手机上本地运行，不回传任何数据 '
        f'—— 这是刻意的设计，不是没做。</text>')
    add("</svg>")
    return "\n".join(p for p in parts if p)


def emit_stats(out_dir: Path, *, domain_result: dict, module_result: dict,
               conf_result: dict, gh: dict, repo: str, repo_url: str) -> dict:
    """产出 dist/stats.svg 与 dist/stats.json。"""
    metrics = build_stats_domains(domain_result, module_result, conf_result)
    gh_metrics = build_stats_github(gh)
    built_at = time.strftime("%Y-%m-%d %H:%M")

    out_dir.mkdir(parents=True, exist_ok=True)
    svg = render_svg(metrics, gh_metrics, repo=repo, built_at=built_at)
    write_text(out_dir / "stats.svg", svg)

    data = {
        "built_at": built_at,
        "repo": repo,
        "metrics": {label: value for value, label, _ in metrics},
        "github": gh,
    }
    (out_dir / "stats.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"metrics": metrics, "github": gh_metrics, "svg": out_dir / "stats.svg"}
