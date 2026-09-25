"""配置层：生成小火箭的 base.conf（代理分组 + 引用域名层/模块层）。

设计要点：
  * 地区分组用 url-test + policy-regex-filter 按节点名自动匹配，
    所以这份配置**适配任何订阅**，不需要你手工挑节点。
  * [Rule] 的顺序在小火箭里是有意义的（从上到下匹配），所以：
      放行 → 去广告 → 分流 → 兜底
    放行必须最前，否则加白名单没用；去广告放在分流前，保证广告域名不会
    因为命中了某个服务的规则集而漏过拦截。
  * 节点订阅留空，由你自己填 —— 本仓库不存放任何节点信息。
"""
from __future__ import annotations

from pathlib import Path

from util import human, write_text

# 从上游配置骨架里沿用的分流结构（原作者 LOWERTOP，见 NOTICE）
# 地区组：按节点名里的国家/地区标识自动匹配，适配任意订阅
REGION_GROUPS = [
    ("香港节点", r"🇭🇰|HK|Hong|hong|香港|深港|沪港|京港|港"),
    ("台湾节点", r"🇹🇼|TW|TWN|Taiwan|Taipei|taiwan|台湾|台灣|台北|台中|新北"),
    ("日本节点", r"🇯🇵|JP|Japan|japan|Tokyo|tokyo|日本|东京|大阪|京日|苏日"),
    ("新加坡节点", r"🇸🇬|SG|Sing|sing|新加坡|狮城|沪新|京新|深新|杭新|广新"),
    ("韩国节点", r"🇰🇷|KR|Korea|korea|KOR|韩国|首尔|韩|韓|春川"),
    ("美国节点", r"🇺🇸|US|USA|America|america|United States|美国|凤凰"),
]
REGIONS = [name for name, _ in REGION_GROUPS]

# 服务分组：默认策略 + 是否允许切到地区组
SERVICE_GROUPS = [
    ("AI", "PROXY"),
    ("YouTube", "PROXY"),
    ("Netflix", "PROXY"),
    ("Disney+", "PROXY"),
    ("Max", "PROXY"),
    ("TikTok", "PROXY"),
    ("Spotify", "PROXY"),
    ("Telegram", "PROXY"),
    ("Twitter", "PROXY"),
    ("Facebook", "PROXY"),
    ("PayPal", "PROXY"),
    ("Amazon", "PROXY"),
    ("苹果服务", "DIRECT"),
    ("谷歌服务", "PROXY"),
    ("微软服务", "DIRECT"),
    ("哔哩哔哩", "DIRECT"),
    ("游戏平台", "PROXY"),
]

# 分流规则：引用 blackmatrix7 的分类规则集（保持上游最新，本仓库不复制内容）
B7 = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket"
SERVICE_RULES = [
    (f"RULE-SET,{B7}/YouTube/YouTube.list", "YouTube"),
    (f"RULE-SET,{B7}/Netflix/Netflix.list", "Netflix"),
    (f"RULE-SET,{B7}/Disney/Disney.list", "Disney+"),
    (f"RULE-SET,{B7}/HBO/HBO.list", "Max"),
    (f"RULE-SET,{B7}/Spotify/Spotify.list", "Spotify"),
    (f"RULE-SET,{B7}/Telegram/Telegram.list", "Telegram"),
    (f"RULE-SET,{B7}/Twitter/Twitter.list", "Twitter"),
    (f"RULE-SET,{B7}/Facebook/Facebook.list", "Facebook"),
    (f"RULE-SET,{B7}/PayPal/PayPal.list", "PayPal"),
    (f"RULE-SET,{B7}/Amazon/Amazon.list", "Amazon"),
    (f"RULE-SET,{B7}/TikTok/TikTok.list", "TikTok"),
    (f"RULE-SET,{B7}/Sony/Sony.list", "游戏平台"),
    (f"RULE-SET,{B7}/Nintendo/Nintendo.list", "游戏平台"),
    (f"RULE-SET,{B7}/Epic/Epic.list", "游戏平台"),
    (f"RULE-SET,{B7}/SteamCN/SteamCN.list", "游戏平台"),
    (f"RULE-SET,{B7}/Steam/Steam.list", "游戏平台"),
    (f"RULE-SET,{B7}/Game/Game.list", "游戏平台"),
    (f"RULE-SET,{B7}/GitHub/GitHub.list", "PROXY"),
    (f"RULE-SET,{B7}/Microsoft/Microsoft.list", "微软服务"),
    (f"RULE-SET,{B7}/Google/Google.list", "谷歌服务"),
    (f"RULE-SET,{B7}/Apple/Apple.list", "苹果服务"),
    (f"RULE-SET,{B7}/BiliBili/BiliBili.list", "哔哩哔哩"),
    # 国内服务强制直连：避免走了代理反而变慢或被风控
    (f"RULE-SET,{B7}/NetEaseMusic/NetEaseMusic.list", "DIRECT"),
    (f"RULE-SET,{B7}/Baidu/Baidu.list", "DIRECT"),
    (f"RULE-SET,{B7}/DouBan/DouBan.list", "DIRECT"),
    (f"RULE-SET,{B7}/WeChat/WeChat.list", "DIRECT"),
    (f"RULE-SET,{B7}/Sina/Sina.list", "DIRECT"),
    (f"RULE-SET,{B7}/Zhihu/Zhihu.list", "DIRECT"),
    (f"RULE-SET,{B7}/XiaoHongShu/XiaoHongShu.list", "DIRECT"),
    (f"RULE-SET,{B7}/DouYin/DouYin.list", "DIRECT"),
    (f"RULE-SET,{B7}/Lan/Lan.list", "DIRECT"),
]

