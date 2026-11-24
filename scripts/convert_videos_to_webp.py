#!/usr/bin/env python3
"""
把 14_ACG动图_acg 下的 MP4 视频转换为 animated WebP 动图，
存入 images/acg/1.webp ~ 50.webp，按文件名排序编号。原 MP4 视频保留。

参数（保证单文件远低于 Cloudflare 25MB 限制）：
  - 截取前 5 秒
  - 宽度缩放至 640px（保持比例）
  - 帧率 10 fps
  - WebP 有损质量 75，method 4，循环播放

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

DURATION = 5       # 截取秒数
WIDTH = 640        # 缩放宽度
FPS = 10           # 帧率
QUALITY = 75       # WebP 质量


def main():
    videos = sorted(
        (f for f in os.listdir(SRC_DIR) if f.lower().endswith('.mp4')),
        key=lambda x: x.lower(),
    )
    if not videos:
        print('未找到 MP4 视频')
        sys.exit(1)

    os.makedirs(DST_DIR, exist_ok=True)
    print(f'共 {len(videos)} 个视频，转换为 animated WebP（前{DURATION}s / {WIDTH}px / {FPS}fps / q{QUALITY}）')

    total_before = total_after = 0
    for idx, name in enumerate(videos, 1):
        src = os.path.join(SRC_DIR, name)
        dst = os.path.join(DST_DIR, f'{idx}.webp')
        total_before += os.path.getsize(src)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            with Image.open(dst) as check:
                if getattr(check, 'n_frames', 1) > 1:
                    total_after += os.path.getsize(dst)
                    print(f'[{idx}/{len(videos)}] {name} - 已存在，跳过')
                    continue
        vf = f'scale={WIDTH}:-2,fps={FPS}'
        cmd = [
            FFMPEG, '-y', '-i', src,
            '-t', str(DURATION),
            '-vf', vf,
            '-loop', '0',
            '-c:v', 'libwebp_anim',
            '-quality', str(QUALITY),
            '-method', '4',
            dst,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f'[{idx}/{len(videos)}] {name} - 失败: {r.stderr[-300:]}')
            sys.exit(1)
        with Image.open(dst) as im:
            frames = getattr(im, 'n_frames', 1)
        size_mb = os.path.getsize(dst) / 1024 / 1024
        total_after += os.path.getsize(dst)
        print(f'[{idx}/{len(videos)}] {name} -> {idx}.webp  {size_mb:.2f}MB / {frames}帧')

    print(f'\n完成：原视频 {total_before/1024**3:.2f}GB -> 动图 {total_after/1024**3:.2f}GB')
    print('原 MP4 视频已保留在 14_ACG动图_acg/。请运行 node scripts/generate-manifest.mjs 更新清单。')


if __name__ == '__main__':
    main()
