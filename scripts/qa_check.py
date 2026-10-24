#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前自动验收：只把"可能失败的指标"列为 PASS/FAIL。

默认读取项目目录下的：
  out/lines.json、out/shots.tsv、out/timeline_report.json、
  out/build_report.json、out/manifest.json

用法:
    python scripts/qa_check.py --project .
    python scripts/qa_check.py --project . --audio song.mp3 --final 成片.mp4
    python scripts/qa_check.py --project . --strict   # WARN 也使退出码非零
"""

import argparse
import csv
import json
import os
import re
import subprocess
from collections import Counter


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


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_shots(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    shots = [dict(id=r["id"].strip(), t0=float(r["t0"]), t1=float(r["t1"]),
                  place=(r.get("place") or "B")) for r in rows]
    return sorted(shots, key=lambda x: x["t0"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--audio", default="")
    ap.add_argument("--final", default="")
    ap.add_argument("--chunk-max", type=int, default=18)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    root = os.path.abspath(a.project)
    outdir = os.path.join(root, "out")
    ff = ffmpeg_exe()
    checks = []

    def add(name, status, detail):
        checks.append(dict(name=name, status=status, detail=detail))
        print("%-4s %-24s %s" % (status, name, detail))

    def path(name):
        p = os.path.join(outdir, name)
        return p if os.path.isfile(p) else ""

    # 1. 时长：build_report 是真实 probe 值，不是从网格反推的值。
    build_path = path("build_report.json")
    if build_path:
        b = read_json(build_path)
        delta = abs(float(b["actual_duration"]) - float(b["target_duration"]))
        add("base_duration", "PASS" if delta <= 0.1 else "FAIL",
            "实际 %.3fs / 目标 %.3fs，差 %.3fs" % (
                b["actual_duration"], b["target_duration"], delta))
    else:
        add("base_duration", "SKIP", "没有 out/build_report.json")

    if a.final and a.audio:
        fd, ad = probe_duration(a.final, ff), probe_duration(a.audio, ff)
        if fd is None or ad is None:
            add("final_audio_duration", "FAIL", "无法读取成片或音频时长")
        else:
            delta = abs(fd - ad)
            add("final_audio_duration", "PASS" if delta <= 0.1 else "FAIL",
                "成片 %.3fs / 音频 %.3fs，差 %.3fs" % (fd, ad, delta))
    else:
        add("final_audio_duration", "SKIP", "未同时提供 --final 与 --audio")

    # 2. 切点必须贴近歌词起点。优先用吸附后的真实 bounds，而不是原始 TSV。
    lines_path, shots_path = path("lines.json"), path("shots.tsv")
    timeline_path = path("timeline_report.json")
    if lines_path and shots_path:
        lines, shots = read_json(lines_path), read_shots(shots_path)
        index = {s["id"]: i for i, s in enumerate(shots)}
        bounds = None
        if timeline_path:
            bounds = read_json(timeline_path).get("bounds")
        rows = []
        for line in lines:
            sid = line.get("shot")
            if sid not in index:
                continue
            i = index[sid]
            cut = bounds[i] if bounds and i < len(bounds) else shots[i]["t0"]
            rows.append((abs(float(cut) - float(line["start"])), sid, line.get("text", "")[:16]))
        if rows:
            worst = max(rows)
            add("cut_lyric_alignment", "PASS" if worst[0] <= 0.1 else "FAIL",
                "最大偏差 %.3fs（%s %s），阈值 0.1s" % worst)
        else:
            add("cut_lyric_alignment", "WARN", "lines.json 没有可关联的 shot 字段")

        lyric = [x for x in lines if x.get("shot")]
        overlaps = []
        for prev, cur in zip(lyric, lyric[1:]):
            if float(cur["start"]) < float(prev["end"]) - 0.02:
                overlaps.append("%s/%s" % (prev.get("shot"), cur.get("shot")))
        add("subtitle_overlap", "FAIL" if overlaps else "PASS",
            ("重叠: " + ", ".join(overlaps[:6])) if overlaps else "相邻歌词字幕无重叠")

        long_lines = [x.get("shot") for x in lyric
                      if len("".join(c for c in x.get("text", "") if c.strip())) > a.chunk_max]
        add("subtitle_chunk", "WARN" if long_lines else "PASS",
            ("超过 %d 字: %s" % (a.chunk_max, ", ".join(long_lines))) if long_lines
            else "没有会被拆段轮流显示的长句")
        places = Counter(x.get("place", "B") for x in lyric)
        add("subtitle_place", "WARN" if len(places) < 2 and len(lyric) > 1 else "PASS",
            "位置分布 %s" % dict(places))
    else:
        add("cut_lyric_alignment", "SKIP", "需要 out/lines.json 与 out/shots.tsv")

    # 吸附位移只报告，不设恒真型 PASS；真正的验收是 cut_lyric_alignment。
    if timeline_path:
        t = read_json(timeline_path)
        add("snap_shift", "INFO", "最大吸附位移 %.4fs，网格 %.4fs" % (
            t.get("max_snap_shift", 0), t.get("grid_step") or 0))

    # 3. 生产清单：未完成和静帧兜底必须在交付说明里显式出现。
    manifest_path = path("manifest.json")
    if manifest_path:
        m = read_json(manifest_path)
        shots = m.get("shots", [])
        pending = [s["id"] for s in shots if s.get("status") != "done"]
        still = [s["id"] for s in shots if s.get("source") == "still"]
        missing = []
        for s in shots:
            clip = s.get("clip") or ""
            if s.get("status") == "done" and clip:
                full = clip if os.path.isabs(clip) else os.path.join(root, clip)
                if not os.path.isfile(full):
                    missing.append(s["id"])
        add("manifest_missing", "FAIL" if missing else "PASS",
            ("已完成但缺素材: " + ", ".join(missing)) if missing else "没有缺失的已完成素材")
        add("manifest_pending", "WARN" if pending else "PASS",
            ("未完成: " + ", ".join(pending)) if pending else "全部镜头已完成")
        add("manifest_fallback", "INFO",
            "静帧兜底: " + (", ".join(still) if still else "无"))
    else:
        add("manifest_pending", "SKIP", "没有 out/manifest.json")

    # 4. 响度是质量 WARN，不用单遍 loudnorm 的读数做硬失败。
    if a.final:
        p = subprocess.run([ff, "-hide_banner", "-i", a.final, "-af", "volumedetect",
                            "-vn", "-f", "null", "-"], capture_output=True, text=True)
        mean = re.search(r"mean_volume:\s*(-?[\d.]+)", p.stderr)
        peak = re.search(r"max_volume:\s*(-?[\d.]+)", p.stderr)
        if mean and peak:
            mean_v, peak_v = float(mean.group(1)), float(peak.group(1))
            ok = -16 <= mean_v <= -12 and peak_v <= -0.5
            add("loudness", "PASS" if ok else "WARN",
                "mean %.1fdB（参考 -16~-12），max %.1fdB（应 ≤ -0.5）" % (mean_v, peak_v))
        else:
            add("loudness", "WARN", "未读到 volumedetect 结果")
    else:
        add("loudness", "SKIP", "未提供 --final")

    counts = Counter(c["status"] for c in checks)
    report = dict(project=root, checks=checks, summary=dict(counts))
    out = a.out or os.path.join(outdir, "qa_report.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("\n汇总:", dict(counts), " 报告:", out)
    if counts.get("FAIL") or (a.strict and counts.get("WARN")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
