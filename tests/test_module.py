"""回归测试 —— 每个用例都对应一个真实踩过的坑。

跑法：python -m unittest discover tests -v
只用标准库 unittest（不需要装任何东西，也不需要网络）；pytest 同样能跑。

为什么要有它：这个项目每天自动发布规则，而这一路所有 bug 都是"跑起来才发现"的
（构建卡死、KeyError、缓存永不命中、参数占位符失效…）。下面每个用例的注释里
都写了它对应哪一次踩坑。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import module as M  # noqa: E402


class SanityFilterTests(unittest.TestCase):
    """脏数据校验：既要能剔掉上游残句，又不能误杀合法规则。"""

    def test_drops_the_real_junk_from_upstream(self):
        """可莉 Surge 版 [URL Rewrite] 里混进的 `hostname - reject` 残句必须被剔除。

        它会被当成「任何 URL 里含 hostname 就拦截」的正则。
        """
        self.assertIsNotNone(M.entry_problem("[URL Rewrite]", "hostname - reject"))

    def test_keeps_redirect_style_rewrites(self):
        """重定向写法（模式 替换值 [标记]）是合法的，不能误杀。

        早期版本要求必须含 ` - `，把 4 条合法的 302 重写当脏数据删了。
        """
        self.assertIsNone(M.entry_problem(
            "[URL Rewrite]", r"^https?://a\.com/x https://b.com/y 302"))

    def test_keeps_reject_style_rewrites(self):
        self.assertIsNone(M.entry_problem(
            "[URL Rewrite]", r"^https?:\/\/ad\.example\.com\/v\d - reject"))

    def test_placeholder_rule_kind_is_valid(self):
        """★ 回归：WiFi Calling 模块把「规则类型」做成了参数，不能当成未知类型删掉。

        早期版本删了这两条 —— 其中第二条是 WiFi Calling 的 IPsec 端口规则
        （UDP 500/4500/16384-16403），删掉模块就直接失效。
        """
        apple = "{{{苹果地区检测}}},gspe1-ssl.ls.apple.com,{{{默认代理分组}}}"
        ipsec = ("{{{通话端口代理}}},((GEOIP,HK),(AND,((PROTOCOL,UDP),"
                 "(OR,((DEST-PORT,500),(DEST-PORT,4500)))))),{{{默认代理分组}}}")
        self.assertIsNone(M.entry_problem("[Rule]", apple))
        self.assertIsNone(M.entry_problem("[Rule]", ipsec))

    def test_unknown_rule_kind_is_flagged(self):
        """真正的未知类型仍要拦（小火箭会静默忽略它）。"""
        self.assertIsNotNone(M.entry_problem("[Rule]", "PROCESS-NAME,curl,REJECT"))

    def test_valid_rule_kinds_pass(self):
        for line in ("DOMAIN,ad.com,REJECT", "DOMAIN-SUFFIX,ad.com,REJECT",
                     "IP-CIDR,1.2.3.4/32,REJECT,no-resolve", "FINAL,PROXY"):
            self.assertIsNone(M.entry_problem("[Rule]", line), line)

    def test_sanity_filter_reports_what_it_drops(self):
        sec = {"[URL Rewrite]": [M.Block("hostname - reject"),
                                 M.Block(r"^https?://ok.com/a - reject")]}
        dropped: dict = {}
        out = M.apply_sanity_filter(sec, dropped)
        self.assertEqual(len(out["[URL Rewrite]"]), 1)
        self.assertEqual(len(dropped["[URL Rewrite]"]), 1)


class SemanticKeyTests(unittest.TestCase):
    """语义去重：Surge 版与 SR 版写法不同但语义相同的，不能被当成新规则重复导入。"""

    def test_map_local_status_code_200_is_equal(self):
        """status-code=200 本来就是 Map Local 的默认值。

        不归一化的话，796 条会被当成"新规则"重复导入，产物虚胖一倍。
        """
        a = '^https?://a.com/x data-type=text data="{}" status-code=200'
        b = '^https?://a.com/x data-type=text data="{}"'
        self.assertEqual(M.semantic_key(a, "[Map Local]"),
                         M.semantic_key(b, "[Map Local]"))

    def test_script_pattern_quotes_are_equal(self):
        """Surge 版给含逗号的 pattern 加了引号。"""
        a = 'x = type=http-response, pattern="^https://a.com/x,", script-path=s.js'
        b = 'x = type=http-response, pattern=^https://a.com/x,, script-path=s.js'
        self.assertEqual(M.semantic_key(a, "[Script]"), M.semantic_key(b, "[Script]"))

    def test_different_rules_differ(self):
        self.assertNotEqual(M.semantic_key("DOMAIN,a.com,REJECT", "[Rule]"),
                            M.semantic_key("DOMAIN,b.com,REJECT", "[Rule]"))


class MitmDerivationTests(unittest.TestCase):
    """MITM 主机名反推：让「要解密却没声明主机名」的死规则活过来。"""

    def test_derives_host_from_escaped_pattern(self):
        """★ 回归：正则里的 \\. 转义必须还原，否则反推不出主机名。

        东方财富那条规则就是这样 —— 早期版本提取不出主机名，漏判了它。
        """
        sec = {"[URL Rewrite]": [M.Block(
                   r"^https?:\/\/emdcadvertise\.eastmoney\.com\/infoService\/v\d - reject")],
               "[MITM]": [M.Block("hostname = %APPEND% other.com")]}
        add, held, _ = M.derive_mitm_hosts(sec, finance_keywords=[])
        self.assertIn("emdcadvertise.eastmoney.com", add)

    def test_default_guard_holds_back_eastmoney(self):
        """同一个主机，用默认守卫时应被拦下（东方财富是券商）。

        这条同时守住一个 API 语义：finance_keywords=[] 表示"不要守卫"，
        传 None 才用默认守卫 —— 早期用 `or` 判断，空列表会被当成假值回退到默认。
        """
        sec = {"[URL Rewrite]": [M.Block(
                   r"^https?:\/\/emdcadvertise\.eastmoney\.com\/infoService\/v\d - reject")],
               "[MITM]": []}
        add, held, _ = M.derive_mitm_hosts(sec)
        self.assertEqual(add, [])
        self.assertTrue(any("eastmoney" in h for h, _ in held))

    def test_finance_guard_holds_back_bank_hosts(self):
        """金融类主机不自动开解密 —— 这个风险不该由脚本替用户承担。"""
        sec = {"[Map Local]": [M.Block(
                   '^https?://mlife.jf365.boc.cn/x data-type=text data="{}"')],
               "[MITM]": []}
        add, held, _ = M.derive_mitm_hosts(sec)
        self.assertEqual(add, [])
        self.assertTrue(any("boc" in h for h, _ in held))

    def test_wildcard_mitm_covers_subdomain(self):
        sec = {"[URL Rewrite]": [M.Block("^https?://api.futunn.com/x - reject")],
               "[MITM]": [M.Block("hostname = %APPEND% *.futunn.com")]}
        add, held, _ = M.derive_mitm_hosts(sec, finance_keywords=[])
        self.assertEqual(add, [])
        self.assertEqual(held, [])

    def test_approved_host_is_added(self):
        """用户手动放进 config/mitm-extra.txt 的主机要能开起来。"""
        sec = {"[URL Rewrite]": [M.Block("^https?://api.futunn.com/x - reject")],
               "[MITM]": []}
        add, held, _ = M.derive_mitm_hosts(sec, approved=["api.futunn.com"])
        self.assertIn("api.futunn.com", add)
        self.assertEqual(held, [])


class ArgumentTests(unittest.TestCase):
    """参数声明解析：上游把占位符写进模块却没声明，我们从 Loon V2 版补。"""

    def test_resolves_arguments_from_loon_v2(self):
        sections = {"[Script]": [M.Block(
            'x = type=http-response, pattern=a, argument="[{{{tab}}},{{{MY}}}]"')]}
        decl = M.Module(sections={"[Argument]": [
            M.Block("tab = switch,true,false,tag=首页"),
            M.Block("MY = select,a|b|b,tag=区域"),
        ]})
        declared, unresolved, used = M.resolve_arguments(sections, decl)
        self.assertEqual(set(used), {"tab", "MY"})
        self.assertEqual(unresolved, [])
        self.assertIn("tab:true", declared)

    def test_reports_unresolved_placeholders(self):
        sections = {"[Script]": [M.Block("x = type=cron, argument={{{unknown_arg}}}")]}
        decl = M.Module(sections={"[Argument]": []})
        _, unresolved, _ = M.resolve_arguments(sections, decl)
        self.assertEqual(unresolved, ["unknown_arg"])


class RulesetWrappingTests(unittest.TestCase):
    """把一个规则集包成模块时，必须补上策略列。"""

    def test_adds_policy_when_missing(self):
        """★ 回归：规则集是「策略无关」格式（DOMAIN,x.com），
        模块里的规则必须带策略（DOMAIN,x.com,REJECT），少了这一列会被忽略。"""
        import extra as E

        self.assertEqual(E._ensure_policy("DOMAIN,mesu.apple.com", "REJECT"),
                         "DOMAIN,mesu.apple.com,REJECT")

    def test_keeps_existing_policy(self):
        import extra as E

        self.assertEqual(E._ensure_policy("DOMAIN,a.com,REJECT", "REJECT"),
                         "DOMAIN,a.com,REJECT")
        self.assertEqual(E._ensure_policy("DOMAIN,a.com,DIRECT", "REJECT"),
                         "DOMAIN,a.com,DIRECT")

    def test_option_column_is_not_a_policy(self):
        """`IP-CIDR,1.2.3.4/32,no-resolve` 的第三列是选项，不是策略。"""
        import extra as E

        self.assertEqual(E._ensure_policy("IP-CIDR,1.2.3.4/32,no-resolve", "REJECT"),
                         "IP-CIDR,1.2.3.4/32,no-resolve,REJECT")

    def test_custom_policy_group_name_is_preserved(self):
        """有些规则集直接写了策略组名，不该被覆盖。"""
        import extra as E

        self.assertEqual(E._ensure_policy("DOMAIN,a.com,香港节点", "REJECT"),
                         "DOMAIN,a.com,香港节点")


class AppModuleTests(unittest.TestCase):
    """per-App 模块的生成逻辑。"""

    def test_vendor_path_preserves_origin(self):
        """脚本本地化后路径必须保留原始出处，便于追溯与更新。"""
        import vendor as V

        rel = V.vendor_rel_path(
            "https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/51card.js")
        self.assertEqual(rel, "fmz200/wool_scripts/main/Scripts/51card.js")

    def test_same_basename_does_not_collide(self):
        """不同仓库的同名脚本，缓存文件名不能撞车。

        早期版本用文件名做缓存键，两个仓库的 youtube.js 会互相覆盖。
        """
        import vendor as V

        a = V.vendor_rel_path("https://raw.githubusercontent.com/a/r1/main/js/x.js")
        b = V.vendor_rel_path("https://raw.githubusercontent.com/b/r2/main/js/x.js")
        self.assertNotEqual(a.replace("/", "__"), b.replace("/", "__"))


if __name__ == "__main__":
    unittest.main()
