#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按分镜表搭 xfade 链，渲染无字幕无音轨的 base.mp4。

做的事:
  1. 读分镜表，取每个镜头的起点作为切点；末尾补上尾奏填充镜头
  2. 自动探测每段素材真实时长（VideoGen 有时给 5.04s 有时给 6.04s）
  3. 调 make_timeline.py 生成"切点吸附拍点 + 叠化中点压拍"的滤镜脚本
  4. 渲染 base.mp4（视频 only，音轨后面单独混）

用法:
    python build_base.py --shots shots.tsv --clips-dir clips --beats beats.json \
        --total 255.814 --fade 0.45 -o out/base.mp4

    # 尾奏（歌词唱完之后那几十秒）用前面几段镜头循环填满：
    python build_base.py ... --fill-ids s02,s10,s04,s27
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def probe_duration(path, ff=None):
    """ffprobe 不一定装，用 ffmpeg -i 的 stderr 读 Duration。"""
    ff = ff or ffmpeg_exe()
    p = subprocess.run([ff, "-hide_banner", "-i", path],
                       capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        raise SystemExit("无法读取时长: %s" % path)
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


def stem(shot_id):
    """s01 → 01；shot_12 → 12；纯数字原样返回。"""
    d = re.sub(r"^\D+", "", shot_id)
    return d or shot_id


def load_shots(path):
    shots = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            shots.append((row["id"].strip(), float(row["t0"]), float(row["t1"])))
    shots.sort(key=lambda s: s[1])
    return shots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", required=True)
    ap.add_argument("--clips-dir", default="clips")
    ap.add_argument("--clip-pattern", default="v{stem}.mp4")
    ap.add_argument("--beats", required=True)
    ap.add_argument("--total", type=float, required=True, help="成片总时长（=音频时长）")
    ap.add_argument("--fade", type=float, default=0.45)
    ap.add_argument("--grid-div", type=float, default=4.0,
                    help="切点吸附网格 = 拍 / N。默认 4（1/4 拍），与歌词起点同一网格；"
                         "设 1 则吸整拍，但会和歌词起点错开最多 ±0.25s")
    ap.add_argument("--fill-ids", default="", help="尾奏填充镜头 id，逗号分隔")
    ap.add_argument("--max-fill", type=float, default=6.0,
                    help="单个填充镜头的时长上限，应 ≤ 素材时长，否则会慢放")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成滤镜脚本，不渲染")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--ffmpeg", default="")
    ap.add_argument("--work-dir", default="out")
    ap.add_argument("-o", "--out", default="out/base.mp4")
    a = ap.parse_args()

    ff = a.ffmpeg or ffmpeg_exe()
    os.makedirs(a.work_dir, exist_ok=True)

    shots = load_shots(a.shots)
    bounds = [s[1] for s in shots] + [shots[-1][2]]

    # 分镜表必须覆盖到演唱结束；多出来的时间交给填充镜头
    if bounds[-1] > a.total + 1e-6:
        raise SystemExit("分镜表末镜 %.3f 超过总时长 %.3f" % (bounds[-1], a.total))

    fill = [x.strip() for x in a.fill_ids.split(",") if x.strip()]
    rest = a.total - bounds[-1]
    if rest > 1e-6:
        if not fill:
            raise SystemExit(
                "还剩 %.2fs 无镜头覆盖，请用 --fill-ids 指定填充镜头" % rest)
        k = max(1, int(round(rest / a.max_fill)))
        while rest / k > a.max_fill:
            k += 1
        step = rest / k
        for j in range(k):
            i = j % len(fill)
            if j >= len(fill):
                print("填充镜头不够，循环复用 %s" % fill[i])
            bounds.append(round(bounds[-1] + step, 3) if j < k - 1 else a.total)
        filler = [fill[(j % len(fill))] for j in range(k)]
        print("尾奏 %.3f s → %d 段，每段 %.3f s" % (rest, k, step))
    else:
        filler = []

    ids = [s[0] for s in shots] + filler
    clips = [os.path.join(a.clips_dir, a.clip_pattern.format(stem=stem(i), id=i))
             for i in ids]
    missing = [c for c in clips if not os.path.isfile(c)]
    if missing:
        raise SystemExit("缺少素材:\n  " + "\n  ".join(missing[:10]))

    lens = [round(probe_duration(c, ff), 3) for c in clips]
    if len(clips) != len(bounds) - 1:
        raise SystemExit("镜头数 %d 与切点数 %d 不匹配" % (len(clips), len(bounds) - 1))

    n_short = sum(1 for i, L in enumerate(lens)
                  if L < (bounds[i + 1] - bounds[i]) + a.fade)
    if n_short:
        print("⚠ 有 %d 段素材短于「镜头时长+叠化」，会在尾部冻结补帧（通常落在叠化区，不可见）"
              % n_short)

    filt = os.path.join(a.work_dir, "filter_base.txt")
    cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "make_timeline.py"),
           "--bounds", ",".join("%.3f" % b for b in bounds),
           "--beats", a.beats,
           "--total", "%.3f" % a.total,
           "--clip-lens", ",".join("%.3f" % x for x in lens),
           "--fade", "%.3f" % a.fade,
           "--grid-div", "%.1f" % a.grid_div,
           "--fps", str(a.fps),
           "--out", filt]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("时间线生成失败")

    if a.dry_run:
        print("\n--dry-run: 滤镜脚本已写入 %s，未渲染" % filt)
        return

    args = [ff, "-hide_banner", "-y"]
    for c in clips:
        args += ["-i", c]
    args += ["-filter_complex_script", filt, "-map", "[out]",
             "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
             "-pix_fmt", "yuv420p", "-r", str(a.fps), "-an", a.out]

    print("渲染 %d 段 → %s …" % (len(clips), a.out), flush=True)
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-3000:])
        raise SystemExit("渲染失败")

    dur = probe_duration(a.out, ff)
    print("base.mp4 完成  时长 %.2fs  镜头 %d  叠化 %.2fs"
          % (dur, len(clips), a.fade))


if __name__ == "__main__":
    main()
