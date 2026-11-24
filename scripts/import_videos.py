#!/usr/bin/env python3
"""
把 14_ACG动图_acg 下的 MP4 视频导入 images/video/1.mp4 ~ 50.mp4，
与 images/acg/ 的动图使用相同排序和编号（同一源文件对应同一编号）。

- 视频 < 25MB：直接复制（不重编码，画质无损）
- 视频 >= 25MB：缩放到 1280px 重编码压缩到 25MB 内（Cloudflare Pages 单文件上限）
- 原视频保留在 14_ACG动图_acg/

依赖：imageio-ffmpeg（提供 ffmpeg，仅压缩超大视频时需要）

用法：
  python scripts/import_videos.py
"""

import os
import shutil
import subprocess
from PIL import Image
import imageio_ffmpeg

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, '14_ACG动图_acg')
DST_DIR = os.path.join(ROOT, 'images', 'video')
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
MAX_BYTES = 25 * 1024 * 1024


def main():
    videos = sorted(
        (f for f in os.listdir(SRC_DIR) if f.lower().endswith('.mp4')),
        key=lambda x: x.lower(),
    )
    if not videos:
        print('未找到 MP4 视频')
        return

    os.makedirs(DST_DIR, exist_ok=True)
    print(f'共 {len(videos)} 个视频，导入 images/video/（与 acg 动图同编号）')

    total = 0
    for idx, name in enumerate(videos, 1):
        src = os.path.join(SRC_DIR, name)
        dst = os.path.join(DST_DIR, f'{idx}.mp4')
        size = os.path.getsize(src)
        if size < MAX_BYTES:
            shutil.copy2(src, dst)
            note = '直接复制'
        else:
            cmd = [FFMPEG, '-y', '-i', src, '-vf', 'scale=1280:-2',
                   '-c:v', 'libx264', '-crf', '28', '-preset', 'fast', '-an', dst]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or os.path.getsize(dst) >= MAX_BYTES:
                print(f'[{idx}] {name} - 压缩失败或仍超 25MB')
                return
            note = '压缩后导入'
        total += os.path.getsize(dst)
        print(f'[{idx}/{len(videos)}] {name} -> {idx}.mp4  '
              f'{os.path.getsize(dst)/1024/1024:.1f}MB  ({note})')

    print(f'\n完成：视频总计 {total/1024**3:.2f}GB，单文件均 < 25MB')
    print('请运行 node scripts/generate-manifest.mjs 更新清单。')


if __name__ == '__main__':
    main()
