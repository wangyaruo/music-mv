#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按"拍点对齐"生成 xfade 时间线滤镜脚本。

保证三件事：
  1. 内部切点吸附到拍点网格，且吸附后仍严格递增、没有零时长镜头
  2. 叠化中点压拍：xfade offset = 切点 − fade/2
  3. 输出时长严格等于 --total；素材不足时慢放，但受 --max-slow 约束

用法:
    python make_timeline.py --bounds 0,4.9,8.3,11.7,15.6,18.9 --beats beats.json \
        --total 18.9 --clip-len 6.04 --fade 0.45 --grid-div 4 --out filter_base.txt

注意：--bounds 必须包含首尾（第一个 0，最后一个等于 --total）。
渲染时按 bounds 顺序把 clips 依次作为 -i 输入即可。
"""

import argparse
import json


def load_beats(path):
    with open(path, encoding="utf-8") as f:
        b = json.load(f)
    return b["beat_period"], b["offset"]


def parse_floats(value):
    return [float(x) for x in value.split(",") if x.strip()]


def durations(bounds, fade, fps):
    """返回每镜时长；拒绝吸附后重合或过短、会让 xfade 链损坏的镜头。"""
    if len(bounds) < 2:
        raise ValueError("至少需要一个镜头")
    durs = [round(bounds[i + 1] - bounds[i], 3) for i in range(len(bounds) - 1)]
    min_dur = max(2.0 / fps, fade if len(durs) > 1 else 2.0 / fps)
    bad = [(i + 1, d) for i, d in enumerate(durs) if d < min_dur - 1e-9]
    if bad:
        detail = "、".join("第%d镜 %.3fs" % (i, d) for i, d in bad)
        raise ValueError(
            "切点吸附后出现零时长或过短镜头：%s；单镜至少 %.3fs。"
            "请合并相邻镜头或拉开切点，不要继续渲染。" % (detail, min_dur))
    return durs


def resize_chain(width, height):
    if not width or not height:
        return ""
    return ("scale=%d:%d:force_original_aspect_ratio=decrease,"
            "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1," % (width, height, width, height))


def build_filter(bounds, lens, total, fade, fps, fadeblack="", width=0, height=0):
    """生成滤镜行，并返回 (lines, durs, slow)。纯函数，便于回归测试。"""
    durs = durations(bounds, fade, fps)
    n = len(durs)
    if len(lens) != n:
        raise ValueError("素材时长数量 %d 与镜头数 %d 不一致" % (len(lens), n))
    if any(x <= 0 for x in lens):
        raise ValueError("素材时长必须全部大于 0")

    slow = {}
    for i in range(n):
        need = durs[i] + fade if i < n - 1 else durs[i]
        if need > lens[i]:
            slow[i + 1] = need / lens[i]

    resize = resize_chain(width, height)
    fb = set(int(x) for x in fadeblack.split(",") if x.strip())
    lines = []
    for i in range(1, n + 1):
        need = durs[i - 1] + fade if i < n else durs[i - 1]
        if i in slow:
            lines.append(
                f"[{i-1}:v]setpts={slow[i]:.4f}*PTS,minterpolate=fps={fps}:mi_mode=blend,"
                f"trim=duration={need:.3f},setpts=PTS-STARTPTS,{resize}"
                f"fps={fps},format=yuv420p,settb=AVTB[v{i}]")
        else:
            lines.append(
                f"[{i-1}:v]trim=duration={need:.3f},setpts=PTS-STARTPTS,{resize}"
                f"fps={fps},format=yuv420p,settb=AVTB[v{i}]")

    # xfade 链天然比 total 短 fade/2（末段没有额外 D）。末尾先 clone 补帧，
    # 再裁到 total，避免音画时长差和尾部缺帧；这是输出时长的最终保证。
    prev, cum = "v1", 0.0
    for k in range(1, n):
        cum += durs[k - 1]
        out = "[xfinal]" if k == n - 1 else f"[x{k}]"
        tr = "fadeblack" if k in fb else "fade"
        lines.append(
            f"[{prev}][v{k+1}]xfade=transition={tr}:duration={fade}:"
            f"offset={cum - fade / 2:.3f}{out}")
        prev = out.strip("[]")

    pad = max(fade, 2.0 / fps)
    lines.append(
        f"[{prev}]tpad=stop_mode=clone:stop_duration={pad:.3f},"
        f"trim=duration={total:.3f},setpts=PTS-STARTPTS,"
        f"fps={fps},format=yuv420p,settb=AVTB[out]")
    return lines, durs, slow


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bounds", required=True, help="逗号分隔的切点，含首尾")
    ap.add_argument("--beats", required=True)
    ap.add_argument("--total", type=float, required=True)
    ap.add_argument("--clip-len", type=float, default=6.04,
                    help="单段素材实际时长（所有段相同时用这个）")
    ap.add_argument("--clip-lens", default="",
                    help="逐段素材实际时长，逗号分隔；给了就覆盖 --clip-len")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--fade", type=float, default=0.45)
    ap.add_argument("--no-snap", action="store_true", help="不吸附拍点")
    ap.add_argument("--grid-div", type=float, default=4.0,
                    help="吸附网格 = 拍 / grid_div，默认 4（1/4 拍，与歌词网格一致）")
    ap.add_argument("--max-slow", type=float, default=1.3,
                    help="允许的最大慢放倍数，默认 1.3；0 表示不限制")
    ap.add_argument("--width", type=int, default=0, help="输出宽；与 --height 一起用")
    ap.add_argument("--height", type=int, default=0, help="输出高；与 --width 一起用")
    ap.add_argument("--fadeblack", default="", help="需要黑场过渡的转场序号，如 5,8")
    ap.add_argument("--report", default="", help="可选：写出时间线 JSON 报告")
    ap.add_argument("--out", default="filter_base.txt")
    a = ap.parse_args()

    if bool(a.width) != bool(a.height):
        raise SystemExit("--width 与 --height 必须同时提供")
    if a.fade <= 0:
        raise SystemExit("--fade 必须大于 0")

    raw = parse_floats(a.bounds)
    if abs(raw[0]) > 1e-6 or abs(raw[-1] - a.total) > 0.01:
        raise SystemExit("--bounds 必须包含首尾：第一个 0，最后一个等于 --total")
    if any(raw[i + 1] <= raw[i] for i in range(len(raw) - 1)):
        raise SystemExit("原始切点必须严格递增")

    grid_step = None
    off = None
    if a.no_snap:
        bounds = raw
    else:
        period, off = load_beats(a.beats)
        grid_step = period / a.grid_div
        bounds = [raw[0]] + [round(off + round((b - off) / grid_step) * grid_step, 3)
                             for b in raw[1:-1]] + [raw[-1]]

    lens = parse_floats(a.clip_lens) if a.clip_lens.strip() else [a.clip_len] * (len(raw) - 1)
    try:
        lines, durs, slow = build_filter(bounds, lens, a.total, a.fade, a.fps,
                                         a.fadeblack, a.width, a.height)
    except ValueError as exc:
        raise SystemExit(str(exc))

    if a.max_slow > 0:
        over = {k: v for k, v in slow.items() if v > a.max_slow + 1e-9}
        if over:
            detail = "、".join("第%d镜 %.2fx" % (k, v) for k, v in over.items())
            raise SystemExit(
                "慢放超过 --max-slow %.2f：%s。请拆镜或更换素材；"
                "确认接受时用 --max-slow 0 关闭限制。" % (a.max_slow, detail))

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(";\n".join(lines))

    shifts = [round(n - o, 4) for n, o in zip(bounds, raw)]
    report = dict(total=a.total, fade=a.fade, fps=a.fps,
                  width=a.width, height=a.height,
                  raw_bounds=raw, bounds=bounds, durations=durs,
                  snap_shifts=shifts, max_snap_shift=max(abs(x) for x in shifts),
                  grid_step=grid_step, slow=slow)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)

    print("镜头数 %d  目标时长 %.3fs  末尾补帧后裁齐" % (len(durs), a.total))
    print("时长", durs)
    print("慢放:", {k: round(v, 3) for k, v in slow.items()} or "无（全部常速）")
    if grid_step:
        print("吸附位移:", shifts)
        print("最大吸附位移 %.4fs（网格 %.4fs，1/8 拍限值 %.4fs）"
              % (report["max_snap_shift"], grid_step, grid_step / 2))


if __name__ == "__main__":
    main()
