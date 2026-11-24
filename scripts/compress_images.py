#!/usr/bin/env python3
"""
将 images/landscape 与 images/portrait 下的图片压缩为有损 WebP（quality=95），
保持现有文件名 1.webp ~ N.webp 不变，目标是把总体积压到原始图片大小以内。

流程（与 convert_to_webp.py 一致，安全替换）：
  1. 多进程压缩到临时目录 images/.landscape_compress / images/.portrait_compress
  2. 全部成功后替换原目录
  3. 支持断点续转

依赖：Pillow（pip install Pillow，需支持 WebP）

用法：
  python scripts/compress_images.py                  # 压缩到临时目录
  python scripts/compress_images.py --apply          # 校验后替换原目录
  python scripts/compress_images.py --quality 95     # 指定质量（默认 95）
  python scripts/compress_images.py --workers 12     # 指定并行进程数
"""

import os
import shutil
import sys
from multiprocessing import Pool
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(ROOT, 'images')
CATEGORIES = ('landscape', 'portrait')


def list_files(category):
    d = os.path.join(IMAGES_DIR, category)
    return sorted(
        (f for f in os.listdir(d) if f.lower().endswith('.webp')),
        key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else x,
    )


def compress_one(args):
    category, name, quality = args
    src = os.path.join(IMAGES_DIR, category, name)
    tmp = os.path.join(IMAGES_DIR, f'.{category}_compress', name)
    if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        return name, True, 'skip'
    try:
        with Image.open(src) as im:
            im.load()
            if im.mode not in ('RGB', 'RGBA'):
                has_alpha = ('A' in im.getbands()
                             or (im.mode == 'P' and 'transparency' in im.info))
                im = im.convert('RGBA' if has_alpha else 'RGB')
            im.save(tmp, 'WEBP', lossless=False, quality=quality, method=4)
        return name, True, 'ok'
    except Exception as e:
        return name, False, str(e)


def process_category(category, quality, workers):
    files = list_files(category)
    tmp_dir = os.path.join(IMAGES_DIR, f'.{category}_compress')
    os.makedirs(tmp_dir, exist_ok=True)
    print(f'[{category}] 共 {len(files)} 张，压缩中（有损 quality={quality}, {workers} 进程）', flush=True)

    tasks = [(category, f, quality) for f in files]
    done = 0
    failed = []
    with Pool(processes=workers) as pool:
        for name, ok, msg in pool.imap_unordered(compress_one, tasks, chunksize=4):
            done += 1
            if not ok:
                failed.append((name, msg))
            if done % 100 == 0 or done == len(files):
                print(f'[{category}] {done}/{len(files)}', flush=True)
    for name, msg in failed[:10]:
        print(f'[{category}] 失败 {name}: {msg}', flush=True)

    generated = [f for f in os.listdir(tmp_dir) if f.endswith('.webp')]
    if len(generated) != len(files):
        print(f'[{category}] 数量不符：原 {len(files)}，新 {len(generated)}', flush=True)
        return False
    for f in generated:
        try:
            with Image.open(os.path.join(tmp_dir, f)) as im:
                im.verify()
        except Exception as e:
            print(f'[{category}] 校验失败 {f}: {e}', flush=True)
            return False
    before = sum(os.path.getsize(os.path.join(IMAGES_DIR, category, f)) for f in files)
    after = sum(os.path.getsize(os.path.join(tmp_dir, f)) for f in files)
    print(f'[{category}] 完成：{before/1024**3:.3f} GB -> {after/1024**3:.3f} GB', flush=True)
    return True


def apply_category(category):
    tmp_dir = os.path.join(IMAGES_DIR, f'.{category}_compress')
    src_dir = os.path.join(IMAGES_DIR, category)
    if not os.path.isdir(tmp_dir):
        print(f'[{category}] 未找到临时目录', flush=True)
        return False
    files = list_files(category)
    generated = [f for f in os.listdir(tmp_dir) if f.endswith('.webp')]
    if len(generated) != len(files):
        print(f'[{category}] 数量不符，拒绝替换', flush=True)
        return False
    shutil.rmtree(src_dir)
    os.rename(tmp_dir, src_dir)
    print(f'[{category}] 已替换', flush=True)
    return True


def main():
    apply = '--apply' in sys.argv
    quality, workers = 95, 12
    if '--quality' in sys.argv:
        quality = int(sys.argv[sys.argv.index('--quality') + 1])
    if '--workers' in sys.argv:
        workers = int(sys.argv[sys.argv.index('--workers') + 1])

    if apply:
        ok = all(apply_category(c) for c in CATEGORIES)
        print('替换完成' if ok else '替换失败', flush=True)
        sys.exit(0 if ok else 1)

    ok = all(process_category(c, quality, workers) for c in CATEGORIES)
    print('压缩完成，可执行 --apply 替换' if ok else '压缩失败，原目录未改动', flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
