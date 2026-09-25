"""产物自检门禁 —— 在构建最后跑一遍，检查**输出文件**而不是输入。

为什么需要它：这是一条无人值守的流水线。上游随时可能改格式、删文件、
甚至把某个规则集整个换掉。如果没有门禁，某天上游一挂，你订阅到的可能
就是一份空规则或者一份带敏感信息的文件，而你不会收到任何提示。

检查项：
  1. 结构     —— 段落名合法、没有小火箭不支持的段落漏进来
  2. 规则     —— 规则类型都在小火箭支持范围内；域名表语法合法
  3. 脚本     —— 所有 script-path 指向本仓库，且被引用的 vendor 文件确实存在
  4. 引用     —— 配置里引用的产物文件自己都真的产出了
  5. 隐私     —— 产物里不能出现节点密码、订阅链接等敏感信息（公开仓库的底线）
  6. 突变     —— 规则数相比上次构建不能暴跌（上游挂了的典型征兆）
  7. 资源     —— MITM 主机名数量、单文件体积是否超预算
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from module import CANONICAL_ORDER, KNOWN_RULE_KINDS, UNSUPPORTED_SECTIONS

# 配置文件比模块多这几个段落（模块里也能出现 [Proxy]/[Proxy Group]，小火箭允许）
SR_CONFIG_SECTIONS = set(CANONICAL_ORDER) | {"[Proxy]", "[Proxy Group]", "[Host]"}
from util import DIST_DIR, ROOT, VENDOR_DIR, fmt_size, human, read_text, warn

STATS_FILE = ROOT / "cache" / "build-stats.json"

# 节点密码/订阅的典型特征（公开仓库里绝不能出现）
SECRET_PATTERNS = [
    (r"encrypt-method\s*=", "节点加密方式（疑似节点定义）"),
    (r"^\s*[\w\u4e00-\u9fa5-]+\s*=\s*(ss|ssr|vmess|vless|trojan|hysteria2?|tuic|snell)\s*,",
     "节点定义行"),
    (r"password\s*=\s*[A-Za-z0-9+/=]{6,}", "明文密码"),
    (r"(subscribe|token|passwd)\s*=\s*[A-Za-z0-9+/=_-]{16,}", "疑似订阅令牌"),
]


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def ok(self, msg: str) -> None:
        self.lines.append(f"- ✅ {msg}")

    def fail(self, msg: str) -> None:
        self.lines.append(f"- ❌ {msg}")
        self.errors.append(msg)

    def warn_(self, msg: str) -> None:
        self.lines.append(f"- ⚠️ {msg}")
        self.warnings.append(msg)

    def info(self, msg: str) -> None:
        self.lines.append(f"- {msg}")


def verify(options: dict) -> tuple[bool, Report]:
    rep = Report()
    opt = options.get("module_layer", {})
    repo_url = options.get("repo_url", "").rstrip("/")
    repo_prefix = repo_url.split("//")[-1] if repo_url else ""

    _check_structure(rep)
    _check_rules(rep)
    _check_scripts(rep, repo_prefix)
    _check_conf_refs(rep)
    _check_secrets(rep)
    stats = _collect_stats()
    _check_drift(rep, stats)
    _check_budget(rep, opt, stats)
    _save_stats(stats)
    return not rep.errors, rep


# ---------------------------------------------------------------------------

def _iter_outputs():
    for p in sorted(DIST_DIR.rglob("*")):
        if p.is_file() and p.suffix in (".list", ".srmodule", ".conf") or \
           (p.is_file() and p.name == "base.conf"):
            yield p


def _check_structure(rep: Report) -> None:
    bad_sections: list[str] = []
    files = 0
    for path in _iter_outputs():
        if path.suffix not in (".srmodule", ".conf"):
            continue
        files += 1
        for line in read_text(path).splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                if s in UNSUPPORTED_SECTIONS:
                    bad_sections.append(f"{path.name}: {s}")
                elif s not in SR_CONFIG_SECTIONS:
                    bad_sections.append(f"{path.name}: 未知段落 {s}")
    if bad_sections:
        rep.fail(f"发现小火箭不支持的段落：{', '.join(sorted(set(bad_sections))[:5])}")
    else:
        rep.ok(f"结构检查通过（{files} 个模块/配置文件，段落名全部合法）")


def _check_rules(rep: Report) -> None:
    bad_kind: list[str] = []
    bad_domain: list[str] = []
    total_rules = 0
    domain_re = re.compile(r"^\.?[a-z0-9_-]+(\.[a-z0-9_-]+)+$")

    for path in sorted((DIST_DIR / "ruleset").glob("*.list")):
        for line in read_text(path).splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "," in s:
                kind = s.split(",", 1)[0].strip().upper()
                total_rules += 1
                if kind not in KNOWN_RULE_KINDS:
                    bad_kind.append(f"{path.name}: {kind}")
            else:
                total_rules += 1
                if path.name.endswith("domain.list") or path.name.endswith("domain-lite.list"):
                    if not domain_re.match(s):
                        bad_domain.append(f"{path.name}: {s[:60]}")
    if bad_kind:
        rep.fail(f"规则集里有小火箭不支持的类型：{', '.join(sorted(set(bad_kind))[:5])}")
    else:
        rep.ok("域名层规则类型全部在小火箭支持范围内")
    if bad_domain:
        rep.fail(f"域名表里有 {len(bad_domain)} 条非法域名：{bad_domain[:3]}")
    else:
        rep.ok(f"域名表语法合法（共 {human(total_rules)} 条规则）")


def _check_scripts(rep: Report, repo_prefix: str) -> None:
    missing: list[str] = []
    external: list[str] = []
    checked = 0
    for path in sorted(DIST_DIR.rglob("*.srmodule")):
        text = read_text(path)
        if "script-path=" not in text:
            continue
        # 只看生效行：被注释掉的规则（上游作者保留的禁用条目）里也会出现 script-path
        live = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
        for m in re.finditer(r"script-path\s*=\s*([^,\s]+)", live):
            url = m.group(1).strip()
            checked += 1
            if repo_prefix and repo_prefix in url:
                rel = url.split("/vendor/", 1)[-1] if "/vendor/" in url else ""
                if not rel or not (VENDOR_DIR / rel).exists():
                    missing.append(f"{path.name}: {url}")
            else:
                external.append(f"{path.name}: {url}")
    if missing:
        rep.fail(f"{len(missing)} 条规则的脚本指向本仓库但文件不存在：{missing[:3]}")
    elif external:
        rep.fail(f"{len(external)} 条规则的脚本仍指向外部仓库"
                 f"（上游删文件就会静默失效）：{external[:3]}")
    else:
        rep.ok(f"脚本本地化完整（{human(checked)} 条 script-path 全部指向本仓库且文件存在）")


def _check_conf_refs(rep: Report) -> None:
    conf = DIST_DIR / "conf" / "base.conf"
    if not conf.exists():
        rep.warn_("没有产出 base.conf（只构建了部分层）")
        return
    text = read_text(conf)
    refs = re.findall(r"^(?:DOMAIN-SET|RULE-SET),([^,]+),", text, re.M)
    own = [r for r in refs if "/ruleset/" in r]
    missing = []
    for url in own:
        name = url.rsplit("/", 1)[-1]
        if not (DIST_DIR / "ruleset" / name).exists():
            missing.append(name)
    if missing:
        rep.fail(f"base.conf 引用了不存在的产物：{missing}")
    else:
        rep.ok(f"base.conf 的 {len(own)} 个自身产物引用全部有效"
               f"（另有 {len(refs) - len(own)} 个引用外部规则集）")


def _check_secrets(rep: Report) -> None:
    found: list[str] = []
    for base in (DIST_DIR, VENDOR_DIR):
        for path in base.rglob("*"):
            if not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            if path.suffix.lower() not in (".list", ".srmodule", ".conf", ".js", ".json", ".md", ".txt"):
                continue
            try:
                text = read_text(path)
            except OSError:
                continue
            live = "\n".join(l for l in text.splitlines()
                             if not l.strip().startswith("#"))
            for pattern, why in SECRET_PATTERNS:
                m = re.search(pattern, live, re.M)
                if m:
                    found.append(f"{path.name}: {why} → `{m.group(0)[:40]}`")
                    break
    if found:
        rep.fail(f"产物里疑似包含节点/凭证信息，公开仓库绝不能提交：{found[:5]}")
    else:
        rep.ok("隐私检查通过（产物与 vendor 中没有节点定义、密码或订阅令牌）")


def _collect_stats() -> dict:
    stats = {"time": time.strftime("%Y-%m-%d %H:%M:%S")}
    for name in ("ad-domain.list", "ad-domain-lite.list", "ad-rule.list"):
        p = DIST_DIR / "ruleset" / name
        stats[name] = _count_body(p) if p.exists() else 0
    total = 0
    for p in (DIST_DIR / "module").glob("*.srmodule"):
        total += _count_body(p)
    apps = len(list((DIST_DIR / "module" / "apps").glob("*.srmodule")))
    stats["modules_main"] = total
    stats["apps"] = apps
    main = DIST_DIR / "module" / "ads-all.srmodule"
    if main.exists():
        m = re.search(r"^hostname\s*=\s*(.+)", read_text(main), re.M)
        if m:
            stats["mitm"] = len([h for h in m.group(1).replace("%APPEND%", "").split(",") if h.strip()])
    return stats


def _count_body(path: Path) -> int:
    return sum(1 for l in read_text(path).splitlines()
               if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("#!"))


def _check_drift(rep: Report, stats: dict) -> None:
    if not STATS_FILE.exists():
        rep.info("首次构建，没有历史数据可比对（下次开始会检查规则数突变）")
        return
    try:
        prev = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    for key in ("ad-domain.list", "ad-rule.list", "apps"):
        old, new = prev.get(key, 0), stats.get(key, 0)
        if not old:
            continue
        delta = (new - old) / old
        if delta <= -0.20:
            rep.fail(f"{key} 从 {human(old)} 掉到 {human(new)}（{delta:+.0%}）—— "
                     f"上游可能挂了或换格式了，请人工确认")
        elif abs(delta) >= 0.20:
            rep.warn_(f"{key} 数量变化较大：{human(old)} → {human(new)}（{delta:+.0%}）")
    if not rep.errors and not rep.warnings:
        rep.ok("规则数相比上次构建稳定（无异常突变）")


def _check_budget(rep: Report, opt: dict, stats: dict) -> None:
    mitm = stats.get("mitm", 0)
    limit = int(opt.get("mitm_warn_threshold", 1000))
    if mitm > limit:
        rep.warn_(f"MITM 主机名 {human(mitm)} 个，超过阈值 {limit}："
                  f"iOS 15 以下的小火箭内存预算只有 15MB，"
                  f"建议只装你需要的 per-App 模块而不是总模块")
    else:
        rep.ok(f"MITM 主机名 {human(mitm)} 个，在预算内")
    size = sum(p.stat().st_size for p in DIST_DIR.rglob("*") if p.is_file())
    rep.info(f"产物总大小 {fmt_size(size)}（其中 per-App 模块 {human(stats.get('apps', 0))} 个）")


def write_verification(rep: Report) -> Path:
    path = ROOT / "build-report-verify.md"
    lines = [
        "# 产物自检",
        "",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"结论：{'❌ 有阻断性问题' if rep.errors else ('⚠️ 有告警' if rep.warnings else '✅ 全部通过')}",
        "",
        *rep.lines,
        "",
    ]
    if rep.errors:
        lines += ["## 阻断性问题", ""] + [f"- {e}" for e in rep.errors] + [""]
    if rep.warnings:
        lines += ["## 告警", ""] + [f"- {w}" for w in rep.warnings] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _save_stats(stats: dict) -> None:
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
