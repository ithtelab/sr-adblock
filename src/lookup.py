"""误杀排查工具 —— 回答"这个域名为什么被拦 / 怎么放行"。

  python src/lookup.py app.weixin.qq.com
  python src/lookup.py taobao.com --deep      # 顺带查每个上游源文件里有没有它

日常用法：某个 App 功能异常 → 抓到它请求的域名 → 跑这个工具 →
把工具给出的那行直接粘进 config/allowlist.txt。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from util import CACHE_DIR, CONFIG_DIR, DIST_DIR, load_yaml, normalize_domain, parent_domains, read_text

PRODUCTS = ("ad-domain.list", "ad-domain-lite.list")


def load_set(path: Path) -> tuple[set[str], set[str]]:
    """读一个域名表产物，返回（精确集合, 后缀集合）。"""
    exact: set[str] = set()
    suffix: set[str] = set()
    if not path.exists():
        return exact, suffix
    for line in read_text(path).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "," in s:
            continue                      # RULE-SET 里的类型化规则行不属于域名表
        if s.startswith("."):
            suffix.add(s[1:])
        else:
            exact.add(s)
    return exact, suffix


def check(domain: str) -> list[tuple[str, str, str]]:
    """返回 [(产物文件名, 命中方式, 命中的规则域名)]。"""
    hits: list[tuple[str, str, str]] = []
    for name in PRODUCTS:
        exact, suffix = load_set(DIST_DIR / "ruleset" / name)
        if not exact and not suffix:
            continue
        if domain in exact:
            hits.append((name, "精确匹配", domain))
            continue
        if domain in suffix:
            hits.append((name, "含子域匹配", domain))
            continue
        for parent in parent_domains(domain):
            if parent in suffix:
                hits.append((name, "被上层后缀覆盖", parent))
                break
    return hits


def deep_sources(domain: str, sources: dict) -> list[tuple[str, str, int]]:
    """在每个上游原始文件里查这个域名及其父域，回答"哪来的"。"""
    wanted = {domain, "." + domain} | set(parent_domains(domain))
    out: list[tuple[str, str, int]] = []
    for src in sources.get("domain_sources", []):
        path = CACHE_DIR / "raw" / f"{src['id']}.txt"
        if not path.exists():
            continue
        count = 0
        sample = ""
        for line in read_text(path).splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("!"):
                continue
            value = (s.split(",")[-1] if "," in s else s).strip().lstrip(".").lower()
            if value in wanted:
                count += 1
                sample = sample or value
        if count:
            out.append((src["id"], sample, count))
    return out


def _allow_suggestion(domain: str, how: str, matched: str) -> list[str]:
    if how == "被上层后缀覆盖":
        return [
            f"    {matched}          # 放行 {matched} 及其所有子域",
            f"    *.{matched}          # 或者：只放行子域，仍拦 {matched} 本身",
        ]
    apex = ".".join(domain.split(".")[1:]) if domain.count(".") >= 1 else domain
    return [
        f"    {domain}          # 放行 {domain} 及其所有子域",
        f"    *.{apex}          # 或者：只放行 {domain} 这一个精确域名",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="查某个域名是否被拦、被谁拦、怎么放行")
    ap.add_argument("domain", help="要查的域名，例如 app.weixin.qq.com")
    ap.add_argument("--deep", action="store_true", help="同时检查各上游源文件")
    args = ap.parse_args()

    d = normalize_domain(args.domain)
    if not d:
        sys.stdout.write(f"\n  ✗ `{args.domain}` 不是合法域名\n\n")
        return 2

    sys.stdout.write(f"\n  查询：{d}\n  " + "-" * 68 + "\n")

    hits = check(d)
    if not hits:
        sys.stdout.write("  ✅ 未被拦截（不在任何域名表产物里）\n")
    else:
        for name, how, matched in hits:
            sys.stdout.write(f"  🚫 被拦  {name}  [{how}] 命中 `{matched}`\n")

    if args.deep:
        rows = deep_sources(d, load_yaml(CONFIG_DIR / "sources.yaml"))
        sys.stdout.write("\n  各上游来源情况：\n")
        if not rows:
            sys.stdout.write("    （没有任何上游包含它）\n")
        for sid, sample, n in rows:
            sys.stdout.write(f"    - {sid:<14} 命中 {n:>4} 行（示例 {sample}）\n")

    if hits:
        name, how, matched = hits[0]
        sys.stdout.write("\n  要放行它，把下面任一行加进 config/allowlist.txt：\n")
        for line in _allow_suggestion(d, how, matched):
            sys.stdout.write(line + "\n")
        sys.stdout.write("\n  改完重跑 `python src/build.py` 生效；不想重跑构建的话，\n"
                         "  也可以直接写进你的私人 include 文件（见 README「私人覆盖」）。\n")

    sys.stdout.write("\n")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
