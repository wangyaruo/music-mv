#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零 AI 额度的端到端 demo：程序生成音频与静帧，跑通完整 MV 工具链。

在仓库根目录运行：
    python examples/make_demo.py --out out/demo

产出：成片.mp4、封面、风格/成片联系表、manifest、QA 报告。
 demo 使用已知 120 BPM 网格保证可复现；真实项目请用 beat_sync.py 实测。
"""

import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def run(cmd, **kwargs):
    print("+", " ".join(str(x) for x in cmd))
    binary = isinstance(kwargs.get("input"), (bytes, bytearray))
    p = subprocess.run([str(x) for x in cmd], capture_output=True,
                       text=not binary, **kwargs)
    if p.returncode:
        stdout = p.stdout.decode("utf-8", "ignore") if binary else p.stdout
        stderr = p.stderr.decode("utf-8", "ignore") if binary else p.stderr
        print(stdout)
        print(stderr[-4000:])
        raise SystemExit("命令失败: %s" % cmd[0])
    return p


def script(name, *args):
    return run([sys.executable, os.path.join(SCRIPTS, name)] + list(args))


def make_audio(path, duration=12.0, sr=22050):
    """120 BPM 的简短合成旋律，每拍一个明确 onset。"""
    beat = 0.5
    audio = np.zeros(int(duration * sr), dtype=np.float64)
    notes = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63,
             293.66, 349.23, 440.00, 587.33, 440.00, 349.23]
    for k in range(int(duration / beat)):
        start = int(k * beat * sr)
        end = min(len(audio), int((k + 1) * beat * sr))
        t = np.arange(end - start) / sr
        f = notes[k % len(notes)]
        env = np.minimum(t / 0.015, 1.0) * np.exp(-t * 2.2)
        audio[start:end] += 0.28 * env * (np.sin(2 * np.pi * f * t)
                                          + 0.25 * np.sin(4 * np.pi * f * t))
        audio[start:end] += 0.36 * np.exp(-t * 65) * np.sin(2 * np.pi * 1200 * t)
    fade = int(0.15 * sr)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    audio *= 0.88 / max(1e-9, np.max(np.abs(audio)))
    pcm = (audio * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def make_image(path, index, width, height):
    """生成确定性的插画式色块图，不依赖 Pillow 或 AI 出图。"""
    palettes = [((44, 62, 104), (244, 177, 131)),
                ((63, 102, 127), (255, 214, 153)),
                ((90, 67, 118), (246, 166, 184)),
                ((30, 83, 92), (178, 220, 190))]
    top, bottom = palettes[index % len(palettes)]
    y = np.linspace(0, 1, height)[:, None, None]
    top_a = np.array(top, dtype=float)[None, None, :]
    bottom_a = np.array(bottom, dtype=float)[None, None, :]
    img = np.repeat(top_a * (1 - y) + bottom_a * y, width, axis=1)
    yy, xx = np.mgrid[0:height, 0:width]
    xn, yn = xx / width, yy / height

    # 太阳与光晕
    sx, sy = 0.76 - index * 0.08, 0.26 + (index % 2) * 0.08
    dist = np.sqrt((xn - sx) ** 2 + (yn - sy) ** 2)
    img[dist < 0.115] = (255, 224, 146)
    img[dist < 0.070] = (255, 241, 188)

    # 远山、地面与近景建筑
    mountain = yn > (0.66 - 0.16 * np.abs(np.sin(xn * 8 + index)))
    img[mountain] = (74, 91, 111)
    img[yn > 0.76] = (54, 73, 75)
    booth = (xn > 0.67) & (xn < 0.88) & (yn > 0.60) & (yn < 0.80)
    img[booth] = (199, 113, 91)
    roof = (xn > 0.64) & (xn < 0.91) & (yn > 0.56) & (yn < 0.61)
    img[roof] = (248, 211, 154)

    # 一个可辨认的小人：头、身体、腿；位置随镜头变化
    cx = 0.25 + index * 0.09
    head = (xn - cx) ** 2 + (yn - 0.58) ** 2 < 0.030 ** 2
    body = (np.abs(xn - cx) < 0.035) & (yn > 0.61) & (yn < 0.72)
    legs = (np.abs(xn - cx) < 0.025) & (yn >= 0.72) & (yn < 0.79)
    img[head] = (238, 190, 155)
    img[body] = (164, 74, 68)
    img[legs] = (42, 54, 78)

    arr = np.clip(img, 0, 255).astype(np.uint8)
    ff = ffmpeg_exe()
    run([ff, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", "%dx%d" % (width, height), "-i", "-", "-frames:v", "1", path],
        input=arr.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/demo")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=360)
    a = ap.parse_args()

    project = os.path.abspath(a.out)
    outdir = os.path.join(project, "out")
    images = os.path.join(project, "images", "c16")
    clips = os.path.join(project, "clips")
    for d in [outdir, images, clips, os.path.join(outdir, "qa")]:
        os.makedirs(d, exist_ok=True)
    ff = ffmpeg_exe()
    audio = os.path.join(project, "song.wav")
    final = os.path.join(project, "成片.mp4")

    make_audio(audio)
    duration, period, offset = 12.0, 0.5, 0.0
    beats = []
    t = offset
    while t < duration + period:
        beats.append(round(t, 4))
        t += period
    with open(os.path.join(outdir, "beats.json"), "w", encoding="utf-8") as f:
        json.dump(dict(bpm=120.0, beat_period=period, offset=offset, duration=duration,
                       beats=beats, subdiv={"1": 0.5, "2": 0.25, "4": 0.125, "8": 0.0625}),
                  f, ensure_ascii=False, indent=1)

    shots = [
        ("s01", 0, 2, "T", "", "黄昏集市入口与摩天轮", "缓慢推进"),
        ("s02", 2, 6, "B", "风吹过夏夜的窗边", "角色在集市中抬头", "轻微横移"),
        ("s03", 6, 10, "T", "把回忆拼好给你", "角色与票根和夕阳", "气球上浮"),
        ("s04", 10, 12, "M", "", "尾奏回到入口", "缓慢拉远"),
    ]
    with open(os.path.join(outdir, "shots.tsv"), "w", encoding="utf-8") as f:
        f.write("id\tt0\tt1\tplace\tlyric\tscene\tmotion\n")
        for row in shots:
            f.write("\t".join(str(x) for x in row) + "\n")
    with open(os.path.join(outdir, "groups.json"), "w", encoding="utf-8") as f:
        json.dump(dict(grid_div=4, max_shift=0.10, groups=[
            dict(t0=2, t1=6, lines=["风吹过夏夜的窗边"]),
            dict(t0=6, t1=10, lines=["把回忆拼好给你"])]), f, ensure_ascii=False, indent=1)
    with open(os.path.join(outdir, "cards.json"), "w", encoding="utf-8") as f:
        json.dump(dict(opening=[dict(start=0.2, end=1.8, text="卡拍小样", title=True,
                                     y=a.height * 0.45)],
                       ending=[dict(start=10.2, end=11.8, text="music-mv demo",
                                    title=True, y=a.height * 0.40)]),
                  f, ensure_ascii=False, indent=1)

    for i in range(4):
        image = os.path.join(images, "s%02d.png" % (i + 1))
        clip = os.path.join(clips, "v%02d.mp4" % (i + 1))
        make_image(image, i, a.width, a.height)
        frames = 84
        run([ff, "-v", "error", "-y", "-loop", "1", "-i", image,
             "-vf", "scale=%d:-1,zoompan=z='min(1.0+0.0008*on,1.08)':"
                    "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=24,"
                    "format=yuv420p" % (a.width * 2, frames, a.width, a.height),
             "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-pix_fmt", "yuv420p", "-an", clip])

    script("lyrics_timing.py", "--groups", os.path.join(outdir, "groups.json"),
           "--beats", os.path.join(outdir, "beats.json"),
           "-o", os.path.join(outdir, "lines_timing.json"))
    script("build_lines.py", "--timing", os.path.join(outdir, "lines_timing.json"),
           "--shots", os.path.join(outdir, "shots.tsv"),
           "--cards", os.path.join(outdir, "cards.json"),
           "-o", os.path.join(outdir, "lines.json"))
    script("make_subs.py", "--lines", os.path.join(outdir, "lines.json"),
           "--beats", os.path.join(outdir, "beats.json"), "--motifs",
           "--width", str(a.width), "--height", str(a.height),
           "-o", os.path.join(outdir, "subs.ass"))

    script("manifest.py", "init", "--shots", os.path.join(outdir, "shots.tsv"),
           "--audio", audio, "--style", "demo-color-block",
           "--width", str(a.width), "--height", str(a.height),
           "--cost-per-shot", "0", "--force", "-o", os.path.join(outdir, "manifest.json"))
    for i in range(1, 5):
        script("manifest.py", "update", "-m", os.path.join(outdir, "manifest.json"),
               "--shot", "s%02d" % i, "--status", "done", "--source", "still",
               "--credits", "0", "--note", "demo 程序静帧，不消耗 AI 额度")
    script("manifest.py", "report", "-m", os.path.join(outdir, "manifest.json"))

    script("build_base.py", "--shots", os.path.join(outdir, "shots.tsv"),
           "--clips-dir", clips, "--beats", os.path.join(outdir, "beats.json"),
           "--audio", audio, "--fade", "0.3", "--grid-div", "4",
           "--width", str(a.width), "--height", str(a.height),
           "--preset", "veryfast", "--work-dir", outdir,
           "-o", os.path.join(outdir, "base.mp4"))
    script("mix_final.py", "--base", os.path.join(outdir, "base.mp4"),
           "--audio", audio, "--subs", os.path.join(outdir, "subs.ass"),
           "--fade-in", "0.4", "--fade-out", "0.8", "--preset", "veryfast",
           "--out", final)
    script("make_cover.py", "--image", os.path.join(images, "s02.png"),
           "--title", "卡拍小样", "--artist", "music-mv demo",
           "--width", str(a.width), "--height", str(a.height),
           "--out", os.path.join(outdir, "cover.png"))
    script("contact_sheet.py", "--images", os.path.join(images, "s*.png"),
           "--out", os.path.join(outdir, "qa", "style_sheet.png"),
           "--cols", "4", "--thumb-width", "320")
    script("contact_sheet.py", "--video", final,
           "--out", os.path.join(outdir, "qa", "film_sheet.png"),
           "--count", "8", "--cols", "4", "--thumb-width", "320")
    script("qa_check.py", "--project", project, "--audio", audio, "--final", final)

    print("\nDEMO 完成")
    print("成片:", final)
    print("封面:", os.path.join(outdir, "cover.png"))
    print("联系表:", os.path.join(outdir, "qa", "film_sheet.png"))
    print("QA:", os.path.join(outdir, "qa_report.json"))


if __name__ == "__main__":
    main()
