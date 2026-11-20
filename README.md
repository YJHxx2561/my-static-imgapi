# 随机图片 API

一个部署在 **Cloudflare Pages** 上的静态随机图片服务：图片文件作为静态资源存放在项目内，通过 Pages Functions 按路径随机返回横屏、竖屏或全部图片。

无需数据库、无需服务器，图片由 Cloudflare 全球 CDN 直接分发，Functions 只负责随机选图并 302 跳转到静态文件。

## 功能

- 三种模式：随机（横竖混合）、横屏、竖屏
- 默认 302 跳转到静态图片，走 CDN 缓存，速度快、不消耗函数流量
- 通过 `_routes.json` 限制只有 `/api/*` 走函数，静态图片等资源直接由 CDN 返回，节约 Functions 请求额度
- 支持 `type=json` 返回图片信息，便于前端按需取用
- 支持 `n=N` 一次取多张不重复图片
- 带 CORS 头，可跨域调用
- 图片清单自动生成，增删图片后一条命令即可更新

## 项目结构

```
.
├── images/                    # 所有图片资源统一放在此目录
│   ├── landscape/             # 横屏图片（404 张）
│   └── portrait/              # 竖屏图片（919 张）
├── functions/
│   ├── api/
│   │   ├── index.js           # /api 接口说明
│   │   └── [mode].js          # 核心动态路由（random / landscape / portrait）
│   └── _lib/
│       └── manifest.js        # 自动生成的图片清单（下划线目录不会被当作路由）
├── scripts/
│   └── generate-manifest.mjs  # 清单生成脚本
├── _routes.json               # 路由白名单：仅 /api 走函数，图片等静态资源跳过
├── 合集.7z                    # 原始图片压缩包（保留，部署时可排除）
└── README.md
```

## 接口用法

部署后假设域名为 `https://your-project.pages.dev`：

| 路径 | 说明 |
| --- | --- |
| `/api/random` | 随机返回一张图片（横屏 + 竖屏） |
| `/api/landscape` | 随机返回一张横屏图片 |
| `/api/portrait` | 随机返回一张竖屏图片 |
| `/api` | 查看接口说明与图片数量 |

直接用浏览器或 `<img>` 标签访问即可显示随机图片：

```html
<img src="https://your-project.pages.dev/api/random" alt="随机图片">
```

```bash
curl -i https://your-project.pages.dev/api/portrait
# HTTP/2 302
# location: /images/portrait/xxxx.jpg
```

### 查询参数

| 参数 | 说明 | 示例 |
| --- | --- | --- |
| `type=json` | 返回 JSON 图片信息，而不是 302 跳转 | `/api/random?type=json` |
| `n=5` | 取 5 张不重复图片（返回 JSON 列表） | `/api/landscape?n=5` |

`type=json` 返回示例：

```json
{
  "mode": "random",
  "count": 1,
  "total": 1323,
  "images": [
    { "file": "images/landscape/0381c302baf7023a0a8097ce134e3663.jpg", "url": "https://…/images/landscape/0381c302baf7023a0a8097ce134e3663.jpg" }
  ]
}
```

### 模式别名

`landscape` 可用 `heng`、`horizontal`；`portrait` 可用 `shu`、`vertical`；`random` 可用 `all`。

## 节约 Functions 请求（_routes.json）

Cloudflare Pages 默认会让所有请求都调用 Functions。项目根目录的 `_routes.json` 把函数限定在接口路径上：

```json
{
  "version": 1,
  "include": ["/api", "/api/*"],
  "exclude": ["/images/*"]
}
```

- `include`：只有 `/api`（说明页）和 `/api/xxx`（随机接口）会调用 Functions。
- `exclude`：显式排除 `/images/*` 下的所有图片，直接由 CDN 返回，不产生函数请求。
- `exclude` 优先级高于 `include`；规则上限合计 100 条。

这样 1323 张图片无论访问量多大都不消耗 Functions 额度，只有调用随机接口时才计费。若后续新增其他静态目录（如 `favicon.ico` 等），同样可以把路径加入 `exclude`。

## 本地运行

需要安装 [Node.js](https://nodejs.org/) 和 Wrangler：

```bash
npm install -g wrangler
wrangler pages dev . --local
```

启动后访问 `http://localhost:8788/api/random`。若端口不同，以终端输出为准。

## 部署到 Cloudflare Pages

两种方式均可，**构建命令留空**（纯静态 + Functions，无需构建）：

1. **直接上传**：在 Cloudflare 控制台 → Workers & Pages → 创建 Pages 项目 → 上传 `dist` 之外的整个项目目录。上传前建议把 `合集.7z` 移到项目外，避免上传约 2GB 的压缩包。
2. **连接 Git 仓库**：连接后同样无需构建命令，Cloudflare 会自动识别 `functions/` 目录并启用函数。

> 提示：`合集.7z` 为原始备份，已解压为 `images/landscape/` 与 `images/portrait/`。部署时可将其从上传目录中移除以加快上传；本地保留即可。`_routes.json` 需保存在项目根目录（即上传/构建输出的根目录）才能生效。

## 增删图片后更新清单

Functions 无法直接读取文件系统，图片路径预先写在 `functions/_lib/manifest.js` 中。新增或删除图片后执行：

```bash
node scripts/generate-manifest.mjs
```

脚本会重新扫描两个图片目录并输出最新清单：

```
已生成 functions\_lib\manifest.js
横屏 404 张，竖屏 919 张，共 1323 张
```

如使用 Git 部署，提交更新后的清单即可生效。图片统一放在 `images/` 下，子目录名固定为 `landscape`（横屏）和 `portrait`（竖屏），修改目录名需同步修改脚本中的 `relDir` 常量。

## 常见问题

- **图片不显示**：确认静态图片可通过 `https://域名/images/landscape/xxx.jpg` 直接访问；Cloudflare 对单文件有 25MB 限制，超大图片需压缩。
- **总是同一张图**：重定向响应已设置 `Cache-Control: no-store`，正常情况下每次请求都会随机。若前面套了自定义缓存层，请检查缓存规则。
- **想返回图片二进制而非跳转**：把 `[mode].js` 中的 302 分支改为 `fetch(new URL('/' + file, request.url))` 并返回图片，但会占用 Functions 请求数并失去 CDN 直出优势。
