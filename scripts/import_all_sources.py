#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 alcy-photos/downloads 的全部来源导入图片到本项目 images/。

规则（按需求）：
  - 复制到本项目，按【实际宽高比】分横屏(landscape)/竖屏(portrait)存放
  - 转换为【有损 WebP】，质量 q85（可用 --quality 调整）
  - 按内容指纹去重：源内部去重 + 排除与项目现有图片重复
  - 过滤低质量（尺寸过小 / 体积异常小）与超大图（输出 > 25MB）
  - 续接编号写入，保证 images/ 上传总文件数 < 20000（--target 控制）
  - 单文件 < 25MB（Cloudflare 单文件上限）
  - 视频(acg/video)保持现状，不导入新视频
  - 断点续传：进度写入 .import_progress.json，重跑跳过已导入

用法：
  python3 scripts/import_all_sources.py                 # 预演（只统计，不写入）
  python3 scripts/import_all_sources.py --apply         # 实际导入
  python3 scripts/import_all_sources.py --apply --workers 8 --quality 85
  python3 scripts/import_all_sources.py --apply --target 19900
"""

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"
SOURCE = ROOT.parent / "alcy-photos" / "downloads"
PROGRESS = ROOT / ".import_progress.json"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
HEAD_BYTES = 65536          # 快速指纹读取头部字节数
MIN_SIDE = 320              # 最小边长（低于视为低质量）
MIN_SRC_SIZE = 12 * 1024    # 源体积下限（低于视为缩略图/损坏）
MAX_OUT = 25 * 1024 * 1024  # 单文件上限 25MB
STATIC_CATS = ("landscape", "portrait")


# -------------------------------------------------------------------------- #
# 工具
# -------------------------------------------------------------------------- #
def head_fingerprint(path, n=HEAD_BYTES):
    """快速指纹：文件大小 + 头部 MD5。足够区分绝大多数重复图片。"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            h = hashlib.md5(f.read(n)).hexdigest()
        return (size, h)
    except OSError:
        return None


def next_number(cat):
    d = IMAGES / cat
    if not d.exists():
        return 1
    nums = [int(p.stem) for p in d.glob("*.webp") if p.stem.isdigit()]
    return max(nums) + 1 if nums else 1


def count_images():
    total = 0
    by_cat = {}
    for cat in ("landscape", "portrait", "acg", "video"):
        d = IMAGES / cat
        n = sum(1 for p in d.iterdir() if p.is_file() and not p.name.startswith(".")) if d.exists() else 0
        by_cat[cat] = n
        total += n
    return total, by_cat


def source_files():
    """收集所有源图片路径（排除隐藏临时文件与非图片）。按来源分组。"""
    groups = {}
    if not SOURCE.exists():
        return groups
    for entry in sorted(SOURCE.iterdir()):
        if not entry.is_dir():
            continue
        files = []
        for root, dirs, names in os.walk(entry):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in names:
                if name.startswith("."):
                    continue
                if Path(name).suffix.lower() in IMG_EXTS:
                    p = Path(root) / name
                    try:
                        if p.stat().st_size >= MIN_SRC_SIZE:
                            files.append(str(p))
                    except OSError:
                        pass
        if files:
            groups[entry.name] = files
    return groups


# -------------------------------------------------------------------------- #
# 并行阶段
# -------------------------------------------------------------------------- #
def fp_worker(paths):
    out = []
    for p in paths:
        fp = head_fingerprint(p)
        if fp:
            out.append((p, fp[0], fp[1]))
    return out


def convert_batch(args):
    """顶层函数：批量转换（可被多进程 pickle）。"""
    paths, quality = args
    return [convert_worker((p, quality)) for p in paths]


def convert_worker(args):
    """子进程：读取源图 -> 按宽高比分类 -> 有损 WebP q85。"""
    src, quality = args
    try:
        with Image.open(src) as im:
            w, h = im.width, im.height
            if w < MIN_SIDE or h < MIN_SIDE:
                return src, None, None, "低分辨率"
            im.load()
            cat = "landscape" if w > h else "portrait"
            if im.mode not in ("RGB", "RGBA"):
                has_alpha = ("A" in im.getbands()
                             or (im.mode == "P" and "transparency" in im.info))
                im = im.convert("RGBA" if has_alpha else "RGB")
            buf = __import__("io").BytesIO()
            im.save(buf, "WEBP", lossless=False, quality=quality, method=4)
        data = buf.getvalue()
        if len(data) > MAX_OUT:
            # 输出超限则降质重试
            with Image.open(src) as im2:
                im2.load()
                if im2.mode not in ("RGB", "RGBA"):
                    im2 = im2.convert("RGB")
                buf2 = __import__("io").BytesIO()
                im2.save(buf2, "WEBP", lossless=False, quality=max(60, quality - 20), method=6)
            data = buf2.getvalue()
            if len(data) > MAX_OUT:
                return src, None, None, "超限"
        return src, cat, data, None
    except Exception as e:
        return src, None, None, str(e)[:80]


def parallel_map(func, items, workers, chunk=200):
    chunks = [items[i:i + chunk] for i in range(0, len(items), chunk)]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(func, c): i for i, c in enumerate(chunks)}
        done = 0
        for fut in as_completed(futs):
            results.extend(fut.result())
            done += 1
            if done % 10 == 0 or done == len(chunks):
                print(f"    {done}/{len(chunks)} 批", flush=True)
    return results


