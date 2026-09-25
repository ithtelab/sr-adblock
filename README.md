# sr-adblock — 自维护的小火箭去广告规则工厂

把 5 个上游开源项目的去广告规则**抓下来 → 检查 → 去重 → 修正 → 整合**，
产出三层可直接被 Shadowrocket（小火箭）使用的东西，每天自动重建。

**本仓库不含任何节点、订阅、账号信息，只有规则。**

---

## 一、三层结构

| 层 | 产物 | 作用 | 要装证书吗 |
| --- | --- | --- | --- |
| ① 域名层 | `ruleset/ad-domain.list`（28.6 万条）+ `ruleset/ad-rule.list` | 按域名拦截广告请求，能拦掉大部分广告 | 不用 |
| ② 模块层 | `module/ads-all.srmodule` + `module/httpdns.srmodule` | 改响应体、去开屏广告、拦 HTTPDNS，管前面拦不住的 | **要** |
| ③ 配置层 | `conf/base.conf` | 代理分组 + 分流规则，把 ①② 接起来 | — |

三层互相独立，可以只装其中一层。
**建议先只装 ① 跑几天**，确认没有误杀、日常使用正常，再上 ② ——
② 要开 HTTPS 解密，风险高一些（部分 App 会因此异常）。

## 二、装哪几个文件

最省事的组合，装这三个：

```
配置：https://raw.githubusercontent.com/ithtelab/sr-adblock/release/conf/base.conf
模块：https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/ads-all.srmodule
模块：https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/httpdns.srmodule
```

### 安装步骤

1. **加配置**：小火箭 → 底部「配置」→ 右上角 `+` → 粘贴上面配置的链接 → 下载
   → 点击该配置「使用配置」。
2. **加节点**：底部「首页」→ 添加你自己的节点/订阅。
   `base.conf` 里**没有任何节点**；地区分组按节点名自动归类，换订阅也不用改配置。
3. **装证书**（只装 ① 可跳过）：
   「配置」→ 点正在用的配置右侧 ⓘ → 「HTTPS 解密」→ 生成新的 CA 证书 → 安装证书
   → 去 iOS「设置」安装描述文件 → 「通用 → 关于本机 → 证书信任设置」里打开**完全信任**。
4. **加模块**：「配置」→「模块」→ 右上角 `+` → 粘贴上面两个模块的链接。
5. 断开重连一次小火箭让规则生效。

> **只用域名层、不装证书**：把 `base.conf` 换成你自己的配置，
> 在 `[Rule]` 段最上面加这两行就行：
> ```
> DOMAIN-SET,https://raw.githubusercontent.com/ithtelab/sr-adblock/release/ruleset/ad-domain.list,REJECT
> RULE-SET,https://raw.githubusercontent.com/ithtelab/sr-adblock/release/ruleset/ad-rule.list,REJECT
> ```

### 其他产物

| 文件 | 什么时候用 |
| --- | --- |
| `ruleset/ad-domain-lite.list` | 只收录**被 2 个以上独立上游都认定**的广告域名（6 万条，是全量的 1/5）。怕误杀就用它替换 `ad-domain.list` |
| `module/apps/*.srmodule` | 726 个 per-App 模块。某个 App 出问题时单独停用它，不用整体关掉去广告；也可以**只装你在意的几个 App**，MITM 主机名最少、最省电 |
| `module/anti-mitm` 思路 | 银行等有证书校验的 App：不是加白名单，而是**不让它走解密**（见 `config/sources.yaml` 的 `lowertop-anti-mitm`） |
| `conf/private.example.conf` | 私人覆盖怎么写（不想每次被上游更新覆盖自己的规则时看它） |

小火箭会自动更新这些订阅（模块默认 1–7 天，配置同理）。
**前提**：iOS「设置 → 通用 → 后台 App 刷新」要对小火箭开启。

---

## 三、出问题了怎么办

### 某个 App 功能异常 / 图片裂 / 打不开

先用排查工具查**是哪个域名被拦**：

```bash
python src/lookup.py api.example.com        # 查这个域名是否被拦、被谁拦、怎么放行
python src/lookup.py api.example.com --deep # 顺带查是哪个上游收录了它
```

它直接告诉你：被哪个产物拦了、命中的是哪条规则、**该往 allowlist 加哪一行**。
把那一行加进 `config/allowlist.txt` 重新构建即可。

