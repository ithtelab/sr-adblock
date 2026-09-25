"""模块产物输出。"""
from __future__ import annotations

import time
from pathlib import Path

from module import Block, CANONICAL_ORDER
from util import fmt_size, human, write_text

BANNER = "# " + "=" * 74


def emit_srmodule(path: Path, sections: dict[str, list[Block]], *,
                  name: str, desc: str, author: str, homepage: str,
                  icon: str = "", update: str = "", arguments: str = "",
                  provenance: list[str], counts: list[tuple[str, str]],
                  usage: list[str], extra_meta: dict[str, str] | None = None) -> int:
    out: list[str] = [
        f"#!name={name}",
        f"#!desc={desc}",
        f"#!author={author}",
    ]
    if icon:
        out.append(f"#!icon={icon}")
    if homepage:
        out.append(f"#!homepage={homepage}")
    out.append(f"#!update={update or time.strftime('%Y-%m-%d')}")
    if arguments:
        out.append(f"#!arguments={arguments}")
    for k, v in (extra_meta or {}).items():
        out.append(f"#!{k}={v}")

    out += [
        "",
        BANNER,
        "#  本文件由 sr-adblock-factory 合并生成，请勿手工编辑",
        f"#  生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "#",
        "#  合并来源：",
    ]
    out += [f"#    - {p}" for p in provenance]
    out.append("#")
    out.append("#  规模：")
    out += [f"#    {k:<22} {v}" for k, v in counts]
    out.append("#")
    out.append("#  在小火箭里的装法：")
    out += [f"#    {line}" for line in usage]
    out.append(BANNER)
    out.append("")

    total = 0
    for section in CANONICAL_ORDER:
        blocks = sections.get(section)
        if not blocks:
            continue
        out.append(section)
        for b in blocks:
            if b.comments:
                out.extend(_dedupe_comments(b.comments))
            out.append(b.text)
            total += 1
        out.append("")
    for section, blocks in sections.items():     # 非规范段落兜底
        if section in CANONICAL_ORDER or not blocks:
            continue
        out.append(section)
        for b in blocks:
            out.extend(_dedupe_comments(b.comments))
            out.append(b.text)
            total += 1
        out.append("")

    write_text(path, "\n".join(out))
    return total


def _dedupe_comments(comments: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in comments:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def modules_index(entries: list[tuple[str, str, str]]) -> str:
    """生成模块目录索引（哪些 App 模块可选）。"""
    lines = ["# 可选的 per-App 模块", "",
             "按需导入；某个 App 出现误杀或异常时，单独停用对应模块即可，",
             "不用整体关掉去广告。", "",
             "| 模块 | 规则数 | MITM 主机名 |", "| --- | --- | --- |"]
    for name, rules, mitm in entries:
        lines.append(f"| {name} | {rules} | {mitm} |")
    return "\n".join(lines) + "\n"
