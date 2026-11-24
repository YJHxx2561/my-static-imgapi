// /api 接口说明页

import { COUNT } from '../_lib/manifest.js';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': '*',
};

export async function onRequestGet(context) {
  const origin = new URL(context.request.url).origin;
  const data = {
    name: '随机图片 API',
    description: '根据路径返回横屏、竖屏或随机图片',
    availableImages: COUNT,
    endpoints: [
      {
        path: '/api/random',
        description: '随机返回一张图片（横屏 + 竖屏 + 动图）',
        example: `${origin}/api/random`,
      },
      {
        path: '/api/landscape',
        description: '随机返回一张横屏图片',
        example: `${origin}/api/landscape`,
      },
      {
        path: '/api/portrait',
        description: '随机返回一张竖屏图片',
        example: `${origin}/api/portrait`,
      },
      {
        path: '/api/acg',
        description: '随机返回一张 ACG 动图（animated WebP）',
        example: `${origin}/api/acg`,
      },
    ],
    queryParams: {
      'type=json': '返回 JSON 图片信息而非重定向',
      'n=5': '返回 n 张图片的 JSON 列表（配合 type=json 或单独使用）',
    },
    aliases: {
      landscape: ['heng', 'horizontal'],
      portrait: ['shu', 'vertical'],
      acg: ['dongtu', 'gif'],
      random: ['all'],
    },
  };
  return new Response(JSON.stringify(data, null, 2), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...CORS_HEADERS,
    },
  });
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}