放行名单对**三层同时生效**：域名层会剔除该域名、模块层里对应的拦截规则也会剔除、
`base.conf` 里会生成优先级最高的 DIRECT 规则。

> 注意：小火箭里**模块的规则优先级高于配置文件**，所以如果只改配置不改模块，
> 是拦不住模块里那 2800 条规则的 —— 这也是 allowlist 必须作用于模块层的原因。

### 想临时放行、不想重新构建

小火箭 → 配置 → 选中正在用的配置 → ⓘ → 「编辑纯文本」，
把你的 `DOMAIN-SUFFIX,某域名.com,DIRECT` 加到 `[Rule]` 段**最上面**，保存。
缺点：点「更新配置」会被远端文件覆盖，适合临时用。长期方案见 `dist/conf/private.example.conf`。

---

## 四、相比直接用上游，这套产物改了什么

上游都是有价值的项目，但各自有坑。本项目每次构建都会在
`build-report.md` / `build-report-scripts.md` / `build-report-verify.md`
里逐条报告实际改动：

**去重与修正**

1. **删掉 167 条上游重复规则**。可莉的模块由 731 个 per-App 文件合并而成，
   合并脚本有个 bug：5 个 App（闲鱼 / 小红书 / 知乎 / 网易云音乐 / 云快充）
   在两个目录下各存了一份近似但不相同的文件，两份都被并了进去。
2. **补回 18 条 SR 版缺失的规则**。可莉的 Surge 版比小火箭版新（CSDN、财新等域名），
   已从 Surge 版补齐；另外 4,700 条只是书写格式差异（`status-code=200`、pattern 加引号），
   已识别为**语义重复，不会重复导入**。
3. **删掉 1 条脏数据**。Surge 版 `[URL Rewrite]` 里混进了一条 `hostname - reject` 残句，
   它会被当成「任何 URL 里含 hostname 就拦截」的正则。已按段落语法校验剔除。
4. **补全 8 个参数声明**。模块里脚本引用了 `logLevel`、`sponsorBlock`、
   `per_filter_video_thread` 等 8 个参数占位符，但上游 `#!arguments` 只声明了一个
   **没人引用**的空开关 `12306_enable`。已从上游 Loon V2 版插件（那里有完整声明）
   取默认值补全，同时丢掉那个空开关。
5. **83 个第三方脚本全部本地化**。上游模块有 1/4 的规则依赖 12 个第三方仓库里的脚本，
   上游改路径或删文件就会**静默失效**（规则还在、脚本 404、广告照常出现，没有任何提示）。
   可莉自己就踩过这个坑（2026-09-10 的提交正是「迁移被删除的美丽修行脚本到本仓库」）。
   现在全部抓进 `vendor/`，路径改指本仓库，并且每次构建用条件请求复查上游更新。
6. **脚本兼容性体检**。这些脚本是 Loon/Surge/QX 多客户端共用的，里面可能用到
   小火箭没有的 API。构建时逐个静态扫描，结果见 `build-report-scripts.md`
   （当前：76 个安全、7 个存疑、0 个不兼容）。
7. **三层用同一份放行名单**，修掉「改了配置但模块还在拦」的问题。
8. **父域压缩**：`.a.b.com` 已覆盖 `a.b.com` 及其子域，冗余的子域条目全部删除，
   并把来源归属上交给父域（这样"两个独立来源都认定"的精简版判定才不会漏）。
9. **策略与选项归一**：上游 `Reject`/`reject`/`REJECT` 混用已统一；
   同一规则在不同来源里差一个 `no-resolve` 选项的（91 条），取并集而不是报冲突。
10. **域名层来源取最新**：Johnshall 项目 `build` 分支里的 `ad.list` 已冻结在
    2025-02-08，必须取 `release` 分支的每日产物 —— 这类"看起来一样但不能用"的坑，
    本项目已绕开并写在 `config/sources.yaml` 的注释里。

**还有一道自检门禁**（`build-report-verify.md`），每次构建都检查：
产物段落名是否合法、规则类型是否都在小火箭支持范围内、脚本是否全部本地化且文件存在、
配置引用是否有效、**产物里是否混进了节点密码/订阅令牌**（公开仓库的底线）、
以及规则数相比上次是否暴跌（上游挂掉的典型征兆，跌超过 20% 直接让构建失败）。

---

## 五、怎么维护

### 日常：什么都不用做

GitHub Actions 每天北京时间 10:00 自动重建并发布到 `release` 分支
（比 Johnshall 的 8:00 晚，等它先更新完）。小火箭会自己拉新版本。

