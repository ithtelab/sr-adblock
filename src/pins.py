"""脚本指纹锁 —— 防止上游脚本被改（或被盗号后投毒）静默进入产物。

**为什么需要它**：`vendor/` 里的脚本每次构建都会拉上游最新版覆盖，然后直接发布。
如果上游某次提交塞进恶意代码，它会**静默进入产物** —— 而唯一的防线只是
"git 历史里有 diff"，可没人会天天读 83 个脚本的 diff。

规则错了顶多误拦；**脚本被投毒是能读到被解密流量内容的**。

**做法**：把每个脚本的 sha256 记进 `config/script-pins.txt`。构建时比对：
  · 内容与指纹一致  → 正常发布
  · 出现新脚本 / 内容变化 → **停止发布**（保留上一版继续服务），
    写一份变更报告（含新增/改动/消失的清单），等人确认
  · 人工确认方式：`python src/build.py --update-script-pins` 更新指纹后提交

这样"自动化"和"内容变化必须被人看过一次"两者兼得。
"""
from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from util import VENDOR_DIR, read_text, write_text

PINS_FILE_NAME = "script-pins.txt"
PINS_HEADER = """# 脚本指纹锁 —— 上游脚本内容变化时必须人工确认一次
#
# 为什么：vendor/ 里的第三方脚本每次构建都会跟随上游更新并直接发布。
# 上游若被投毒，恶意代码会静默进入产物，而脚本能读到被解密流量的内容。
#
# 怎么用：
#   · 构建时内容与这里不一致 → 停止发布（保留上一版），并生成变更报告
#   · 确认改动没问题后，跑 `python src/build.py --update-script-pins` 更新指纹并提交
#   · 加了新的 per-App 模块导致出现新脚本，同理需要确认一次
#
# 格式：sha256<TAB>相对路径（相对 vendor/）。这个文件**不要手改**。
#
# 生成时间：{built_at}
# 共 {count} 个脚本
"""


@dataclass
class PinDiff:
    added: list[str] = field(default_factory=list)      # 新出现的脚本
    changed: list[str] = field(default_factory=list)    # 内容变了的
    removed: list[str] = field(default_factory=list)    # 不再引用的
    unchanged: int = 0
    bootstrapped: bool = False                          # 首次建立指纹

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.changed or self.removed)

    def summary(self) -> str:
        if self.bootstrapped:
            return f"首次建立指纹（{self.unchanged} 个脚本）"
        if not self.has_changes:
            return f"全部一致（{self.unchanged} 个脚本）"
        parts = []
        if self.added:
            parts.append(f"新增 {len(self.added)}")
        if self.changed:
            parts.append(f"**内容变化 {len(self.changed)}**")
        if self.removed:
            parts.append(f"不再引用 {len(self.removed)}")
        return "、".join(parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pins_path(root: Path) -> Path:
    return root / "config" / PINS_FILE_NAME


def load_pins(path: Path) -> dict[str, str]:
    """读指纹表：{相对路径: sha256}。"""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        s = line.split("#", 1)[0].strip()
        if not s or "\t" not in s:
            continue
        digest, _, rel = s.partition("\t")
        rel = rel.strip()
        digest = digest.strip()
        if digest and rel:
            out[rel] = digest
    return out


def save_pins(path: Path, pins: dict[str, str], *, built_at: str = "") -> None:
    body = "\n".join(f"{digest}\t{rel}" for rel, digest in sorted(pins.items()))
    header = PINS_HEADER.format(built_at=built_at or "-", count=len(pins))
    write_text(path, header + "\n" + body + "\n")


def current_pins(vendor_dir: Path | None = None) -> dict[str, str]:
    """扫描 vendor/ 下所有脚本，算出当前指纹表。"""
    base = vendor_dir or VENDOR_DIR
    pins: dict[str, str] = {}
    for p in sorted(base.rglob("*.js")):
        pins[p.relative_to(base).as_posix()] = sha256_file(p)
    return pins


def diff_pins(old: dict[str, str], new: dict[str, str]) -> PinDiff:
    diff = PinDiff()
    for rel, digest in new.items():
        if rel not in old:
            diff.added.append(rel)
        elif old[rel] != digest:
            diff.changed.append(rel)
        else:
            diff.unchanged += 1
    for rel in old:
        if rel not in new:
            diff.removed.append(rel)
    return diff


def changes_report(diff: PinDiff, *, old_pins: dict[str, str],
                   vendor_dir: Path | None = None,
                   max_lines: int = 40) -> list[str]:
    """生成给人看的变更报告（含改动行摘要）。"""
    base = vendor_dir or VENDOR_DIR
    lines = ["# 脚本变更待确认", "",
             "上游脚本的内容与 `config/script-pins.txt` 里的指纹不一致。",
             "**本次构建已跳过发布**（用户手上的还是上一版），等你确认。", "",
             f"- 新增脚本：{len(diff.added)} 个",
             f"- 内容变化：{len(diff.changed)} 个",
             f"- 不再引用：{len(diff.removed)} 个", ""]

    if diff.changed:
        lines += ["## 内容变化的脚本（重点看这些）", ""]
        for rel in diff.changed:
            lines += [f"### `{rel}`", ""]
            lines += _diff_excerpt(base / rel, rel, max_lines)
            lines += [""]
    if diff.added:
        lines += ["## 新增脚本", "",
                  "上游新增了脚本（通常是我们整合了新的 per-App 模块带进来的）。",
                  "**新脚本要当成陌生代码看一遍。**", ""]
        lines += [f"- `{rel}`" for rel in diff.added] + [""]
    if diff.removed:
        lines += ["## 不再引用的脚本", "",
                  "上游删掉了引用（不影响安全，构建会自动清理指纹）。", ""]
        lines += [f"- `{rel}`" for rel in diff.removed] + [""]

    lines += ["## 怎么确认", "",
              "看上面没问题后，跑一次：", "",
              "```bash",
              "python src/build.py --update-script-pins",
              "```",
              "",
              "它会更新指纹并继续正常构建。然后提交 `config/script-pins.txt` 即可。",
              "",
              "在 GitHub 上也可以：Actions → build → Run workflow → 勾选 `accept_scripts`。", ""]
    _ = old_pins
    return lines


def _diff_excerpt(path: Path, rel: str, max_lines: int) -> list[str]:
    """给出改动行的摘要。因为旧内容没留档，这里退化为"当前文件的关键行 + 统计"。"""
    if not path.exists():
        return ["（文件不存在）"]
    text = read_text(path)
    out = [f"当前大小 {len(text)} 字节，{len(text.splitlines())} 行"]
    # 挑出最值得人看的行：网络调用、动态执行、长 base64
    interesting = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(k in line for k in ("$httpClient", "$task.fetch", "fetch(",
                                   "XMLHttpRequest", "eval(", "new Function",
                                   "atob(", "Buffer.from")):
            interesting.append(f"  第 {i} 行：{line.strip()[:110]}")
        if len(interesting) >= max_lines // 3:
            break
    if interesting:
        out.append("值得看一眼的行（网络调用 / 动态执行）：")
        out += interesting
    else:
        out.append("没有明显的网络调用或动态执行")
    return out
