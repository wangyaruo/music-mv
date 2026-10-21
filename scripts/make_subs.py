#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成"一字一块、逐字蹦出、卡在拍上"的 ASS 字幕。

用法:
    python make_subs.py --lines lines.json --beats beats.json --out subs.ass \
        [--font "ZCOOL KuaiLe"] [--theme cut|box]

lines.json（每句一条）:
    [
      {"start":1.83,"end":4.30,"text":"我们都是渺小真实存在","place":"M"},
      {"start":8.35,"end":10.60,"text":"直到遇见你我以为就光明起来","place":"B"},
      {"start":54.0,"end":56.0,"text":"把回忆拼好给你","title":true,"y":236}
    ]

每条可用的字段:
    start/end   起止秒
    text        文本
    place       T 顶部 / M 中部 / B 底部（缺省 B）
    title       true = 整块浮现（片头/片尾用），逐字打散会来不及看完
    block       true = 单条事件、保留空格（词曲署名这类整行小字）
    y / fs / sp / bord / fade   位置、字号、字距、描边、淡入淡出毫秒的逐条覆盖

要点（都已在实现里）:
  · 颜色按 ASS 的 &HAABBGGRR 写（BGR 倒序）；\\1c \\3c \\4c 用 &HBBGGRR&
  · 每个字独立事件、独立 \\pos、独立 \\frz
  · 字的出现时刻吸附到 1/8 拍网格；每句首字就近吸附（不偏向后方）
  · 超过 CHUNK_MAX 字自动均分成多段轮流显示
  · fontsdir 必须是绝对路径，否则 ffmpeg 会静默退回默认字体
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motifs import detect as motif_detect, build as motif_build   # noqa: E402

# 装饰层（气泡/爱心/气球/太阳…）是否启用，由 --motifs 打开
MOTIFS_ON = False
MOTIF_SIZE = 100

# ---- 版式（日系动画字幕：无底框、暖白字 + 深褐描边 + 投影）----
FS, PAD, GAP, ROW_Y = 88, 0, 10, 986       # 正文：字号 / 留白(无框=0) / 字间缝 / 底部行中心
TOP_Y, MID_Y = 118, 486                     # 顶部 / 中部行中心
TFS, TPAD, TGAP, TROW_Y = 150, 0, 14, 860  # 片尾标题
OUTLINE, SHADOW = 3.6, 2.4                  # 描边 / 投影
BORDER = 1                                  # 1=描边 3=不透明底框
CHUNK_MAX = 18                              # 每段最多几个字（整句一行）
MIN_STEP = 0.15                             # 每字最短间隔，防密集句过快
REVEAL = 0.78                              # 出字只用句长的前 78%，末字留住在长音上
                                           # （铺满整句会让句尾越拖越慢，听起来字幕滞后）
TILT = [-2.2, 1.6, -1.1, 2.6, -1.8, 0.9, -0.6, 2.1, -2.8, 1.3, -1.4, 2.3]

# 主题预设：cut = 描边字（推荐，最不挡画面）；box = 色块底框（复古 MV 感）
THEMES = {
    "cut": dict(border=1, pad=0, outline=3.6, shadow=2.4, fs=88, tfs=150),
    "box": dict(border=3, pad=9, outline=9.0, shadow=0.0, fs=82, tfs=140),
}

# 每句一套 (投影色, 字色, 描边色)；日系动画统一暖白 + 深褐描边，最耐各种底
PALETTE = [((0, 0, 0), (255, 250, 240), (58, 40, 30))] * 13


def bgr(rgb):
    r, g, b = rgb
    return "&H%02X%02X%02X&" % (b, g, r)


def bgr_a(rgb, alpha=0x00):
    r, g, b = rgb
    return "&H%02X%02X%02X%02X" % (alpha, b, g, r)