### 改行为：改 `config/` 下的文件

| 文件 | 作用 |
| --- | --- |
| `config/allowlist.txt` | **放行名单，你最常改的就是它**。`foo.com` = 放行该域名及所有子域；`*.foo.com` = 只放行子域 |
| `config/blocklist-extra.txt` | 自己想额外拦的域名 |
| `config/sources.yaml` | 增删上游来源（每个来源都有注释说明它的坑） |
| `config/options.yaml` | 构建选项：是否产出精简版、精简版门槛、是否本地化脚本、MITM 数量阈值、订阅根地址 |

改完在 GitHub 上点一下 Actions 的 `Run workflow`，或本地跑：

```bash
python src/build.py                # 全量构建（联网，带缓存）
python src/build.py --offline      # 只用本地缓存，不联网
python src/build.py --refresh      # 强制重下所有上游
python src/build.py --layer domain # 只构建域名层
python src/lookup.py <域名>        # 排查某个域名为什么被拦
```

### 本地跑构建

```bash
pip install pyyaml          # 唯一的依赖
python src/build.py
```

Python 3.11+（用到 `tomllib` 之外的标准库特性，3.11 起都行；实测 3.12）。

---

## 六、目录说明

```
config/     配置源：上游清单、放行名单、构建选项   ← 你要改的
src/        构建工具
  build.py      构建入口（三层编排 + 报告）
  parse.py      各上游格式 → 统一中间表示
  merge.py      合并/去重/父域压缩/放行名单
  module.py     模块解析、语义去重、脏数据校验、参数解析
  emit_*.py     域名层/模块层/配置层的产物输出
  vendor.py     第三方脚本本地化与兼容性体检
  apps.py       per-App 模块生成
  verify.py     产物自检门禁
  lookup.py     误杀排查工具（你日常最常用的）
vendor/     本地化的第三方脚本（构建产出，不入库）
dist/       构建产出（发布到 release 分支）
cache/      上游原始文件缓存（不入库）
```

分支分工：`main` 只放源码与配置；`release` 只放产物，
每天以单个 orphan 提交强推（不然 28 万行文件每天累积会把仓库撑爆）。

---

## 七、常见问题

**Q：装完没效果？**
① 确认小火箭的「全局路由」是**配置**模式 —— 模块里的规则只在配置模式下生效。
② 确认 HTTPS 解密已开启且证书被**完全信任**（只装描述文件不信任是没用的）。
③ 部分 App 要清缓存或重装才生效（上游作者的原话）。
④ 看 `build-report-verify.md` 确认产物本身没问题。

**Q：会不会拖慢网速？**
域名匹配在小火箭里是编译成搜索树 + 哈希缓存的（Johnshall 与 SR 作者交流后记录在案，
但这是社区转述、非官方文档，所以只对域名类规则可信）。
`URL-REGEX` 是正则扫描、`IP-CIDR` 未带 `no-resolve` 时还要额外解析域名，这两类是真实的开销来源。
本项目已给能带的 IP 规则都加了 `no-resolve`。

**Q：为什么 `ad-rule.list` 和模块里都有域名规则？**
两层的定位不同：`ad-rule.list` 是**长尾**（28 万条，域名的兜底），
模块里那 2800 条是**最高优先级**（模块规则优先于配置，所以广告域名不会被你的分流规则放走）。
重复不会导致重复拦截，只是层级分工。

**Q：MITM 主机名 946 个会不会太多？**
iOS 15 以下小火箭的内存预算只有 15MB，主机名太多会出现「模块失效」或「VPN 自动断开」。
所以本项目：① 构建时超过 1000 个会告警；② 提供 726 个 per-App 模块，
你只装需要的几个 App，主机名能降到几十个。

**Q：会不会收集/上传我的信息？**
不会。仓库里只有规则。构建时只做一件事：从各上游的公开 URL 下载文本。
唯一的"外发"是……没有。所有产物都在你自己的机器和你的仓库里。

---

## 八、许可与署名

本项目的构建代码是 MIT。整合的规则来自多个上游，各有各的许可
（blackmatrix7 是 GPL-2.0、Johnshall 是 CC-BY-SA-4.0、部分项目未声明许可），
**逐源署名与说明见 [NOTICE](NOTICE)**。

如果你打算二次分发本项目产物，请先读 NOTICE 里的许可说明。