# -------------------------------------------------------------------------- #
# 主流程
# -------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="全来源图片导入（横竖屏分类 + 有损WebP q85）")
    ap.add_argument("--apply", action="store_true", help="实际写入；默认预演")
    ap.add_argument("--target", type=int, default=19900, help="images 总文件数上限（默认19900）")
    ap.add_argument("--quality", type=int, default=85, help="有损WebP质量（默认85）")
    ap.add_argument("--workers", type=int, default=8, help="并发进程数")
    args = ap.parse_args()

    total_now, by_cat = count_images()
    quota = args.target - total_now
    print(f"当前 images 文件数: {total_now} {by_cat}")
    print(f"目标上限 {args.target} -> 可新增配额: {quota}")
    if quota <= 0:
        print("已达上限，无需导入。")
        return

    # 断点续传进度
    progress = {"imported_src": []}
    if PROGRESS.exists():
        try:
            progress.update(json.loads(PROGRESS.read_text(encoding="utf-8")))
        except Exception:
            pass
    imported = set(progress["imported_src"])

    print("\n[1/4] 扫描项目现有图片指纹 ...")
    existing = set()
    for cat in STATIC_CATS:
        paths = [str(p) for p in (IMAGES / cat).iterdir()
                 if p.is_file() and p.suffix.lower() == ".webp"]
        for p, size, h in parallel_map(fp_worker, paths, args.workers):
            existing.add((size, h))
    print(f"  现有指纹 {len(existing)} 条")

    print("\n[2/4] 扫描源图片并去重 ...")
    groups = source_files()
    all_src = []
    for g, paths in groups.items():
        print(f"  [{g}] {len(paths)} 张")
        all_src.extend((g, p) for p in paths if p not in imported)
    print(f"  待评估源图 {len(all_src)} 张")

    scanned = parallel_map(fp_worker, [p for _, p in all_src], args.workers)
    fp_map = {p: (size, h) for p, size, h in scanned}

    seen = set(existing)
    candidates = []
    dup = 0
    # 轮转各来源，保证多样性
    by_group = {}
    for g, p in all_src:
        by_group.setdefault(g, []).append(p)
    keys = list(by_group.keys())
    idx = {k: 0 for k in keys}
    while True:
        progressed = False
        for k in keys:
            lst = by_group[k]
            if idx[k] >= len(lst):
                continue
            p = lst[idx[k]]
            idx[k] += 1
            progressed = True
            fp = fp_map.get(p)
            if not fp or fp in seen:
                dup += 1
                continue
            seen.add(fp)
            candidates.append(p)
        if not progressed:
            break
    print(f"  去重后候选 {len(candidates)} 张（重复/跳过 {dup} 张）")
    if len(candidates) > quota:
        candidates = candidates[:quota]
        print(f"  按配额截取 {len(candidates)} 张")
    if not candidates:
        print("无候选图片。")
        return

    print(f"\n[3/4] 转换有损 WebP q{args.quality} 并分类 ...")
    conv_chunks = [(candidates[i:i + 100], args.quality)
                   for i in range(0, len(candidates), 100)]
    converted = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(convert_batch, c) for c in conv_chunks]
        done = 0
        for fut in as_completed(futs):
            converted.extend(fut.result())
            done += 1
            if done % 20 == 0 or done == len(conv_chunks):
                print(f"    {done}/{len(conv_chunks)} 批", flush=True)
    # parallel_map 已扁平化
    ok = [r for r in converted if r[0] and r[1] and r[2]]
    fail_reason = {}
    for r in converted:
        if r[0] and not r[1]:
            fail_reason[r[3]] = fail_reason.get(r[3], 0) + 1
    print(f"  转换成功 {len(ok)} 张，失败 {len(converted) - len(ok)} {fail_reason}")

    if not args.apply:
        lc = sum(1 for r in ok if r[1] == "landscape")
        pc = sum(1 for r in ok if r[1] == "portrait")
        size_sum = sum(len(r[2]) for r in ok)
        print("\n[预演] 未写入。预估:")
        print(f"  横屏 +{lc}, 竖屏 +{pc}")
        print(f"  新增体积 {size_sum / 1024**3:.2f} GB")
        print(f"  导入后总数 {total_now + len(ok)} (上限 {args.target})")
        print("  加 --apply 执行导入。")
        return

    print("\n[4/4] 写入 images/ 并续接编号 ...")
    counters = {"landscape": next_number("landscape"), "portrait": next_number("portrait")}
    added = {"landscape": 0, "portrait": 0}
    written = 0
    for src, cat, data, err in ok:
        num = counters[cat]
        out = IMAGES / cat / f"{num}.webp"
        with open(out, "wb") as f:
            f.write(data)
        counters[cat] += 1
        added[cat] += 1
        imported.add(src)
        written += 1
        if written % 200 == 0 or written == len(ok):
            print(f"  写入 {written}/{len(ok)}", flush=True)
            progress["imported_src"] = sorted(imported)
            PROGRESS.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")

    progress["imported_src"] = sorted(imported)
    PROGRESS.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")

    total_after, after_cat = count_images()
    print("\n导入完成:")
    print(f"  横屏 +{added['landscape']} (至 {counters['landscape'] - 1})")
    print(f"  竖屏 +{added['portrait']} (至 {counters['portrait'] - 1})")
    print(f"  images 总数 {total_after} {after_cat}  (上限 {args.target})")
    print("\n请运行 node scripts/generate-manifest.mjs 更新清单。")


if __name__ == "__main__":
    main()
