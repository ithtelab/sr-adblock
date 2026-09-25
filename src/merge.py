"""合并层：多来源并集、父域压缩、放行名单、规则冲突消解。

核心设计：
  * 每个域名记录它出现在哪些来源里 —— 这是"高置信"(lite) 判定的依据，
    也是误杀排查时回答"这条规则哪来的"的唯一凭据。
  * 父域压缩：DOMAIN-SUFFIX 语义含 apex 自身（.foo.com 已覆盖 foo.com
    及其所有子域），所以只要某个上层后缀在列，它的子域条目无论精确还是后缀
    都是冗余的，可以安全删除。这是把 34 万条压下来的关键。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from parse import Layer, Rule, is_reject
from util import human, parent_domains, warn


@dataclass
class Merged:
    exact: dict[str, set[str]] = field(default_factory=dict)
    suffix: dict[str, set[str]] = field(default_factory=dict)
    rules: dict[tuple, Rule] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    option_merges: list[str] = field(default_factory=list)
    dropped_by_allow: list[tuple[str, str]] = field(default_factory=list)
    compressed: int = 0
    source_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def total_domains(self) -> int:
        return len(self.exact) + len(self.suffix)

    def high_confidence(self, trusted: set[str], min_sources: int,
                        always: set[str] | None = None
                        ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """出现在 >= min_sources 个独立来源里的域名（lite 精简版用）。

        always 里的来源单独一条就够 —— 用于本仓库自建黑名单：
        用户亲手加的域名不该因为"只有我自己写"而被精简版漏掉。

        返回的仍是"域名 -> 来源集合"，好让精简版产物里的来源统计依然准确。
        """
        always = always or set()

        def pick(table):
            return {d: owners for d, owners in table.items()
                    if (owners & always) or len(owners & trusted) >= min_sources}
        return pick(self.exact), pick(self.suffix)


def merge_layers(layers: dict[str, Layer]) -> Merged:
    m = Merged()
    for src, layer in layers.items():
        stats = dict(layer.stats)
        stats["domains_exact"] = len(layer.exact)
        stats["domains_suffix"] = len(layer.suffix)
        stats["rules"] = len(layer.rules)
        m.source_stats[src] = stats
        for d, owners in layer.exact.items():
            m.exact.setdefault(d, set()).update(owners)
        for d, owners in layer.suffix.items():
            m.suffix.setdefault(d, set()).update(owners)
        for rule in layer.rules:
            _merge_rule(m, rule)
    return m


def _merge_rule(m: Merged, rule: Rule) -> None:
    existing = m.rules.get(rule.key)
    if existing is None:
        m.rules[rule.key] = rule
        return
    if existing.target == rule.target and existing.options == rule.options:
        return

    # 只差选项（典型：一个来源写了 no-resolve，另一个没写）——这不是冲突。
    # 取选项的并集：no-resolve 对 IP 类规则是更安全的选择（避免为匹配 IP 规则
    # 去解析域名）。记一笔但不进冲突清单，否则报告会被这种噪音淹没。
    if existing.target == rule.target:
        if set(existing.options) != set(rule.options):
            union = tuple(sorted(set(existing.options) | set(rule.options)))
            m.rules[rule.key] = Rule(rule.kind, rule.value, union, rule.target,
                                     existing.source)
            m.option_merges.append(
                f"`{rule.render(with_policy=False)}` 选项取并集 → "
                f"{' '.join(union) or '无'}（{existing.source} + {rule.source}）")
        return

    detail = (f"`{existing.render(with_policy=False)}`："
              f"{existing.source}({(existing.target or '无策略')}"
              f"/{' '.join(existing.options) or '无选项'}) "
              f"vs {rule.source}({(rule.target or '无策略')}"
              f"/{' '.join(rule.options) or '无选项'})")

    winner, loser = existing, rule
    if is_reject(rule.target) and not is_reject(existing.target):
        winner, loser = rule, existing
    elif is_reject(existing.target) or not is_reject(rule.target):
        m.conflicts.append(detail)      # 双方同类，保留先到的，仅记录
        return
    m.rules[rule.key] = winner
    m.conflicts.append(f"{detail} → 采用 {winner.source}（REJECT 优先）")


# ---------------------------------------------------------------------------
# 放行名单
# ---------------------------------------------------------------------------

@dataclass
class AllowList:
    full: set[str] = field(default_factory=set)      # 放行该域名及其所有子域
    sub_only: set[str] = field(default_factory=set)  # 只放行子域，apex 仍拦

    def matches(self, domain: str) -> bool:
        if domain in self.full:
            return True
        if domain in self.sub_only:
            return False
        for parent in parent_domains(domain):
            if parent in self.full or parent in self.sub_only:
                return True
        return False


def load_allowlist(path) -> AllowList:
    allow = AllowList()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("*."):
            if len(line) > 2:
                allow.sub_only.add(line[2:].lower())
        else:
            allow.full.add(line.lstrip(".").lower())
    return allow


def apply_allowlist(m: Merged, allow: AllowList) -> None:
    """把被放行的域名从结果里剔除（`foo.com` 同时覆盖 foo.com 自身与所有子域）。"""
    for table_name, table in (("exact", m.exact), ("suffix", m.suffix)):
        for domain in list(table):
            if allow.matches(domain):
                m.dropped_by_allow.append((domain, table_name))
                del table[domain]


# ---------------------------------------------------------------------------
# 父域压缩
# ---------------------------------------------------------------------------

def compress(m: Merged) -> None:
    """删掉被上层后缀覆盖的冗余条目，并把来源归属上交给覆盖它的父域。

    归属上交很重要：A 来源写了 .sub.ad.com、B 来源写了 .ad.com，压缩掉前者后
    把 A 记到 ad.com 上，lite 的"两个独立来源都认为这里有广告"判定才不会漏。
    """
    suffix_set = set(m.suffix)
    removed = 0

    for domain in list(m.exact):
        cover = _covering_parent(domain, suffix_set)
        if cover is not None:
            m.suffix[cover].update(m.exact.pop(domain))
            removed += 1

    for domain in list(m.suffix):
        # 后缀条目自身被父级后缀覆盖（.a.b.com 被 .b.com 覆盖）；
        # 必须跳过自己，否则每条都会"覆盖自己"被误删。
        cover = _covering_parent(domain, suffix_set, skip_self=True)
        if cover is not None:
            m.suffix[cover].update(m.suffix.pop(domain))
            removed += 1

    m.compressed = removed


def _covering_parent(domain: str, suffix_set: set[str], *,
                     skip_self: bool = False) -> str | None:
    """返回覆盖 domain 的**最高**幸存父后缀。

    必须取最高的那个，不能就近取：中间层父域自己也会被更上层覆盖而删除，
    若把归属交给它，回填时那个键已经不存在了。最高的父后缀没有任何
    上层覆盖者，所以它必然存活到最后。
    """
    best = None
    if not skip_self and domain in suffix_set:
        best = domain
    for parent in parent_domains(domain):   # 由近及远，最后一次赋值即最高层
        if parent in suffix_set:
            best = parent
    return best


# ---------------------------------------------------------------------------
# 校验与告警
# ---------------------------------------------------------------------------

def audit(m: Merged) -> None:
    bare = sorted(d for d in m.suffix if "." not in d)
    if bare:
        warn(f"发现 {len(bare)} 个单标签后缀（会匹配整个顶级域，疑似脏数据）："
             f"{', '.join(bare[:10])}")

    both = sorted(set(m.exact) & set(m.suffix))
    if both:
        warn(f"{human(len(both))} 个域名同时以精确+后缀形式存在（后缀已含精确，属冗余）："
             f"{', '.join(both[:5])}")

    reject_rules = [r for r in m.rules.values() if is_reject(r.target)]
    non_reject = [r for r in m.rules.values() if r.target and not is_reject(r.target)]
    if non_reject:
        warn(f"{len(non_reject)} 条规则的策略不是 REJECT（域名层应只做拦截）："
             f"{non_reject[0].render(with_policy=True)[:80]}")

    if m.conflicts:
        warn(f"{len(m.conflicts)} 条规则在多个来源间策略不一致（详见报告）", "info")

    _ = reject_rules
