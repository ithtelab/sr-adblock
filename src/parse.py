"""把各上游五花八门的格式解析成统一的中间表示（IR）。

支持的格式：
  domain_set       纯域名表（裸域名=精确，前导点=含子域）
  ruleset          "类型, 值[, 选项]" 的规则集（无策略列）
  surge_conf_rules Surge/SR 配置文件，取 [Rule] 段（"类型, 值, 策略[, 选项]"）
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
