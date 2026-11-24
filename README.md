# 随机图片 API

一个部署在 **Cloudflare Pages** 上的静态随机图片服务：图片文件作为静态资源存放在项目内，通过 Pages Functions 按路径随机返回横屏、竖屏或全部图片。

无需数据库、无需服务器，图片由 Cloudflare 全球 CDN 直接分发，Functions 只负责随机选图并 302 跳转到静态文件。

## 功能

- 四种模式：随机（横屏 + 竖屏 + 动图混合）、横屏、竖屏、ACG 动图
- 默认 302 跳转到静态图片，走 CDN 缓存，速度快、不消耗函数流量
- 通过 `_routes.json` 限制只有 `/api/*` 走函数，静态图片等资源直接由 CDN 返回，节约 Functions 请求额度
- 支持 `type=json` 返回图片信息，便于前端按需取用
- 支持 `n=N` 一次取多张不重复图片
- 带 CORS 头，可跨域调用
- 图片清单自动生成，增删图片后一条命令即可更新

## 图片资源

所有资源统一为 **WebP** 格式，按三类分别独立编号，从 `1.webp` 开始递增：

| 类别 | 目录 | 编号范围 | 数量 | 格式 | 体积 |
| --- | --- | --- | --- | --- | --- |
| 横屏 | `images/landscape/` | `1.webp` ~ `1070.webp` | 1070 张 | WebP (q95 静态) | 约 0.80 GB |
| 竖屏 | `images/portrait/` | `1.webp` ~ `1926.webp` | 1926 张 | WebP (q95 静态) | 约 1.03 GB |
| ACG 动图 | `images/acg/` | `1.webp` ~ `50.webp` | 50 张 | animated WebP | 约 46 MB |
| **合计** | — | — | **3046 张** | — | **约 1.87 GB** |

- 三类各自从 1 开始编号、连续递增，互不影响。静态图采用有损 WebP（`quality=95`），动图为 animated WebP（640px / 10fps / q75，截取前 5 秒）。
- 横屏前 404 张、竖屏前 919 张为原始图；横屏 405~1070（666 张）、竖屏 920~1926（1007 张）为后追加图片（含 1 张从竖图目录纠正过来的横屏图）。
- 原视频（50 个 MP4）保留在 `14_ACG动图_acg/`，动图由视频转换而来。
- 图片按数字自然顺序整理（`1.webp`、`2.webp` … `1070.webp`），清单 likewise 按此顺序排列。
- `random` 模式返回全部 3046 个资源（含动图）；`/api/acg` 只返回 50 张动图。

## 项目结构

```
.
├── images/                    # 所有图片资源统一放在此目录
│   ├── landscape/             # 横屏：1.webp ~ 1070.webp（1070 张）
│   ├── portrait/              # 竖屏：1.webp ~ 1926.webp（1926 张）
│   └── acg/                   # ACG 动图：1.webp ~ 50.webp（50 张，animated WebP）
├── 01_PC横图_pc/              # 后添加的横图源文件（已导入 images/）
├── 02_移动竖图_mp/            # 后添加的竖图源文件（已导入 images/）
├── 14_ACG动图_acg/            # 50 个原始 MP4 视频（保留）
├── functions/
│   ├── api/
│   │   ├── index.js           # /api 接口说明
│   │   └── [mode].js          # 核心动态路由（random / landscape / portrait / acg）
│   └── _lib/
│       └── manifest.js        # 自动生成的图片清单（下划线目录不会被当作路由）
├── scripts/
│   ├── generate-manifest.mjs      # 清单生成脚本
│   ├── convert_to_webp.py         # 原始图片转无损 WebP + 按序重命名
│   ├── compress_images.py         # 图片压缩为有损 WebP(q95)
│   ├── import_new_images.py       # 新图片续接编号导入
│   └── convert_videos_to_webp.py  # MP4 视频转 animated WebP
├── _routes.json               # 路由白名单：仅 /api 走函数，图片等静态资源跳过
├── README.md
```

## 接口用法

部署后假设域名为 `https://your-project.pages.dev`：

| 路径 | 说明 |
| --- | --- |
| `/api/random` | 随机返回一张资源（横屏 + 竖屏 + 动图，共 3046 个） |
| `/api/landscape` | 随机返回一张横屏图片 |
| `/api/portrait` | 随机返回一张竖屏图片 |
| `/api/acg` | 随机返回一张 ACG 动图（animated WebP） |
| `/api` | 查看接口说明与图片数量 |

直接用浏览器或 `<img>` 标签访问即可显示随机图片：

```html
<img src="https://your-project.pages.dev/api/random" alt="随机图片">
```

```bash
curl -i https://your-project.pages.dev/api/portrait
# HTTP/2 302
# location: /images/portrait/123.webp
```

### 访问固定图片

图片作为静态资源存放，可绕过 Functions、直接通过路径访问某张固定的图片（内容固定不变，不随机）：

```
/images/landscape/1.webp      # 第 1 张横屏图
/images/portrait/1926.webp    # 第 1926 张竖屏图
/images/acg/1.webp            # 第 1 张 ACG 动图（浏览器会播放动画）
```

