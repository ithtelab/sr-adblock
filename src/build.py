"""构建入口。

  python src/build.py                  # 构建全部已实现的层
  python src/build.py --layer domain   # 只构建域名层
  python src/build.py --offline        # 只用本地缓存（不联网）
  python src/build.py --refresh        # 强制重新下载上游
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge as merge_mod
import parse
from emit_ruleset import emit_domain_set, emit_rule_set
from util import (CACHE_DIR, CONFIG_DIR, DIST_DIR, ROOT, WARNINGS, fmt_size,
                  human, load_yaml, log, read_text, section, warn)


def load_config() -> tuple[dict, dict, merge_mod.AllowList]:
    sources = load_yaml(CONFIG_DIR / "sources.yaml")
    options = load_yaml(CONFIG_DIR / "options.yaml")
    allow = merge_mod.load_allowlist(CONFIG_DIR / "allowlist.txt")
    return sources, options, allow


def build_domain_layer(sources: dict, options: dict, allow, *,
                       offline: bool, refresh: bool) -> dict:
    from util import fetch_text

    opt = options.get("domain_layer", {})
    prefix = options.get("output", {}).get("prefix", "ad")
    layers: dict[str, parse.Layer] = {}
    fetch_rows: list[tuple[str, str, str, str]] = []

    section("① 域名层：拉取上游")
    for src in sources.get("domain_sources", []):
        sid = src["id"]
        text, res = fetch_text(sid, src["url"], f"{sid}.txt",
                               offline=offline, refresh=refresh)
        state = "缓存" if res.from_cache else "下载"
        note = res.error or ""
        fetch_rows.append((sid, human(res.size), state, note))
        log(f"  {sid:<14} {human(res.size):>12} B  {state}  {note}")
        if not res.ok:
            warn(f"来源 {sid} 拉取失败且无缓存，本次跳过：{res.error}", "error")
            continue

        fmt = src.get("format", "ruleset")
        kwargs = {"only": src.get("only")} if src.get("only") else {}
        parser = {
            "domain_set": parse.parse_domain_set,
            "ruleset": parse.parse_ruleset,
            "surge_conf_rules": parse.parse_surge_conf_rules,
        }.get(fmt)
        if parser is None:
            warn(f"来源 {sid} 的 format={fmt} 未知，跳过", "error")
            continue
        layer = parser(text, sid, **kwargs) if kwargs else parser(text, sid)
        layers[sid] = layer
        log(f"       ├ 精确域名 {human(len(layer.exact)):>8}"
            f"  含子域 {human(len(layer.suffix)):>8}"
            f"  其他规则 {human(len(layer.rules)):>6}")

    # 自建黑名单作为一个来源参与合并（默认 trust=True：你亲手加的域名
    # 应该同时出现在全量版和精简版里，否则精简版会把它漏掉）
    extra_path = CONFIG_DIR / "blocklist-extra.txt"
    if extra_path.exists():
        extra_layer = parse.parse_domain_set(read_text(extra_path), "mine")
        if extra_layer.exact or extra_layer.suffix:
            layers["mine"] = extra_layer
            log(f"  mine          自建黑名单：精确 {human(len(extra_layer.exact))}"
                f"  含子域 {human(len(extra_layer.suffix))}")

    section("② 合并 / 放行 / 压缩")
    merged = merge_mod.merge_layers(layers)
    before = merged.total_domains()
    log(f"  并集后                 {human(before):>9} 条")

    merge_mod.apply_allowlist(merged, allow)
    if merged.dropped_by_allow:
        log(f"  放行名单剔除           {len(merged.dropped_by_allow):>9} 条")
        for domain, table in merged.dropped_by_allow[:10]:
            log(f"       - {domain} ({table})")
    else:
        log("  放行名单剔除                    0 条")

    if opt.get("compress", True):
        merge_mod.compress(merged)
        log(f"  父域压缩去冗余         {human(merged.compressed):>9} 条")

    if opt.get("promote_exact_to_suffix", False):
        promoted = len(merged.exact)
        for d, owners in merged.exact.items():
            merged.suffix.setdefault(d, set()).update(owners)
        merged.exact.clear()
        log(f"  精确→子域提升          {human(promoted):>9} 条")

    merge_mod.audit(merged)

    section("③ 输出产物")
    out_dir = DIST_DIR / "ruleset"
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {s["id"]: s["name"] for s in sources.get("domain_sources", [])}
    names.setdefault("mine", "本仓库自建黑名单（config/blocklist-extra.txt）")
    licences = {s["id"]: s.get("license", "未声明") for s in sources.get("domain_sources", [])}
    licences.setdefault("mine", "本项目自有")
    for sid, lic in licences.items():
        merged.source_stats.setdefault(sid, {})["license"] = lic

    repo_url = options.get("repo_url", "").rstrip("/")
    written = [
        (f"{prefix}-domain.list", emit_domain_set(
            out_dir / f"{prefix}-domain.list", merged.exact, merged.suffix,
            title="广告域名合并表（全量）", merged=merged,
            trusted_names=names, repo_url=repo_url,
            rel_path=f"ruleset/{prefix}-domain.list")),
    ]
    rule_lines = sorted(merged.rules.values(), key=lambda r: r.render(with_policy=False))
    written.append((f"{prefix}-rule.list", emit_rule_set(
        out_dir / f"{prefix}-rule.list", rule_lines,
        title="广告规则集（IP / 关键词 / 正则）", merged=merged,
        trusted_names=names, repo_url=repo_url,
        rel_path=f"ruleset/{prefix}-rule.list")))

    lite_stats = None
    if options.get("output", {}).get("lite", True):
        min_src = int(options.get("output", {}).get("lite_min_sources", 2))
        trusted_ids = {s["id"] for s in sources.get("domain_sources", [])
                       if s.get("trust", True)}
        lx, ls = merged.high_confidence(trusted_ids, min_src, always={"mine"})
        # lite 也做一次压缩（高置信子集里同样存在父子关系）
        lite_merged = merge_mod.Merged(exact=dict(lx), suffix=dict(ls),
                                       source_stats=merged.source_stats)
        merge_mod.compress(lite_merged)
        written.append((f"{prefix}-domain-lite.list", emit_domain_set(
            out_dir / f"{prefix}-domain-lite.list", lite_merged.exact,
            lite_merged.suffix, title="广告域名合并表（精简版·高置信）",
            merged=lite_merged, trusted_names=names, repo_url=repo_url,
            rel_path=f"ruleset/{prefix}-domain-lite.list")))
        lite_stats = (len(lite_merged.exact) + len(lite_merged.suffix), min_src)
        log(f"  精简版：两个以上独立来源都收录的域名 "
            f"{human(lite_stats[0])} 条（门槛 {min_src} 个来源）")

    for name, count in written:
        p = out_dir / name
        log(f"  {name:<28} {human(count):>9} 条  {fmt_size(p.stat().st_size):>9}")

    return {"merged": merged, "written": written, "fetch_rows": fetch_rows,
            "layers": layers, "lite": lite_stats, "prefix": prefix,
            "out_dir": out_dir, "names": names}


def build_module_layer(sources: dict, options: dict, allow, *, offline: bool,
                       refresh: bool) -> dict:
    """模块层：合并去广告模块、本地化脚本、产出小火箭原生模块。"""
    import module as module_mod
    import vendor as vendor_mod
    from emit_module import emit_srmodule
    from util import fetch_text

    opt = options.get("module_layer", {})
    merge_opt = options.get("merge", {})
    out_dir = DIST_DIR / "module"
    out_dir.mkdir(parents=True, exist_ok=True)

    section("① 模块层：拉取上游")
    mods: dict[str, module_mod.Module] = {}
    fetch_rows: list[tuple[str, str, str, str]] = []
    for src in sources.get("module_sources", []):
        sid = src["id"]
        text, res = fetch_text(sid, src["url"], f"{sid}.module",
                               offline=offline, refresh=refresh)
        fetch_rows.append((sid, src.get("name", sid), human(res.size),
                           res.error or ("缓存" if res.from_cache else "下载")))
        log(f"  {sid:<24} {human(res.size):>9} B  "
            f"{'缓存' if res.from_cache else '下载'}  {res.error}")
        if not res.ok:
            warn(f"模块源 {sid} 拉取失败，本次跳过：{res.error}", "error")
            continue
        mods[sid] = module_mod.parse_module(text, sid)

    core_id = next((s["id"] for s in sources.get("module_sources", [])
                    if s.get("role") == "core"), None)
    if core_id not in mods:
        warn("核心模块拉取失败，模块层本次跳过", "error")
        return {"skipped": True, "fetch_rows": fetch_rows}

    primary = mods[core_id]
    others, supplement, companions, args_ref = [], [], {}, None
    for src in sources.get("module_sources", []):
        sid, role = src["id"], src.get("role")
        if sid == core_id or sid not in mods:
            continue
        if role == "reference":
            supplement.append(mods[sid])
        elif role == "companion":
            companions[sid] = mods[sid]
        elif role == "args_ref":
            args_ref = mods[sid]          # 只读它的 [Argument]，内容一律不合并
        else:
            others.append(mods[sid])

    section("② 合并模块")
    sections, rep = module_mod.merge_modules(primary, others, supplement=supplement)

    # 脏数据体检：逐条按段落语法校验，丢掉上游的残句/错格式
    junk: dict[str, list[str]] = {}
    sections = module_mod.apply_sanity_filter(sections, junk)
    if junk:
        total_junk = sum(len(v) for v in junk.values())
        warn(f"从上游剔除 {total_junk} 条格式不合法的条目（详见报告）", "warn")
        for sec, items in junk.items():
            for it in items[:3]:
                log(f"  ├ 剔除脏数据 [{sec}] {it[:110]}")

    # 用同一份放行名单过滤模块规则（模块优先级高于配置，必须一起过滤）
    allow_dropped: list[str] = []
    if "[Rule]" in sections:
        sections["[Rule]"], allow_dropped = module_mod.filter_rules_by_allowlist(
            sections["[Rule]"], allow)
        if allow_dropped:
            log(f"  ├ 按放行名单剔除模块内拦截规则 {len(allow_dropped)} 条："
                f"{', '.join(sorted(set(allow_dropped))[:6])}")
    log(f"  核心模块 {core_id}：{human(primary.count())} 条")
    for name, n in rep.added.items():
        log(f"       {name:<18} {human(n):>6} 条")
    if rep.total_dupes_primary():
        log(f"  ├ 去重删除上游重复条目 {human(rep.total_dupes_primary())} 条"
            f"（上游合并脚本的 bug 产物）")
    if rep.total_supplemented():
        log(f"  ├ 用 Surge 版补齐 SR 版缺失 {human(rep.total_supplemented())} 条"
            f"（其余 {human(rep.total_dupes_supplement())} 条为书写差异，语义重复，未重复导入）")

    # 脚本本地化
    script_urls = vendor_mod.collect_script_urls(sections,
                                                module_mod.extract_script_path)
    script_stats = {}
    rewritten = 0
    infos: dict = {}
    if opt.get("vendor_scripts", True) and script_urls:
        section("③ 脚本本地化（防止上游删文件导致规则静默失效）")
        log(f"  共 {len(script_urls)} 个脚本，被 {sum(len(v) for v in script_urls.values())} 条规则引用")
        infos = vendor_mod.download_scripts(list(script_urls), offline=offline,
                                            refresh=refresh)
        for url, names in script_urls.items():
            infos[url].used_by = names
        script_stats = vendor_mod.audit_vendored(infos)
        log(f"  已本地化 {human(script_stats.get('safe', 0) + script_stats.get('dubious', 0) + script_stats.get('broken', 0))}"
            f" / {len(script_urls)} 个，合计 {fmt_size(script_stats.get('bytes', 0))}")
        if script_stats.get("failed"):
            warn(f"{script_stats['failed']} 个脚本下载失败（规则会失效，见报告）", "error")
        if script_stats.get("broken"):
            warn(f"{script_stats['broken']} 个脚本无条件调用了小火箭没有的 API，"
                 f"这些规则在小火箭里不会生效", "warn")
        if script_stats.get("dubious"):
            warn(f"{script_stats['dubious']} 个脚本用了别家专有写法，"
                 f"是否需要处理请见 build-report-scripts.md", "info")

        repo_url = options.get("repo_url", "").rstrip("/")
        new_blocks = []
        for b in sections.get("[Script]", []):
            url = module_mod.extract_script_path(b)
            if url and url in infos and infos[url].ok:
                b = module_mod.rewrite_script_path(
                    b, f"{repo_url}/vendor/{infos[url].local_rel}")
                rewritten += 1
            new_blocks.append(b)
        sections["[Script]"] = new_blocks
        log(f"  ├ 已把 {human(rewritten)} 条规则的 script-path 改指本仓库")

    section("④ 输出模块")
    mitm_count = len(module_mod.parse_mitm(
        module_mod.Module(sections={"[MITM]": sections.get("[MITM]", [])})))
    if mitm_count > int(opt.get("mitm_warn_threshold", 1000)):
        warn(f"MITM 主机名 {human(mitm_count)} 个，超过阈值 "
             f"{opt.get('mitm_warn_threshold')}；iOS 15 以下小火箭内存预算只有 15MB，"
             f"建议只装需要的 per-App 模块", "warn")

    src_names = {s["id"]: s.get("name", s["id"]) for s in sources.get("module_sources", [])}
    merged_lines = sum(len(v) for v in sections.values())
    provenance = [f"{src_names.get(primary.source, primary.source)}（主来源）"]
    provenance += [f"{src_names.get(m.source, m.source)}（并入）" for m in others]
    provenance += [f"{src_names.get(m.source, m.source)}（仅用于补齐缺失规则）"
                   for m in supplement]
    counts = [(k, human(len(v))) for k, v in sections.items()]
    counts.append(("合计", human(merged_lines)))

    # 参数声明：只声明真正被引用的占位符（丢弃上游那个无人引用的空开关）
    arguments, unresolved_args, used_args = ("", [], [])
    if args_ref is not None:
        arguments, unresolved_args, used_args = module_mod.resolve_arguments(
            sections, args_ref)
        if arguments:
            log(f"  ├ 补全参数声明 {len(used_args)} 个（上游只声明了 1 个无人引用的空开关）")
        if unresolved_args:
            warn(f"以下参数占位符在模块里被引用但上游任何版本都没有声明，"
                 f"脚本可能拿不到值：{', '.join(unresolved_args)}", "warn")
    uses_args = bool(used_args)
    meta = {k: v for k, v in primary.meta.items()
            if k in ("icon", "category", "tg-channel")}
    path = out_dir / "ads-all.srmodule"
    total = emit_srmodule(
        path, sections,
        name="去广告合集（自维护·小火箭）",
        desc=(f"合并 {len(provenance)} 个上游：{counts[0][1] if counts else ''}"
              f"条规则，覆盖约 700 款 App；脚本已本地化，不依赖上游存活"),
        author="sr-adblock-factory（原始规则见 NOTICE）",
        homepage=options.get("repo_url", "").split("/re", 1)[0],
        icon=meta.get("icon", ""),
        arguments=arguments,
        provenance=provenance,
        counts=counts,
        usage=[
            "小火箭 → 配置 → 模块 → 右上角 + → 粘贴本文件的 raw 链接",
            "首次使用前必须先开启 HTTPS 解密并安装信任证书，否则重写类规则不生效",
            "模块里的规则优先级高于配置文件，装了就一定生效（这是去广告能拦住的关键）",
        ],
    )
    if not uses_args and primary.meta.get("arguments"):
        log("  ├ 丢弃上游的 #!arguments（它声明的是无人引用的空开关）")
    log(f"  ads-all.srmodule       {human(total):>7} 条  {fmt_size(path.stat().st_size)}")

    # HTTPDNS 配套模块：剔除与主模块重复的条目，避免两份规则打架/冗余
    httpdns_path = None
    httpdns_total = 0
    httpdns_dropped = 0
    for sid, mod in companions.items():
        if "httpdns" not in sid.lower():
            continue
        prim_keys = {sec: {module_mod.semantic_key(b.text, sec) for b in blocks}
                     for sec, blocks in sections.items()}
        filt: dict[str, list] = {}
        for sec, blocks in mod.sections.items():
            if sec == "[MITM]":
                continue
            keep = [b for b in blocks
                    if module_mod.semantic_key(b.text, sec) not in prim_keys.get(sec, set())]
            httpdns_dropped += len(blocks) - len(keep)
            if keep:
                filt[sec] = keep
        # MITM 也要去掉主模块已有的主机名
        main_hosts = set(module_mod.parse_mitm(
            module_mod.Module(sections={"[MITM]": sections.get("[MITM]", [])})))
        extra_hosts = [h for h in module_mod.parse_mitm(mod) if h not in main_hosts]
        if extra_hosts:
            filt["[MITM]"] = [module_mod.Block(
                "hostname = %APPEND% " + ", ".join(extra_hosts), [], sid)]
        httpdns_dropped += len(module_mod.parse_mitm(mod)) - len(extra_hosts)

        httpdns_path = out_dir / "httpdns.srmodule"
        httpdns_total = emit_srmodule(
            httpdns_path, filt,
            name="HTTPDNS 拦截（配套）",
            desc=("阻止 App 绕过代理自己解析域名 —— 不拦它的话，很多 App 的广告会"
                  "绕开你的规则直连，去广告形同虚设。已剔除与主模块重复的条目"),
            author="可莉🅥 / VirgilClyne（上游 luestr/ProxyResource），本项目仅去重整合",
            homepage=options.get("repo_url", "").split("/re", 1)[0],
            provenance=["可莉/奶思 • HTTPDNS 拦截器（上游实为 luestr/ProxyResource）",
                        "已剔除与 ads-all.srmodule 重复的条目"],
            counts=[(k, human(len(v))) for k, v in filt.items()],
            usage=["建议与 ads-all.srmodule 一起装",
                   "本模块已自动剔除与主模块重复的规则，两份同时装不会重复拦截"],
        )
        log(f"  httpdns.srmodule       {human(httpdns_total):>7} 条  "
            f"{fmt_size(httpdns_path.stat().st_size)}"
            f"（剔除与主模块重复 {human(httpdns_dropped)} 条）")

    app_stats = {"skipped": True}
    if options.get("module_layer", {}).get("per_app_modules", True):
        section("⑤ per-App 可选模块")
        import apps as apps_mod
        vendor_map = {u: i.local_rel for u, i in infos.items() if i.ok}
        app_stats = apps_mod.build_app_modules(
            sources.get("app_module_source", {}), offline=offline, refresh=refresh,
            vendor_map=vendor_map, repo_url=options.get("repo_url", "").rstrip("/"))
        if not app_stats.get("skipped"):
            log(f"  生成 {human(app_stats['apps'])} 个 per-App 模块"
                f"（归并自上游 {human(app_stats['variants'])} 个 split 文件，"
                f"其中 {app_stats['downloaded']} 个新下载 / {app_stats['reused']} 个用缓存）")
            if app_stats.get("scripts"):
                log(f"  ├ 额外本地化 {human(app_stats['scripts'])} 个 per-App 专用脚本"
                    f"（{fmt_size(app_stats['script_bytes'])}）")
            if app_stats.get("broken"):
                warn(f"{app_stats['broken']} 个 per-App 脚本与小火箭不兼容", "warn")

    return {"skipped": False, "fetch_rows": fetch_rows, "sections": sections,
            "app_stats": app_stats, "allow_dropped": allow_dropped,
            "rep": rep, "mitm": mitm_count, "path": path, "total": total,
            "httpdns_path": httpdns_path, "httpdns_total": httpdns_total,
            "httpdns_dropped": httpdns_dropped, "scripts": script_stats,
            "script_urls": script_urls, "rewritten": rewritten,
            "infos": infos, "src_names": src_names, "junk": junk,
            "arguments": arguments, "used_args": used_args,
            "unresolved_args": unresolved_args}


def build_conf_layer(sources: dict, options: dict, allow, result: dict) -> dict:
    """配置层：生成 base.conf（代理分组 + 引用域名层/模块层）。"""
    from emit_conf import emit_base_conf, emit_private_example

    section("配置层：生成 base.conf")
    out_dir = DIST_DIR / "conf"
    out_dir.mkdir(parents=True, exist_ok=True)
    dom = result.get("domain") or {}
    dom_mod = result.get("module") or {}
    prefix = options.get("output", {}).get("prefix", "ad")
    repo_url = options.get("repo_url", "").rstrip("/")

    stats = {"domains": dom.get("merged").total_domains() if dom.get("merged") else 0,
             "lite": dom.get("lite")[0] if dom.get("lite") else 0}
    lines = emit_base_conf(out_dir / "base.conf", repo_url=repo_url, allow=allow,
                           prefix=prefix, mitm_hosts=["*.google.cn"], stats=stats)
    emit_private_example(out_dir / "private.example.conf")
    log(f"  base.conf              {human(lines)} 行"
        f"  （放行 {len(allow.full) + len(allow.sub_only)} 条，"
        f"引用域名层 {human(stats['domains'])} 条 + 模块层）")
    log("  private.example.conf   私人覆盖示例")
    return {"path": out_dir / "base.conf", "lines": lines, "stats": stats}


def build_module_report(add, result: dict) -> None:
    """模块层的报告段落。"""
    mod = result.get("module") or {}
    if not mod or mod.get("skipped"):
        return
    add("## ② 模块层")
    add("")
    add(f"- 产物：`dist/module/ads-all.srmodule`（{human(mod['total'])} 条）、"
        f"`dist/module/httpdns.srmodule`（{human(mod['httpdns_total'])} 条）")
    add(f"- MITM 主机名：**{human(mod['mitm'])}** 个")
    rep = mod["rep"]
    add(f"- 去重删除上游重复条目：{human(rep.total_dupes_primary())} 条"
        f"（上游合并脚本的 bug 产物）")
    add(f"- 用 Surge 版补齐 SR 版缺失：{human(rep.total_supplemented())} 条"
        f"（另有 {human(rep.total_dupes_supplement())} 条仅书写格式不同、语义重复，未重复导入）")
    add(f"- 脚本本地化：{human(mod['rewritten'])} 条规则的 script-path 已改指本仓库")
    add(f"- HTTPDNS 模块剔除与主模块重复：{human(mod['httpdns_dropped'])} 条")
    add("")
    add("### 各段条目数")
    add("")
    add("| 段落 | 条数 |")
    add("| --- | --- |")
    for name, blocks in mod["sections"].items():
        add(f"| `{name}` | {human(len(blocks))} |")
    add("")

    app = mod.get("app_stats") or {}
    if not app.get("skipped"):
        add("### per-App 可选模块")
        add("")
        add(f"- 产出 **{human(app['apps'])}** 个（归并自上游 {human(app['variants'])} 个 split 文件，"
            f"同名变体已合并去重）")
        add(f"- 额外本地化 per-App 专用脚本：{human(app.get('scripts', 0))} 个"
            f"（{fmt_size(app.get('script_bytes', 0))}）")
        add("")
        add("索引见 `dist/module/apps/README.md`。")
        add("")

    scripts = mod.get("scripts") or {}
    if scripts:
        add("### 脚本体检")
        add("")
        add(f"共 {len(mod['script_urls'])} 个第三方脚本："
            f"✅ 安全 {scripts.get('safe', 0)} 个、"
            f"⚠️ 存疑 {scripts.get('dubious', 0)} 个、"
            f"❌ 不兼容 {scripts.get('broken', 0)} 个、"
            f"下载失败 {scripts.get('failed', 0)} 个，"
            f"合计 {fmt_size(scripts.get('bytes', 0))}")
        add("")
        add("「不兼容」表示脚本**无条件**调用了小火箭没有的 API（如 `$httpAPI`），"
            "对应的去广告规则在小火箭里不会生效；"
            "「存疑」多是有客户端判断保护、但写法上值得看一眼的。"
            "**这是静态检查，不能替代真机验证。**")
        add("")
        add("完整清单见 `build-report-scripts.md`。")
        add("")


def write_report(result: dict, options: dict, elapsed: float) -> Path:
    dom = result.get("domain") or {}
    if not dom:
        return ROOT / "build-report.md"
    m: merge_mod.Merged = dom["merged"]
    names = dom["names"]
    lines: list[str] = []
    add = lines.append

    add("# 构建报告")
    add("")
    add(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"- 耗时：{elapsed:.1f} 秒")
    add("")
    add("## ① 域名层")
    add("")
    add(f"- 合计：**{human(m.total_domains())}** 条"
        f"（精确 {human(len(m.exact))} + 含子域 {human(len(m.suffix))}）")
    add(f"- 其他规则：{human(len(m.rules))} 条")
    add("")

    add("## 上游拉取")
    add("")
    add("| 来源 | 大小 | 状态 | 备注 |")
    add("| --- | --- | --- | --- |")
    for sid, size, state, note in dom["fetch_rows"]:
        add(f"| {sid} | {size} B | {state} | {note} |")
    add("")

    add("## 各来源贡献")
    add("")
    add("| 来源 | 精确域名 | 含子域 | 其他规则 | 备注 |")
    add("| --- | --- | --- | --- | --- |")
    for sid, st in m.source_stats.items():
        note = ""
        extra = {k: v for k, v in st.items()
                 if k not in ("domains_exact", "domains_suffix", "rules", "license")}
        filtered = {k: v for k, v in extra.items() if k.startswith("filtered_")}
        if filtered:
            note = "过滤：" + ", ".join(f"{k[9:]}:{v}" for k, v in filtered.items())
        if st.get("composite_skipped"):
            note += ("；" if note else "") + f"跳过复合规则 {st['composite_skipped']} 条"
        if st.get("invalid"):
            note += ("；" if note else "") + f"无效条目 {st['invalid']} 条"
        add(f"| {names.get(sid, sid)} | {human(st.get('domains_exact', 0))} "
            f"| {human(st.get('domains_suffix', 0))} | "
            f"{human(st.get('rules', 0))} | {note} |")
    add("")

    add("## 去重与压缩")
    add("")
    add(f"- 父域压缩删除冗余条目：{human(m.compressed)} 条")
    add(f"- 放行名单剔除：{len(m.dropped_by_allow)} 条")
    if m.dropped_by_allow:
        for domain, table in m.dropped_by_allow:
            add(f"  - `{domain}`（{table}）")
    add(f"- 精简版（≥2 个来源）：{human(dom['lite'][0]) if dom['lite'] else '未产出'} 条")
    add("")

    if m.option_merges:
        add("## 规则选项合并（非冲突）")
        add("")
        add("同一规则被多个来源定义，仅选项不同，已取并集（`no-resolve` 对 IP 类规则是更安全的选择）：")
        add("")
        for c in m.option_merges[:20]:
            add(f"- {c}")
        if len(m.option_merges) > 20:
            add(f"- ...（还有 {len(m.option_merges) - 20} 条）")
        add("")

    if m.conflicts:
        add("## 规则策略冲突")
        add("")
        add("同一规则被多个来源定义成不同策略，已按 REJECT 优先处理：")
        add("")
        for c in m.conflicts[:50]:
            add(f"- {c}")
        if len(m.conflicts) > 50:
            add(f"- ...（还有 {len(m.conflicts) - 50} 条）")
        add("")

    build_module_report(add, result)

    add("## 产物")
    add("")
    add("| 文件 | 条数 |")
    add("| --- | --- |")
    for name, count in dom["written"]:
        add(f"| dist/ruleset/{name} | {human(count)} |")
    if result.get("module") and not result["module"].get("skipped"):
        add(f"| dist/module/ads-all.srmodule | {human(result['module']['total'])} |")
        add(f"| dist/module/httpdns.srmodule | {human(result['module']['httpdns_total'])} |")
    add("")

    if WARNINGS:
        add("## 告警")
        add("")
        for w in WARNINGS:
            add(f"- {w}")
        add("")

    mod_info = result.get("module") or {}
    if mod_info.get("infos"):
        import vendor as vendor_mod
        rows = [
            "# 第三方脚本体检报告", "",
            f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "",
            f"共 {len(mod_info['infos'])} 个脚本，全部已抓取到本仓库 `vendor/` 目录，",
            "所有 script-path 已改为指向本仓库 —— 上游删库或改路径都不会让规则失效。", "",
            "结论含义：", "",
            "- ✅ **安全**：只做响应体改写，或用的都是小火箭支持的 API",
            "- ⚠️ **有风险**：依赖别家专有写法（如 Loon 的 `$argument` 对象取值），小火箭里可能取不到值",
            "- ❌ **不兼容**：用了小火箭**没有**的 API（`$httpAPI`/`$task` 等），"
            "对应的去广告规则在小火箭里**不会生效**", "",
            *vendor_mod.report_lines(mod_info["infos"]), "",
        ]
        (ROOT / "build-report-scripts.md").write_text("\n".join(rows) + "\n",
                                                     encoding="utf-8")

    path = ROOT / "build-report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="sr-adblock-factory 构建")
    ap.add_argument("--layer", default="all",
                    choices=["all", "domain", "module", "conf"])
    ap.add_argument("--offline", action="store_true", help="只用本地缓存")
    ap.add_argument("--refresh", action="store_true", help="强制重新下载上游")
    args = ap.parse_args()

    started = time.time()
    sources, options, allow = load_config()
    result: dict = {}

    section(f"sr-adblock-factory 构建开始（{args.layer}）")
    if args.layer in ("all", "domain", "module", "conf"):
        result["domain"] = build_domain_layer(sources, options, allow,
                                              offline=args.offline,
                                              refresh=args.refresh)
    if args.layer in ("all", "module"):
        result["module"] = build_module_layer(sources, options, allow,
                                              offline=args.offline,
                                              refresh=args.refresh)
    if args.layer in ("all", "conf"):
        result["conf"] = build_conf_layer(sources, options, allow, result)

    report = write_report(result, options, time.time() - started)

    section("产物自检")
    from verify import verify, write_verification
    ok, vrep = verify(options)
    vpath = write_verification(vrep)
    for line in vrep.lines:
        log("  " + line)
    log(f"  自检报告：{vpath}")

    section("完成")
    log(f"  报告：{report}")
    if WARNINGS:
        log(f"  告警 {len(WARNINGS)} 条（见报告）")
    if not ok:
        log("  ❌ 自检发现阻断性问题，构建标记为失败（产物仍已写出，请人工检查）")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