GENERAL = [
    ("skip-proxy", "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,localhost,*.local,"
                   "captive.apple.com,*.ccb.com,*.abchina.com.cn,*.psbc.com"),
    ("tun-excluded-routes", "10.0.0.0/8,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,"
                            "192.0.0.0/24,192.0.2.0/24,192.88.99.0/24,192.168.0.0/16,"
                            "198.51.100.0/24,203.0.113.0/24,224.0.0.0/4,255.255.255.255/32"),
    ("dns-server", "https://doh.pub/dns-query,https://dns.alidns.com/dns-query,223.5.5.5,119.29.29.29"),
    ("fallback-dns-server", "system"),
    ("ipv6", "true"),
    ("prefer-ipv6", "false"),
    ("dns-direct-system", "false"),
    ("icmp-auto-reply", "true"),
]


def emit_base_conf(path: Path, *, repo_url: str, allow, prefix: str,
                   mitm_hosts: list[str], stats: dict) -> int:
    L: list[str] = []
    add = L.append
    r = repo_url.rstrip("/")

    add("# " + "=" * 74)
    add("#  小火箭配置模板（由 sr-adblock-factory 生成）")
    add("#")
    add("#  这份配置把三层接在一起：")
    add(f"#    ① 域名层   DOMAIN-SET {prefix}-domain.list + RULE-SET {prefix}-rule.list  → REJECT")
    add("#    ② 模块层   去广告模块（重写/MITM，需要单独导入，见 README）")
    add("#    ③ 配置层   就是本文件：代理分组 + 分流规则")
    add("#")
    add("#  【必读】节点订阅：本文件不含任何节点。")
    add("#    导入后请在小火箭底部「首页 → 添加节点/订阅」里填你自己的订阅，")
    add("#    然后回到「配置」里启用本文件。地区分组会按节点名自动匹配，不用手工挑节点。")
    add("#")
    add("#  【必读】去广告要生效，除了本文件还需要导入两个模块（见 README 的安装清单）：")
    add(f"#    {r}/module/ads-all.srmodule")
    add(f"#    {r}/module/httpdns.srmodule")
    add("#    模块里的规则优先级高于本文件，所以装了模块就等于装上了最强的那一层。")
    add("#")
    add("#  改动建议：不要直接改这份文件（重新下载会被覆盖）。")
    add("#            想加白/加黑，改仓库的 config/allowlist.txt 后重新构建；")
    add("#            临时放行也可以在小火箭里「配置 → 编辑纯文本」加一行。")
    add("# " + "=" * 74)
    add("")

    add("[General]")
    add("# 通用设置：DNS 用国内 DoH（解析快且不被污染），局域网与苹果服务走直连")
    for k, v in GENERAL:
        add(f"{k} = {v}")
    add("")

    add("[Proxy]")
    add("# 这里留空 —— 你的节点/订阅不在本仓库里，请在小火箭里单独添加。")
    add("# 如果你的节点是写死在配置里的，按下面格式加（示例已注释）：")
    add("# 我的节点 = ss,1.2.3.4,8388,encrypt-method=aes-256-gcm,password=xxxx")
    add("")

    add("[Proxy Group]")
    add("# 地区分组：url-test 自动在组内选延迟最低的节点，")
    add("# policy-regex-filter 按节点名里的国家/地区标识自动归类 —— 所以换订阅也不用改配置。")
    for name, pattern in REGION_GROUPS:
        add(f"{name} = url-test,url=http://www.gstatic.com/generate_204,interval=600,"
            f"tolerance=0,timeout=5,select=0,policy-regex-filter={pattern}")
    add("#")
    add("# 服务分组：默认策略 + 可手动切到某个地区组")
    for name, default in SERVICE_GROUPS:
        add(f"{name} = select,{default},PROXY,{','.join(REGIONS)},policy-select-name={default}")
    add("")

    add("[Rule]")
    add("# " + "-" * 70)
    add("#  ① 放行（来源：config/allowlist.txt）")
    add("#     小火箭从上到下匹配，所以放行必须放在最前面才有效。")
    add("#     注意：模块里的规则优先级高于配置文件，被模块拦掉的域名需要")
    add("#     在模块层解决（改 allowlist 重新构建，或单独停用对应的 per-App 模块）。")
    add("# " + "-" * 70)
    if allow.full or allow.sub_only:
        for d in sorted(allow.full):
            add(f"DOMAIN-SUFFIX,{d},DIRECT")
        for d in sorted(allow.sub_only):
            add(f"DOMAIN-WILDCARD,*.{d},DIRECT")
    else:
        add("#（当前放行名单为空）")
    add("")

    add("# " + "-" * 70)
    add("#  ② 去广告（本项目生成，全量版）")
    add(f"#     域名表 {human(stats.get('domains', 0))} 条；"
        f"想减少误杀可换成 lite 版（{human(stats.get('lite', 0))} 条）：")
    add(f"#     DOMAIN-SET,{r}/ruleset/{prefix}-domain-lite.list,REJECT")
    add("# " + "-" * 70)
    add(f"DOMAIN-SET,{r}/ruleset/{prefix}-domain.list,REJECT")
    add(f"RULE-SET,{r}/ruleset/{prefix}-rule.list,REJECT")
    add("")

    add("# " + "-" * 70)
    add("#  ③ 分流（引用 blackmatrix7 的分类规则集，保持上游每日更新）")
    add("# " + "-" * 70)
    for rule, policy in SERVICE_RULES:
        add(f"{rule},{policy}")
    add("")

    add("# ④ 兜底")
    add("GEOIP,CN,DIRECT")
    add("FINAL,PROXY")
    add("")

    add("[Host]")
    add("*.apple.com = server:system")
    add("*.icloud.com = server:system")
    add("localhost = 127.0.0.1")
    add("")

    add("[URL Rewrite]")
    add("^https?://(www.)?google.cn https://www.google.com 302")
    add("")

    add("[MITM]")
    add("# 只解密这些主机名。去广告模块会用 %APPEND% 把自己的主机名加进来，")
    add("# 所以这里保持最小即可 —— 解密的主机名越多越费电，也越容易触发证书校验。")
    add(f"hostname = {', '.join(mitm_hosts) or '*.google.cn'}")
    add("")

    write_text(path, "\n".join(L))
    return len(L)


