"""把各上游五花八门的格式解析成统一的中间表示（IR）。

支持的格式：
  domain_set       纯域名表（裸域名=精确，前导点=含子域）
  ruleset          "类型, 值[, 选项]" 的规则集（无策略列）
  surge_conf_rules Surge/SR 配置文件，取 [Rule] 段（"类型, 值, 策略[, 选项]"）
  hosts            hosts 文件 / 纯域名表（`0.0.0.0 ad.com`），一律按含子域收录
  adblock          AdGuard/ABP 基础规则（`||ad.com^`、`@@||ad.com^`）

后两种是为了直接消费 DNS 拦截生态的名单（StevenBlack / Hagezi / OISD /
AdGuard Home 过滤器）而加的 —— 这些名单不属于上面三种格式，以前只能先转换
再自建一份托管，现在在 config/sources.yaml 里填 URL 即可。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from util import looks_like_ip, normalize_domain, warn

# 域名层关心的规则类型 -> 归一到 IR 的 kind
_DOMAIN_KINDS = {
    "DOMAIN": "exact",
    "DOMAIN-SUFFIX": "suffix",
    "DOMAIN-KEYWORD": "keyword",
    "DOMAIN-WILDCARD": "wildcard",
}

# 纯 IP / 其他类型，原样保留到规则集输出
_PASSTHROUGH_KINDS = {
    "IP-CIDR", "IP-CIDR6", "IP-ASN", "USER-AGENT", "URL-REGEX",
    "DST-PORT", "GEOIP", "PROTOCOL",
}

# 复合规则（AND/OR/NOT）：小火箭的 RULE-SET 里带这些风险高，域名层直接跳过并计数
_COMPOSITE_PREFIXES = ("AND,", "OR,", "NOT,", "AND(", "OR(", "NOT(")

_TARGET_ALIASES = {
    "REJECT": "REJECT",
    "REJECT-DROP": "REJECT-DROP",
    "REJECT-NO-DROP": "REJECT-NO-DROP",
    "REJECT-TINYGIF": "REJECT-TINYGIF",
    "REJECT-DICT": "REJECT-DICT",
    "REJECT-ARRAY": "REJECT-ARRAY",
    "REJECT-IMG": "REJECT-IMG",
    "REJECT-200": "REJECT-200",
    "REJECT-VIDEO": "REJECT-VIDEO",
    "DIRECT": "DIRECT",
    "PROXY": "PROXY",
}

_REJECT_FAMILY = {t for t in _TARGET_ALIASES if t.startswith("REJECT")}


@dataclass(frozen=True)
class Rule:
    """一条非域名类规则（IP/KEYWORD/URL-REGEX...），用于生成 RULE-SET。"""
    kind: str
    value: str
    options: tuple[str, ...] = ()
    target: str | None = None
    source: str = ""

    @property
    def key(self) -> tuple:
        """去重键：同类型同值即视为同一条（选项差异另行报告）。"""
        return (self.kind, self.value)

    def render(self, *, with_policy: bool, default_policy: str | None = None) -> str:
        parts = [self.kind, self.value]
        if with_policy:
            policy = self.target or default_policy or "REJECT"
            parts.append(policy)
        parts.extend(self.options)
        return ",".join(parts)


@dataclass
class Layer:
    """域名层的解析结果：精确域名 / 含子域域名 / 其他规则 + 来源归属。"""
    exact: dict[str, set[str]] = field(default_factory=dict)
    suffix: dict[str, set[str]] = field(default_factory=dict)
    rules: list[Rule] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    # 来源自带的放行域名（adblock 的 @@||domain^）。由 build.py 并入放行名单，
    # 语义与 config/allowlist.txt 的“放行该域名及其所有子域”一致。
    allow: set[str] = field(default_factory=set)

    def add_exact(self, domain: str, source: str) -> None:
        self.exact.setdefault(domain, set()).add(source)

    def add_suffix(self, domain: str, source: str) -> None:
        self.suffix.setdefault(domain, set()).add(source)

    def bump(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n


def _is_comment(line: str) -> bool:
    s = line.lstrip()
    return (not s) or s.startswith("#") or s.startswith("!") or s.startswith("//")


def _clean(line: str) -> str:
    """去掉行尾注释和多余空白（URL-REGEX 里可能有 # 号，只在前面是空白时才当注释）。"""
    s = line.rstrip("\n").rstrip("\r")
    m = re.search(r"\s+#", s)
    if m:
        s = s[:m.start()]
    return s.strip()


