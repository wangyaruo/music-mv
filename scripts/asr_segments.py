#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 ASR 的段落边界生成 groups.json 草稿，绝不采用 ASR 的歌词文本。

可选依赖（不随基础工具链安装）：
    python -m pip install -r scripts/requirements-asr.txt

用法:
    python scripts/asr_segments.py --audio song.mp3 --lyrics lyrics.txt \
        -o out/groups.json

输出必须人工核对，尤其是复唱段落与长副歌。脚本只回答"哪些时刻是段落边界"，
歌词文本始终来自人工校对后的 lyrics.txt。
"""

import argparse
import json
import os


def clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def allocate(lines, segments):
    """按字数比例的句中点，把人工歌词分配到 ASR 段落。纯函数，便于测试。"""
    if not lines:
        raise ValueError("歌词为空")
    if not segments:
        raise ValueError("ASR 没有给出段落边界")
    segments = sorted(segments, key=lambda s: (s["start"], s["end"]))
    total = sum(len("".join(c for c in line if c.strip())) for line in lines)
    if total == 0:
        raise ValueError("歌词没有有效字符")
    audio_start = float(segments[0]["start"])
    audio_end = float(segments[-1]["end"])
    span = audio_end - audio_start
    if span <= 0:
        raise ValueError("ASR 段落时长无效")

    grouped = {}
    acc = 0
    for line in lines:
        n = len("".join(c for c in line if c.strip()))
        ideal_mid = audio_start + span * (acc + n / 2) / total
        acc += n
        # 优先落在包含理想中点的段落；落在静音区时取最近段落。
        def distance(i):
            start, end = float(segments[i]["start"]), float(segments[i]["end"])
            if start <= ideal_mid <= end:
                return 0.0
            return min(abs(ideal_mid - start), abs(ideal_mid - end))

        idx = min(range(len(segments)), key=distance)
        grouped.setdefault(idx, dict(t0=float(segments[idx]["start"]),
                                     t1=float(segments[idx]["end"]), lines=[]))
        grouped[idx]["lines"].append(line)
    return [grouped[i] for i in sorted(grouped)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--lyrics", required=True, help="人工核对后的歌词，每行一句")
    ap.add_argument("--model", default="small", help="faster-whisper 模型，默认 small")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--compute-type", default="auto")
    ap.add_argument("--grid-div", type=float, default=4)
    ap.add_argument("--max-shift", type=float, default=0.10)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("缺少可选依赖 faster-whisper；请先运行：\n"
                         "  python -m pip install -r scripts/requirements-asr.txt")

    with open(a.lyrics, encoding="utf-8") as f:
        lines = clean_lines(f.read())
    print("载入人工歌词 %d 句；ASR 文本将被丢弃，只保留段落边界。" % len(lines))
    model = WhisperModel(a.model, device=a.device, compute_type=a.compute_type)
    result, info = model.transcribe(
        a.audio, language=a.language, beam_size=1, temperature=0,
        word_timestamps=False, vad_filter=True, condition_on_previous_text=False)
    segments = [dict(start=float(s.start), end=float(s.end)) for s in result]
    print("ASR 段落 %d 个，音频时长约 %.2fs" % (len(segments), getattr(info, "duration", 0)))
    try:
        groups = allocate(lines, segments)
    except ValueError as exc:
        raise SystemExit(str(exc))
    if len(groups) <= 2 and len(lines) > 8:
        print("⚠ 段落过少，长副歌可能被并成一组；必须人工拆分，不能直接生产。")

    data = dict(grid_div=a.grid_div, max_shift=a.max_shift, groups=groups)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("已写出 groups.json 草稿: %s（%d 组 / %d 句）" % (a.out, len(groups), len(lines)))
    print("下一步：人工核对组边界与复唱，再运行 lyrics_timing.py 和 check_repeat.py。")


if __name__ == "__main__":
    main()
