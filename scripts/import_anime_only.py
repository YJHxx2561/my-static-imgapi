#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仅从 alcy-photos 导入【二次元/动漫】图片，排除真人、头像、风景、写实/P站。

白名单策略（只导入明确为二次元的来源）：
  - 编号目录 01~06、08~10、12~13（PC/移动/萌版/原神/初音/白底/胡桃/小狐狸，经抽样确认为二次元）
  - loliapi（电脑端二次元_pc、移动端二次元_pe）
  - mtyqx（二次元动漫）
  - r10086 除以下排除子目录外的所有动漫分类

排除（真人/头像/风景/写实混杂）：
  - 07_风景横图_fj        风景
  - 11_头像方图_tx        头像
  - r10086/少女写真       真人写真
  - r10086/现实风景       风景
  - r10086/P站           混有写实人像插画

处理：有损 WebP(q85) 转换、按内容指纹去重（源内部 + 排除与项目现有重复）、
      按实际宽高比分横竖、续接编号、单文件 < 25MB、总文件数受 --target 限制。

用法：
  python scripts/import_anime_only.py                          # 预演
  python scripts/import_anime_only.py --apply --workers 12     # 实际导入
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
PROGRESS = ROOT / ".import_anime_progress.json"

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
HEAD_BYTES = 65536
MIN_SIDE = 320
MIN_SRC_SIZE = 12 * 1024
MAX_OUT = 25 * 1024 * 1024
STATIC_CATS = ("landscape", "portrait")

# 顶层目录白名单（编号目录中的二次元来源）
TOP_WHITELIST = {
    "01_PC横图_pc", "02_移动竖图_mp", "03_萌版横图_moe", "04_萌版竖图_moemp",
    "05_原神横图_ys", "06_原神竖图_ysmp", "08_初音未来横图_miku", "09_初音未来竖图_mikump",
    "10_白底横图_bd", "12_七濑胡桃_lai", "13_小狐狸_xhl",
    "loliapi", "mtyqx", "r10086",
}
# 明确排除的顶层目录
TOP_EXCLUDE = {"07_风景横图_fj", "11_头像方图_tx", "14_ACG动图_acg"}
# r10086 内排除的子目录（真人/风景/写实）
R10086_EXCLUDE = {"少女写真", "现实风景", "P站"}


def head_fingerprint(path, n=HEAD_BYTES):
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            h.update(f.read(n))
        return h.hexdigest()
    except OSError:
        return ""


def next_number(cat):
    d = IMAGES / cat
    nums = [int(p.stem) for p in d.iterdir()
            if p.is_file() and p.stem.isdigit() and p.suffix.lower() == ".webp"]
    return max(nums) + 1 if nums else 1


def count_images():
    by_cat = {}
    total = 0
    for cat in ("landscape", "portrait", "acg", "video"):
        n = len([p for p in (IMAGES / cat).iterdir() if p.is_file()])
        by_cat[cat] = n
        total += n
    return total, by_cat


def source_files():
    """按白名单收集二次元来源图片，跳过排除目录。"""
    groups = {}
    if not SOURCE.exists():
        return groups
    for entry in sorted(SOURCE.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in TOP_EXCLUDE or entry.name not in TOP_WHITELIST:
            continue
        files = []
        for root, dirs, names in os.walk(entry):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            # r10086 内排除真人/风景/P站子目录
            if entry.name == "r10086":
                rel = Path(root).relative_to(entry)
                if any(part in R10086_EXCLUDE for part in rel.parts):
                    continue
                dirs[:] = [d for d in dirs if d not in R10086_EXCLUDE]
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


def fp_worker(paths):
    return [(p, os.path.getsize(p), head_fingerprint(p)) for p in paths]


def convert_one(items):
    """处理一批 (src, quality) 任务，返回 [(src, cat, data, err), ...]。"""
    out = []
    for src, quality in items:
        try:
            with Image.open(src) as im:
                im.load()
                if min(im.size) < MIN_SIDE:
                    out.append((src, None, None, "too_small"))
                    continue
                cat = "landscape" if im.width > im.height else "portrait"
                if im.mode not in ("RGB", "RGBA"):
                    has_alpha = ("A" in im.getbands()
                                 or (im.mode == "P" and "transparency" in im.info))
                    im = im.convert("RGBA" if has_alpha else "RGB")
                from io import BytesIO
                buf = BytesIO()
                im.save(buf, "WEBP", lossless=False, quality=quality, method=4)
                data = buf.getvalue()
            if len(data) >= MAX_OUT:
                out.append((src, None, None, "too_large"))
            else:
                out.append((src, cat, data, None))
        except Exception as e:
            out.append((src, None, None, str(e)[:80]))
    return out


def parallel_map(func, items, workers, chunk=200):
    if not items:
        return []
    batches = [items[i:i + chunk] for i in range(0, len(items), chunk)]
    out = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(func, b) for b in batches]
        for fut in as_completed(futs):
            out.extend(fut.result())
    return out


