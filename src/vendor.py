"""第三方脚本本地化与兼容性体检。

为什么必须本地化：可莉模块的 217 条 [Script] 里，指向 12 个第三方仓库的脚本占四分之一。
上游一旦改路径或删文件，规则会**静默失效**（规则还在、脚本 404、广告照常出现，
而且不会有任何提示）。可莉自己就踩过这个坑 —— 2026-09-10 那次提交的标题正是
"迁移被删除的美丽修行脚本到本仓库"。抓到自己仓库里就永远不会被上游删掉。

兼容性扫描的价值：这些脚本是 Loon/Surge/QX 多客户端共用的，里面可能用到
小火箭根本没有的 API。上游的 SR 版模块并不会帮你检查这一点。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from util import VENDOR_DIR, fmt_size, human, read_text, stable_id, warn

# 小火箭支持的全局对象（对照 LOWERTOP 的小火箭手册 + 实际运行的 SR 模块）
SR_SUPPORTED = {"$request", "$response", "$done", "$httpClient", "$persistentStore",
                "$notification", "$script", "$argument", "$rocket", "$config"}

# 只有 Surge 有（面板/HTTP API 那一套）
SURGE_ONLY = {"$httpAPI": "Surge 面板 HTTP API，小火箭没有面板功能",
              "$trigger": "Surge 面板触发",
              "$intent": "Surge 快捷指令",
              "$input": "Surge 面板输入",
              "$keystore": "Surge 密钥库",
              "$network": "Surge 网络信息"}

# 只有 Loon 有
LOON_ONLY = {"$loon": "Loon 标识对象（小火箭里不能用它做判断）",
             "$dns": "Loon 的 $dns.query"}

# 只有 QuantumultX 有
QX_ONLY = {"$task": "QuantumultX 的 $task（小火箭没有 $task.fetch）",
           "$prefs": "QuantumultX 的 $prefs"}

_GITHUB_RAW = re.compile(
    r"^https?://raw\.githubusercontent\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/"
    r"(?P<ref>[^/]+)/(?P<path>.+)$", re.I)
_GITHUB_BLOB = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/"
    r"(?:raw|blob)/(?P<ref>[^/]+)/(?P<path>.+)$", re.I)


@dataclass
class ScriptInfo:
    url: str
    name: str
    used_by: list[str] = field(default_factory=list)
    local_rel: str = ""
    ok: bool = False
    error: str = ""
    size: int = 0
    updated: bool = False
    verdict: str = "未检查"
    notes: list[str] = field(default_factory=list)


def vendor_rel_path(url: str) -> str:
    """把脚本 URL 映射成 vendor/ 下的相对路径，保留出处方便日后追溯与更新。"""
    for pattern in (_GITHUB_RAW, _GITHUB_BLOB):
        m = pattern.match(url)
        if m:
            path = m.group("path").split("?")[0]
            return f"{m.group('owner')}/{m.group('repo')}/{m.group('ref')}/{path}"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("//")[-1].split("?")[0])
    return f"_other/{slug[:150]}"


def collect_script_urls(sections: dict[str, list], extract) -> dict[str, list[str]]:
    """从 [Script] 段收集所有 script-path，返回 {url: [用到它的条目名]}。"""
    found: dict[str, list[str]] = {}
    for block in sections.get("[Script]", []):
        url = extract(block)
        if not url:
            continue
        name = block.text.split("=", 1)[0].strip() if "=" in block.text else "?"
        found.setdefault(url, []).append(name)
    return found


def download_scripts(urls: list[str], *, offline: bool = False,
                     refresh: bool = False) -> dict[str, ScriptInfo]:
    """把脚本抓到 vendor/ 下。

    每次构建都用条件请求复查上游（304 就复用本地副本）：
    既能让上游的脚本修复及时进来，又不用每天重下全部脚本。
    缓存文件名由完整相对路径派生，避免不同仓库的同名脚本互相覆盖。
    """
    from util import download

    infos: dict[str, ScriptInfo] = {}
    for url in urls:
        rel = vendor_rel_path(url)
        dest = VENDOR_DIR / rel
        info = ScriptInfo(url=url, name=Path(rel).name, local_rel=rel)
        cached_name = "vendor_" + rel.replace("/", "__")

        if offline:
            if dest.exists():
                info.ok = True
                info.size = dest.stat().st_size
            else:
                info.error = "offline 且未本地化"
            infos[url] = info
            continue

        res = download(f"_vendor__{stable_id(url)}", url, cached_name,
                       refresh=refresh)
        if res.ok and res.path.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(res.path.read_bytes())
            info.ok = True
            info.size = dest.stat().st_size
            info.updated = not res.from_cache
        else:
            info.error = res.error or "下载失败"
        infos[url] = info
    return infos


def analyze(text: str) -> tuple[str, list[str]]:
    """体检一个脚本，返回（结论, 说明）。

    结论分三档：
      ✅ 安全   —— 只改写 $response.body，或客户端差异由客户端探测/多客户端运行时自动分派
      ⚠️ 存疑   —— 用到了别家专有写法，在小火箭里**可能**取不到值，值得人工看一眼
      ❌ 不兼容 —— 无条件调用了小火箭没有的 API，且没有任何客户端判断保护

    重要：这是静态启发式检查，只用来**提示风险**，不能替代真机验证。
    压缩过的脚本写法千奇百怪（`"undefined"!=typeof $task`、`typeof $task<"u"`），
    漏判会导致把能用的脚本误报成不可用，所以这里对"客户端探测"的识别做得比较宽。
    """
    reasons: list[str] = []      # 先列问题，报告里截断时先看到的是原因
    evidence: list[str] = []     # 再列正面证据

    runtime = ("function Env(" in text) or ("isQuanX" in text) or ("isShadowrocket" in text)
    # 压缩版运行时不一定有 function Env(，但一定会有 typeof $loon / $task 这类探测
    probes = re.findall(r"typeof\s+\$(\w+)\s*[<>!=]", text)
    if runtime:
        evidence.append("内含多客户端运行时，按当前客户端自动分派")
    elif probes:
        evidence.append(f"含客户端探测（{'/'.join(sorted(set(probes)))}），按客户端分派")
    if "$rocket" in text:
        evidence.append("显式识别了小火箭（$rocket）")
    if "$httpClient" in text:
        evidence.append("使用 $httpClient（小火箭支持）")

    dispatch = runtime or bool(probes)
    for table, tag in ((SURGE_ONLY, "Surge 专有"), (QX_ONLY, "QuantumultX 专有"),
                       (LOON_ONLY, "Loon 专有")):
        for obj, why in table.items():
            if obj not in text or _guarded(text, obj):
                continue
            detail = f"{obj} 未加判断 —— {why}"
            if dispatch:
                reasons.append(detail + "（但脚本有客户端探测，大概率在对应分支内，建议实机确认）")
            elif table is LOON_ONLY:
                reasons.append(detail)
            else:
                reasons.append(detail + "，且脚本没有任何客户端探测")

    # 小火箭的 $argument 是字符串，Loon 是对象：`$argument.xxx` 在 SR 里取到 undefined
    if re.search(r"\$argument\.\w", text) and not re.search(
            r"typeof\s+\$argument|JSON\.parse\(\s*\$argument|\$argument\.split|parseArgs", text):
        reasons.append("用 `$argument.xxx` 直接取属性 —— 小火箭的 $argument 是字符串不是对象，"
                       "这里会取到 undefined")

    fatal = [r for r in reasons if "没有任何客户端探测" in r]
    if fatal:
        return "❌ 不兼容", reasons + evidence
    if reasons:
        return "⚠️ 存疑", reasons + evidence
    return "✅ 安全", evidence


# 压缩器会把 typeof x === "undefined" 写成 typeof x < "u"，所以保护写法有四种形态
_GUARD_PATTERNS = (
    r"typeof\s+{o}\s*[!=]={{1,2}}",                      # typeof $task === / !==
    r"{o}\s*!==?\s*[\"']undefined[\"']",                 # $task !== "undefined"
    r"[\"']undefined[\"']\s*!==?\s*typeof\s+{o}",        # "undefined" != typeof $task
    r"typeof\s+{o}\s*[<>]",                              # typeof $task < "u"（压缩产物）
)


def _guarded(text: str, obj: str) -> bool:
    """该对象是否被客户端判断保护（多客户端脚本的常见写法，属于安全用法）。"""
    escaped = re.escape(obj)
    return any(re.search(p.format(o=escaped), text) for p in _GUARD_PATTERNS)


def audit_vendored(infos: dict[str, ScriptInfo]) -> dict[str, int]:
    stats = {"safe": 0, "dubious": 0, "broken": 0, "failed": 0, "bytes": 0}
    for info in infos.values():
        if not info.ok:
            stats["failed"] += 1
            continue
        stats["bytes"] += info.size
        text = read_text(VENDOR_DIR / info.local_rel)
        info.verdict, info.notes = analyze(text)
        if info.verdict.startswith("✅"):
            stats["safe"] += 1
        elif info.verdict.startswith("⚠️"):
            stats["dubious"] += 1
        else:
            stats["broken"] += 1
    return stats


def report_lines(infos: dict[str, ScriptInfo]) -> list[str]:
    rows = ["| 脚本 | 结论 | 大小 | 说明 |", "| --- | --- | --- | --- |"]
    order = {"❌ 不兼容": 0, "⚠️ 存疑": 1, "✅ 安全": 2, "未检查": 3}
    for info in sorted(infos.values(),
                       key=lambda i: (order.get(i.verdict, 9), i.name)):
        notes = "；".join(info.notes[:3]) if info.notes else (info.error or "")
        size = fmt_size(info.size) if info.size else "—"
        rows.append(f"| `{info.name}` | {info.verdict} | {size} | {notes[:150]} |")
    return rows
