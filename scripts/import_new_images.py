#!/usr/bin/env python3
"""
把根目录新增的两批图片导入 images/，接着已有编号继续递增。

- 01_PC横图_pc  → images/landscape/（从现有最大编号 +1 继续）
- 02_移动竖图_mp → images/portrait/（按实际方向判断，横屏图归入 landscape）

图片已是有损 WebP，直接复制避免二次编码；非 WebP（如 jpg）转有损 WebP(q95)。
处理完成后源文件目录保留不动。

用法：
  python scripts/import_new_images.py           # 预演（只打印计划，不写入）
  python scripts/import_new_images.py --apply   # 实际导入
"""

import os
import shutil
import sys
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, 'images')
SOURCES = {
    '01_PC横图_pc': 'landscape',
    '02_移动竖图_mp': 'portrait',
}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif'}


def next_number(category):
    d = os.path.join(IMAGES, category)
    nums = [int(os.path.splitext(f)[0]) for f in os.listdir(d)
            if os.path.splitext(f)[0].isdigit()]
    return max(nums) + 1 if nums else 1


def source_files(folder):
    d = os.path.join(ROOT, folder)
    files = sorted(
        (f for f in os.listdir(d)
         if os.path.isfile(os.path.join(d, f)) and os.path.splitext(f)[1].lower() in IMAGE_EXTS),
        key=lambda x: x.lower(),
    )
    return d, files


def detect_orientation(path):
    with Image.open(path) as im:
        w, h = im.size
    return 'landscape' if w > h else 'portrait'


def main():
    apply = '--apply' in sys.argv
    counters = {'landscape': next_number('landscape'), 'portrait': next_number('portrait')}
    print(f'起始编号: landscape 从 {counters["landscape"]}, portrait 从 {counters["portrait"]}')
    plan = []

    for folder, default_cat in SOURCES.items():
        d, files = source_files(folder)
        print(f'\n[{folder}] {len(files)} 张')
        for name in files:
            src = os.path.join(d, name)
            category = detect_orientation(src)
            if category != default_cat:
                print(f'  方向纠正: {name} -> {category}')
            num = counters[category]
            counters[category] += 1
            plan.append((src, category, num))

    print(f'\n导入计划: landscape 新增 {sum(1 for _,c,_ in plan if c=="landscape")} 张 '
          f'(至 {counters["landscape"]-1}), portrait 新增 {sum(1 for _,c,_ in plan if c=="portrait")} 张 '
          f'(至 {counters["portrait"]-1})')
    if not apply:
        print('\n[预演模式] 未写入。加 --apply 执行导入。')
        return

    for src, category, num in plan:
        dst = os.path.join(IMAGES, category, f'{num}.webp')
        if src.lower().endswith('.webp'):
            shutil.copy2(src, dst)
        else:
            with Image.open(src) as im:
                im.load()
                if im.mode not in ('RGB', 'RGBA'):
                    has_alpha = ('A' in im.getbands()
                                 or (im.mode == 'P' and 'transparency' in im.info))
                    im = im.convert('RGBA' if has_alpha else 'RGB')
                im.save(dst, 'WEBP', lossless=False, quality=95, method=4)
    print('\n导入完成。请运行 node scripts/generate-manifest.mjs 更新清单。')


if __name__ == '__main__':
    main()
