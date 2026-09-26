# 构建报告

- 生成时间：2026-09-26 07:16:55
- 耗时：22.6 秒

## ① 域名层

- 合计：**286,135** 条（精确 16,274 + 含子域 269,861）
- 其他规则：387 条

## 上游拉取

| 来源 | 大小 | 状态 | 备注 |
| --- | --- | --- | --- |
| blackmatrix7 | 5,767,475 B | 下载 |  |
| johnshall | 2,371,741 B | 下载 |  |
| fmz200 | 103,295 B | 缓存 |  |
| iab0x00 | 31,383 B | 缓存 |  |
| lowertop | 8,254 B | 缓存 |  |

## 各来源贡献

| 来源 | 精确域名 | 含子域 | 其他规则 | 备注 |
| --- | --- | --- | --- | --- |
| blackmatrix7 • Advertising 广告规则集 | 16,234 | 269,029 | 207 |  |
| Johnshall • 仅去广告规则（每日 8:00 重建） | 0 | 59,565 | 128 |  |
| 可莉/奶思 • rejectAd 去广告列表 | 329 | 2,194 | 130 | 跳过复合规则 1 条；无效条目 4 条 |
| iab0x00 • Block 轻量去广告 | 309 | 781 | 13 | 无效条目 1 条 |
| LOWERTOP • AntiAD 自用去广告 | 61 | 129 | 14 | 无效条目 1 条 |
| 本仓库自建黑名单（config/blocklist-extra.txt） | 0 | 0 | 0 |  |

## 去重与压缩

- 父域压缩删除冗余条目：1,342 条
- 放行名单剔除：3 条
  - `wxa.wxs.qq.com`（exact）
  - `wxs.qq.com`（exact）
  - `wxsnsdythumb.wxs.qq.com`（suffix）
- 精简版（≥2 个来源）：60,768 条

## 规则选项合并（非冲突）

同一规则被多个来源定义，仅选项不同，已取并集（`no-resolve` 对 IP 类规则是更安全的选择）：

