<div align="center">

# 🧹 sr-adblock

**自维护的小火箭去广告规则工厂**

把上游项目的规则抓下来 → 体检 → 去重 → 修正 → 整合，
每天自动重建，产出 Shadowrocket 可以直接订阅的三层产物。

[![build](https://github.com/ithtelab/sr-adblock/actions/workflows/build.yml/badge.svg)](https://github.com/ithtelab/sr-adblock/actions/workflows/build.yml)
[![最近构建](https://img.shields.io/github/last-commit/ithtelab/sr-adblock/release?label=%E6%9C%80%E8%BF%91%E6%9E%84%E5%BB%BA)](https://github.com/ithtelab/sr-adblock/commits/release)
![广告域名](https://img.shields.io/badge/%E5%B9%BF%E5%91%8A%E5%9F%9F%E5%90%8D-28.6%E4%B8%87-2ea44f)
![适配 App](https://img.shields.io/badge/%E8%A6%86%E7%9B%96%20App-726%20%E6%AC%BE-blue)
![平台](https://img.shields.io/badge/%E5%B9%B3%E5%8F%B0-iOS%20%C2%B7%20%E5%B0%8F%E7%81%AB%E7%AE%AD-black)
![不支持](https://img.shields.io/badge/%E4%B8%8D%E6%94%AF%E6%8C%81-Android%20%2F%20%E5%AE%89%E5%8D%93-red)
[![协议](https://img.shields.io/badge/%E5%8D%8F%E8%AE%AE-MIT-yellow)](LICENSE)

**本仓库不含任何节点、订阅、账号信息 —— 只有规则。**

> ## ⚠️ 只支持 iOS + 小火箭（Shadowrocket）
>
> **不支持安卓，也不支持 iPhone 上的其他代理 App**（Clash / sing-box / v2rayNG / Quantumult X 都读不了）。
>
> 原因很简单：产物的语法是小火箭（和 Surge 系）专用的 ——
> 配置里用了 `policy-regex-filter`、`DOMAIN-SET`、`%APPEND%`，
> 模块是 `.srmodule`（重写 / 脚本 / MITM 那套），规则集是"有类型、无策略列"的写法。
> **安卓客户端一种都读不了。**
>
> 而且更根本的问题是：**安卓上做不了"去开屏广告"这类能力** ——
> Clash / Mihomo 没有 HTTPS 解密（MITM），sing-box 不支持脚本，
> 所以本项目的模块层（改响应体、去开屏广告）在安卓上没有对应实现。
>
> 安卓能用的只有"按域名拦截"这一部分，而且必须**转换格式**
> （Clash 要 YAML 的 `payload:`，sing-box 要 JSON，AdGuard 是 `||domain^`）。
> 本项目的上游（blackmatrix7、fmz200）都提供安卓格式，可以去那里取现成的。
> 详见 [常见问题 → 我是安卓，能用吗](#-常见问题)。

</div>

---

## ⚡ 三条链接，复制即用

<table>
<tr><td width="90"><b>配置</b></td><td><code>https://raw.githubusercontent.com/ithtelab/sr-adblock/release/conf/base.conf</code></td></tr>
<tr><td><b>模块</b></td><td><code>https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/ads-all.srmodule</code></td></tr>
<tr><td><b>模块</b></td><td><code>https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/httpdns.srmodule</code></td></tr>
</table>

装法见 [🚀 安装](#-安装)。`base.conf` 里**没有任何节点**，导入后自己加订阅即可 ——
地区分组会按节点名自动归类，**换订阅不用改配置**。

---

## 📖 写在前面 —— 请保护好自己

> 这个位置，之前换过两棒人。
>
> 最早是 [h2y](https://github.com/h2y) 的 Shadowrocket-ADBlock-Rules，他把小火箭的规则
> 划分得细致精美；他停更之后，[Johnshall](https://github.com/Johnshall) 接手，
> 一路维护到今天，做到每天北京时间 8:00 自动更新。
>
> 我们是第三棒。我们不打算做第四个"规则合集"—— 网络上不缺合集。
> 我们做的是把前面几棒的成果**验证、去重、修正**，
> 因为把它们的产物直接叠加起来，会互相打架（[具体冲突见这里](#-我们相比上游改了什么)）。

### 先说说「信息」这件事

我们往往以为自己在打破信息的壁垒，其实打破的可能是保护自己的那道屏障。

外面的世界并不比里面更「中立」。任何平台、任何媒体、任何看起来开放的公共讨论场，
背后都有它自己的利益结构和叙事框架；它们也常常把平等、自由这类旗号挂在最显眼的地方
—— 但旗号本身说明不了内容是否可信。真正值得警惕的，是那种听起来「天然正确」、
让你觉得不必再动脑子的说法：那种潜移默化的影响，比明着骗你更有力。

但另一面同样成立：既然外面有这个问题，我们身边也不是没有。
**所以唯一靠得住的不是某个网站、某个工具、某个「消息源」，而是你自己保留独立判断的习惯。**

遇到任何观点 —— 包括我上面这一段 —— 都值得先问一句：这是谁说的、为什么这么说、对他有什么好处。
如果你发现自己容易被某一套说法推着走，那么不管那套说法来自哪一边，
建议先退回到自己熟悉的地方，把判断力找回来再说。

本项目的规则只提供给大家用于更便捷地学习和工作。它只是文本规则，
**不提供、也不宣传任何观点**，没有能力带你「翻墙」，只定义了哪些域名直连、哪些走代理。
如果你对上面这些话持相反意见，这个项目可能不适合你 —— 规则本身只是工具，用不用由你。

### 具体到这个项目，请务必保护好自己

这句话放在这里，是因为这个项目要做的事，
本质上就是**让一个 App 解密你的 HTTPS 流量**。

你为了去掉开屏广告，会把银行、支付、社交、办公的流量一并交给它。
这不是危言耸听，这是 MITM 的固有代价：

- 开了 HTTPS 解密，就意味着被解密的那些域名，内容对你手机上的小火箭是**明文**的。
- iOS 15 以下小火箭的内存预算只有 15MB，MITM 主机名塞太多会出现「模块失效」甚至「VPN 自动断开」。所以本项目把去广告拆成 **726 个 per-App 模块**——**只装你在意的几个 App**，是既省电又安全的选择。
- 银行、券商、涉及工作机密的 App，**不要解密**。用 [`mitm-exclude.srmodule`](#-出问题了怎么办) 把它们排除掉。域名层（不需要证书的那一层）通常就够拦掉它们的广告了。
- 你的节点信息、订阅链接、截图里露出的服务器地址，**不要发到公开的地方**。本项目在构建时会自动扫一遍产物，确认没有节点密码混进去才会发布。

规则是为了让你用得更舒服，不是让你把身家性命交出去。
**能不开解密就不开，能少解密一个域名就少解密一个 —— 这是本项目的默认取向：**
三层互相独立，你可以只喝第一层（域名层，不碰证书）。

> ### 🔒 想知道"数据会不会泄露"？→ [**看这份安全说明**](docs/安全说明.md)
>
> 它把风险分成三层讲清楚，并且给出**可验证**的依据：这个仓库会不会上传你的数据、
> 域名层为什么天然安全、模块层的风险边界到底有多大、83 个脚本的网络行为审计结果
> （**75 个完全不含网络 API**、**0 处"把内容 POST 出去"的代码路径**、
> 9 个出现第三方域名的脚本逐个列出），以及**按安全性从高到低的四种装法**。
> 那份文档里还有"怎么自己验证、不用信作者"的方法。

本项目的所有产物都只是**文本规则**，它不会、也没有能力给你"魔法上网"。
它只定义哪些域名该直连、哪些该走代理、哪些该拦掉。

---

## 🗂 三层结构

```
① 域名层（不需要证书）
     ad-domain.list           285,799   拦掉大部分广告
     ad-domain-lite.list       60,148   只收被 2 个以上上游都认定的域名，怕误杀用这个
     ad-rule.list                 387   IP / 关键词 / 正则
                     ↓   装完这层就够用很久，可以先只装它
② 模块层（需要证书）
     ads-all.srmodule           4,504   改响应体、去开屏广告
     httpdns.srmodule             161   拦 HTTPDNS 绕行（必需配套）
     apps/*.srmodule              726   per-App 模块，出事时的逃生通道
     mitm-exclude.srmodule          —   排除解密的域名（银行类用）
                     ↓
③ 配置层（可选）
     base.conf                      —   代理分组 + 分流规则，节点订阅自填
```

| 层 | 作用 | 要装证书吗 |
| :-- | :-- | :--: |
| **① 域名层** | 按域名拦截广告请求，能拦掉大部分广告 | ❌ |
| **② 模块层** | 改响应体、去开屏广告、拦 HTTPDNS，管前面拦不住的 | ✅ |
| **③ 配置层** | 代理分组 + 分流规则，把 ①② 接起来 | — |

三层互相独立，可以只装其中一层。
**建议先只装 ① 跑几天**，确认没有误杀、日常使用正常，再上 ②。

---

## 🚀 安装

> ### 👉 第一次用、不熟悉小火箭？[**看这份图文教程，跟着点就行 →**](docs/新手安装.md)
>
> 它会先让你确认自己属于哪种情况（有没有节点订阅、要不要开屏广告拦截），
> 然后只给你看你那一节的步骤，不需要懂技术。

下面是简版（给已经熟悉小火箭的人）：

### 1. 加配置

小火箭 → 底部 <kbd>配置</kbd> → 右上角 <kbd>+</kbd> → 粘贴配置链接 → 下载
→ 点击该配置「使用配置」。

### 2. 加节点

底部 <kbd>首页</kbd> → 添加你自己的节点/订阅。
`base.conf` 里**没有任何节点**；地区分组按节点名自动归类，换订阅也不用改配置。

### 3. 装证书（只装 ① 可跳过）

「配置」→ 点正在用的配置右侧 <kbd>ⓘ</kbd> → 「HTTPS 解密」→ 生成新的 CA 证书 → 安装证书
→ 去 iOS「设置」安装描述文件 → **「通用 → 关于本机 → 证书信任设置」里打开「完全信任」**。

> ⚠️ 只装描述文件、不在「证书信任设置」里打开完全信任，是最常见的"装了没用"原因。

### 4. 加模块

「配置」→「模块」→ 右上角 <kbd>+</kbd> → 粘贴模块链接。

### 5. 断开重连一次小火箭，让规则生效。

<details>
<summary><b>只用域名层、不装证书的写法（点开）</b></summary>

把你自己的配置打开，在 `[Rule]` 段**最上面**加这两行：

```
DOMAIN-SET,https://raw.githubusercontent.com/ithtelab/sr-adblock/release/ruleset/ad-domain.list,REJECT
RULE-SET,https://raw.githubusercontent.com/ithtelab/sr-adblock/release/ruleset/ad-rule.list,REJECT
```

</details>

<details>
<summary><b>如果 raw 链接拉不动（国内网络常见，点开）</b></summary>

`raw.githubusercontent.com` 在国内经常连不上或时断时续。两种办法：

1. **让小火箭自己走代理去拉（推荐）**：小火箭请求规则集 URL 时本来就会走它自己的隧道，
   只要节点通就能拉到。加载失败时在「配置 → 规则集URL」里点重新下载。
2. **换镜像地址**：把链接里的
   `raw.githubusercontent.com/ithtelab/sr-adblock/release/`
   换成 `cdn.jsdelivr.net/gh/ithtelab/sr-adblock@release/`：

   ```
   https://cdn.jsdelivr.net/gh/ithtelab/sr-adblock@release/ruleset/ad-domain.list
   ```

   jsDelivr 有缓存延迟（通常几小时），更新不如 raw 及时。
   也可以改 `config/options.yaml` 里的 `repo_url`，让产物里的说明跟着变。

</details>

---

## 🧰 全部产物

| 文件 | 规模 | 什么时候用 |
| :-- | --: | :-- |
| `ruleset/ad-domain.list` | 285,799 | 域名层全量。默认用它 |
| `ruleset/ad-domain-lite.list` | 60,148 | **只收录被 2 个以上独立上游都认定的域名**。怕误杀就用它替换全量 |
| `ruleset/ad-rule.list` | 387 | IP / 关键词 / 正则类规则，域名表放不下这些，两个要一起引用 |
| `module/ads-all.srmodule` | 4,504 | 去广告总模块。**日常只装这一个**，不要叠加别的去广告模块 |
| `module/httpdns.srmodule` | 161 | 阻止 App 绕过代理自己解析域名。**必需配套**，已剔除与总模块的重复 |
| `module/mitm-exclude.srmodule` | 预置 45 个 | **银行 / 券商 / 支付 / 办公 App 一律装它**（已预置域名，装上就生效，装在模块列表**最下方**）。要加自己的在「编辑参数」里填 `-域名` |
| `module/apps/*.srmodule` | 726 个 | per-App 模块。**只装你在意的几个 App**，MITM 主机名最少、最省电 |
| `conf/base.conf` | — | 配置骨架：代理分组 + 分流 + 引用上面两层 |
| `conf/private.example.conf` | — | 私人覆盖怎么写（不想每次被上游更新覆盖自己的规则时看它） |

小火箭会自动更新这些订阅（模块默认 1–7 天）。
**前提**：iOS「设置 → 通用 → 后台 App 刷新」要对小火箭开启。

---

## 🩺 出问题了怎么办

### 某个 App 功能异常 / 图片裂 / 打不开

先用排查工具查**是哪个域名被拦**：

```bash
python src/lookup.py api.example.com        # 查它是否被拦、被谁拦、怎么放行
python src/lookup.py api.example.com --deep # 顺带查是哪个上游收录了它
```

它直接告诉你：被哪个产物拦了、命中的是哪条规则、**该往 allowlist 加哪一行**。
把那一行加进 `config/allowlist.txt` 重新构建即可。

放行名单对**三层同时生效**：域名层会剔除、模块层里对应的拦截规则也会剔除、
`base.conf` 里会生成优先级最高的 DIRECT 规则。

<details>
<summary><b>为什么必须作用于模块层？（点开）</b></summary>

小火箭里**模块的规则优先级高于配置文件**。所以如果只改配置不改模块，
拦不住模块里那 2800 条规则 —— 这正是很多"加了白名单还是打不开"的原因。

</details>

### 想临时放行、不想重新构建

小火箭 → 配置 → 选中正在用的配置 → <kbd>ⓘ</kbd> → 「编辑纯文本」，
把你的 `DOMAIN-SUFFIX,某域名.com,DIRECT` 加到 `[Rule]` 段**最上面**。
缺点：点「更新配置」会被远端文件覆盖，适合临时用。

---

## 🔧 我们相比上游改了什么

上游都是有价值的项目，但各自有坑。把它们的产物**直接叠加会互相打架** ——
本项目每次构建都会在 `build-report.md` 里逐条报告实际改动：

<details open>
<summary><b>去重与修正（点开看细节）</b></summary>

1. **删掉 167 条上游重复规则**。可莉的模块由 731 个 per-App 文件合并而成，
   合并脚本有个 bug：5 个 App（闲鱼 / 小红书 / 知乎 / 网易云音乐 / 云快充）
   在两个目录下各存了一份近似但不相同的文件，两份都被并了进去。
2. **补回 18 条 SR 版缺失的规则**。可莉的 Surge 版比小火箭版新（CSDN、财新等域名），
   已从 Surge 版补齐；另外 4,700 条只是书写格式差异（`status-code=200`、pattern 加引号），
   已识别为**语义重复，不会重复导入** —— 否则产物会虚胖一倍。
3. **删掉 1 条脏数据**。Surge 版 `[URL Rewrite]` 里混进了一条 `hostname - reject` 残句，
   会被当成「任何 URL 里含 hostname 就拦截」的正则。已按段落语法逐条校验剔除。
4. **补全 8 个参数声明**。模块里脚本引用了 `logLevel`、`sponsorBlock`、
   `per_filter_video_thread` 等 8 个占位符，上游 `#!arguments` 却只声明了一个
   **没人引用**的空开关 `12306_enable`。默认值已从上游 Loon V2 版插件（那里有完整声明）取回。
5. **83 个第三方脚本全部本地化**。上游约 1/4 的规则依赖 12 个第三方仓库的脚本，
   上游改路径或删文件就会**静默失效**（规则还在、脚本 404、广告照常出现，没有任何提示）。
   可莉自己就踩过这个坑（2026-09-10 的提交正是「迁移被删除的美丽修行脚本到本仓库」）。
   现在全部抓进 `vendor/`、路径改指本仓库，且每次构建用条件请求复查上游更新。
6. **脚本兼容性体检**（上游没人做过）。这些脚本是 Loon/Surge/QX 多客户端共用的，
   里面可能用到小火箭没有的 API。构建时逐个静态扫描并在
   `build-report-scripts.md` 出报告（当前：**76 安全 / 7 存疑 / 0 不兼容**）。
7. **三层用同一份放行名单**，修掉「改了配置但模块还在拦」的问题。
8. **父域压缩**：`.a.b.com` 已覆盖 `a.b.com` 及其子域，冗余子域条目全部删除，
   并把来源归属上交给父域（这样"两个独立来源都认定"的精简版判定才不会漏）。
9. **策略与选项归一**：上游 `Reject`/`reject`/`REJECT` 混用已统一；
   同一规则在不同来源里只差一个 `no-resolve` 选项的（91 条），取并集而不是报冲突。
10. **域名层来源取最新**：Johnshall 项目 `build` 分支里的 `ad.list` 已冻结在
    2025-02-08，必须取 `release` 分支的每日产物 —— 这类"看起来一样但不能用"的坑，
    本项目已绕开并写在 `config/sources.yaml` 的注释里。

</details>

<details>
<summary><b>还有一道自检门禁（点开看检查项）</b></summary>

每次构建结束都会跑一遍，报告在 `build-report-verify.md`：

- ✅ 产物段落名是否合法、有没有混进小火箭不支持的段落（`[Panel]` 之类）
- ✅ 规则类型是否都在小火箭支持范围内
- ✅ 脚本是否全部本地化、被引用的文件是否真实存在
- ✅ 配置里引用的产物是否都真的产出了
- ✅ **产物里有没有混进节点密码 / 订阅令牌**（公开仓库的底线）
- ✅ 规则数相比上次是否暴跌（上游挂掉的典型征兆，跌超 20% 直接让构建失败、**不发布**）

</details>

> 🔧 **想知道这些修复具体是怎么做出来的？** 看 **[实现原理](docs/实现原理.md)** ——
> 讲清了数据流水线、五个不显然的算法（父域压缩的归属上交、语义去重、
> MITM 主机名反推与金融守卫、放行名单的三层生效、ETag 条件请求）、自检门禁的设计，
> 以及每条链路上踩过的坑。**想改这个项目、或想判断它可不可信，看那份。**

---

## 🔨 怎么维护

### 日常：什么都不用做

GitHub Actions 每天**北京时间 10:00** 自动重建并发布到 `release` 分支
（比 Johnshall 的 8:00 晚两小时 —— 等它先更新完，否则永远拿到前一天的数据）。
小火箭会自己拉新版本。

### 改行为：只改 `config/` 下的文件

| 文件 | 作用 |
| :-- | :-- |
| `config/allowlist.txt` | **放行名单，你最常改的就是它**。`foo.com` = 放行该域名及所有子域；`*.foo.com` = 只放行子域 |
| `config/blocklist-extra.txt` | 自己想额外拦的域名 |
| `config/sources.yaml` | 增删上游来源（每个来源都注明了它有什么坑） |
| `config/options.yaml` | 构建选项：精简版开关与门槛、是否本地化脚本、MITM 数量阈值、订阅根地址 |

改完在 GitHub Actions 页面点 <kbd>Run workflow</kbd>，或本地跑：

```bash
pip install pyyaml     # 唯一依赖，Python 3.11+
python src/build.py                # 全量构建（联网，带缓存）
python src/build.py --offline      # 只用本地缓存
python src/build.py --refresh      # 强制重下所有上游
python src/build.py --layer domain # 只构建域名层
python src/lookup.py <域名>        # 排查某个域名为什么被拦
```

---

## 📁 目录说明

```
config/     配置源：上游清单、放行名单、构建选项          ← 你要改的
docs/       文档：[新手安装](docs/新手安装.md) · [安全说明](docs/安全说明.md) · [实现原理](docs/实现原理.md)
src/        构建工具（3,100 行 Python）
  build.py      构建入口：三层编排 + 报告
  parse.py      各上游格式 → 统一中间表示
  merge.py      合并 / 去重 / 父域压缩 / 放行名单
  module.py     模块解析、语义去重、脏数据校验、参数解析
  emit_*.py     域名层 / 模块层 / 配置层的产物输出
  vendor.py     第三方脚本本地化与兼容性体检
  apps.py       per-App 模块生成
  verify.py     产物自检门禁
  lookup.py     误杀排查工具（日常最常用）
vendor/     本地化的第三方脚本（构建产出，不入库）
dist/       构建产出（发布到 release 分支）
cache/      上游原始文件缓存（不入库）
```

**分支分工**：`main` 只放源码与配置；`release` 只放产物，
每天以单个 orphan 提交强推 —— 不然 28 万行的域名表每天全量提交，会把仓库历史撑爆。

---

## ❓ 常见问题

<details>
<summary><b>我是安卓手机，能用吗？</b></summary>

**不能。** 产物的语法是小火箭/Surge 系专用的：

| 产物 | 用的东西 | 安卓能读吗 |
| :-- | :-- | :-- |
| `conf/base.conf` | `[Proxy Group]` + `policy-regex-filter`、`DOMAIN-SET`、`RULE-SET` | ❌ |
| `module/*.srmodule` | 模块格式（`[URL Rewrite]`/`[Body Rewrite]`/`[Map Local]`/`[Script]`/`[MITM]`） | ❌ |
| `ruleset/*.list` | 有规则类型、无策略列的规则集写法 | ❌（格式不同） |

**更根本的问题是：安卓上做不了"去开屏广告"。**
这一层的原理是让 App 解密 HTTPS 流量再改写响应体，而：
- **Clash / Mihomo 没有 MITM**（不解密就改不了内容）
- **sing-box 不支持脚本**
- v2rayNG 等只做分流

所以安卓能用的只有**按域名拦截**（也就是本项目的①域名层），而且必须先转格式：
Clash 要 YAML 的 `payload:`、sing-box 要 JSON、AdGuard 用 `||domain^`。

**安卓用户建议**：直接去上游找现成的安卓格式，别转换本项目的产物：
- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的 `rule/Clash/Advertising/` —— 同一个源，Clash YAML
- 它的 `rule/AdGuard/Advertising/Advertising.txt` —— 就是 AdGuard 语法
- Clash 用户还可以用 `rule-providers` 直接订阅 YAML

> 顺带说明：本项目**能不能**支持安卓？技术上可以新增一层输出（域名层的域名是通用的，
> 转成 Clash YAML / sing-box JSON 就行），但它只覆盖①域名层，
> 带来不了任何"去开屏广告"的能力 —— 而后者才是本项目的重点。
> 如果你需要，可以提 issue，我评估要不要做。

</details>

<details>
<summary><b>我是 iPhone，但用的是 Clash / Quantumult X / Stash，能用吗？</b></summary>

**不能直接使用。** 本项目只针对 **Shadowrocket（小火箭）** 输出：
`.srmodule` 模块、`DOMAIN-SET`/`RULE-SET` 写法、`policy-regex-filter` 这些分组参数，
都是小火箭/Surge 的语法。

Quantumult X 的重写要用 `[rewrite_local]` + `url ... jsonjq-response-body` 那种写法，
Clash / Stash 用 YAML —— 都和小火箭不同，**没有测试过、也不保证可用**。

**Surge**（iOS/macOS）格式和小火箭最接近，本项目的模块内容理论上能被 Surge 读，
但**没有测试过**，不要当成支持。

如果你用的是 Loon / QX，去可莉（fmz200）那边找对应格式，他同时维护了
`Loon/plugin/`、`QuantumultX/rewrite/` 的同类产物。

</details>

<details>
<summary><b>装完没效果？</b></summary>

1. 确认小火箭「全局路由」是**配置**模式 —— 模块里的规则只在配置模式下生效。
2. 确认 HTTPS 解密已开启**且证书被完全信任**（只装描述文件不信任是没用的）。
3. 部分 App 要清缓存或重装才生效（上游作者的原话）。
4. 看 `build-report-verify.md` 确认产物本身没问题。

</details>

<details>
<summary><b>会不会拖慢网速？</b></summary>

域名匹配在小火箭里是编译成搜索树 + 哈希缓存的（Johnshall 与 SR 作者交流后记录在案，
属于社区转述而非官方文档，所以只对域名类规则可信）。
`URL-REGEX` 是正则扫描、`IP-CIDR` 未带 `no-resolve` 时还要额外解析域名，
这两类是真实的开销来源。本项目已给能带的 IP 规则都加了 `no-resolve`。

</details>

<details>
<summary><b>为什么 ad-rule.list 和模块里都有域名规则？</b></summary>

两层的定位不同：`ad-rule.list` 是**长尾兜底**（28 万条域名），
模块里那 2800 条是**最高优先级**（模块规则优先于配置，所以广告域名不会被你的分流规则放走）。
重复不会导致重复拦截，只是层级分工。

</details>

<details>
<summary><b>MITM 主机名 946 个会不会太多？</b></summary>

会。iOS 15 以下小火箭内存预算只有 15MB，主机名太多会出现「模块失效」或「VPN 自动断开」。
所以本项目：① 构建时超过 1000 个会告警；② 提供 726 个 per-App 模块，
只装需要的几个 App，主机名能降到几十个。

</details>

<details>
<summary><b>会不会收集/上传我的信息？</b></summary>

不会。仓库里只有规则。构建时只做一件事：从各上游的公开 URL 下载文本。
唯一的"外发"是……没有。所有产物都在你自己的机器和你的仓库里。

</details>

---

## 📜 许可与署名

构建代码是 MIT。整合的规则来自多个上游，各有各的许可
（blackmatrix7 是 GPL-2.0、Johnshall 是 CC-BY-SA-4.0、部分项目未声明许可），
**逐源署名与说明见 [NOTICE](NOTICE)**。二次分发前请先读它。

<div align="center">
<sub>如果这个项目帮到了你，给上游点个 Star —— 规则是他们写的，我们只是把它们整理干净。</sub>
</div>