def emit_private_example(path: Path) -> None:
    """给用户看的「私人覆盖」示例：不改仓库也能加白/加黑。"""
    write_text(path, "\n".join([
        "# " + "=" * 74,
        "#  私人覆盖示例（可选）",
        "#",
        "#  目的：不想每次上游更新都重新加一遍自己的规则时，把私人规则单独放一个文件。",
        "#",
        "#  用法一（推荐，最简单）：",
        "#    小火箭 → 配置 → 选中正在用的配置 → 点右侧 ⓘ → 编辑纯文本",
        "#    把自己的规则加到 [Rule] 段最上面，保存。",
        "#    注意：点「更新配置」会用远端文件覆盖本地改动，所以这条路适合临时用。",
        "#",
        "#  用法二（长期）：把下面的 [Rule] 段内容追加到你的 base.conf 里，",
        "#    并把这份文件放在本地（iCloud 或小火箭配置目录），",
        "#    在 base.conf 的 [General] 段加一行：",
        "#      include = private.conf",
        "#    小火箭支持 include，且被包含的配置优先。",
        "#    （include 的具体路径写法请以小火箭手册为准，不同版本可能有差异）",
        "# " + "=" * 74,
        "",
        "[Rule]",
        "# 示例：强制直连（放行）—— 放在最上面，优先级最高",
        "# DOMAIN-SUFFIX,某域名.com,DIRECT",
        "",
        "# 示例：追加拦截",
        "# DOMAIN-SUFFIX,某广告域名.com,REJECT",
        "",
        "# 示例：把某个服务固定走某个地区组",
        "# DOMAIN-SUFFIX,某服务.com,日本节点",
        "",
    ]))