完整 URL 示例：`https://your-project.pages.dev/images/landscape/1.webp`。路径不存在时返回 404。这类请求由 CDN 直接返回，不消耗 Functions 额度。

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
  "total": 3046,
  "images": [
    { "file": "images/landscape/42.webp", "url": "https://…/images/landscape/42.webp" }
  ]
}
```

### 模式别名

`landscape` 可用 `heng`、`horizontal`；`portrait` 可用 `shu`、`vertical`；`acg` 可用 `dongtu`、`gif`；`random` 可用 `all`。

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

这样 3046 个资源（含动图）无论访问量多大都不消耗 Functions 额度，只有调用随机接口时才计费。若后续新增其他静态目录（如 `favicon.ico` 等），同样可以把路径加入 `exclude`。

## 本地运行

需要安装 [Node.js](https://nodejs.org/) 和 Wrangler：

```bash
npm install -g wrangler
wrangler pages dev . --local
```

启动后访问 `http://localhost:8788/api/random`。若端口不同，以终端输出为准。

## 部署到 Cloudflare Pages

两种方式均可，**构建命令留空**（纯静态 + Functions，无需构建）：

1. **直接上传**：在 Cloudflare 控制台 → Workers & Pages → 创建 Pages 项目 → 上传整个项目目录。
2. **连接 Git 仓库**：连接后同样无需构建命令，Cloudflare 会自动识别 `functions/` 目录并启用函数。

> 提示：`images/` 总量约 1.87GB（静态图 q95 + 动图），另有原始 MP4 视频约 0.57GB 保留在 `14_ACG动图_acg/`。若不想上传视频源文件，部署前可从上传目录移除该文件夹（动图已生成在 `images/acg/`，不影响 API）。`_routes.json` 需保存在项目根目录才生效。

## 增删图片后更新清单

Functions 无法直接读取文件系统，图片路径预先写在 `functions/_lib/manifest.js` 中。新增或删除图片后执行：

```bash
node scripts/generate-manifest.mjs
```

脚本会重新扫描三个目录（`landscape`、`portrait`、`acg`）并输出最新清单：

```
已生成 functions\_lib\manifest.js
横屏 1070 张，竖屏 1926 张，动图 50 张，共 3046 张
```

如使用 Git 部署，提交更新后的清单即可生效。图片统一放在 `images/` 下，子目录名固定为 `landscape`（横屏）、`portrait`（竖屏）、`acg`（动图），修改目录名需同步修改脚本中的 `relDir` 常量。

## 图片处理脚本

处理分两个阶段，均依赖 Pillow（`pip install Pillow`，需支持 WebP），且都采用「先写临时目录、校验通过后替换」的安全流程，支持断点续转。

**阶段一：原始图片 → 无损 WebP + 按顺序重命名**（仅在处理原始 JPG/PNG 时需要）

```bash
python scripts/convert_to_webp.py --workers 12    # 转换到临时目录
python scripts/convert_to_webp.py --apply          # 校验后替换，命名为 1.webp ~ N.webp
```

- 横竖两类独立编号，各自从 `1.webp` 递增。

**阶段二：压缩体积 → 有损 WebP(q95)**（当前项目已处于此阶段结果）

```bash
python scripts/compress_images.py --quality 95 --workers 12   # 压缩到临时目录
python scripts/compress_images.py --apply                      # 校验后替换
```

- 保持 `1.webp ~ N.webp` 文件名不变，`--quality` 可调。
- 每次替换图片后需重新运行 `node scripts/generate-manifest.mjs` 更新清单。

**阶段三：导入新图片（续接编号）**

```bash
python scripts/import_new_images.py           # 预演，打印导入计划
python scripts/import_new_images.py --apply   # 实际导入
```

- 把 `01_PC横图_pc/`（横图）与 `02_移动竖图_mp/`（竖图）导入 `images/`，接着已有最大编号递增。
- 按图片实际方向分类（竖图目录里混入的横屏图会纠正到 landscape）；已是 WebP 的直接复制避免二次编码，非 WebP 的转 q95。源文件目录保留。

**阶段四：MP4 视频转 animated WebP 动图**

```bash
pip install imageio-ffmpeg Pillow
python scripts/convert_videos_to_webp.py
```

- 把 `14_ACG动图_acg/` 的 50 个 MP4 转为 `images/acg/1.webp ~ 50.webp`，原视频保留。
- 参数：截取前 5 秒、宽度 640px、10fps、q75；单文件 0.34~1.67MB，远低于 Cloudflare 25MB 限制。
- 依赖 `imageio-ffmpeg` 提供的 ffmpeg。

> 当前共 3046 个资源（1070 横屏 + 1926 竖屏 + 50 动图），`images/` 约 1.87GB；`random` 含全部，`/api/acg` 仅动图。

## 常见问题

- **图片不显示**：确认静态图片可通过 `https://域名/images/landscape/1.webp` 直接访问；Cloudflare 对单文件有 25MB 限制，超大图片需压缩。
- **总是同一张图**：重定向响应已设置 `Cache-Control: no-store`，正常情况下每次请求都会随机。若前面套了自定义缓存层，请检查缓存规则。
- **想返回图片二进制而非跳转**：把 `[mode].js` 中的 302 分支改为 `fetch(new URL('/' + file, request.url))` 并返回图片，但会占用 Functions 请求数并失去 CDN 直出优势。