def _split(line: str) -> list[str]:
    return [p.strip() for p in line.split(",")]


def _normalize_target(raw: str) -> str | None:
    return _TARGET_ALIASES.get(raw.strip().upper())


# ---------------------------------------------------------------------------
# domain_set：纯域名表
# ---------------------------------------------------------------------------

def parse_domain_set(text: str, source: str) -> Layer:
    layer = Layer()
    for line in text.splitlines():
        if _is_comment(line):
            continue
        s = _clean(line)
        if not s:
            continue
        if looks_like_ip(s):
            layer.rules.append(Rule("IP-CIDR", _as_cidr(s), ("no-resolve",), "REJECT", source))
            layer.bump("ip_from_domain_list")
            continue
        is_suffix = s.startswith(".")
        domain = normalize_domain(s)
        if not domain:
            layer.bump("invalid")
            continue
        (layer.add_suffix if is_suffix else layer.add_exact)(domain, source)
    return layer


def _as_cidr(value: str) -> str:
    if "/" in value:
        return value
    return f"{value}/32" if looks_like_ip(value) and "." in value else f"{value}/128"


# ---------------------------------------------------------------------------
# hosts：hosts 文件 / 纯域名表
# ---------------------------------------------------------------------------

# hosts 文件里表示“屏蔽”的地址。首列是这些（或任何 IP 字面量）时，
# 后面的 token 才是域名；否则整行按纯域名表处理。
_HOSTS_IPS = {"0.0.0.0", "127.0.0.1", "::1", "::", "255.255.255.255"}


def parse_hosts(text: str, source: str) -> Layer:
    """hosts 文件（`0.0.0.0 ad.com`）或纯域名表（一行一个域名）。

    一行可以有多个域名：`0.0.0.0 a.com b.com` 两个都收。

    收录语义一律是**含子域**（DOMAIN-SUFFIX）：这类名单在 DNS 拦截里的用法就是
    “拦 ad.com 连带 *.ad.com” —— Pi-hole、AdGuard Home、esp32-c3-adblock 的
    父域匹配都是这个行为。所以**不能**按 domain_set 的“裸域名 = 精确匹配”来收，
    那会把子域全部漏掉（这正是直接拿 hosts 名单喂 domain_set 的坑）。
    确实需要精确匹配时请改用 `domain_set` 格式。

    `127.0.0.1 localhost` 这类单标签条目会被判为无效并计数，不会误收。
    """
    layer = Layer()
    for line in text.splitlines():
        if _is_comment(line):
            continue
        s = _clean(line)
        if not s:
            continue
        parts = s.split()
        if parts[0] in _HOSTS_IPS or looks_like_ip(parts[0]):
            parts = parts[1:]          # hosts 行：首列是 IP，其余才是域名
        elif len(parts) > 1:
            layer.bump("malformed")    # 非 hosts 行又不止一个 token：不是域名表
            continue
        for token in parts:
            domain = normalize_domain(token)
            if not domain:
                layer.bump("invalid")
                continue
            layer.add_suffix(domain, source)
            layer.bump("domain_suffix")
    return layer


# ---------------------------------------------------------------------------
# adblock：AdGuard / Adblock Plus 基础规则
# ---------------------------------------------------------------------------

# ||domain^  或  @@||domain^  后面可跟 $修饰符
_ADBLOCK_RULE_RE = re.compile(r"^(@@)?\|\|([^\s^$/*|]+)\^?(\$.*)?$")


