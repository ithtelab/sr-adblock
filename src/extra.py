"""整合上游的「额外可选模块」—— 非去广告类，用户按需单独导入。

和 ads-all 的区别：这些模块**不并入主模块**，因为它们是不同的东西
（证书、GitHub 加速、WiFi Calling、单 App 增强…）。混进去会：
  · 让不想用的人被动接受（比如屏蔽系统更新，有人就是要更新）
  · 让 ads-all 的 MITM 主机名和脚本数继续膨胀

统一做四件事（和主模块同一套标准）：
  1. 脚本本地化：script-path 全部改为指向本仓库，上游删库也不失效
  2. 规则集本地化：模块里引用的外部 .list 也抓下来，改为指向本仓库
  3. MITM 主机名补全：规则要解密却没声明主机名的，自动补上（金融类受守卫保护）
  4. 脏数据校验：按段落语法逐条检查，剔除上游的残句/错格式

**保留上游的 `#!arguments`**：那是用户在手机上配置这些模块的界面
（比如 GitHubPro 的 14 个参数、WiFi Calling 的代理分组选择），必须原样保留。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import module as module_mod
import vendor as vendor_mod
from util import (DIST_DIR, VENDOR_DIR, download, fetch_text, fmt_size, human,
                  log, read_text, stable_id, warn, write_text)


@dataclass
class ExtraInfo:
    id: str
    name: str
    output: str
    group: str
    path: Path | None = None
    entries: int = 0
    scripts: int = 0
    rulesets: int = 0
    mitm_added: int = 0
    mitm_held: int = 0
    dropped: int = 0
    ok: bool = False
    error: str = ""
    note: str = ""
    has_args: bool = False


def _vendor_rulesets(sections: dict, *, offline: bool, refresh: bool,
                     repo_url: str) -> tuple[dict, int]:
    """把模块里引用的外部规则集抓到本仓库，并把 URL 改指本仓库。

    上游模块常用 RULE-SET,https://.../Foo.list,策略 的方式引用别人仓库的文件 ——
    那个仓库改名/删文件，规则就静默失效。抓到自己仓库里最稳。
    """
    rewritten = 0
    out_dir = VENDOR_DIR / "rulesets"
    for sec in ("[Rule]", "[URL Rewrite]"):
        blocks = sections.get(sec)
        if not blocks:
            continue
        for b in blocks:
            m = re.match(r"^(RULE-SET|DOMAIN-SET),\s*(\S+?)\s*,\s*(.+)$", b.text)
            if not m:
                continue
            kind, url, policy = m.group(1), m.group(2), m.group(3)
            if "//" not in url or repo_url.split("//")[-1] in url:
                continue
            name = url.split("?")[0].rsplit("/", 1)[-1] or "ruleset.list"
            local = out_dir / name
            if offline:
                if not local.exists():
                    warn(f"离线模式且规则集未本地化，保留原引用：{name}", "warn")
                    continue
            else:
                res = download(f"_ruleset__{stable_id(url)}", url, f"ruleset__{name}",
                               refresh=refresh)
                if not res.ok or not res.path.exists():
                    warn(f"规则集抓取失败，保留原引用：{url}", "warn")
                    continue
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(res.path.read_bytes())
            b.text = f"{kind},{repo_url}/vendor/rulesets/{name},{policy}"
            rewritten += 1
    return sections, rewritten


# 规则集是「策略无关」的格式（DOMAIN,x.com），而模块里的规则**必须带策略**
# （DOMAIN,x.com,REJECT）—— 少这一列规则会被小火箭忽略。
_POLICY_TOKENS = {
    "REJECT", "REJECT-DROP", "REJECT-NO-DROP", "REJECT-TINYGIF", "REJECT-DICT",
    "REJECT-ARRAY", "REJECT-IMG", "REJECT-200", "REJECT-VIDEO", "DIRECT", "PROXY",
}
_OPTION_TOKENS = {"no-resolve", "extended-matching", "pre-matching", "force-remote-dns"}


def _ensure_policy(text: str, policy: str) -> str:
    """给规则补上策略列（已经有了就不动）。

    要区分「选项」和「策略」：`IP-CIDR,1.2.3.4/32,no-resolve` 的第 3 列是选项，
    不能因为它"有 3 列"就当成已经带了策略。
    """
    parts = [p.strip() for p in text.split(",")]
    tail = parts[2:]                     # 只看「值」之后的列（parts[1] 是值本身）
    if any(t.upper() in _POLICY_TOKENS for t in tail):
        return text                      # 已带已知策略
    if any(t and t not in _OPTION_TOKENS for t in tail):
        return text                      # 不是选项的未知列 → 可能是策略组名，保留原样
    return f"{text},{policy}"


def _build_from_ruleset(text: str, source: str, *, policy: str = "REJECT") -> dict:
    """把一个纯规则集（有类型、无策略列）包成模块的 [Rule] 段，并补上策略。"""
    blocks = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("!"):
            continue
        blocks.append(module_mod.Block(_ensure_policy(s, policy), [], source))
    return {"[Rule]": blocks} if blocks else {}


def build_extra_modules(src_list: list[dict], options: dict, *,
                        offline: bool, refresh: bool,
                        vendor_map: dict[str, str]) -> dict:
    """抓取并整合所有额外可选模块。返回统计信息。"""
    out_dir = DIST_DIR / "module" / "extra"
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_url = options.get("repo_url", "").rstrip("/")
    infos: list[ExtraInfo] = []

    for src in src_list:
        sid = src["id"]
        info = ExtraInfo(id=sid, name=src.get("name", sid),
                         output=src.get("output", sid),
                         group=src.get("group", "其他"),
                         note=src.get("note", ""))
        text, res = fetch_text(sid, src["url"], f"extra__{sid}.txt",
                               offline=offline, refresh=refresh)
        if not res.ok:
            info.error = res.error or "拉取失败"
            warn(f"额外模块 {sid} 拉取失败：{info.error}", "error")
            infos.append(info)
            continue

        kind = src.get("kind", "module")
        if kind == "ruleset":
            sections = _build_from_ruleset(text, sid,
                                           policy=src.get("policy", "REJECT"))
            meta = {"name": src.get("name", sid), "desc": src.get("desc", "")}
        else:
            mod = module_mod.parse_module(text, sid)
            sections = dict(mod.sections)
            meta = dict(mod.meta)

        # 脏数据校验
        junk: dict[str, list[str]] = {}
        sections = module_mod.apply_sanity_filter(sections, junk)
        info.dropped = sum(len(v) for v in junk.values())

        # 脚本本地化
        urls = vendor_mod.collect_script_urls(sections, module_mod.extract_script_path)
        if urls:
            if offline:
                infos_map = {u: vendor_mod.ScriptInfo(url=u, name=Path(vendor_mod.vendor_rel_path(u)).name,
                                                      local_rel=vendor_mod.vendor_rel_path(u))
                             for u in urls}
                for u, i in infos_map.items():
                    p = VENDOR_DIR / i.local_rel
                    i.ok, i.size = p.exists(), (p.stat().st_size if p.exists() else 0)
            else:
                infos_map = vendor_mod.download_scripts(list(urls), refresh=refresh)
            new_blocks = []
            for b in sections.get("[Script]", []):
                u = module_mod.extract_script_path(b)
                if u and infos_map.get(u) and infos_map[u].ok:
                    b = module_mod.rewrite_script_path(
                        b, f"{repo_url}/vendor/{infos_map[u].local_rel}")
                new_blocks.append(b)
            sections["[Script]"] = new_blocks
            info.scripts = len([u for u in urls if infos_map.get(u) and infos_map[u].ok])

        # 规则集本地化
        sections, info.rulesets = _vendor_rulesets(sections, offline=offline,
                                                   refresh=refresh, repo_url=repo_url)

        # MITM 主机名补全（金融守卫同样生效）
        added, held, _ = module_mod.derive_mitm_hosts(sections)
        if added:
            module_mod.append_mitm(sections, added)
        info.mitm_added, info.mitm_held = len(added), len(held)

        info.entries = sum(len(v) for v in sections.values())
        info.has_args = bool(meta.get("arguments"))
        info.path = out_dir / f"{info.output}.srmodule"

        from emit_module import emit_srmodule
        mitm = module_mod.parse_mitm(
            module_mod.Module(sections={"[MITM]": sections.get("[MITM]", [])}))
        counts = [(k, human(len(v))) for k, v in sections.items()]
        emit_srmodule(
            info.path, sections,
            name=meta.get("name", info.name) or info.name,
            desc=meta.get("desc", "") or info.name,
            author=src.get("author", meta.get("author", "上游作者")) + "（本仓库仅本地化脚本并重新发布）",
            homepage=meta.get("homepage", repo_url.split("/re", 1)[0]),
            icon=meta.get("icon", ""),
            arguments=meta.get("arguments", ""),
            extra_meta={"arguments-desc": meta.get("arguments-desc", "")}
                       if meta.get("arguments-desc") else {},
            provenance=[src.get("source_name", src["url"].split("raw.githubusercontent.com/")[-1]),
                        f"来源：{src.get('repo', '')}",
                        *([f"已本地化 {info.rulesets} 个外部规则集引用"] if info.rulesets else []),
                        *([f"已本地化 {info.scripts} 个脚本"] if info.scripts else [])],
            counts=counts + [("MITM 主机名", human(len(mitm)))],
            usage=[src.get("usage", "导入方式：小火箭 → 配置 → 模块 → 右上角 + → 粘贴本文件链接")],
        )
        info.ok = True
        infos.append(info)

    ok = [i for i in infos if i.ok]
    groups: dict[str, list[ExtraInfo]] = {}
    for i in ok:
        groups.setdefault(i.group, []).append(i)

    # 分组索引
    lines = ["# 额外可选模块", "",
             "这些模块**不属于去广告三层**，是额外功能，按需单独导入。",
             "每个都做了脚本本地化与 MITM 补全，并保留了上游的参数声明。", ""]
    for g, items in sorted(groups.items()):
        lines += [f"## {g}", "", "| 模块 | 条目 | 脚本 | 参数 | 说明 |",
                  "| :-- | --: | --: | :--: | :-- |"]
        for i in sorted(items, key=lambda x: x.output):
            lines.append(f"| `{i.output}.srmodule` | {i.entries} | "
                         f"{i.scripts or '—'} | {'有' if i.has_args else '—'} | {i.note} |")
        lines.append("")
    write_text(out_dir / "README.md", "\n".join(lines))

    return {"infos": infos, "ok": len(ok), "total": len(infos),
            "groups": {g: len(v) for g, v in groups.items()},
            "scripts": sum(i.scripts for i in ok),
            "rulesets": sum(i.rulesets for i in ok),
            "mitm_added": sum(i.mitm_added for i in ok),
            "dropped": sum(i.dropped for i in ok),
            "bytes": sum(i.path.stat().st_size for i in ok if i.path)}
