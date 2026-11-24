// Cloudflare Pages Function：随机图片接口
// 路由：/api/random  /api/landscape  /api/portrait
// 详见项目根目录 README.md

import { LANDSCAPE, PORTRAIT, ACG, VIDEO, ALL, COUNT } from '../_lib/manifest.js';

const POOLS = {
  random: ALL,          // 横屏 + 竖屏 + 动图（不含视频）
  landscape: LANDSCAPE,
  portrait: PORTRAIT,
  acg: ACG,             // 仅动图（animated WebP）
  video: VIDEO,         // 仅视频（MP4）
  // 常用别名，方便记忆与兼容
  heng: LANDSCAPE,
  horizontal: LANDSCAPE,
  shu: PORTRAIT,
  vertical: PORTRAIT,
  dongtu: ACG,
  gif: ACG,
  shipin: VIDEO,
  mp4: VIDEO,
  all: ALL,
};

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': '*',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...CORS_HEADERS,
    },
  });
}

// 从数组中随机取一项
function pickOne(pool) {
  return pool[Math.floor(Math.random() * pool.length)];
}

// 无重复地随机取 n 项（n 大于池容量时返回全部并打乱）
function pickMany(pool, n) {
  const copy = [...pool];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, Math.min(n, copy.length));
}

export async function onRequestGet(context) {
  const { request, params } = context;
  const url = new URL(request.url);
  const mode = (params.mode || 'random').toLowerCase();
  const pool = POOLS[mode];

  if (!pool) {
    return json({
      error: '未知模式',
      message: `模式 "${mode}" 不存在`,
      availableModes: ['random', 'landscape', 'portrait', 'acg', 'video'],
      example: '/api/random',
    }, 404);
  }

  if (pool.length === 0) {
    return json({ error: '图片池为空，请检查清单是否已生成' }, 503);
  }

  const type = (url.searchParams.get('type') || '').toLowerCase();
  const nParam = Number(url.searchParams.get('n'));
  const n = Number.isFinite(nParam) && nParam > 0 ? Math.floor(nParam) : 0;

  // JSON 模式：返回图片信息而非重定向
  if (type === 'json') {
    const origin = url.origin;
    const toItem = (file) => ({
      file,
      url: `${origin}/${file}`,
    });
    return json({
      mode,
      count: n > 0 ? Math.min(n, pool.length) : 1,
      total: pool.length,
      images: n > 0 ? pickMany(pool, n).map(toItem) : [toItem(pickOne(pool))],
    });
  }

  // 默认模式：302 重定向到静态图片，由 Cloudflare CDN 直接提供文件
  if (n > 1) {
    // 批量模式无法用单次重定向表达，返回 JSON 列表
    const origin = url.origin;
    return json({
      mode,
      count: Math.min(n, pool.length),
      total: pool.length,
      images: pickMany(pool, n).map((file) => ({ file, url: `${origin}/${file}` })),
    });
  }

  const file = pickOne(pool);
  return new Response(null, {
    status: 302,
    headers: {
      Location: `/${file}`,
      // 避免 CDN/浏览器缓存重定向结果，保证每次都是随机图
      'Cache-Control': 'no-store, no-cache, must-revalidate',
      'X-Image-Mode': mode,
      ...CORS_HEADERS,
    },
  });
}

// 支持跨域预检请求
export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}
