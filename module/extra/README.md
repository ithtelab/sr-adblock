# 额外可选模块

这些模块**不属于去广告三层**，是额外功能，按需单独导入。
每个都做了脚本本地化与 MITM 补全，并保留了上游的参数声明。

## 怎么安装

和小火箭的其他模块一样：**配置 → 模块 → 右上角 + → 粘贴下面的链接**。

链接格式固定，换模块名即可：

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/<模块名>.srmodule
```

> ⚠️ 不要一次全装。装得越多，被解密的主机名越多、越费电。只装真正需要的。

## GitHub 体验包

| 模块 | 条目 | 脚本 | 参数 | 说明 |
| :-- | --: | --: | :--: | :-- |
| [`github-cdn`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/github-cdn.srmodule) | 4 | — | 有 | 把 raw.githubusercontent.com 的请求 302 到国内可用的 jsDelivr 镜像。**国内刚需** |
| [`github-no-zoom`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/github-no-zoom.srmodule) | 2 | 1 | — | 手机上逛 GitHub 时禁止页面缩放，浏览体验好很多 |
| [`github-pro`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/github-pro.srmodule) | 7 | 2 | 有 | 私有库/大文件加速。**14 个参数，装完要按需填写**（私库地址等） |

**本组链接（可直接复制）：**

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/github-cdn.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/github-no-zoom.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/github-pro.srmodule
```

## 单 App 增强

| 模块 | 条目 | 脚本 | 参数 | 说明 |
| :-- | --: | --: | :--: | :-- |
| [`cmcc-itv`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/cmcc-itv.srmodule) | 13 | — | 有 | 咪咕直播源（看电视直播）。引用了外部规则集，构建时会一并本地化 |
| [`deepseek`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/deepseek.srmodule) | 13 | — | 有 | DeepSeek App 的净化规则 |
| [`hongguo`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/hongguo.srmodule) | 7 | — | — | 红果免费短剧的去广告规则 |
| [`luckin`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/luckin.srmodule) | 4 | — | — | 瑞幸咖啡 App 的广告与弹窗处理 |
| [`netinfo`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/netinfo.srmodule) | 1 | 1 | 有 | 在 App 内查看当前出口 IP / 节点信息，排查网络问题时有用 |
| [`spotify`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/spotify.srmodule) | 6 | 2 | 有 | Spotify 去广告与歌词增强（含 2 个脚本） |
| [`youtube-noad`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/youtube-noad.srmodule) | 4 | 2 | 有 | 纯 JS 实现（binary-body-mode），无域名拦截。我们主模块里没有这个 |

**本组链接（可直接复制）：**

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/cmcc-itv.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/deepseek.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/hongguo.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/luckin.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/netinfo.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/spotify.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/youtube-noad.srmodule
```

## 境外卡 / WiFi Calling

| 模块 | 条目 | 脚本 | 参数 | 说明 |
| :-- | --: | --: | :--: | :-- |
| [`talkatone`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/talkatone.srmodule) | 97 | — | 有 | Talkatone 保号与通话优化（境外号玩家常用），97 条规则 |
| [`ultramobile-wificalling`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/ultramobile-wificalling.srmodule) | 19 | — | 有 | Ultra Mobile 的 Wi-Fi Calling 规则 |
| [`wificalling-hk`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/wificalling-hk.srmodule) | 25 | — | 有 | 香港 SIM 卡（CSL / CMHK / 3HK）的 Wi-Fi Calling 规则。模块内自带自动匹配香港节点的策略组 |
| [`wificalling-uk`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/wificalling-uk.srmodule) | 18 | — | 有 | 英国 SIM 卡的 Wi-Fi Calling 规则 |
| [`wificalling-us`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/wificalling-us.srmodule) | 20 | — | 有 | 美国 SIM 卡的 Wi-Fi Calling 规则 |

**本组链接（可直接复制）：**

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/talkatone.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/ultramobile-wificalling.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/wificalling-hk.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/wificalling-uk.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/wificalling-us.srmodule
```

## 插件生态

| 模块 | 条目 | 脚本 | 参数 | 说明 |
| :-- | --: | --: | :--: | :-- |
| [`plugin-hub2rocket`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/plugin-hub2rocket.srmodule) | 3 | — | — | 上面那个的精简版，**需要先装 Script-Hub 模块**。两个别同时装 |
| [`plugin2rocket`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/plugin2rocket.srmodule) | 8 | 4 | — | ★ 打通另一个生态：把「可莉插件中心」(hub.kelee.one) 的 Loon 插件，
在手机上**实时转换成小火箭模块**。已内嵌 Script-Hub 脚本，不需要额外装依赖。
 |

**本组链接（可直接复制）：**

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/plugin-hub2rocket.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/plugin2rocket.srmodule
```

## 系统

| 模块 | 条目 | 脚本 | 参数 | 说明 |
| :-- | --: | --: | :--: | :-- |
| [`no-ota`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/no-ota.srmodule) | 9 | — | — | ★ 很受欢迎的功能，但**和去广告是两回事**，所以做成独立模块。
想升级系统时把它停用就行。
 |

**本组链接（可直接复制）：**

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/no-ota.srmodule
```

## 证书 / 安全

| 模块 | 条目 | 脚本 | 参数 | 说明 |
| :-- | --: | --: | :--: | :-- |
| [`ca-module`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/ca-module.srmodule) | 5 | — | 有 | ★ 解决一个真实痛点：小火箭的 HTTPS 解密是**跟配置走**的，换一次配置就要重开一次。
装了它，把证书内容填进参数，解密状态就跟着模块走。
需要自己在「编辑参数」里粘贴证书内容（ca-p12）和密码。
 |
| [`vpn-detected`](https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/vpn-detected.srmodule) | 3 | — | 有 | 让 App 检测不到你在用代理（把检测用的域名跳过代理）。很多国内 App 会因代理检测报错 |

**本组链接（可直接复制）：**

```
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/ca-module.srmodule
https://raw.githubusercontent.com/ithtelab/sr-adblock/release/module/extra/vpn-detected.srmodule
```
