"""模块层：解析 .srmodule/.sgmodule/.module，合并去重，生成小火箭原生模块。

模块文件格式（与 Surge 相同，小火箭直接吃）：
    #!name=xxx
    #!desc=xxx
    #!author=...
    #!arguments=参数名:默认值

    [Rule]
    DOMAIN-SUFFIX,ad.com,REJECT
    # 注释（可莉模块用注释标注了每条规则对应的 hostname，很有价值，必须保留）

    [URL Rewrite] / [Header Rewrite] / [Body Rewrite] / [Map Local] / [Script] / [MITM]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from util import warn

# 小火箭支持的段落（Surge 专有的 [Panel] 等一律不出现在输出里）
CANONICAL_ORDER = [
    "[General]", "[Rule]", "[Header Rewrite]", "[URL Rewrite]",
    "[Body Rewrite]", "[Map Local]", "[Script]", "[MITM]",
]

# 小火箭不支持的段落：一旦在输入里出现必须剔除
UNSUPPORTED_SECTIONS = {
    "[Panel]", "[SSID Setting]", "[Keystore]", "[Replica]", "[Ponte]",
    "[Port Forwarding]", "[DHCP]", "[Snell Server]", "[MTProto]", "[Testing]",
}

_META_RE = re.compile(r"^#!\s*([A-Za-z0-9_-]+)\s*=\s*(.*)$")
_SECTION_RE = re.compile(r"^\[([^\[\]]+)\]$")


@dataclass
class Block:
    """一条规则 + 紧贴在它上方的注释（注释是上游的知识，合并时要保留）。"""
    text: str
    comments: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def key(self) -> str:
        return normalize_rule(self.text)


@dataclass
class Module:
    meta: dict[str, str] = field(default_factory=dict)
    sections: dict[str, list[Block]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    source: str = ""

    def entries(self, section: str) -> list[Block]:
        return self.sections.get(section, [])

    def count(self) -> int:
        return sum(len(v) for v in self.sections.values())


def normalize_rule(text: str) -> str:
    """用于去重的归一化：压掉多余空白、统一逗号后的空格。"""
    s = re.sub(r"\s+", " ", text.strip())
    s = re.sub(r"\s*,\s*", ",", s)
    return s


# 各段的语义归一化：Surge 版与 SR 版在书写上有些差异，但语义相同，
# 不归一化的话会被误判成"新规则"而重复导入。已核实的两类差异：
#   [Map Local] Surge 版多写 status-code=200（200 本就是 Map Local 的默认状态码）
#   [Script]    Surge 版给含逗号的 pattern 加了引号（SR 版不加）
_SEMANTIC_STRIPS = {
    "[Map Local]": (r"\s*status-code\s*=\s*200\b", ""),
    "[Script]": (r'(pattern\s*=\s*)"([^"]*)"', r"\1\2"),
}


def semantic_key(text: str, section: str) -> str:
    key = normalize_rule(text)
    rule = _SEMANTIC_STRIPS.get(section)
    if rule:
        key = re.sub(rule[0], rule[1], key)
    return key


# 小火箭支持的规则类型（来自小火箭手册的规则类型表）。
# 出现别的类型说明这条规则在小火箭里会被忽略 —— 属于必须报告的问题。
KNOWN_RULE_KINDS = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-WILDCARD",
    "USER-AGENT", "URL-REGEX", "IP-CIDR", "IP-CIDR6", "IP-ASN",
    "RULE-SET", "DOMAIN-SET", "SCRIPT", "DST-PORT", "GEOIP", "FINAL",
    "AND", "OR", "NOT", "PROTOCOL",
}


def entry_problem(section: str, text: str) -> str | None:
    """返回条目不合法的原因；合法返回 None。用来剔除上游脏数据。

    实例：可莉 Surge 版模块的 [URL Rewrite] 里混进了一条 `hostname - reject`
    （在「WIFI万能钥匙」小节，应是作者编辑时留下的残句）。它会被当成
    「任何 URL 里含 hostname 就 reject」的正则 —— 必须拦下来。
    """
    if section == "[URL Rewrite]":
        # 两种合法写法：`模式 替换值 [标记]`（重定向）与 `模式 - 动作`（拦截）
        if " - " in text:
            pattern, _, action = text.rpartition(" - ")
            pattern, action = pattern.strip(), action.strip()
            if not pattern:
                return "匹配模式为空"
            if not action:
                return "动作为空"
        else:
            fields = text.split()
            if len(fields) < 2:
                return "格式应为 `模式 替换值 [标记]` 或 `模式 - 动作`"
            pattern = fields[0]
        if "://" not in pattern and "/" not in pattern and not pattern.startswith("^"):
            return f"匹配模式 `{pattern}` 不像 URL（既没有 :// 也没有 /）"
    elif section == "[Header Rewrite]":
        if " " not in text:
            return "格式不完整"
    elif section == "[Map Local]":
        if "data-type=" not in text:
            return "缺少 data-type 参数"
    elif section == "[Script]":
        if "type=" not in text:
            return "缺少 type 参数"
        if "script-path=" not in text:
            return "缺少 script-path"
    elif section == "[Rule]":
        if "," not in text:
            return "不像规则（没有逗号分隔）"
        kind = text.split(",", 1)[0].strip().upper()
        if kind not in KNOWN_RULE_KINDS:
            return f"小火箭不支持的规则类型 {kind}"
    elif section == "[MITM]":
        if "hostname" not in text:
            return "MITM 段缺少 hostname"
    return None


def apply_sanity_filter(sections: dict[str, list[Block]],
                        dropped: dict[str, list[str]]) -> dict[str, list[Block]]:
    """按段落语法逐条体检，丢掉不合法条目并记录原因。"""
    out: dict[str, list[Block]] = {}
    for section, blocks in sections.items():
        if section == "[MITM]":
            out[section] = blocks
            continue
        keep: list[Block] = []
        for b in blocks:
            problem = entry_problem(section, b.text)
            if problem:
                dropped.setdefault(section, []).append(f"{b.text[:90]}  ← {problem}")
                continue
            keep.append(b)
        if keep:
            out[section] = keep
    return out


def resolve_arguments(sections: dict[str, list[Block]],
                      decl_module: Module) -> tuple[str, list[str], list[str]]:
    """把模块里用到的 {{{参数}}} 解析成 #!arguments 声明。

    上游缺陷：可莉的 SR/Surge 版模块里脚本引用了 8 个参数占位符
    （logLevel / sponsorBlock / tab / useractivity / MY / DT / FX /
    per_filter_video_thread），但 #!arguments 只声明了一个无人引用的
    12306_enable。结果是这 8 个占位符在小火箭里拿不到值（脚本收到字面量或空值），
    而用户界面上却显示一个没用的开关。

    修法：从 Loon V2 插件的 [Argument] 段（那里有完整声明）取默认值，
    只声明真正被引用的那些。

    Loon 写法  name = switch,true,false,tag=xxx  →  小火箭写法  name:true
    Loon 写法  name = select,a|b|c,tag=xxx       →  小火箭写法  name:a
    """
    used: list[str] = []
    for blocks in sections.values():
        for b in blocks:
            for name in re.findall(r"\{\{\{([A-Za-z0-9_]+)\}\}\}", b.text):
                if name not in used:
                    used.append(name)

    decls: dict[str, str] = {}
    for b in decl_module.entries("[Argument]"):
        if "=" not in b.text:
            continue
        name, _, value = b.text.partition("=")
        parts = [p.strip() for p in value.split(",")]
        if not parts:
            continue
        kind = parts[0].lower()
        default = ""
        if kind == "switch" and len(parts) >= 2:
            default = parts[1]
        elif kind == "select" and len(parts) >= 2:
            default = parts[1].split("|")[0].strip()
        elif kind == "input" and len(parts) >= 2:
            default = parts[1]
        decls[name.strip()] = default

    declared = [f"{n}:{decls[n]}" for n in used if n in decls]
    unresolved = [n for n in used if n not in decls]
    return ",".join(declared), unresolved, used


def parse_module(text: str, source: str) -> Module:
    mod = Module(source=source)
    section: str | None = None
    pending: list[str] = []

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        m = _META_RE.match(stripped)
        if m:
            mod.meta.setdefault(m.group(1).lower(), m.group(2).strip())
            continue

        if not stripped:
            pending = []          # 空行切断注释与规则的绑定关系
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            name = stripped
            if name in UNSUPPORTED_SECTIONS:
                warn(f"[{source}] 含小火箭不支持的段落 {name}，已剔除")
                section = None
                continue
            section = name
            if name not in mod.sections:
                mod.sections[name] = []
                mod.order.append(name)
            pending = []
            continue

        if stripped.startswith("#"):
            pending.append(stripped)
            continue

        if section is None:
            continue
        mod.sections[section].append(Block(normalize_rule(line), pending, source))
        pending = []

    return mod


# ---------------------------------------------------------------------------
# 合并
# ---------------------------------------------------------------------------

@dataclass
class MergeReport:
    added: dict[str, int] = field(default_factory=dict)      # 各段最终条数
    dupes_primary: dict[str, int] = field(default_factory=dict)   # 主/平级来源内部的重复（上游 bug）
    supplemented: dict[str, int] = field(default_factory=dict)    # 从参考版本真正补回的条数
    dupes_supplement: dict[str, int] = field(default_factory=dict)  # 参考版里已有的（正常）
    mitm: int = 0
    mitm_dupes: int = 0

    def total_dupes_primary(self) -> int:
        return sum(self.dupes_primary.values())

    def total_supplemented(self) -> int:
        return sum(self.supplemented.values())

    def total_dupes_supplement(self) -> int:
        return sum(self.dupes_supplement.values())


def merge_modules(primary: Module, others: list[Module], *,
                  supplement: list[Module] | None = None) -> tuple[dict[str, list[Block]], MergeReport]:
    """合并模块。

    others     —— 平级来源，各段的条目直接并入
    supplement —— 用来"补齐"的来源（例如用 Surge 版补 SR 版缺的规则）：
                  只补 primary+others 里没有的条目
    """
    rep = MergeReport()
    merged: dict[str, list[Block]] = {}
    seen: dict[str, set[str]] = {}

    def add_blocks(mod: Module, *, only_missing: bool = False) -> None:
        for name, blocks in mod.sections.items():
            if name == "[MITM]":
                continue
            bucket = merged.setdefault(name, [])
            keys = seen.setdefault(name, set())
            for b in blocks:
                k = semantic_key(b.text, name)
                if k in keys:
                    if only_missing:
                        rep.dupes_supplement[name] = rep.dupes_supplement.get(name, 0) + 1
                    else:
                        rep.dupes_primary[name] = rep.dupes_primary.get(name, 0) + 1
                    continue
                keys.add(k)
                bucket.append(b)
                if only_missing:
                    rep.supplemented[name] = rep.supplemented.get(name, 0) + 1
                else:
                    rep.added[name] = rep.added.get(name, 0) + 1

    add_blocks(primary)
    for mod in others:
        add_blocks(mod)
    for mod in (supplement or []):
        add_blocks(mod, only_missing=True)

    # MITM 单独处理：取并集
    hosts: list[str] = []
    seen_hosts: set[str] = set()
    for mod in [primary, *others, *(supplement or [])]:
        for h in parse_mitm(mod):
            if h in seen_hosts:
                rep.mitm_dupes += 1
                continue
            seen_hosts.add(h)
            hosts.append(h)
    rep.mitm = len(hosts)
    if hosts:
        merged["[MITM]"] = [Block("hostname = %APPEND% " + ", ".join(hosts),
                                   [], primary.source)]

    ordered = {name: merged[name] for name in CANONICAL_ORDER if name in merged}
    for name in merged:            # 出现但不在规范顺序里的段落，附在最后
        if name not in ordered:
            ordered[name] = merged[name]
    return ordered, rep


def parse_mitm(mod: Module) -> list[str]:
    hosts: list[str] = []
    for block in mod.entries("[MITM]"):
        text = block.text
        if "=" not in text:
            continue
        _, _, value = text.partition("=")
        value = value.replace("%APPEND%", "").replace("%INSERT%", "")
        for h in value.split(","):
            h = h.strip()
            if h and h not in hosts:
                hosts.append(h)
    return hosts


def extract_script_path(block: Block) -> str | None:
    m = re.search(r"script-path\s*=\s*([^,]+)", block.text)
    return m.group(1).strip() if m else None


def rewrite_script_path(block: Block, new_url: str) -> Block:
    text = re.sub(r"(script-path\s*=\s*)[^,]+", lambda m: m.group(1) + new_url, block.text)
    return Block(text, list(block.comments), block.source)


def filter_rules_by_allowlist(blocks: list[Block], allow) -> tuple[list[Block], list[str]]:
    """按放行名单剔除模块里 [Rule] 段的拦截规则。

    必须做这一步：小火箭里**模块的规则优先级高于配置文件**，
    所以只把域名从域名层剔掉是不够的 —— 模块里那 2800 条 REJECT 一样会拦。
    三层用同一份 allowlist，放行行为才是一致的。
    """
    kept: list[Block] = []
    dropped: list[str] = []
    for b in blocks:
        parts = b.text.split(",")
        kind = parts[0].strip().upper()
        if kind in ("DOMAIN", "DOMAIN-SUFFIX") and len(parts) >= 2:
            domain = parts[1].strip().lower().lstrip(".")
            if domain and allow.matches(domain):
                dropped.append(domain)
                continue
        kept.append(b)
    return kept, dropped
