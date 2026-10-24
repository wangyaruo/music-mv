#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从分镜图或成片抽帧生成封面，补齐"MP4 + 封面"的交付承诺。

用法:
    python scripts/make_cover.py --image images/c16/s12.png \
        --title "园游会" --artist "周杰伦" --out out/cover.png
    python scripts/make_cover.py --video 成片.mp4 --time 42 \
        --title "园游会" --width 1080 --height 1920 --out out/cover_916.png
"""

import argparse
import os
import subprocess
import tempfile


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def filter_path(path):
    return (os.path.abspath(path).replace("\\", "\\\\")
            .replace(":", "\\:").replace("'", "\\'"))


def ass_text(text):
    return str(text).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        print(p.stderr[-3000:])
        raise SystemExit("封面生成失败")


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image")
    src.add_argument("--video")
    ap.add_argument("--time", type=float, default=0.0, help="视频抽帧秒数")
    ap.add_argument("--title", required=True)
    ap.add_argument("--artist", default="")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--font", default="ZCOOL KuaiLe")
    ap.add_argument("--fontsdir", default="")
    ap.add_argument("--darken", type=float, default=0.04, help="压暗背景 0~0.3，默认 0.04")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ff = ffmpeg_exe()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fontsdir = a.fontsdir or os.path.join(root, "assets", "fonts")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    unit = min(a.width, a.height)
    title_fs, artist_fs = round(unit * 0.115), round(unit * 0.045)
    outline = max(2.0, unit * 0.006)

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cover,%s,%d,&H00F0FAFF,&H00F0FAFF,&H003A281E,&H80000000,-1,0,0,0,100,100,0,0,1,%.1f,2.0,5,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (a.width, a.height, a.font, title_fs, outline)
    events = ["Dialogue: 0,0:00:00.00,0:00:01.00,Cover,,0,0,0,,"
              "{\\an5\\pos(%.1f,%.1f)}%s" % (a.width / 2, a.height * 0.46, ass_text(a.title))]
    if a.artist:
        events.append("Dialogue: 0,0:00:00.00,0:00:01.00,Cover,,0,0,0,,"
                      "{\\an5\\pos(%.1f,%.1f)\\fs%d\\bord%.1f}%s" % (
                          a.width / 2, a.height * 0.60, artist_fs,
                          max(1.5, outline * 0.65), ass_text(a.artist)))

    with tempfile.TemporaryDirectory(prefix="mv_cover_") as tmp:
        image = a.image
        if a.video:
            image = os.path.join(tmp, "frame.png")
            run([ff, "-v", "error", "-y", "-ss", "%.3f" % a.time,
                 "-i", a.video, "-frames:v", "1", image])
        subs = os.path.join(tmp, "cover.ass")
        with open(subs, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events) + "\n")

        vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
              "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1" % (
                  a.width, a.height, a.width, a.height))
        if a.darken > 0:
            vf += ",eq=brightness=%.3f" % (-min(a.darken, 0.3))
        vf += ",ass=filename='%s':fontsdir='%s'" % (filter_path(subs), filter_path(fontsdir))
        run([ff, "-v", "error", "-y", "-i", image, "-vf", vf,
             "-frames:v", "1", a.out])

    print("封面: %s（%dx%d）" % (a.out, a.width, a.height))


if __name__ == "__main__":
    main()
