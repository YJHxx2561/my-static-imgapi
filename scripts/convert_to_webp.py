#!/usr/bin/env python3
"""
将 images/landscape 与 images/portrait 下的图片统一转换为无损 WebP，
并按文件名排序后依次重命名为 1.webp、2.webp、3.webp ...（两类各自独立编号）。

流程：
  1. 先转换到临时目录 images/.landscape_webp / images/.portrait_webp（多进程并行）
  2. 全部成功后，替换原目录（原文件删除）
  3. 支持断点续转：已生成的 <序号>.webp 会跳过

依赖：Pillow（pip install Pillow，需支持 webp）

用法：
  python scripts/convert_to_webp.py                 # 转换到临时目录
  python scripts/convert_to_webp.py --apply         # 校验临时目录后替换原目录
  python scripts/convert_to_webp.py --workers 12    # 指定并行进程数
"""

import os
import shutil
import sys
from multiprocessing import Pool
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # 允许处理超大分辨率图片

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(ROOT, 'images')
CATEGORIES = ('landscape', 'portrait')
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif'}
METHOD = 0  # 无损压缩等级 0~6；0 最快，均为无损，仅体积略大


def list_source_files(category):
    src_dir = os.path.join(IMAGES_DIR, category)
    files = sorted(
        f for f in os.listdir(src_dir)
        if os.path.isfile(os.path.join(src_dir, f))
        and os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )
    return src_dir, files


def convert_one(args):
    """转换单张图片。args = (category, index, filename) -> (index, ok, msg)"""
    category, idx, name = args
    src_dir, _ = list_source_files(category)
    tmp_dir = os.path.join(IMAGES_DIR, f'.{category}_webp')
    out = os.path.join(tmp_dir, f'{idx}.webp')
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return idx, True, 'skip'
    try:
        with Image.open(os.path.join(src_dir, name)) as im:
            im.load()
            if im.mode not in ('RGB', 'RGBA'):
                has_alpha = ('A' in im.getbands()
                             or (im.mode == 'P' and 'transparency' in im.info))
                im = im.convert('RGBA' if has_alpha else 'RGB')
            im.save(out, 'WEBP', lossless=True, method=METHOD)
        return idx, True, 'ok'
    except Exception as e:
        return idx, False, str(e)


def convert_category(category, workers):
    src_dir, files = list_source_files(category)
    tmp_dir = os.path.join(IMAGES_DIR, f'.{category}_webp')
    os.makedirs(tmp_dir, exist_ok=True)

    tasks = [(category, i, name) for i, name in enumerate(files, 1)]
    print(f'[{category}] 共 {len(files)} 张，开始转换（无损 WebP, method={METHOD}, {workers} 进程）', flush=True)

    done = 0
    failed = []
    with Pool(processes=workers) as pool:
        for idx, ok, msg in pool.imap_unordered(convert_one, tasks, chunksize=4):
            done += 1
            if not ok:
                failed.append((idx, msg))
            if done % 50 == 0 or done == len(files):
                print(f'[{category}] {done}/{len(files)}', flush=True)
    for idx, msg in failed[:10]:
        print(f'[{category}] 失败 {idx}.webp: {msg}', flush=True)

    # 校验临时目录：编号连续、文件可打开
    generated = [f for f in os.listdir(tmp_dir) if f.endswith('.webp')]
    expected = set(range(1, len(files) + 1))
    actual = set()
    for f in generated:
        stem = os.path.splitext(f)[0]
        if stem.isdigit():
            actual.add(int(stem))
        try:
            with Image.open(os.path.join(tmp_dir, f)) as im:
                im.verify()
        except Exception as e:
            print(f'[{category}] 校验失败: {f} -> {e}', flush=True)
            return False
    if actual != expected:
        print(f'[{category}] 编号不连续，缺失: {sorted(expected - actual)[:10]}', flush=True)
        return False

    print(f'[{category}] 转换与校验完成：{len(files)} 张', flush=True)
    return True


def apply_category(category):
    """校验临时目录无误后，删除原目录并把临时目录改名为正式目录"""
    tmp_dir = os.path.join(IMAGES_DIR, f'.{category}_webp')
    src_dir = os.path.join(IMAGES_DIR, category)
    if not os.path.isdir(tmp_dir):
        print(f'[{category}] 未找到临时目录，请先执行转换', flush=True)
        return False
    _, files = list_source_files(category)
    generated = [f for f in os.listdir(tmp_dir) if f.endswith('.webp')]
    if len(generated) != len(files):
        print(f'[{category}] 数量不符：原 {len(files)} 张，新 {len(generated)} 张，拒绝替换', flush=True)
        return False

    shutil.rmtree(src_dir)
    os.rename(tmp_dir, src_dir)
    print(f'[{category}] 已替换为 {len(generated)} 张无损 WebP', flush=True)
    return True


def main():
    apply = '--apply' in sys.argv
    workers = 12
    if '--workers' in sys.argv:
        try:
            workers = int(sys.argv[sys.argv.index('--workers') + 1])
        except (IndexError, ValueError):
            pass

    if apply:
        ok = all(apply_category(c) for c in CATEGORIES)
        print('替换完成' if ok else '替换失败', flush=True)
        sys.exit(0 if ok else 1)

    ok = all(convert_category(c, workers) for c in CATEGORIES)
    print('转换完成，可执行 --apply 替换原目录' if ok else '转换失败，原目录未改动', flush=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
