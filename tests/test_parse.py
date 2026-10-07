"""上游格式解析的回归测试 —— 重点是 hosts / adblock 两种新增格式的语义。

跑法：python -m unittest discover tests -v
只用标准库 unittest（不需要装任何东西，也不需要网络）；pytest 同样能跑。

为什么要有它：这两种格式是给"直接消费 DNS 拦截名单"用的，语义坑很集中 ——
hosts 名单如果按 domain_set 的"裸域名 = 精确匹配"去收，子域会全漏（拦截率暴跌）；
adblock 名单里的 $修饰符 / 正则 / 通配如果当成域名收进来，会拦出莫名其妙的结果。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import parse  # noqa: E402


class HostsFormatTests(unittest.TestCase):
    """hosts 文件 / 纯域名表：一律按"含子域"收录。"""

    def test_hosts_lines_are_suffix_not_exact(self):
        """★ 核心语义：hosts 行必须进 suffix（含子域），不能进 exact。

        进 exact 的话 `0.0.0.0 ad.com` 只能拦 ad.com 本身，
        `a.ad.com`、`b.ad.com` 全部漏掉 —— 这正是拿 hosts 名单直接喂
        domain_set 的坑（那里裸域名 = 精确匹配）。
        """
        layer = parse.parse_hosts(
            "0.0.0.0 ads.example.com\n"
            "127.0.0.1 tracker.example.net\n"
            "::1 x.example.org\n", "t")
        self.assertEqual(set(layer.suffix),
                         {"ads.example.com", "tracker.example.net", "x.example.org"})
        self.assertEqual(layer.exact, {})

    def test_multiple_domains_on_one_line(self):
        """hosts 行可以一行多个域名：`0.0.0.0 a.com b.com` 两个都要收。"""
        layer = parse.parse_hosts("0.0.0.0 a.example.com b.example.com\n", "t")
        self.assertEqual(set(layer.suffix), {"a.example.com", "b.example.com"})

    def test_localhost_entries_are_not_collected(self):
        """`127.0.0.1 localhost` 这类单标签条目必须判无效，不能当域名收。

        收进来会变成拦整个 `localhost`（无害但也无用），且会污染统计。
        """
        layer = parse.parse_hosts(
            "127.0.0.1 localhost\n::1 ip6-localhost\n255.255.255.255 broadcasthost\n", "t")
        self.assertEqual(layer.suffix, {})
        self.assertEqual(layer.stats.get("invalid"), 3)

    def test_plain_domain_list_works_too(self):
        """纯域名表（Hagezi 的 onlydomains 那种）也要能解析。"""
        layer = parse.parse_hosts("# Title: something\ntelemetry.a.example.com\n\n"
                                  "ad.b.example.com\n", "t")
        self.assertEqual(set(layer.suffix),
                         {"telemetry.a.example.com", "ad.b.example.com"})

    def test_comment_styles_are_skipped(self):
        layer = parse.parse_hosts("! adblock 注释\n// 斜杠注释\n# 井号注释\n"
                                  "0.0.0.0 a.example.com\n", "t")
        self.assertEqual(set(layer.suffix), {"a.example.com"})

    def test_multi_token_non_hosts_line_is_rejected(self):
        """非 hosts 行又不止一个 token —— 不是能识别的域名表，跳过并计数。"""
        layer = parse.parse_hosts("a.example.com b.example.com\n", "t")
        self.assertEqual(layer.suffix, {})
        self.assertEqual(layer.stats.get("malformed"), 1)


class AdblockFormatTests(unittest.TestCase):
    """AdGuard / ABP 基础规则：只收域名锚定规则，其余跳过并计数。"""

    def test_basic_block_rule_becomes_suffix(self):
        layer = parse.parse_adblock("||ads.example.com^\n", "t")
        self.assertEqual(set(layer.suffix), {"ads.example.com"})
        self.assertEqual(layer.exact, {})

    def test_rule_without_caret(self):
        layer = parse.parse_adblock("||ads.example.com\n", "t")
        self.assertEqual(set(layer.suffix), {"ads.example.com"})

    def test_allow_rule_goes_to_allow(self):
        """@@||domain^ 是放行，不能当成拦截收进 suffix。"""
        layer = parse.parse_adblock("@@||ok.example.com^\n", "t")
        self.assertEqual(layer.allow, {"ok.example.com"})
        self.assertEqual(layer.suffix, {})
        self.assertEqual(layer.stats.get("adblock_allow"), 1)

    def test_modifiers_are_skipped(self):
        """带 $修饰符的规则，修饰符在域名层表达不了 —— 跳过并计数，不能当域名收。

        收进来会把 `ad.com^$third-party` 变成"拦整个 ad.com"（超集，会误杀）。
        """
        layer = parse.parse_adblock(
            "||a.example.com^$third-party\n||b.example.com^$important\n", "t")
        self.assertEqual(layer.suffix, {})
        self.assertEqual(layer.stats.get("adblock_modifiers"), 2)

    def test_cosmetic_regex_and_wildcard_are_skipped(self):
        layer = parse.parse_adblock(
            "example.com##.banner\n"
            "/banner\\d+/\n"
            "||*.wild.example.com^\n", "t")
        self.assertEqual(layer.suffix, {})
        self.assertEqual(layer.allow, set())
        self.assertEqual(layer.stats.get("adblock_skipped"), 3)

    def test_abp_header_is_ignored(self):
        """`[Adblock Plus 2.0]` 是格式头，不是被跳过的规则，不该进统计。"""
        layer = parse.parse_adblock("[Adblock Plus 2.0]\n||ad.example.com^\n", "t")
        self.assertEqual(set(layer.suffix), {"ad.example.com"})
        self.assertIsNone(layer.stats.get("adblock_skipped"))

    def test_mixed_list(self):
        layer = parse.parse_adblock(
            "! 注释\n"
            "||ad.example.com^\n"
            "@@||ok.example.com^\n"
            "||ad2.example.com^$script\n", "t")
        self.assertEqual(set(layer.suffix), {"ad.example.com"})
        self.assertEqual(layer.allow, {"ok.example.com"})
        self.assertEqual(layer.stats.get("adblock_modifiers"), 1)


class DomainSetUnchangedTests(unittest.TestCase):
    """新格式不能改到 domain_set 的既有语义（裸域名 = 精确）。"""

    def test_bare_domain_is_still_exact(self):
        layer = parse.parse_domain_set("foo.com\n.foo2.com\n", "t")
        self.assertEqual(set(layer.exact), {"foo.com"})
        self.assertEqual(set(layer.suffix), {"foo2.com"})


if __name__ == "__main__":
    unittest.main()