- `IP-CIDR,154.7.80.158/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,162.252.214.4/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,167.206.10.148/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,167.99.31.227/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.135/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.137/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.139/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.140/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.150/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.152/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.199/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.2/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.228/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.248/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.252/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.254/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,172.255.6.59/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,174.123.15.43/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,188.42.84.110/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- `IP-CIDR,188.42.84.137/32` 选项取并集 → no-resolve（blackmatrix7 + johnshall）
- ...（还有 71 条）

## ② 模块层

- 产物：`dist/module/ads-all.srmodule`（4,539 条）、`dist/module/httpdns.srmodule`（161 条）
- MITM 主机名：**1,010** 个
- 去重删除上游重复条目：176 条（上游合并脚本的 bug 产物）
- 用 Surge 版补齐 SR 版缺失：18 条（另有 4,700 条仅书写格式不同、语义重复，未重复导入）
- 脚本本地化：231 条规则的 script-path 已改指本仓库
- HTTPDNS 模块剔除与主模块重复：22 条

### 各段条目数

| 段落 | 条数 |
| --- | --- |
| `[Rule]` | 2,857 |
| `[Header Rewrite]` | 1 |
| `[URL Rewrite]` | 534 |
| `[Body Rewrite]` | 113 |
| `[Map Local]` | 802 |
| `[Script]` | 231 |
| `[MITM]` | 1 |

### MITM 主机名修复

- 检查了 827 个规则涉及的主机名，其中 71 个**该解密却没声明**（规则永远不执行）
- 已自动补上：64 个
- **金融守卫拦下 7 个**（银行/券商/支付类默认不自动开解密，避免你登录不了或交易失败）。确认没问题再手动加进 `config/mitm-extra.txt`：

  - `api.futunn.com`（命中关键词 `futunn`）
  - `apid.futunn.com`（命中关键词 `futunn`）
  - `creditcard.bankcomm`（命中关键词 `bank`）
  - `creditcardapp.bankcomm`（命中关键词 `bank`）
  - `emdcadvertise.eastmoney.com`（命中关键词 `eastmoney`）
  - `firefly.abchina.com.cn`（命中关键词 `abchina`）
  - `images.cib.com.cn`（命中关键词 `cib.`）

### 额外可选模块（非去广告）

共 20 / 20 个，按分组列在 `dist/module/extra/README.md`。统一做了脚本本地化、外部规则集本地化（1 处）、MITM 主机名补全（0 个）、脏数据剔除（0 条）。

| 模块 | 分组 | 条目 | 脚本 | 说明 |
| --- | --- | --: | --: | --- |
| `github-cdn.srmodule` | GitHub 体验包 | 4 | — | 把 raw.githubusercontent.com 的请求 302 到国内可用的 jsDelivr 镜像。**国内刚 |
| `github-no-zoom.srmodule` | GitHub 体验包 | 2 | 1 | 手机上逛 GitHub 时禁止页面缩放，浏览体验好很多 |
| `github-pro.srmodule` | GitHub 体验包 | 7 | 2 | 私有库/大文件加速。**14 个参数，装完要按需填写**（私库地址等） |
| `cmcc-itv.srmodule` | 单 App 增强 | 13 | — | 咪咕直播源（看电视直播）。引用了外部规则集，构建时会一并本地化 |
| `deepseek.srmodule` | 单 App 增强 | 13 | — | DeepSeek App 的净化规则 |
| `hongguo.srmodule` | 单 App 增强 | 7 | — | 红果免费短剧的去广告规则 |
| `luckin.srmodule` | 单 App 增强 | 4 | — | 瑞幸咖啡 App 的广告与弹窗处理 |
| `netinfo.srmodule` | 单 App 增强 | 1 | 1 | 在 App 内查看当前出口 IP / 节点信息，排查网络问题时有用 |
| `spotify.srmodule` | 单 App 增强 | 6 | 2 | Spotify 去广告与歌词增强（含 2 个脚本） |
| `youtube-noad.srmodule` | 单 App 增强 | 4 | 2 | 纯 JS 实现（binary-body-mode），无域名拦截。我们主模块里没有这个 |
| `talkatone.srmodule` | 境外卡 / WiFi Calling | 97 | — | Talkatone 保号与通话优化（境外号玩家常用），97 条规则 |
| `ultramobile-wificalling.srmodule` | 境外卡 / WiFi Calling | 19 | — | Ultra Mobile 的 Wi-Fi Calling 规则 |
| `wificalling-hk.srmodule` | 境外卡 / WiFi Calling | 25 | — | 香港 SIM 卡（CSL / CMHK / 3HK）的 Wi-Fi Calling 规则。模块内自带自动匹配香港节点的策 |
| `wificalling-uk.srmodule` | 境外卡 / WiFi Calling | 18 | — | 英国 SIM 卡的 Wi-Fi Calling 规则 |
| `wificalling-us.srmodule` | 境外卡 / WiFi Calling | 20 | — | 美国 SIM 卡的 Wi-Fi Calling 规则 |
| `plugin-hub2rocket.srmodule` | 插件生态 | 3 | — | 上面那个的精简版，**需要先装 Script-Hub 模块**。两个别同时装 |
| `plugin2rocket.srmodule` | 插件生态 | 8 | 4 | ★ 打通另一个生态：把「可莉插件中心」(hub.kelee.one) 的 Loon 插件， |
| `no-ota.srmodule` | 系统 | 9 | — | ★ 很受欢迎的功能，但**和去广告是两回事**，所以做成独立模块。 |
| `ca-module.srmodule` | 证书 / 安全 | 5 | — | ★ 解决一个真实痛点：小火箭的 HTTPS 解密是**跟配置走**的，换一次配置就要重开一次。 |
| `vpn-detected.srmodule` | 证书 / 安全 | 3 | — | 让 App 检测不到你在用代理（把检测用的域名跳过代理）。很多国内 App 会因代理检测报错 |

### per-App 可选模块

- 产出 **726** 个（归并自上游 731 个 split 文件，同名变体已合并去重）
- 额外本地化 per-App 专用脚本：0 个（0B）

索引见 `dist/module/apps/README.md`。

### 脚本体检

共 83 个第三方脚本：✅ 安全 76 个、⚠️ 存疑 7 个、❌ 不兼容 0 个、下载失败 0 个，合计 876.9KB

**网络安全审计**：75 个脚本完全不含网络 API（只改写响应体，没有外发数据的能力）；8 个含网络 API；9 个出现了第三方域名；「把请求/响应内容 POST 出去」的代码路径：**0 个**。

「不兼容」表示脚本**无条件**调用了小火箭没有的 API（如 `$httpAPI`），对应的去广告规则在小火箭里不会生效；「存疑」多是有客户端判断保护、但写法上值得看一眼的。**这是静态检查，不能替代真机验证。**

完整清单见 `build-report-scripts.md`。

## 产物

| 文件 | 条数 |
| --- | --- |
| dist/ruleset/ad-domain.list | 286,135 |
| dist/ruleset/ad-rule.list | 387 |
| dist/ruleset/ad-domain-lite.list | 60,768 |
| dist/module/ads-all.srmodule | 4,539 |
| dist/module/httpdns.srmodule | 161 |

## 告警

- ⚠️ 从上游剔除 1 条格式不合法的条目（详见报告）
- ℹ️ 7 个脚本用了别家专有写法，是否需要处理请见 build-report-scripts.md
- ℹ️ 9 个脚本出现了第三方域名（清单见 build-report-scripts.md 的「网络安全审计」）

