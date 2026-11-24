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
    name: '随机资源 API',
    description: '根据路径随机返回横屏图、竖屏图、ACG 动图或视频',
    availableResources: COUNT,
    endpoints: [
      {
        path: '/api/random',
        description: '随机返回一个资源（横屏 + 竖屏 + 动图，不含视频）',
        example: `${origin}/api/random`,
      },
      {
        path: '/api/landscape',
        description: '随机返回一张横屏图片（WebP 静态图）',
        example: `${origin}/api/landscape`,
      },
      {
        path: '/api/portrait',
        description: '随机返回一张竖屏图片（WebP 静态图）',
        example: `${origin}/api/portrait`,
      },
      {
        path: '/api/acg',
        description: '随机返回一张 ACG 动图（animated WebP，会播放动画）',
        example: `${origin}/api/acg`,
      },
      {
        path: '/api/video',
        description: '随机返回一个 ACG 视频（MP4），302 跳转到视频文件',
        example: `${origin}/api/video`,
      },
    ],
    mediaGuide: {
      acg: {
        format: 'animated WebP（多帧动图，浏览器 <img> 标签可直接播放）',
        count: COUNT.acg,
        randomApi: `${origin}/api/acg`,
        fixedFileExample: `${origin}/images/acg/1.webp`,
        note: '动图由 MP4 视频转换而来（前 5 秒 / 1280px / 20fps），每个文件 < 25MB。',
      },
      video: {
        format: 'MP4 视频',
        count: COUNT.video,
        randomApi: `${origin}/api/video`,
        fixedFileExample: `${origin}/images/video/1.mp4`,
        note: '与原动图一一对应（同编号同源视频），每个文件 < 25MB。可用 <video> 标签播放。',
        htmlExample: `<video src="${origin}/api/video" autoplay muted loop></video>`,
      },
    },
    queryParams: {
      'type=json': '返回 JSON 资源信息而非重定向（视频同样适用）',
      'n=5': '返回 n 个资源的 JSON 列表（配合 type=json 或单独使用）',
    },
    aliases: {
      landscape: ['heng', 'horizontal'],
      portrait: ['shu', 'vertical'],
      acg: ['dongtu', 'gif'],
      video: ['shipin', 'mp4'],
      random: ['all'],
    },
    fixedFileAccess: {
      description: '所有资源都可绕过 Functions、通过静态路径直接访问固定文件，内容不变且不消耗函数额度',
      examples: [
        `${origin}/images/landscape/1.webp`,
        `${origin}/images/portrait/1.webp`,
        `${origin}/images/acg/1.webp`,
        `${origin}/images/video/1.mp4`,
      ],
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
