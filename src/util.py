"""公共工具：路径、配置加载、文本读取、带缓存的下载。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CACHE_DIR = ROOT / "cache"
RAW_DIR = CACHE_DIR / "raw"
VENDOR_DIR = ROOT / "vendor"
DIST_DIR = ROOT / "dist"

USER_AGENT = "sr-adblock-factory/1.0 (+https://github.com)"
MANIFEST = CACHE_DIR / "manifest.json"

# 域名层里出现这些顶级标签基本可以判定不是域名（做脏数据过滤用）
_TLD_MIN = 2


def log(msg: str = "") -> None:
    # 不用 print()：某些环境（含 ZCode 的 sitecustomize）会包装 print，
    # 与 flush 关键字冲突，直接写 stdout 最稳。
    sys.stdout.write(f"{msg}\n")
    sys.stdout.flush()


def section(title: str) -> None:
    log("")
    log("=" * 72)
    log(f"  {title}")
    log("=" * 72)


# ---------------------------------------------------------------------------
# 文本读取：上游文件编码很杂（utf-8 / utf-8-sig / gbk 都有），逐个尝试
# ---------------------------------------------------------------------------

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "latin-1")


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 统一 LF 换行 + 结尾空行，避免 Windows/Linux 构建产出不同
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    if not body.endswith("\n"):
        body += "\n"
    path.write_bytes(body.encode("utf-8"))


def load_yaml(path: Path) -> dict:
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ---------------------------------------------------------------------------
# 下载（带本地缓存 + 清单）
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    source_id: str
    url: str
    path: Path
    size: int
    sha256: str
    from_cache: bool
    elapsed: float
    ok: bool = True
    error: str = ""


def _load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_manifest(data: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def download(source_id: str, url: str, filename: str, *, offline: bool = False,
             refresh: bool = False, retries: int = 3, timeout: int = 120,
             check_update: bool = True) -> FetchResult:
    """下载到缓存。

    check_update=True 时带 If-None-Match 发条件请求：上游没变就返回 304，
    直接复用本地缓存。这对每日流水线是必需的 —— 否则要么每天重下 30MB，
    要么永远拿不到上游更新。
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / filename
    manifest = _load_manifest()
    entry = manifest.get(source_id) or {}
    cached_ok = dest.exists() and entry.get("url") == url

    if offline:
        if dest.exists():
            sha = _sha256(dest)
            return FetchResult(source_id, url, dest, dest.stat().st_size, sha,
                               True, 0.0, True, error="offline：使用本地缓存")
        return FetchResult(source_id, url, dest, 0, "", False, 0.0, False,
                           error="offline 且无缓存")

    if cached_ok and not refresh and not check_update:
        sha = _sha256(dest)
        if entry.get("sha256") == sha:
            return FetchResult(source_id, url, dest, dest.stat().st_size, sha,
                               True, 0.0, True)

    last_err = ""
    for attempt in range(1, retries + 1):
        started = time.time()
        try:
            headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
            etag = entry.get("etag") if (cached_ok and not refresh) else None
            if etag:
                headers["If-None-Match"] = etag
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    new_etag = resp.headers.get("ETag", "")
            except urllib.error.HTTPError as exc:
                if exc.code == 304 and dest.exists():
                    sha = _sha256(dest)
                    manifest[source_id] = {**entry, "checked_at":
                                           time.strftime("%Y-%m-%d %H:%M:%S")}
                    _save_manifest(manifest)
                    return FetchResult(source_id, url, dest, dest.stat().st_size,
                                       sha, True, time.time() - started, True)
                raise
            if not data:
                raise urllib.error.URLError("响应为空")
            dest.write_bytes(data)
            sha = _sha256(dest)
            manifest[source_id] = {"url": url, "sha256": sha, "size": len(data),
                                   "etag": new_etag,
                                   "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")}
            _save_manifest(manifest)
            return FetchResult(source_id, url, dest, len(data), sha, False,
                               time.time() - started, True)
        except Exception as exc:  # noqa: BLE001 - 网络异常种类多，统一重试
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(2 * attempt)

    # 全部重试失败：有旧缓存就用旧缓存，保证构建不中断
    if dest.exists():
        sha = _sha256(dest)
        return FetchResult(source_id, url, dest, dest.stat().st_size, sha, True,
                           0.0, True, error=f"下载失败，回退旧缓存（{last_err}）")
    return FetchResult(source_id, url, dest, 0, "", False, 0.0, False, error=last_err)


def stable_id(text: str, n: int = 12) -> str:
    """稳定的短标识。

    不要用内置 hash()：Python 对 str 的哈希每个进程都不同（PYTHONHASHSEED），
    用它做缓存键会导致每次构建都被当成新源，缓存永远命中不了。
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_text(source_id: str, url: str, filename: str, **kw) -> tuple[str, FetchResult]:
    res = download(source_id, url, filename, **kw)
    if not res.ok:
        return "", res
    return read_text(res.path), res


# ---------------------------------------------------------------------------
# 域名规整与校验
# ---------------------------------------------------------------------------

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9_-]{1,63}(?<!-)"
                        r"(?:\.(?!-)[a-z0-9_-]{1,63}(?<!-))*$")
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_IPV6_RE = re.compile(r"^[0-9a-f:]+$")


def normalize_domain(raw: str) -> str | None:
    """规整成小写 ASCII 域名；非域名返回 None。"""
    s = raw.strip().strip(".").lower()
    if not s:
        return None
    # 去掉可能带的通配前缀（调用方另行处理通配语义）
    s = s.lstrip("*").lstrip(".")
    if not s:
        return None
    if any(ch.isspace() for ch in s):
        return None
    if not s.isascii():
        s = _to_idna(s)
        if s is None:
            return None
    if not _DOMAIN_RE.match(s):
        return None
    labels = s.split(".")
    if len(labels) < 2:               # 单标签不是域名（如广告过滤器的 .pagespeed-mod）
        return None
    if len(labels[-1]) < _TLD_MIN:
        return None
    if labels[-1].isdigit():          # 纯数字结尾基本是脏数据
        return None
    if _IPV4_RE.match(s):             # IPv4 字面量：交给 IP 层
        return None
    return s


def _to_idna(s: str) -> str | None:
    try:
        return s.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        try:
            out = []
            for label in unicodedata.normalize("NFC", s).split("."):
                out.append(label.encode("punycode").decode("ascii"))
            return ".".join(out)
        except Exception:  # noqa: BLE001
            return None


def looks_like_ip(value: str) -> bool:
    v = value.strip()
    if "/" in v:
        v = v.split("/", 1)[0]
    if _IPV4_RE.match(v):
        return all(0 <= int(p) <= 255 for p in v.split("."))
    return ":" in v and bool(_IPV6_RE.match(v.replace("/", "")))


def parent_domains(domain: str):
    """依次产出各级父域：a.b.c -> b.c, c"""
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        yield ".".join(parts[i:])


def human(n: int) -> str:
    return f"{n:,}"


def fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    value = float(n)
    for unit in ("KB", "MB", "GB"):
        value /= 1024
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}"
    return f"{value:.1f}GB"


@dataclass
class Warning_:  # 构建过程中的告警收集
    level: str
    message: str

    def __str__(self) -> str:
        icon = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}.get(self.level, "·")
        return f"{icon} {self.message}"


WARNINGS: list[Warning_] = []


def warn(message: str, level: str = "warn") -> None:
    WARNINGS.append(Warning_(level, message))
