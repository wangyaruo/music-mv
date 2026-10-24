#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验复唱段落：两遍同一句歌词的起点差必须是常数。

不再假设"整首歌恰好对半分两遍"，而是显式给句号区间（1 起、含端点）。

用法:
    python scripts/check_repeat.py --timing out/lines_timing.json \
        --first 1-18 --second 19-36
    # 需要修正时，以第一遍 + 中位偏移重建第二遍，写到新文件：
    python scripts/check_repeat.py --timing out/lines_timing.json \
        --first 1-18 --second 19-36 --fix-out out/lines_timing.fixed.json
"""

import argparse
import json
import statistics


def parse_range(value, upper):
    try:
        a, b = value.split("-", 1)
        start, end = int(a), int(b)
    except ValueError:
        raise SystemExit("区间格式应为 1-18（1 起、含端点）: %s" % value)
    if start < 1 or end < start or end > upper:
        raise SystemExit("区间越界: %s（当前共 %d 句）" % (value, upper))
    return list(range(start - 1, end))


def compare(lines, first, second):
    if len(first) != len(second):
        raise ValueError("两遍句数不同：%d vs %d；请检查区间" % (len(first), len(second)))
    rows = []
    for i, j in zip(first, second):
        a, b = lines[i], lines[j]
        rows.append(dict(first_idx=i + 1, second_idx=j + 1,
                         first_start=float(a["start"]), second_start=float(b["start"]),
                         delta=float(b["start"]) - float(a["start"]),
                         first_text=a["text"], second_text=b["text"],
                         same_text=a["text"] == b["text"]))
    deltas = [r["delta"] for r in rows]
    offset = statistics.median(deltas)
    drift = max(deltas) - min(deltas)
    return rows, offset, drift


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", required=True)
    ap.add_argument("--first", required=True, help="第一遍句号区间，如 1-18")
    ap.add_argument("--second", required=True, help="第二遍句号区间，如 19-36")
    ap.add_argument("--tolerance", type=float, default=0.15,
                    help="允许的最大偏移极差，默认 0.15s")
    ap.add_argument("--fix-out", default="",
                    help="可选：按第一遍 + 中位偏移重建第二遍，写到新文件")
    a = ap.parse_args()

    with open(a.timing, encoding="utf-8") as f:
        lines = json.load(f)
    first = parse_range(a.first, len(lines))
    second = parse_range(a.second, len(lines))
    try:
        rows, offset, drift = compare(lines, first, second)
    except ValueError as exc:
        raise SystemExit(str(exc))

    for r in rows:
        mark = "" if r["same_text"] else "  ⚠文本不同"
        print("%2d → %2d  %8.3f → %8.3f  差 %+7.3fs  %s%s" % (
            r["first_idx"], r["second_idx"], r["first_start"], r["second_start"],
            r["delta"], r["first_text"][:18], mark))
    print("\n中位偏移 %.3fs，偏移极差 %.3fs，容差 %.3fs" % (offset, drift, a.tolerance))
    if drift > a.tolerance:
        print("FAIL：偏移不是常数，第二遍很可能按字数重新分配过。")
    else:
        print("PASS：两遍偏移恒定。")

    if a.fix_out:
        fixed = [dict(x) for x in lines]
        for i, j in zip(first, second):
            dur = float(lines[i]["end"]) - float(lines[i]["start"])
            fixed[j]["start"] = round(float(lines[i]["start"]) + offset, 3)
            fixed[j]["end"] = round(fixed[j]["start"] + dur, 3)
            fixed[j]["dur"] = round(dur, 3)
        with open(a.fix_out, "w", encoding="utf-8") as f:
            json.dump(fixed, f, ensure_ascii=False, indent=1)
        print("已按第一遍 + %.3fs 重建第二遍: %s" % (offset, a.fix_out))
        print("请人工抽查后再替换原 lines_timing.json，并重建 lines/subs/base。")

    if drift > a.tolerance:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