def ts(t):
    return "%d:%02d:%05.2f" % (int(t // 3600), int(t % 3600 // 60), t % 60)


def _emit_motifs(out, text, start, end, y, total, x0, fs, idx=0):
    """在文字行两端挂小图案（气泡/爱心/气球/太阳…）。

    整句只挂一次。放不下时挪到文字上方居中，绝不上到文字行里。
    """
    names = motif_detect(text)
    if not names:
        return
    size = MOTIF_SIZE
    t_on = start + 0.12
    t_end = max(end, t_on + 0.6)

    left_edge = x0 - fs / 2
    right_edge = left_edge + total

    # 统一贴在文字左侧，像句首的标记点：
    # 放右侧会飘到画框边缘，和场景里的灯笼/云混在一起就认不出来了
    GAP = 34
    slots = []
    lx = left_edge - GAP - size
    if lx >= 18:
        slots.append((lx, y - size / 2))
    else:                              # 两侧都没余量：贴到文字上方/下方
        sx = max(24, left_edge - GAP - size * 0.6)
        if y < 300:
            slots.append((sx, y + fs * 0.62 + 8))
        else:
            slots.append((sx, y - fs * 0.62 - size - 8))

    edge = bgr(PALETTE[0][2])
    for k, name in enumerate(names):
        path, floaty, color = motif_build(name, size)
        sx, sy = slots[k % len(slots)]
        tilt = 0 if floaty else (-6 if (idx + k) % 2 == 0 else 6)
        if floaty:
            pos = ("\\an7\\move(%.1f,%.1f,%.1f,%.1f,0,%d)"
                   % (sx, sy, sx, sy - 34, int((t_end - t_on) * 1000)))
        else:
            pos = "\\an7\\pos(%.1f,%.1f)" % (sx, sy)
        tags = ("{%s\\p1\\frz%d\\fscx0\\fscy0\\t(0,150,\\fscx112\\fscy112)"
                "\\t(150,230,\\fscx100\\fscy100)\\fad(110,240)"
                "\\1c%s\\3c%s\\bord3.2\\shad1.2\\b1}" % (pos, tilt, bgr(color), edge))
        out.append("Dialogue: 0,%s,%s,Tile,,0,0,0,,%s%s"
                   % (ts(t_on), ts(t_end), tags, path))


def head(font):
    fill, ink, edge = PALETTE[0]
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Tile,{font},{fs},{ink},{ink},{edge},{fill},-1,0,0,0,100,100,2.4,0,{border},{ol},{sh},5,0,0,0,1
Style: BigTile,{font},{tfs},{tink},{tink},{tedge},{tfill},-1,0,0,0,100,100,4.0,0,{border},{tol},{tsh},5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(font=font, fs=FS, tfs=TFS, border=BORDER,
           ink=bgr_a(ink), edge=bgr_a(edge), fill=bgr_a(fill),
           ol=OUTLINE, sh=SHADOW, tol=OUTLINE * 1.3, tsh=SHADOW * 1.2,
           tink=bgr_a(PALETTE[12][1]), tedge=bgr_a(PALETTE[12][2]), tfill=bgr_a(PALETTE[12][0]))


class BeatGrid:
    def __init__(self, path):
        self.ok = False
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                b = json.load(f)
            self.base = b["beat_period"] / 8.0
            self.off = b["offset"]
            self.ok = True

    def snap(self, t):
        if not self.ok:
            return t
        return self.off + round((t - self.off) / self.base) * self.base

    def plan(self, start, end, n):
        """把 n 个字排到网格上：步长取网格整数或半整数倍，首字就近吸附。"""
        if not self.ok:
            step = (end - start) / n
            return [start + i * step for i in range(n)]
        base, dur = self.base, end - start
        best_m, best_err = None, 1e18
        m = 0.5
        while m <= 24:
            span = n * m * base
            if span > dur + 0.50:
                break
            if m * base >= MIN_STEP:
                err = abs(span - dur)
                if best_m is None or err < best_err - 1e-9:
                    best_m, best_err = m, err
            m += 0.5
        if best_m is None:
            best_m = max(0.5, np.ceil(MIN_STEP / base * 2) / 2)
        step = best_m * base

        # 首字：在 [start-0.20, start+0.10] 里取最近网格点（正拍仅在 ±0.06 内才用）
        lo, hi = start - 0.20, start + 0.10
        k_lo = int(np.ceil((lo - self.off) / base))
        k_hi = int(np.floor((hi - self.off) / base))
        cands = list(range(k_lo, k_hi + 1))
        if cands:
            strong = [k for k in cands if k % 8 == 0
                      and abs(self.off + k * base - start) <= 0.06]
            pool = strong if strong else cands
            t0 = self.off + min(pool, key=lambda k: abs(self.off + k * base - start)) * base
        else:
            t0 = self.off + np.ceil((start - self.off) / base) * base
        return [t0 + i * step for i in range(n)]


def emit(out, item, grid, idx):
    text = "".join(ch for ch in item["text"] if ch.strip())
    if not text:
        return
    start, end = float(item["start"]), float(item["end"])
    title = bool(item.get("title"))
    place = item.get("place", "B")
    fs, pad, gap, y = (TFS, TPAD, TGAP, TROW_Y) if title else (FS, PAD, GAP, ROW_Y)
    if "y" in item:
        y = float(item["y"])
    elif place == "T" and not title:
        y = TOP_Y
    elif place == "M" and not title:
        y = MID_Y
    else:
        y = TROW_Y if title else ROW_Y
    if "fs" in item:
        fs = float(item["fs"])
    bord = float(item["bord"]) if "bord" in item else (OUTLINE * 1.3 if title else OUTLINE)
    sp = float(item["sp"]) if "sp" in item else (4.0 if title else 2.4)
    tile = fs + 2 * pad

    # 整块文本（片头歌名/署名用）：单条事件、不逐字拆块
    if item.get("block"):
        fd = int(item.get("fade", 600))
        out.append("Dialogue: 0,%s,%s,Tile,,0,0,0,,"
                   "{\\an5\\pos(960,%.1f)\\fs%d\\fsp%.1f\\bord%.2f"
                   "\\fad(%d,%d)\\1c%s\\3c%s\\fscx100\\fscy100}%s"
                   % (ts(start), ts(end), y, int(fs), sp, bord,
                      fd, fd, bgr(PALETTE[idx][1]), bgr(PALETTE[idx][2]),
                      item["text"].strip()))
        return

    # 出字窗口只占句长的前 REVEAL，末字落到长音上而不是一直拖到句尾
    plan_end = start + (end - start) * REVEAL
    times = [start] * len(text) if title else grid.plan(start, plan_end, len(text))
    # 末字已经在 REVEAL 之后的 22% 里停住了，句尾无需再留；
    # 留太多会和下一句重叠，看起来就是"字幕和画面没对上"
    hold = 0.0 if title else 0.06

    n = len(text)
    if title or n <= CHUNK_MAX:
        chunks = [text]
    else:
        k = -(-n // CHUNK_MAX)
        base_len, extra = divmod(n, k)
        chunks, pos = [], 0
        for c in range(k):
            size = base_len + (1 if c < extra else 0)
            chunks.append(text[pos:pos + size])
            pos += size

    i = 0
    for ci, chunk in enumerate(chunks):
        m = len(chunk)
        total = m * tile + (m - 1) * gap
        x0 = (1920 - total) / 2 + tile / 2
        if i + m < n:
            seg_end = times[i + m] + 0.10
        else:
            seg_end = max(end + hold, times[min(i + m - 1, n - 1)] + 0.35)
        for j, ch in enumerate(chunk):
            k = i + j
            t_on = times[k]
            t_end = max(seg_end, t_on + 0.35)
            rot = TILT[k % len(TILT)] * (1.25 if title else 1.0)
            x = x0 + j * (tile + gap)
            if title:
                anim = "\\fscx92\\fscy92\\t(0,320,\\fscx100\\fscy100)\\fad(420,520)"
            else:
                out_ms = 150 if i + m < n else 0
                anim = ("\\fscx50\\fscy50\\t(0,80,\\fscx118\\fscy118)"
                        "\\t(80,170,\\fscx100\\fscy100)\\fad(55,%d)" % out_ms)
            head_txt = ("{\\an5\\pos(%.1f,%.1f)\\fs%d\\fsp%.1f\\bord%.2f\\frz%.2f%s"
                        "\\1c%s\\2c&HFF000000&\\3c%s\\4c%s}"
                        % (x, y, int(fs), sp, bord, rot, anim,
                           bgr(PALETTE[idx][1]),
                           bgr(PALETTE[idx][2]), bgr(PALETTE[idx][0])))
            out.append("Dialogue: 0,%s,%s,%s,,0,0,0,,%s%s"
                       % (ts(t_on), ts(t_end),
                          "BigTile" if title else "Tile", head_txt, ch))

        # 装饰层：整句只挂一次，不逐字重复
        if MOTIFS_ON and not title and ci == 0:
            _emit_motifs(out, item["text"], start, end, y, total, x0, fs, idx)
        i += m


def main():
    global FS, PAD, TFS, OUTLINE, SHADOW, BORDER, MOTIFS_ON, MOTIF_SIZE
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True)
    ap.add_argument("--beats", default="")
    ap.add_argument("--out", "-o", default="subs.ass")
    ap.add_argument("--font", default="ZCOOL KuaiLe")
    ap.add_argument("--theme", default="cut", choices=sorted(THEMES),
                    help="cut=描边字（默认） box=色块底框")
    ap.add_argument("--motifs", action="store_true",
                    help="按歌词意象在句子两端加小图案（气泡/爱心/气球/太阳等）")
    ap.add_argument("--motif-size", type=int, default=100)
    ap.add_argument("--fontsdir", default="",
                    help="打印可直接粘贴的 ass 滤镜串时用的字体目录")
    a = ap.parse_args()

    t = THEMES[a.theme]
    BORDER, PAD, OUTLINE, SHADOW = t["border"], t["pad"], t["outline"], t["shadow"]
    FS, TFS = t["fs"], t["tfs"]
    MOTIFS_ON = a.motifs
    MOTIF_SIZE = a.motif_size

    with open(a.lines, encoding="utf-8") as f:
        items = json.load(f)
    grid = BeatGrid(a.beats)

    lines = [head(a.font)]
    allt = []
    for idx, it in enumerate(items):
        emit(lines, it, grid, idx % len(PALETTE))
        txt = "".join(c for c in it["text"] if c.strip())
        if not it.get("title") and not it.get("block"):
            allt += grid.plan(float(it["start"]), float(it["end"]), len(txt))

    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("written:", a.out, "events:", len(lines) - 1, " theme:", a.theme)
    if grid.ok:
        errs = [abs(t - grid.snap(t)) for t in allt]
        print("网格 %.4fs 偏移 %.3fs 最大偏离 %.4fs"
              % (grid.base, grid.off, max(errs) if errs else 0))

    # 直接给出可粘贴的滤镜串——fontsdir 必须是绝对路径，否则 ffmpeg 静默失败
    fd = a.fontsdir or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "assets", "fonts")
    fd = os.path.abspath(fd)
    print("\n叠加到视频时用：")
    print("  ass=%s:fontsdir='%s'" % (os.path.abspath(a.out), fd))


if __name__ == "__main__":
    main()
