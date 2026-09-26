# 第三方脚本体检报告

生成时间：2026-09-26 07:16:55

共 83 个脚本，全部已抓取到本仓库 `vendor/` 目录，
所有 script-path 已改为指向本仓库 —— 上游删库或改路径都不会让规则失效。

结论含义：

- ✅ **安全**：只做响应体改写，或用的都是小火箭支持的 API
- ⚠️ **有风险**：依赖别家专有写法（如 Loon 的 `$argument` 对象取值），小火箭里可能取不到值
- ❌ **不兼容**：用了小火箭**没有**的 API（`$httpAPI`/`$task` 等），对应的去广告规则在小火箭里**不会生效**

| 脚本 | 兼容性 | 网络API | 大小 | 说明 |
| --- | --- | --- | --- | --- |
| `UnblockURLinWeChat.js` | ⚠️ 存疑 | 含 | 84.4KB | 第三方域名：spotify.link, web.archive.org, webcache.googleusercontent.com；$task 未加判断 —— QuantumultX 的 $task（小火箭没有 $task.fetch）（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；$ |
| `rrtv_json.js` | ⚠️ 存疑 | 含 | 25.4KB | 第三方域名：img.rr.tv；$prefs 未加判断 —— QuantumultX 的 $prefs（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；内含多客户端运行时，按当前客户端自动分派 |
| `youtube.response.js` | ⚠️ 存疑 | 含 | 129.9KB | $prefs 未加判断 —— QuantumultX 的 $prefs（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；含客户端探测（argument/loon/task），按客户端分派；使用 $httpClient（小火箭支持） |
| `meiyou_ads.js` | ⚠️ 存疑 | 含 | 13.6KB | $prefs 未加判断 —— QuantumultX 的 $prefs（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；内含多客户端运行时，按当前客户端自动分派；显式识别了小火箭（$rocket） |
| `miguvideo_ads.js` | ⚠️ 存疑 | 含 | 13.1KB | $prefs 未加判断 —— QuantumultX 的 $prefs（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；内含多客户端运行时，按当前客户端自动分派；显式识别了小火箭（$rocket） |
| `soul_ads.js` | ⚠️ 存疑 | 含 | 14.9KB | $prefs 未加判断 —— QuantumultX 的 $prefs（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；内含多客户端运行时，按当前客户端自动分派；显式识别了小火箭（$rocket） |
| `xiaohongshu.js` | ⚠️ 存疑 | 含 | 28.0KB | $prefs 未加判断 —— QuantumultX 的 $prefs（但脚本有客户端探测，大概率在对应分支内，建议实机确认）；内含多客户端运行时，按当前客户端自动分派；显式识别了小火箭（$rocket） |
| `bilibili.json.js` | ✅ 安全 | 无 | 18.9KB | ✓ 完全不含网络 API，只改写响应体；第三方域名：i0.hdslb.com, live.bilibili.com, member.bilibili.com；含客户端探测（argument/loon/request/response/task），按客户端分派 |
| `adsense.js` | ✅ 安全 | 无 | 2.3KB | ✓ 完全不含网络 API，只改写响应体；第三方域名：developers.adnet.qq.com, u.kuaishou.com, www.csjplatform.com |
| `keep.js` | ✅ 安全 | 无 | 12.1KB | ✓ 完全不含网络 API，只改写响应体；第三方域名：keepland.gotokeep.com, m.gotokeep.com, static1.keepcdn.com |
| `BahamutAnimeAds.js` | ✅ 安全 | 含 | 1.8KB | 第三方域名：api.gamer.com.tw；含客户端探测（httpClient/task），按客户端分派；使用 $httpClient（小火箭支持） |
| `bilibili.protobuf.request.js` | ✅ 安全 | 无 | 61.9KB | ✓ 完全不含网络 API，只改写响应体；第三方域名：bsbsb.top；含客户端探测（argument/loon/request/response/task），按客户端分派 |
| `bilibili.protobuf.response.js` | ✅ 安全 | 无 | 95.1KB | ✓ 完全不含网络 API，只改写响应体；含客户端探测（argument/environment/loon/request/response/task），按客户端分派；使用 $httpClient（小火箭支持） |
| `kuwo.js` | ✅ 安全 | 无 | 4.5KB | ✓ 完全不含网络 API，只改写响应体；第三方域名：image.kuwo.cn, vip1.kuwo.cn |
| `xjsp.js` | ✅ 安全 | 无 | 1.8KB | ✓ 完全不含网络 API，只改写响应体；第三方域名：www.aa2.app |
| `51job.js` | ✅ 安全 | 无 | 1.1KB | ✓ 完全不含网络 API，只改写响应体 |
| `airchina.js` | ✅ 安全 | 无 | 808B | ✓ 完全不含网络 API，只改写响应体 |
| `alicdn.js` | ✅ 安全 | 无 | 604B | ✓ 完全不含网络 API，只改写响应体 |
| `baidumap.js` | ✅ 安全 | 无 | 78.4KB | ✓ 完全不含网络 API，只改写响应体；内含多客户端运行时，按当前客户端自动分派 |
| `bilibiliManga.js` | ✅ 安全 | 无 | 2.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `ddxq.js` | ✅ 安全 | 无 | 1.8KB | ✓ 完全不含网络 API，只改写响应体 |
| `dianping.js` | ✅ 安全 | 无 | 2.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `dianyinglieshou.js` | ✅ 安全 | 无 | 1.1KB | ✓ 完全不含网络 API，只改写响应体 |
| `dict-youdao-ad.js` | ✅ 安全 | 无 | 1.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `fenbi.js` | ✅ 安全 | 无 | 826B | ✓ 完全不含网络 API，只改写响应体 |
| `flyert.js` | ✅ 安全 | 无 | 842B | ✓ 完全不含网络 API，只改写响应体 |
| `foliday.js` | ✅ 安全 | 无 | 972B | ✓ 完全不含网络 API，只改写响应体 |
| `freshippo.js` | ✅ 安全 | 无 | 2.0KB | ✓ 完全不含网络 API，只改写响应体 |
| `ithome.js` | ✅ 安全 | 无 | 1.3KB | ✓ 完全不含网络 API，只改写响应体 |
| `ltsst-ad.js` | ✅ 安全 | 无 | 869B | ✓ 完全不含网络 API，只改写响应体 |
| `mafengwo.js` | ✅ 安全 | 无 | 1.0KB | ✓ 完全不含网络 API，只改写响应体 |
| `mdb.js` | ✅ 安全 | 无 | 738B | ✓ 完全不含网络 API，只改写响应体 |
| `mlxx.js` | ✅ 安全 | 无 | 2.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `qmai.js` | ✅ 安全 | 无 | 2.0KB | ✓ 完全不含网络 API，只改写响应体 |
| `rednote.js` | ✅ 安全 | 无 | 14.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `soda.js` | ✅ 安全 | 无 | 220B | ✓ 完全不含网络 API，只改写响应体 |
| `tieba-proto.js` | ✅ 安全 | 无 | 94.8KB | ✓ 完全不含网络 API，只改写响应体；内含多客户端运行时，按当前客户端自动分派 |
| `tuhu.js` | ✅ 安全 | 无 | 2.5KB | ✓ 完全不含网络 API，只改写响应体 |
| `usmile.js` | ✅ 安全 | 无 | 739B | ✓ 完全不含网络 API，只改写响应体 |
| `wnbz.js` | ✅ 安全 | 无 | 604B | ✓ 完全不含网络 API，只改写响应体 |
| `zhangshanggongjiao.js` | ✅ 安全 | 无 | 688B | ✓ 完全不含网络 API，只改写响应体 |
| `12306.js` | ✅ 安全 | 无 | 357B | ✓ 完全不含网络 API，只改写响应体 |
| `51card.js` | ✅ 安全 | 无 | 536B | ✓ 完全不含网络 API，只改写响应体 |
| `555Ad.js` | ✅ 安全 | 无 | 360B | ✓ 完全不含网络 API，只改写响应体 |
| `Coolapk_Redirect.js` | ✅ 安全 | 无 | 369B | ✓ 完全不含网络 API，只改写响应体 |
| `PupuSplashAds.js` | ✅ 安全 | 无 | 1.8KB | ✓ 完全不含网络 API，只改写响应体 |
| `QuDa.js` | ✅ 安全 | 无 | 267B | ✓ 完全不含网络 API，只改写响应体 |
| `Smzdm.js` | ✅ 安全 | 无 | 3.1KB | ✓ 完全不含网络 API，只改写响应体 |
| `Spotify.Crack.Dev.js` | ✅ 安全 | 无 | 10.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `adrive.js` | ✅ 安全 | 无 | 1.1KB | ✓ 完全不含网络 API，只改写响应体 |
| `blued.js` | ✅ 安全 | 无 | 246B | ✓ 完全不含网络 API，只改写响应体 |
| `bohe_ads.js` | ✅ 安全 | 无 | 956B | ✓ 完全不含网络 API，只改写响应体 |
| `cainiao.js` | ✅ 安全 | 无 | 4.9KB | ✓ 完全不含网络 API，只改写响应体 |
| `caixinAd.js` | ✅ 安全 | 无 | 1.7KB | ✓ 完全不含网络 API，只改写响应体 |
| `ccbLifeAds.js` | ✅ 安全 | 无 | 674B | ✓ 完全不含网络 API，只改写响应体 |
| `cmschina.js` | ✅ 安全 | 无 | 408B | ✓ 完全不含网络 API，只改写响应体 |
| `cnftp.js` | ✅ 安全 | 无 | 30.9KB | ✓ 完全不含网络 API，只改写响应体 |
| `coolapk.js` | ✅ 安全 | 无 | 2.4KB | ✓ 完全不含网络 API，只改写响应体 |
| `didiAds.js` | ✅ 安全 | 无 | 2.7KB | ✓ 完全不含网络 API，只改写响应体 |
| `fly.js` | ✅ 安全 | 无 | 488B | ✓ 完全不含网络 API，只改写响应体 |
| `goofish.js` | ✅ 安全 | 无 | 8.7KB | ✓ 完全不含网络 API，只改写响应体 |
| `header.js` | ✅ 安全 | 无 | 2.8KB | ✓ 完全不含网络 API，只改写响应体；内含多客户端运行时，按当前客户端自动分派 |
| `huifutianxia_ads.js` | ✅ 安全 | 无 | 322B | ✓ 完全不含网络 API，只改写响应体 |
| `jingdong.js` | ✅ 安全 | 无 | 10.1KB | ✓ 完全不含网络 API，只改写响应体 |
| `jingxiAd.js` | ✅ 安全 | 无 | 285B | ✓ 完全不含网络 API，只改写响应体 |
| `lawson.js` | ✅ 安全 | 无 | 1.8KB | ✓ 完全不含网络 API，只改写响应体 |
| `lowertop.github.io_Shadowrocket-First_JS_baozimh.js` | ✅ 安全 | 无 | 3.3KB | ✓ 完全不含网络 API，只改写响应体 |
| `maimai_ads.js` | ✅ 安全 | 无 | 861B | ✓ 完全不含网络 API，只改写响应体 |
| `myBlockAds.js` | ✅ 安全 | 无 | 7.5KB | ✓ 完全不含网络 API，只改写响应体；含客户端探测（response），按客户端分派 |
| `qq-news.js` | ✅ 安全 | 无 | 2.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `quark.js` | ✅ 安全 | 无 | 13.9KB | ✓ 完全不含网络 API，只改写响应体 |
| `reddit.js` | ✅ 安全 | 无 | 742B | ✓ 完全不含网络 API，只改写响应体 |
| `req_replace_body.js` | ✅ 安全 | 无 | 353B | ✓ 完全不含网络 API，只改写响应体 |
| `smzdm_ads.js` | ✅ 安全 | 无 | 1.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `tieba-json.js` | ✅ 安全 | 无 | 9.7KB | ✓ 完全不含网络 API，只改写响应体 |
| `umetrip_ads.js` | ✅ 安全 | 无 | 215B | ✓ 完全不含网络 API，只改写响应体 |
| `vgtime.js` | ✅ 安全 | 无 | 292B | ✓ 完全不含网络 API，只改写响应体 |
| `wyres.js` | ✅ 安全 | 无 | 16.9KB | ✓ 完全不含网络 API，只改写响应体；含客户端探测（argument），按客户端分派 |
| `xiaotucc.js` | ✅ 安全 | 无 | 340B | ✓ 完全不含网络 API，只改写响应体 |
| `xmApp.js` | ✅ 安全 | 无 | 340B | ✓ 完全不含网络 API，只改写响应体 |
| `yx.js` | ✅ 安全 | 无 | 134B | ✓ 完全不含网络 API，只改写响应体 |
| `zhihu.js` | ✅ 安全 | 无 | 7.2KB | ✓ 完全不含网络 API，只改写响应体 |
| `zhuanzhuan.js` | ✅ 安全 | 无 | 1020B | ✓ 完全不含网络 API，只改写响应体 |

