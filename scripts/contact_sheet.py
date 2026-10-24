#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一张图做视觉验收：分镜风格总览，或成片等距抽帧联系表。

用法:
    python scripts/contact_sheet.py --images 'images/c16/s*.png' \
        --out out/qa/style_sheet.png --cols 7
    python scripts/contact_sheet.py --video 成片.mp4 \
        --out out/qa/film_sheet.png --count 12 --cols 4
    python scripts/contact_sheet.py --video 成片.mp4 --times 10,30,60,90 \
        --out out/qa/check.png
"""

import argparse
import glob
import math
import os
import re
import shutil
import subprocess
import tempfile


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def probe_duration(path, ff):
    p = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        raise SystemExit("无法读取视频时长: %s" % path)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def probe_size(path, ff):
    p = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, text=True)
    m = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", p.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else None


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        print(p.stderr[-3000:])
        raise SystemExit("ffmpeg 执行失败")


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--images", help="图片 glob，如 'images/c16/s*.png'")
    src.add_argument("--video", help="成片路径，按 --count 或 --times 抽帧")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--times", default="", help="逗号分隔的抽帧秒数；给了就覆盖 --count")
    ap.add_argument("--thumb-width", type=int, default=320)
    ap.add_argument("--thumb-height", type=int, default=0,
                    help="缩略图高；0=按首帧比例自动，竖屏不会被压进横屏格")
    a = ap.parse_args()

    if a.cols < 1 or a.thumb_width < 16 or (a.thumb_height and a.thumb_height < 16):
        raise SystemExit("列数与缩略图尺寸不合法")
    ff = ffmpeg_exe()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mv_sheet_") as tmp:
        if a.images:
            sources = sorted(glob.glob(a.images, recursive=True))
            if not sources:
                raise SystemExit("没有匹配到图片: %s" % a.images)
            files = []
            for i, source in enumerate(sources):
                out = os.path.join(tmp, "f_%04d.png" % i)
                run([ff, "-v", "error", "-y", "-i", source, "-frames:v", "1", out])
                files.append(out)
        else:
            if a.times.strip():
                times = [float(x) for x in a.times.split(",") if x.strip()]
            else:
                dur = probe_duration(a.video, ff)
                # 取每个等分区间的中点，避开首尾黑场与淡入淡出。
                times = [(i + 0.5) * dur / a.count for i in range(a.count)]
            files = []
            for i, t in enumerate(times):
                out = os.path.join(tmp, "f_%04d.png" % i)
                run([ff, "-v", "error", "-y", "-ss", "%.3f" % t, "-i", a.video,
                     "-frames:v", "1", out])
                files.append(out)

        rows = math.ceil(len(files) / a.cols)
        needed = rows * a.cols
        # tile 需要凑满整张；重复最后一格比静默丢掉最后一行更容易验收。
        last = sorted(glob.glob(os.path.join(tmp, "f_*.png")))[-1]
        for i in range(len(files), needed):
            shutil.copyfile(last, os.path.join(tmp, "f_%04d.png" % i))

        thumb_height = a.thumb_height
        if not thumb_height:
            size = probe_size(files[0], ff)
            thumb_height = round(a.thumb_width * size[1] / size[0]) if size else 180
            thumb_height = max(16, thumb_height)
        vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
              "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,"
              "tile=%dx%d:padding=4:color=0x101010" % (
                  a.thumb_width, thumb_height, a.thumb_width, thumb_height,
                  a.cols, rows))
        run([ff, "-v", "error", "-y", "-start_number", "0",
             "-i", os.path.join(tmp, "f_%04d.png"), "-vf", vf, "-frames:v", "1", a.out])

    print("联系表: %s（%d 个样本，%d 列）" % (a.out, len(files), a.cols))
    print("验收重点：风格孤岛、人物一致性、字幕压脸、片头片尾完整性。")


if __name__ == "__main__":
    main()
