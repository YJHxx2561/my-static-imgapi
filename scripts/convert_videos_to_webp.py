#!/usr/bin/env python3
"""
把 14_ACG动图_acg 下的 MP4 视频转换为高质量 animated WebP 动图，
存入 images/acg/1.webp ~ 50.webp，按文件名排序编号。原 MP4 视频保留。

质量策略（画质优先，单个文件严格 < 25MB —— Cloudflare Pages 单文件上限）：
  基准参数：1280px 宽 / 20fps / quality 88 / method 6
  若某视频转换后超过 25MB，自动逐级降档重转，直到达标：
    (1280,20,88) -> (1280,16,85) -> (960,16,85) -> (960,12,82) -> (800,12,80)
  截取前 5 秒，循环播放。

依赖：imageio-ffmpeg（提供 ffmpeg）、Pillow（校验）

用法：
  python scripts/convert_videos_to_webp.py
"""

import os
import subprocess
import sys
from PIL import Image
import imageio_ffmpeg

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, '14_ACG动图_acg')
DST_DIR = os.path.join(ROOT, 'images', 'acg')
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

DURATION = 5
MAX_BYTES = 25 * 1024 * 1024  # 25MB 硬上限
# 从高到低的画质档位，逐个尝试直到体积达标
TIERS = [
    (1280, 20, 88),
    (1280, 16, 85),
    (960, 16, 85),
    (960, 12, 82),
    (800, 12, 80),
]


def encode(src, dst, width, fps, quality):
    vf = f'scale={width}:-2,fps={fps}'
    cmd = [
        FFMPEG, '-y', '-i', src,
        '-t', str(DURATION),
        '-vf', vf,
        '-loop', '0',
        '-c:v', 'libwebp_anim',
        '-quality', str(quality),
        '-method', '6',
        dst,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])


def main():
    videos = sorted(
        (f for f in os.listdir(SRC_DIR) if f.lower().endswith('.mp4')),
        key=lambda x: x.lower(),
    )
    if not videos:
        print('未找到 MP4 视频')
        sys.exit(1)

    os.makedirs(DST_DIR, exist_ok=True)
    print(f'共 {len(videos)} 个视频，转换为高质量 animated WebP（前{DURATION}s，单文件 < 25MB）')

    total_bytes = 0
    for idx, name in enumerate(videos, 1):
        src = os.path.join(SRC_DIR, name)
        dst = os.path.join(DST_DIR, f'{idx}.webp')
        used_tier = None
        for width, fps, quality in TIERS:
            encode(src, dst, width, fps, quality)
            size = os.path.getsize(dst)
            if size < MAX_BYTES:
                used_tier = (width, fps, quality, size)
                break
        if used_tier is None:
            print(f'[{idx}/{len(videos)}] {name} - 即使最低档仍超 25MB，跳过')
            sys.exit(1)
        width, fps, quality, size = used_tier
        with Image.open(dst) as im:
            frames = getattr(im, 'n_frames', 1)
        total_bytes += size
        print(f'[{idx}/{len(videos)}] {name} -> {idx}.webp  {width}px/{fps}fps/q{quality}  '
              f'{size/1024/1024:.2f}MB / {frames}帧')

    print(f'\n完成：动图总计 {total_bytes/1024**3:.2f}GB，单文件均 < 25MB')
    print('原 MP4 视频已保留在 14_ACG动图_acg/。请运行 node scripts/generate-manifest.mjs 更新清单。')


if __name__ == '__main__':
    main()