def parse_adblock(text: str, source: str) -> Layer:
    """AdGuard / Adblock Plus 基础规则里能表达成“域名后缀”的那部分。

    只处理两类，其余一律跳过并计数（DNS 域名层表达不了）：

      ||ad.com^                拦截 ad.com 及其子域
      @@||ad.com^              放行 ad.com 及其子域
      ||ad.com^$third-party    带 $修饰符 —— 修饰符无法在域名层表达，跳过
      ||*.ad.com^              通配 —— 跳过
      /banner\\d+/、a.com##.x    正则 / 元素隐藏 —— 跳过

    注意 `@@` 放行是**全局**的：`@@||ad.com^` 会让所有来源里的 ad.com 都被放行。
    这与小火箭“放行名单对三层同时生效”的既有设计一致，也与 AdGuard Home 同时
    启用多份过滤器时的行为一致。来源自带放行规则会记进构建报告，便于回溯。
    """
    layer = Layer()
    for line in text.splitlines():
        if _is_comment(line):
            continue
        s = _clean(line)
        if not s:
            continue
        if s.startswith("["):              # ABP/AdGuard 头部声明，如 [Adblock Plus 2.0]
            continue
        m = _ADBLOCK_RULE_RE.match(s)
        if not m:
            layer.bump("adblock_skipped")
            continue
        if m.group(3):                     # $修饰符
            layer.bump("adblock_modifiers")
            continue
        domain = normalize_domain(m.group(2))
        if not domain:
            layer.bump("invalid")
            continue
        if m.group(1):                     # @@ 放行
            layer.allow.add(domain)
            layer.bump("adblock_allow")
        else:
            layer.add_suffix(domain, source)
            layer.bump("domain_suffix")
    return layer


# ---------------------------------------------------------------------------
# ruleset："类型, 值[, 选项]"，无策略列
# ---------------------------------------------------------------------------

def parse_ruleset(text: str, source: str, *, only: list[str] | None = None) -> Layer:
    layer = Layer()
    only_set = {k.upper() for k in only} if only else None
    for line in text.splitlines():
        if _is_comment(line):
            continue
        s = _clean(line)
        if not s:
            continue
        if s.upper().startswith(_COMPOSITE_PREFIXES):
            layer.bump("composite_skipped")
            continue
        parts = _split(s)
        kind = parts[0].upper()
        if len(parts) < 2 or not parts[1]:
            layer.bump("malformed")
            continue
        _add_typed(layer, kind, parts[1], tuple(p for p in parts[2:] if p),
                   source, only_set, policy=None)
    return layer


# ---------------------------------------------------------------------------
# surge_conf_rules：配置文件 [Rule] 段，带策略列
# ---------------------------------------------------------------------------

def parse_surge_conf_rules(text: str, source: str, *,
                           only: list[str] | None = None) -> Layer:
    layer = Layer()
    only_set = {k.upper() for k in only} if only else None
    in_rule = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_rule = stripped.lower() == "[rule]"
            continue
        if not in_rule or _is_comment(line):
            continue
        s = _clean(line)
        if not s:
            continue
        if s.upper().startswith(_COMPOSITE_PREFIXES):
            layer.bump("composite_skipped")
            continue
        parts = _split(s)
        kind = parts[0].upper()
        if len(parts) < 3:
            layer.bump("malformed")
            continue
        value, raw_target = parts[1], parts[2]
        target = _normalize_target(raw_target)
        if target is None:
            layer.bump("unknown_target")
            continue
        _add_typed(layer, kind, value, tuple(p for p in parts[3:] if p),
                   source, only_set, policy=target)
    return layer


# ---------------------------------------------------------------------------

def _add_typed(layer: Layer, kind: str, value: str, options: tuple[str, ...],
               source: str, only_set: set[str] | None, policy: str | None) -> None:
    if only_set and kind not in only_set:
        layer.bump(f"filtered_{kind.lower().replace('-', '_')}")
        return

    if kind in _DOMAIN_KINDS:
        form = _DOMAIN_KINDS[kind]
        if form in ("exact", "suffix"):
            domain = normalize_domain(value)
            if not domain:
                layer.bump("invalid")
                return
            (layer.add_suffix if form == "suffix" else layer.add_exact)(domain, source)
            layer.bump(f"domain_{form}")
        else:
            layer.rules.append(Rule(kind, value, options, policy, source))
            layer.bump(kind.lower().replace("-", "_"))
        return

    if kind in _PASSTHROUGH_KINDS:
        if kind in ("IP-CIDR", "IP-CIDR6") and not looks_like_ip(value):
            layer.bump("invalid")
            return
        layer.rules.append(Rule(kind, value, options, policy, source))
        layer.bump(kind.lower().replace("-", "_"))
        return

    layer.bump("unknown_kind")
    if layer.stats["unknown_kind"] <= 3:
        warn(f"[{source}] 遇到未知规则类型 {kind}，已跳过：{value[:60]}")


def is_reject(target: str | None) -> bool:
    return bool(target) and target.upper() in _REJECT_FAMILY
