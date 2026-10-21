#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把基片 + 音频 + 字幕合成成片（含去水印、调色、响度标准化、首尾淡入淡出）。

一条命令收尾，避免每次手写滤镜串时把顺序写错。

用法:
    python mix_final.py --base out/base.mp4 --audio song.mp3 --subs out/subs.ass \
        --duration 255.58 --out "成片.mp4"

    # 生成图没有水印就去掉 delogo
    python mix_final.py ... --delogo off

滤镜顺序是有讲究的，不要随意调换：
    视频  delogo → eq → vignette → ass → fade → format
    音频  atrim → loudnorm → afade → aresample

  1. delogo 必须最靠前，否则水印会被调色改得不好抹
  2. ass 必须在 fade 之前，否则淡出时字幕不跟着暗
  3. loudnorm 会把采样率升到 96kHz，必须补 aresample=44100 回到常规采样率
"""

import argparse
import os
import re
import subprocess
import sys
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
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="无字幕无音轨的基片")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--subs", default="", help="ASS 字幕，留空则不加")
    ap.add_argument("--duration", type=float, default=0.0, help="成片时长，0=自动取音频时长")
    ap.add_argument("--out", "-o", default="out/final.mp4")
    ap.add_argument("--fontsdir", default="")
    ap.add_argument("--delogo", default="4:6:134:62",
                    help="水印位置 x:y:w:h，写 off 关闭")
    ap.add_argument("--eq", default="contrast=1.04:saturation=1.06")
    ap.add_argument("--vignette", default="a=PI/9", help="暗角强度，off 关闭")
    ap.add_argument("--fade-in", type=float, default=1.2)
    ap.add_argument("--fade-out", type=float, default=3.1)
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--true-peak", type=float, default=-1.0)
    ap.add_argument("--lra", type=float, default=11.0)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--ffmpeg", default="")
    a = ap.parse_args()

    ff = a.ffmpeg or ffmpeg_exe()

    dur = a.duration
    if dur <= 0:
        dur = probe_duration(a.audio, ff)
        if not dur:
            raise SystemExit("无法读取音频时长，请显式给 --duration")

    # 视频链
    v = []
    if a.delogo.strip().lower() != "off":
        x, y, w, h = [int(t) for t in a.delogo.split(":")]
        v.append("delogo=x=%d:y=%d:w=%d:h=%d:show=0" % (x, y, w, h))
    if a.eq.strip().lower() != "off":
        v.append("eq=" + a.eq)
    if a.vignette.strip().lower() != "off":
        v.append("vignette=" + a.vignette)
    if a.subs:
        fd = a.fontsdir or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "assets", "fonts")
        v.append("ass=%s:fontsdir='%s'" % (os.path.abspath(a.subs), os.path.abspath(fd)))
    if a.fade_in > 0:
        v.append("fade=t=in:st=0:d=%.2f" % a.fade_in)
    if a.fade_out > 0:
        st = max(0.0, dur - 0.1 - a.fade_out)
        v.append("fade=t=out:st=%.2f:d=%.2f" % (st, a.fade_out))
    v.append("format=yuv420p")

    # 音频链
    au = ["atrim=0:%.3f" % dur, "asetpts=PTS-STARTPTS",
          "loudnorm=I=%.1f:TP=%.1f:LRA=%.1f" % (a.lufs, a.true_peak, a.lra)]
    if a.fade_in > 0:
        au.append("afade=t=in:st=0:d=%.2f" % min(0.8, a.fade_in))
    if a.fade_out > 0:
        au.append("afade=t=out:st=%.2f:d=%.2f" % (max(0.0, dur - 0.2 - a.fade_out),
                                                  a.fade_out + 0.2))
    au.append("aresample=44100")

    script = "[0:v]%s[v];\n[1:a]%s[a]\n" % (",".join(v), ",".join(au))
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(script)
        fpath = f.name

    print("滤镜脚本:\n  " + script.replace(";\n", "\n  ").strip())

    cmd = [ff, "-hide_banner", "-y", "-i", a.base, "-i", a.audio,
           "-filter_complex_script", fpath, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
           "-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "192k",
           "-t", "%.3f" % dur, "-movflags", "+faststart", a.out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(fpath)
    if p.returncode != 0:
        print(p.stderr[-3000:])
        raise SystemExit("合成失败")

    print("\n完成: %s" % a.out)
    print("  时长 %.2fs" % (probe_duration(a.out, ff) or 0))

    # 响度验收
    p = subprocess.run([ff, "-hide_banner", "-i", a.out, "-af", "volumedetect",
                        "-vn", "-f", "null", "-"], capture_output=True, text=True)
    for line in p.stderr.splitlines():
        if "mean_volume" in line or "max_volume" in line:
            print("  " + line.split("] ")[-1])
    print("  验收线: mean ≈ -14~-15 dB, max ≤ -1.0 dB")


if __name__ == "__main__":
    main()
