#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把逐句时间轴 + 分镜字幕位置合成 lines.json（喂给 make_subs.py）。

核心作用：**字幕位置跟着镜头走**。
每句歌词落在哪个镜头里，就继承那个镜头的 place（T 顶部 / M 中部 / B 底部），
而不是全片固定一行。这是"字幕与画面联动"的落地点——
人物在哪一侧、画面哪里是空的，由分镜表决定，字幕照抄。

用法:
    python build_lines.py --timing lines_timing.json --shots shots.tsv \
        --cards cards.json -o lines.json

shots.tsv 必须有列: id, t0, t1, place
cards.json（可选）结构:
    {
      "opening": [ {"start":0.85,"end":7.05,"text":"歌名","title":true,"y":505,"fs":208} ],
      "ending":  [ {"start":248.8,"end":251.9,"text":"歌名","title":true,"y":236} ]
    }
card 支持的字段见 references/subtitle-styling.md
"""

import argparse
import csv
import json
from collections import Counter


def load_shots(path):
    shots = []
    with open(path, encoding="utf-8-sig") as f:      # 注意 BOM：Excel 另存的 TSV 常带
        for row in csv.DictReader(f, delimiter="\t"):
            shots.append({"id": row["id"].strip(),
                          "t0": float(row["t0"]), "t1": float(row["t1"]),
                          "place": (row.get("place") or "B").strip() or "B"})
    shots.sort(key=lambda s: s["t0"])
    return shots


def place_at(shots, t0, t1, default="B"):
    """按"歌词中点落在哪个镜头"决定字幕位置。

    为什么不用起点：切点是吸附到拍点的，常与歌词起点差几十毫秒，
    按起点归属会把歌词判给上一个镜头。用中点最稳，也能正确处理
    "一个镜头里跨两句歌词"的情况（取覆盖时长更多的那一镜）。
    """
    if not shots:
        return default, None
    mid = (t0 + t1) / 2.0
    eps = 1e-6
    for s in shots:
        if s["t0"] - eps <= mid < s["t1"] + eps:
            return s["place"], s["id"]
    near = min(shots, key=lambda s: abs((s["t0"] + s["t1"]) / 2.0 - mid))
    return near["place"], near["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", required=True)
    ap.add_argument("--shots", required=True)
    ap.add_argument("--cards", default="")
    ap.add_argument("--default-place", default="B")
    ap.add_argument("-o", "--out", default="lines.json")
    a = ap.parse_args()

    with open(a.timing, encoding="utf-8") as f:
        timing = json.load(f)
    shots = load_shots(a.shots)

    out, hits = [], Counter()
    for ln in timing:
        pl, sid = place_at(shots, float(ln["start"]), float(ln["end"]), a.default_place)
        hits[pl] += 1
        out.append({"start": ln["start"], "end": ln["end"],
                    "text": ln["text"], "place": pl, "shot": sid})

    if a.cards:
        with open(a.cards, encoding="utf-8") as f:
            cards = json.load(f)
        out = list(cards.get("opening", [])) + out + list(cards.get("ending", []))

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("字幕条目 %d（歌词 %d）" % (len(out), len(timing)))
    print("位置分布:", dict(hits))
    for o in out[:3] + out[-3:]:
        print("  %6.2f-%6.2f %s %-6s %s"
              % (o["start"], o["end"], o.get("place", "-"),
                 o.get("shot", "-") or "-", o["text"]))


if __name__ == "__main__":
    main()
