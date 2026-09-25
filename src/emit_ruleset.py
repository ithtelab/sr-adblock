"""域名层产物输出：DOMAIN-SET 域名表 + RULE-SET 规则集。"""
from __future__ import annotations

import time
from pathlib import Path

from merge import Merged
from parse import Rule
from util import fmt_size, human, write_text

BANNER = "# " + "=" * 74


def _header(title: str, subtitle: str, counts: list[tuple[str, str]],
            sources: list[tuple[str, str, str]], usage: list[str]) -> list[str]:
    out = [
        BANNER,
        f"#  {title}",
        f"#  {subtitle}",
        "#",
        "#  由 sr-adblock-factory 自动生成，请勿手工编辑本文件",
        "#  （要增删规则请改仓库 config/ 下的配置源，或加进你的私人 include 文件）",
        f"#  生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "#",
        "#  规模：",
    ]
    out += [f"#    {k:<18} {v}" for k, v in counts]
    out.append("#")
    out.append("#  在小火箭里的用法：")
    out += [f"#    {line}" for line in usage]
    out.append("#")
    out.append("#  来源与许可（详见仓库根目录 NOTICE）：")
    for name, lic, contrib in sources:
        out.append(f"#    - {name}  [{lic}]  {contrib}")
    out.append(BANNER)
    return out


def emit_domain_set(path: Path, exact: dict, suffix: dict, *,
                    title: str, merged: Merged, trusted_names: dict[str, str],
                    repo_url: str, rel_path: str) -> int:
    """输出 DOMAIN-SET：裸域名=精确匹配，前导点=含子域匹配。"""
    lines: list[tuple[str, str]] = []
    for d in exact:
        lines.append((d, d))
    for d in suffix:
        lines.append((d, "." + d))
    lines.sort(key=lambda t: t[0])

    counts = [("精确匹配", human(len(exact))),
              ("含子域匹配", human(len(suffix))),
              ("合计", human(len(lines)))]
    sources = _source_table(merged, trusted_names, exact, suffix)
    usage = [
        "配置 → [Rule] 段加一行（策略由这一行决定，所以本文件不带策略列）：",
        f"  DOMAIN-SET,{repo_url}/{rel_path},REJECT",
        "DOMAIN-SET 读纯域名表，比 RULE-SET 更省内存、加载更快。",
    ]
    body = "\n".join(line for _, line in lines)
    text = "\n".join(_header(title, "纯域名表，供 DOMAIN-SET 使用", counts, sources, usage))
    text += "\n" + body + "\n"
    write_text(path, text)
    return len(lines)


def emit_rule_set(path: Path, rules: list[Rule], *, title: str,
                  merged: Merged, trusted_names: dict[str, str],
                  repo_url: str, rel_path: str,
                  default_policy: str = "REJECT") -> int:
    """输出 RULE-SET：带规则类型、不带策略列。

    没有策略列是 RULE-SET 的约定 —— 策略由配置里引用它的那一行给出，
    所以同一份规则集可以既用于拦截也可以用于放行。
    """
    rendered = sorted({r.render(with_policy=False) for r in rules})
    by_kind: dict[str, int] = {}
    for line in rendered:
        by_kind[line.split(",", 1)[0]] = by_kind.get(line.split(",", 1)[0], 0) + 1

    counts = [(k, human(v)) for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])]
    counts.append(("合计", human(len(rendered))))

    sources = _source_table(merged, trusted_names)
    usage = [
        "配置 → [Rule] 段加一行（策略由这一行决定，所以本文件不带策略列）：",
        f"  RULE-SET,{repo_url}/{rel_path},{default_policy}",
        "本文件包含 IP / 关键词 / 正则类规则 —— 这些无法写进 DOMAIN-SET，",
        "所以域名层的完整部署需要同时引用 -domain.list 和 -rule.list 两个文件。",
    ]
    text = "\n".join(_header(title, "规则集，供 RULE-SET 使用", counts, sources, usage))
    text += "\n" + "\n".join(rendered) + "\n"
    write_text(path, text)
    return len(rendered)


def _source_table(merged: Merged, trusted_names: dict[str, str],
                  exact: dict | None = None, suffix: dict | None = None
                  ) -> list[tuple[str, str, str]]:
    """统计每个来源贡献了多少条（含与其他来源重叠的部分）。"""
    if exact is None:
        exact, suffix = merged.exact, merged.suffix
    counter: dict[str, int] = {}
    for table in (exact, suffix):
        for _, owners in table.items():
            for src in owners:
                counter[src] = counter.get(src, 0) + 1
    stats = merged.source_stats
    rows = []
    for src, n in sorted(counter.items(), key=lambda kv: -kv[1]):
        name = trusted_names.get(src, src)
        lic = stats.get(src, {}).get("license", "")
        rows.append((name, lic or "未声明", f"{human(n)} 条"))
    return rows


def dir_size(paths: list[Path]) -> str:
    return fmt_size(sum(p.stat().st_size for p in paths if p.exists()))