def main():
    ap = argparse.ArgumentParser(description="仅导入二次元/动漫图片（排除真人/头像/风景/P站）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--target", type=int, default=19900)
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    total_now, by_cat = count_images()
    quota = args.target - total_now
    print(f"当前 images: {total_now} {by_cat}")
    print(f"目标上限 {args.target} -> 可新增 {quota}")
    if quota <= 0:
        print("已达上限"); return

    progress = {"imported_src": []}
    if PROGRESS.exists():
        try:
            progress.update(json.loads(PROGRESS.read_text(encoding="utf-8")))
        except Exception:
            pass
    imported = set(progress["imported_src"])

    print("\n[1/4] 扫描现有图片指纹 ...")
    existing = set()
    for cat in STATIC_CATS:
        paths = [str(p) for p in (IMAGES / cat).iterdir()
                 if p.is_file() and p.suffix.lower() == ".webp"]
        for p, size, h in parallel_map(fp_worker, paths, args.workers):
            existing.add((size, h))
    print(f"  现有指纹 {len(existing)} 条")

    print("\n[2/4] 扫描二次元来源（排除真人/头像/风景/P站）...")
    groups = source_files()
    all_src = []
    for g, paths in groups.items():
        print(f"  [{g}] {len(paths)} 张")
        all_src.extend((g, p) for p in paths if p not in imported)
    print(f"  待评估 {len(all_src)} 张")

    print("\n[3/4] 源内去重 + 排除与现有重复 ...")
    fingerprints = parallel_map(fp_worker, [p for _, p in all_src], args.workers)
    fp_map = {p: (size, h) for p, size, h in fingerprints}
    seen = set(existing)
    candidates = []
    for g, p in all_src:
        fp = fp_map.get(p)
        if not fp:
            continue
        if fp in seen:
            continue
        seen.add(fp)
        candidates.append(p)
    # 受配额限制
    candidates = candidates[:quota]
    print(f"  去重后候选 {len(candidates)} 张")

    if not args.apply:
        print("\n[预演] 未写入。加 --apply 执行导入。")
        lc = sum(1 for p in candidates if True)
        print(f"  预计最多导入 {len(candidates)} 张")
        return

    print("\n[4/4] 转换 WebP 并写入 ...")
    results = parallel_map(convert_one, [(p, args.quality) for p in candidates], args.workers, chunk=20)
    ok = [(p, cat, data) for p, cat, data, err in results if cat]
    failed = [(p, err) for p, cat, data, err in results if not cat]
    print(f"  成功 {len(ok)} 张，失败/过滤 {len(failed)} 张")

    counters = {"landscape": next_number("landscape"), "portrait": next_number("portrait")}
    added = {"landscape": 0, "portrait": 0}
    for p, cat, data in ok:
        num = counters[cat]
        counters[cat] += 1
        out = IMAGES / cat / f"{num}.webp"
        with open(out, "wb") as f:
            f.write(data)
        added[cat] += 1
        imported.add(p)

    PROGRESS.write_text(json.dumps({"imported_src": sorted(imported)}, ensure_ascii=False), encoding="utf-8")
    print(f"\n导入完成: 横屏 +{added['landscape']} (至 {counters['landscape']-1}), "
          f"竖屏 +{added['portrait']} (至 {counters['portrait']-1})")
    print("请运行 node scripts/generate-manifest.mjs 更新清单。")


if __name__ == "__main__":
    main()
