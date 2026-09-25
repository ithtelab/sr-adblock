"""per-App 可选模块：从上游 split 目录生成每 App 一个的独立模块。

上游结构：Surge/module/split/part<字母>/<AppName>.sgmodule（731 个文件）。

顺手修掉的上游缺陷：有 5 个 App 同时存在于两个桶里（xianyu/xiaohongshu/zhihu/
neteasecloudmusic/yunkuaichong 各出现两次，内容近似但不完全相同），上游合并脚本
把它们都并了进去，这正是主模块里出现重复规则的直接原因。这里按 App 名归并，
同一 App 的多个变体合并去重后只产出一个模块。
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

import module as module_mod
from util import (CACHE_DIR, DIST_DIR, USER_AGENT, download, human, log,
                  read_text, stable_id, warn)

TREE_CACHE = CACHE_DIR / "app_tree.json"
BLOB_MANIFEST = CACHE_DIR / "app_blobs.json"


def fetch_tree(api_url: str, *, offline: bool = False, refresh: bool = False) -> list[dict]:
    """取仓库文件树（1 次 API 请求，含每个文件的 blob sha，用于判断是否需要重下）。"""
    if TREE_CACHE.exists() and not refresh:
        try:
            cached = json.loads(TREE_CACHE.read_text(encoding="utf-8"))
            if cached.get("url") == api_url:
                return cached.get("tree", [])
        except json.JSONDecodeError:
            pass
    if offline:
        return []
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    # 匿名调用 GitHub API 限额只有 60 次/小时，而且 Actions 是共享出口 IP，
    # 很容易被别的任务用光。有 token 就用 token（限额 5000 次/小时）。
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tree = data.get("tree", [])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TREE_CACHE.write_text(json.dumps({"url": api_url, "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                      "tree": tree}, ensure_ascii=False), encoding="utf-8")
    return tree


def _load_blobs() -> dict[str, str]:
    if BLOB_MANIFEST.exists():
        try:
            return json.loads(BLOB_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_blobs(data: dict[str, str]) -> None:
    BLOB_MANIFEST.write_text(json.dumps(data, indent=1), encoding="utf-8")


def app_key(path: str) -> str:
    """从 split 路径取出 App 名（用于归并同名变体）。"""
    return Path(path).stem.lower()


def raw_url(repo_raw_base: str, path: str) -> str:
    return f"{repo_raw_base.rstrip('/')}/{path}"


def build_app_modules(src_cfg: dict, *, offline: bool, refresh: bool,
                      vendor_map: dict[str, str], repo_url: str,
                      limit: int | None = None) -> dict:
    """生成 per-App 模块。vendor_map 是核心模块已本地化的脚本映射（url -> 相对路径）。"""
    from module import extract_script_path, parse_module, rewrite_script_path
    from util import VENDOR_DIR, write_text
    from vendor import analyze, vendor_rel_path

    api_url = src_cfg.get("list_api", "")
    prefix = src_cfg.get("path_prefix", "")
    suffix = src_cfg.get("path_suffix", ".sgmodule")
    raw_base = src_cfg.get("raw_base", "")
    if not (api_url and prefix and raw_base):
        return {"skipped": True}

    # refresh=True：文件树是唯一的"该不该更新"依据，必须每次重新取
    # （1 次 API 请求，成本可以忽略；用缓存里的旧树会永远发现不了上游改动）
    tree = fetch_tree(api_url, offline=offline, refresh=refresh or not offline)
    paths = [t["path"] for t in tree
             if t["path"].startswith(prefix) and t["path"].endswith(suffix)]
    if not paths:
        warn("拿不到上游 split 文件树，per-App 模块本次跳过", "warn")
        return {"skipped": True}
    if limit:
        paths = paths[:limit]

    blobs = _load_blobs()
    sha_by_path = {t["path"]: t.get("sha", "") for t in tree}

    # 按 App 名归并变体
    groups: dict[str, list[str]] = {}
    for p in paths:
        groups.setdefault(app_key(p), []).append(p)

    out_dir = DIST_DIR / "module" / "apps"
    out_dir.mkdir(parents=True, exist_ok=True)
    index: list[tuple[str, str, str]] = []
    stats = {"apps": 0, "variants": 0, "downloaded": 0, "reused": 0, "scripts": 0,
             "script_bytes": 0, "broken": 0}
    new_scripts: dict[str, str] = dict(vendor_map)

    for app, variants in sorted(groups.items()):
        stats["variants"] += len(variants)
        mods = []
        for path in sorted(variants):
            fname = f"app__{app}__{Path(path).parent.name}.sgmodule"
            dest = CACHE_DIR / "raw" / fname
            need = not dest.exists() or blobs.get(path) != sha_by_path.get(path, "")
            if need and not offline:
                # blob sha 变了就必须强制重下：普通缓存路径会因为清单命中而跳过
                res = download(f"app__{app}__{Path(path).parent.name}",
                               raw_url(raw_base, path), fname, refresh=True)
                if res.ok:
                    blobs[path] = sha_by_path.get(path, "")
                    stats["downloaded"] += 1
                else:
                    continue
            elif dest.exists():
                stats["reused"] += 1
            if not dest.exists():
                continue
            mods.append(parse_module(read_text(dest), path))
        if not mods:
            continue

        sections, rep = module_mod.merge_modules(mods[0], mods[1:])

        # 该 App 用到的脚本：已本地化的直接用，没见过的现场本地化
        for b in sections.get("[Script]", []):
            url = extract_script_path(b)
            if not url or url in new_scripts:
                continue
            rel = vendor_rel_path(url)
            target = VENDOR_DIR / rel
            if not target.exists() and not offline:
                res = download(f"_vendor__{stable_id(url)}", url,
                               f"vendor_{Path(rel).name}", refresh=True)
                if not res.ok:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(res.path.read_bytes())
            if target.exists():
                new_scripts[url] = rel
                stats["scripts"] += 1
                stats["script_bytes"] += target.stat().st_size
                verdict, _ = analyze(read_text(target))
                if verdict.startswith("❌"):
                    stats["broken"] += 1

        rewritten = []
        for b in sections.get("[Script]", []):
            url = extract_script_path(b)
            if url and url in new_scripts:
                b = rewrite_script_path(b, f"{repo_url}/vendor/{new_scripts[url]}")
            rewritten.append(b)
        if "[Script]" in sections:
            sections["[Script]"] = rewritten

        mitm = module_mod.parse_mitm(
            module_mod.Module(sections={"[MITM]": sections.get("[MITM]", [])}))
        counts = [(k, human(len(v))) for k, v in sections.items()]
        from emit_module import emit_srmodule
        display = Path(variants[0]).stem
        emit_srmodule(
            out_dir / f"{display}.srmodule", sections,
            name=f"{display} 去广告",
            desc=f"只针对 {display} 的去广告模块，出问题时可以单独停用而不影响其他 App",
            author="sr-adblock-factory（原始规则来自 可莉/奶思 wool_scripts）",
            homepage=repo_url.split("/re", 1)[0],
            provenance=[f"fmz200/wool_scripts split/{Path(variants[0]).parent.name}/"
                        f"{Path(variants[0]).name}",
                        *([f"同名变体已合并：{', '.join(Path(v).parent.name for v in variants[1:])}"]
                          if len(variants) > 1 else [])],
            counts=counts,
            usage=[f"只想去掉 {display} 的广告、不想装总模块时用这个",
                   "导入方式与总模块相同（配置 → 模块 → + → 粘贴链接）"],
        )
        stats["apps"] += 1
        index.append((f"{display}.srmodule", human(sum(len(v) for v in sections.values())),
                      human(len(mitm))))

    _save_blobs(blobs)

    from emit_module import modules_index
    (out_dir / "README.md").write_text(
        "# per-App 可选模块\n\n"
        f"共 {stats['apps']} 个（归并自上游 {stats['variants']} 个 split 文件）。\n\n"
        "**日常只需要装 `ads-all.srmodule` 一个总模块**（符合「只装一个、不叠加」原则）。\n"
        "这些 per-App 模块是「出事时的逃生通道」：某个 App 出现误杀或功能异常，\n"
        "单独停用它对应的模块即可，不用整体关掉去广告。\n\n"
        "也可以只用它们而不是总模块 —— 只装你在意的几个 App，MITM 主机名最少、最省电最稳。\n\n"
        + modules_index(index).split("\n", 2)[2],          # 去掉重复的标题
        encoding="utf-8")

    return {"skipped": False, **stats, "index_size": len(index)}
