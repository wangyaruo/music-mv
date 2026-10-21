#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""歌词分组 → 逐句时间轴（锚点 + 按字比例分配 + 拍点吸附）。

为什么需要"分组"：ASR 对演唱中的中文歌词识别率极低（会把「被我收得好好的」
识别成「被我收远不尔斯坦」），但它给出的**段落边界**通常是对的。
因此本脚本采用"锚点法"：

    人工写准歌词 → 用 ASR 边界把歌词切成若干"组" →
    组内按字数比例分配时间 → 每句起止吸附到拍点网格

这比逐字强对齐稳，也比纯平均分配准。

用法:
    python lyrics_timing.py --groups groups.json --beats beats.json -o lines_timing.json

groups.json 结构:
    {
      "grid_div": 4,        # 吸附网格 = 拍 / grid_div，默认 4（1/4 拍）
      "max_shift": 0.10,    # 吸附允许的最大位移（秒），超出则保留原值
      "groups": [
        {"t0": 32.00, "t1": 35.90, "lines": ["琥珀色黄昏像糖 在很美的远方"]},
        {"t0": 35.95, "t1": 43.40, "lines": ["你的脸没有化妆 我却疯狂爱上",
                                             "思念跟影子在傍晚一起被拉长"]}
      ]
    }

group 的 t0/t1 只作为"组边界"，组内每句的长度由字数比例决定。
"""

import argparse
import json

import numpy as np


def nchars(s):
    """只数非空白字符——歌词里的空格是分句用的，不占时间。"""
    return len([c for c in s if c.strip()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", required=True)
    ap.add_argument("--beats", required=True)
    ap.add_argument("-o", "--out", default="lines_timing.json")
    a = ap.parse_args()

    with open(a.beats, encoding="utf-8") as f:
        b = json.load(f)
    per, off = b["beat_period"], b["offset"]

    with open(a.groups, encoding="utf-8") as f:
        cfg = json.load(f)
    grid_div = float(cfg.get("grid_div", 4))
    max_shift = float(cfg.get("max_shift", 0.10))
    groups = cfg["groups"]

    GRID = per / grid_div

    def snap(t):
        g = off + round((t - off) / GRID) * GRID
        return g if abs(g - t) <= max_shift else t

    lines = []
    for gi, g in enumerate(groups, 1):
        texts = g["lines"]
        total = sum(nchars(t) for t in texts)
        if total == 0:
            continue
        span = float(g["t1"]) - float(g["t0"])
        acc = 0
        for i, t in enumerate(texts):
            n = nchars(t)
            s = float(g["t0"]) + span * acc / total
            acc += n
            e = float(g["t0"]) + span * acc / total
            # 组首句起点、组末句终点保持贴紧组边界，不吸附
            if i > 0:
                s = snap(s)
            if i < len(texts) - 1:
                e = snap(e)
            lines.append({"start": round(s, 3), "end": round(e, 3),
                          "text": t, "group": gi})

    # 首尾与音频实际演唱区间对齐
    lines[0]["start"] = float(groups[0]["t0"])
    lines[-1]["end"] = float(groups[-1]["t1"])

    for i, l in enumerate(lines):
        l["idx"] = i + 1
        l["dur"] = round(l["end"] - l["start"], 3)
        l["n"] = nchars(l["text"])

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False, indent=1)

    print("共 %d 句，覆盖 %.2f - %.2f s" % (len(lines), lines[0]["start"], lines[-1]["end"]))
    for l in lines:
        print("%2d  %6.2f-%6.2f  %4.2fs  %2d字  %5.2f s/字  %s"
              % (l["idx"], l["start"], l["end"], l["dur"], l["n"],
                 l["dur"] / max(l["n"], 1), l["text"]))

    # 语速体检：同一首歌里 s/字 差异过大通常说明某个组边界估错了
    rates = [l["dur"] / max(l["n"], 1) for l in lines]
    if rates:
        med = float(np.median(rates))
        print("\n语速中位数 %.3f s/字" % med)
        odd = [l for l in lines if abs(l["dur"] / max(l["n"], 1) - med) > med * 0.45]
        if odd:
            print("⚠ 以下行语速明显偏离中位数，检查对应的组边界：")
            for l in odd:
                print("   #%d %.2f-%.2f %.2f s/字  %s"
                      % (l["idx"], l["start"], l["end"], l["dur"] / max(l["n"], 1), l["text"]))


if __name__ == "__main__":
    main()