## 第三方域名清单

下面这些脚本里出现了 GitHub 之外的域名。**这不代表它们有问题** ——
多数是为了实现自己的功能（例如「解开微信里被屏蔽的链接」必须去查 archive.org）。
列出来是为了让你知道：**装了对应模块，这些域名会看到你的请求**。

| 脚本 | 涉及域名 |
| --- | --- |
| `BahamutAnimeAds.js` | api.gamer.com.tw |
| `UnblockURLinWeChat.js` | spotify.link, web.archive.org, webcache.googleusercontent.com |
| `adsense.js` | developers.adnet.qq.com, u.kuaishou.com, www.csjplatform.com |
| `bilibili.json.js` | i0.hdslb.com, live.bilibili.com, member.bilibili.com, www.bilibili.com |
| `bilibili.protobuf.request.js` | bsbsb.top |
| `keep.js` | keepland.gotokeep.com, m.gotokeep.com, static1.keepcdn.com |
| `kuwo.js` | image.kuwo.cn, vip1.kuwo.cn |
| `rrtv_json.js` | img.rr.tv |
| `xjsp.js` | www.aa2.app |

## 关于「数据会不会泄露」

静态检查**能证明**的是：

- 75 个脚本完全不含网络 API —— 它们只改写响应体，**没有外发数据的能力**；
- 全库**没有任何一处**「把请求/响应内容 POST 出去」的代码路径（检出 0 处）；
- 所有 script-path 已指向本仓库，上游偷偷改动会体现在 git 历史与构建报告里。

静态检查**不能替代**的是：人工审计每个含网络 API 的脚本到底发了什么。
更稳妥的做法是**只装你需要的 per-App 模块**，把解密范围从上千个主机名降到几个。
完整的风险说明见 `docs/安全说明.md`。

