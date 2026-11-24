#!/usr/bin/env python3
"""
从根目录的两个初音未来压缩包导入新图到 images/：
  - 初音未来横图.zip (horizontal/) -> images/landscape/
  - 初音未来竖图.zip (vertical/)   -> images/portrait/

直接从 zip 读取，转有损 WebP（默认 quality=82, method=4）以减小体积，
按图片实际宽高比归类，编号接着现有最大值递增。

用法：
  python scripts/import_miku_images.py            # 预演（只打印计划）
  python scripts/import_miku_images.py --apply    # 实际导入
  python scripts/import_miku_images.py --apply --quality 80 --workers 8
"""

import io
import os
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, 'images')
ZIPS = {
    'landscape': '初音未来横图.zip',
    'portrait': '初音未来竖图.zip',
}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}


def next_number(category):
    d = os.path.join(IMAGES, category)
    nums = [int(os.path.splitext(f)[0]) for f in os.listdir(d)
            if os.path.splitext(f)[0].isdigit()]
    return max(nums) + 1 if nums else 1


def zip_images(zip_path):
    path = os.path.join(ROOT, zip_path)
    with zipfile.ZipFile(path) as z:
        return [i.filename for i in z.infolist()
                if not i.is_dir() and os.path.splitext(i.filename)[1].lower() in IMAGE_EXTS]


def convert_one(args):
    """在子进程里从 zip 读取单张图片并转 WebP。返回 (name, category, bytes, err)。"""
    zip_path, member, dst_path, quality = args
    try:
        with zipfile.ZipFile(os.path.join(ROOT, zip_path)) as z:
            raw = z.read(member)
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            category = 'landscape' if im.width > im.height else 'portrait'
            if im.mode not in ('RGB', 'RGBA'):
                has_alpha = ('A' in im.getbands()
                             or (im.mode == 'P' and 'transparency' in im.info))
                im = im.convert('RGBA' if has_alpha else 'RGB')
            buf = io.BytesIO()
            im.save(buf, 'WEBP', lossless=False, quality=quality, method=4)
        return member, category, buf.getvalue(), dst_path, None
    except Exception as e:
        return member, None, None, dst_path, str(e)


def main():
    apply = '--apply' in sys.argv
    quality, workers = 82, 8
    if '--quality' in sys.argv:
        quality = int(sys.argv[sys.argv.index('--quality') + 1])
    if '--workers' in sys.argv:
        workers = int(sys.argv[sys.argv.index('--workers') + 1])

    counters = {'landscape': next_number('landscape'), 'portrait': next_number('portrait')}
    print(f'起始编号: landscape 从 {counters["landscape"]}, portrait 从 {counters["portrait"]}')
    print(f'目标质量: WebP quality={quality}, {workers} 进程\n')

    tasks = []
    for default_cat, zip_path in ZIPS.items():
        members = zip_images(zip_path)
        print(f'[{zip_path}] {len(members)} 张')
        for m in members:
            # 目标编号按来源压缩包所属类别先占号；实际方向由 convert_one 判定后再调整
            num = counters[default_cat]
            counters[default_cat] += 1
            dst = os.path.join(IMAGES, default_cat, f'{num}.webp')
            tasks.append((zip_path, m, dst, quality))

    print(f'\n共 {len(tasks)} 张待处理（临时按来源分类占号，转换后按实际方向落盘）')
    if not apply:
        print('[预演模式] 未写入。加 --apply 执行导入。')
        return

    # 实际方向可能与来源分类不同：先全部转换到内存，再统一按实际方向编号写入
    results = []
    failed = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(convert_one, t) for t in tasks]
        done = 0
        for fut in as_completed(futs):
            member, category, data, dst, err = fut.result()
            done += 1
            if err:
                failed.append((member, err))
            else:
                results.append((member, category, data))
            if done % 100 == 0 or done == len(tasks):
                print(f'  转换 {done}/{len(tasks)}', flush=True)

    if failed:
        print(f'\n失败 {len(failed)} 张，中止导入（保持原目录不变）：')
        for m, e in failed[:10]:
            print(f'  {m}: {e}')
        sys.exit(1)

    # 按原 zip 的命名顺序排序，保证编号稳定
    order = {m: i for i, (_, _, m, _) in enumerate(tasks)}
    results.sort(key=lambda r: order.get(r[0], 0))

    final_num = {'landscape': next_number('landscape'), 'portrait': next_number('portrait')}
    added = {'landscape': 0, 'portrait': 0}
    total_bytes = {'landscape': 0, 'portrait': 0}
    for member, category, data in results:
        num = final_num[category]
        final_num[category] += 1
        out = os.path.join(IMAGES, category, f'{num}.webp')
        with open(out, 'wb') as f:
            f.write(data)
        added[category] += 1
        total_bytes[category] += len(data)

    print(f'\n导入完成: landscape +{added["landscape"]} (至 {final_num["landscape"]-1})，'
          f'portrait +{added["portrait"]} (至 {final_num["portrait"]-1})')
    for c in ('landscape', 'portrait'):
        print(f'  {c} 新增体积 {total_bytes[c]/1024**3:.3f} GB')
    print('\n请运行 node scripts/generate-manifest.mjs 更新清单。')


if __name__ == '__main__':
    main()
