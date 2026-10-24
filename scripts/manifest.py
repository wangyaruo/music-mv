#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导演草稿 + 逐镜生产清单（manifest）。

在花费任何出图/视频额度之前，从 shots.tsv 生成：
  - out/storyboard.md：给用户确认的导演草稿
  - out/manifest.json：每镜的提示词、素材、来源、成本与状态

用法:
    python scripts/manifest.py init --shots out/shots.tsv --audio song.mp3 \
        --style cel --width 1920 --height 1080 -o out/manifest.json
    python scripts/manifest.py update -m out/manifest.json --shot s01 \
        --status done --source i2v --credits 93 --image-prompt "S01 ..." \
        --video-prompt "Animate ..."
    python scripts/manifest.py update -m out/manifest.json --shot s02 \
        --status done --source still --note "429，静帧 zoompan 兜底"
    python scripts/manifest.py report -m out/manifest.json
    python scripts/manifest.py storyboard -m out/manifest.json
"""

import argparse
import csv
import datetime
import json
import os
import re
from collections import Counter

STATUSES = ["draft", "approved", "image_done", "clip_done", "done"]
SOURCES = ["pending", "i2v", "still", "reuse"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def read_shots(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    shots = []
    for row in rows:
        sid = row["id"].strip()
        stem = re.sub(r"^\D+", "", sid) or sid
        shots.append(dict(
            id=sid, t0=float(row["t0"]), t1=float(row["t1"]),
            place=(row.get("place") or "B").strip() or "B",
            lyric=(row.get("lyric") or "").strip(),
            scene=(row.get("scene") or "").strip(),
            motion=(row.get("motion") or "").strip(),
            status="draft", source="pending",
            image="images/c16/s%s.png" % stem,
            clip="clips/v%s.mp4" % stem,
            image_prompt="", video_prompt="", model="", seed="",
            credits=0, note=""))
    shots.sort(key=lambda x: x["t0"])
    return shots


def storyboard_text(data):
    shots = data["shots"]
    canvas = data.get("canvas", {})
    estimate = len(shots) * data.get("cost_per_shot", 93)
    lines = [
        "# 导演草稿（生成前确认）", "",
        "> 本页用于在消耗出图/视频额度之前确认方向。确认后再把 manifest 中各镜状态改为 approved。", "",
        "- 画幅：%s x %s" % (canvas.get("width", "?"), canvas.get("height", "?")),
        "- 风格：%s" % (data.get("style") or "待确认"),
        "- 音频：%s" % (data.get("audio") or "待填写"),
        "- 镜头数：%d" % len(shots),
        "- 预估成本：≈ %d credits（按 %d/镜，不含角色设计图）" % (estimate, data.get("cost_per_shot", 93)),
        "", "## 确认门（全部勾选后才出第一张分镜图）", "",
        "- [ ] 画风参考图已确认，且不是仅凭风格名称想象",
        "- [ ] 角色设计图与可辨识特征复述已确认",
        "- [ ] 分镜、单镜时长、字幕 place 已确认",
        "- [ ] 成本量级与静帧兜底策略已告知用户",
        "", "## 分镜表", "",
        "| 镜头 | 时间 | 时长 | 字幕 | 歌词 | 画面 | 运动 | 状态 |",
        "|---|---|---:|---|---|---|---|---|"]
    for s in shots:
        scene = s["scene"].replace("|", "\\|")
        motion = s["motion"].replace("|", "\\|")
        lyric = s["lyric"].replace("|", "\\|")
        lines.append("| %s | %.2f–%.2f | %.2fs | %s | %s | %s | %s | %s |" % (
            s["id"], s["t0"], s["t1"], s["t1"] - s["t0"], s["place"],
            lyric, scene, motion, s["status"]))
    lines += ["", "## 交付时要能回答", "",
              "- 哪些镜头是 `still`（静帧兜底），哪些素材被复用？",
              "- 实际 credits 与预估值差多少？",
              "- 是否还有 missing 素材或未完成镜头？",
              "- 是否已跑 qa_check.py 与 contact_sheet.py？", ""]
    return "\n".join(lines)


def cmd_init(a):
    if os.path.exists(a.out) and not a.force:
        raise SystemExit("manifest 已存在；如需重建请显式加 --force：%s" % a.out)
    shots = read_shots(a.shots)
    if not shots:
        raise SystemExit("分镜表为空")
    data = dict(schema_version=1,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                audio=a.audio, style=a.style,
                canvas=dict(width=a.width, height=a.height),
                cost_per_shot=a.cost_per_shot, shots=shots)
    save(a.out, data)
    board = a.storyboard or os.path.join(os.path.dirname(a.out), "storyboard.md")
    with open(board, "w", encoding="utf-8") as f:
        f.write(storyboard_text(data))
    print("已生成 %d 镜的导演草稿与生产清单：" % len(shots))
    print("  %s\n  %s" % (a.out, board))
    print("预估成本 ≈ %d credits。请先确认 storyboard，再开始出图。" % (len(shots) * a.cost_per_shot))


def cmd_update(a):
    data = load(a.manifest)
    matches = [s for s in data["shots"] if s["id"] == a.shot]
    if not matches:
        raise SystemExit("manifest 中没有镜头 %s" % a.shot)
    shot = matches[0]
    fields = ["status", "source", "image", "clip", "image_prompt", "video_prompt",
              "model", "seed", "note"]
    for key in fields:
        value = getattr(a, key)
        if value is not None:
            shot[key] = value
    if a.credits is not None:
        shot["credits"] = a.credits
    if shot["source"] == "still" and not shot["note"]:
        shot["note"] = "静帧兜底；交付时必须主动说明"
    save(a.manifest, data)
    print("%s → status=%s source=%s credits=%s" % (
        a.shot, shot["status"], shot["source"], shot["credits"]))
    if shot["source"] == "still":
        print("  已标记静帧兜底，report 会把它列入交付说明。")


def cmd_storyboard(a):
    data = load(a.manifest)
    out = a.out or os.path.join(os.path.dirname(a.manifest), "storyboard.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(storyboard_text(data))
    print("已更新:", out)


def cmd_report(a):
    data = load(a.manifest)
    shots = data["shots"]
    counts = Counter(s["status"] for s in shots)
    sources = Counter(s["source"] for s in shots)
    pending = [s["id"] for s in shots if s["status"] != "done"]
    fallback = [s["id"] for s in shots if s["source"] == "still"]
    actual = sum(float(s.get("credits") or 0) for s in shots)
    estimate = len(shots) * data.get("cost_per_shot", 93)
    root = os.path.dirname(os.path.dirname(os.path.abspath(a.manifest)))
    missing = []
    for s in shots:
        if s["status"] == "done" and s.get("clip"):
            path = s["clip"] if os.path.isabs(s["clip"]) else os.path.join(root, s["clip"])
            if not os.path.isfile(path):
                missing.append("%s:%s" % (s["id"], s["clip"]))
    print("状态:", dict(counts), " 来源:", dict(sources))
    print("成本: 实际 %.0f / 预估 ≈ %d credits" % (actual, estimate))
    print("未完成:", ", ".join(pending) if pending else "无")
    print("静帧兜底（交付必须说明）:", ", ".join(fallback) if fallback else "无")
    print("已完成但缺素材:", ", ".join(missing) if missing else "无")
    if a.strict and (pending or missing):
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--shots", required=True)
    p.add_argument("--audio", default="")
    p.add_argument("--style", default="")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--cost-per-shot", type=int, default=93)
    p.add_argument("--storyboard", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("-o", "--out", required=True)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("update")
    p.add_argument("-m", "--manifest", required=True)
    p.add_argument("--shot", required=True)
    for key in ["image", "clip", "image_prompt", "video_prompt", "model", "seed", "note"]:
        p.add_argument("--" + key.replace("_", "-"), default=None)
    p.add_argument("--status", choices=STATUSES, default=None)
    p.add_argument("--source", choices=SOURCES, default=None)
    p.add_argument("--credits", type=float, default=None)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("storyboard")
    p.add_argument("-m", "--manifest", required=True)
    p.add_argument("-o", "--out", default="")
    p.set_defaults(func=cmd_storyboard)

    p = sub.add_parser("report")
    p.add_argument("-m", "--manifest", required=True)
    p.add_argument("--strict", action="store_true")
    p.set_defaults(func=cmd_report)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
