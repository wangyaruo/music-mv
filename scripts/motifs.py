#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字幕装饰层：按歌词意象生成 ASS 矢量小图案。

ASS 的 \\p1 绘图可以直接画矢量图形，不需要额外的渲染层，也不需要图片素材。
每个图案都定义在 100x100 的归一化方框里，运行时按目标尺寸缩放。

用法（在 make_subs.py 里）:
    from motifs import detect, build
    names = detect("气球在我手上 我牵着你瞎逛")   # -> ["balloon"]
    path  = build("balloon", x, y, size)          # -> ("m 0 0 b ...", 是否浮动)

设计原则
  1. 图案只用纯色填充 + 深色描边，和赛璐璐字幕同一套观感
  2. 单个图案控制在 60-100px，不抢画面
  3. 一句最多两个，且只在关键词命中时出现——满屏就会变成贴纸
"""

import math

# ---------------------------------------------------------------- 路径构造

def _circle(cx, cy, r, steps=4):
    """用 steps 段三次贝塞尔逼近圆，返回 ASS 绘图路径片段。"""
    k = 0.5523 * r
    out = []
    pts = [(cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)]
    for i in range(steps):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % steps]
        # 控制点沿切线方向
        c1 = (x0 + (k if i % 2 == 0 else -k) * (0 if i % 2 else 1), y0 + (k if i % 2 else -k))
        # 简单起见用标准四段圆
        out.append((x1, y1))
    return out


def _bezier_circle(cx, cy, r):
    """标准四段贝塞尔圆。"""
    k = 0.5523 * r
    return (
        f"m {cx} {cy - r} "
        f"b {cx + k} {cy - r} {cx + r} {cy - k} {cx + r} {cy} "
        f"b {cx + r} {cy + k} {cx + k} {cy + r} {cx} {cy + r} "
        f"b {cx - k} {cy + r} {cx - r} {cy + k} {cx - r} {cy} "
        f"b {cx - r} {cy - k} {cx - k} {cy - r} {cx} {cy - r}"
    )


def _poly(points):
    head = f"m {points[0][0]:.1f} {points[0][1]:.1f} "
    return head + " ".join(f"l {x:.1f} {y:.1f}" for x, y in points[1:])


def _heart():
    return ("m 50 92 "
            "b 30 74 4 54 4 34 "
            "b 4 16 16 4 30 4 "
            "b 40 4 47 10 50 18 "
            "b 53 10 60 4 70 4 "
            "b 84 4 96 16 96 34 "
            "b 96 54 70 74 50 92")


def _sun():
    body = _bezier_circle(50, 50, 24)
    rays = []
    for i in range(8):
        a = math.radians(i * 45)
        x0, y0 = 50 + 30 * math.cos(a), 50 + 30 * math.sin(a)
        x1, y1 = 50 + 42 * math.cos(a), 50 + 42 * math.sin(a)
        rays.append(f"m {x0:.1f} {y0:.1f} l {x1:.1f} {y1:.1f}")
    # 多段独立绘制用 m 重新起笔即可
    return body + " " + " ".join(rays)


def _balloon():
    # 体形更饱满、系绳更短，小尺寸下才认得出是气球
    body = ("m 50 8 "
            "b 28 8 12 24 12 44 "
            "b 12 62 30 76 50 76 "
            "b 70 76 88 62 88 44 "
            "b 88 24 72 8 50 8")
    knot = _poly([(45, 76), (55, 76), (50, 86)])
    string = "m 50 86 c 50 90 46 93 49 97"
    return body + " " + knot + " " + string


def _bubble():
    # 单色实心圆即可；加内部高光需要二次绘制，100px 下收益很小
    return _bezier_circle(50, 50, 40)


def _star():
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        r = 46 if i % 2 == 0 else 20
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    return _poly(pts)


def _ticket():
    # 铺满 100x100 的票根：左侧半圆缺口 + 中间虚线
    body = ("m 18 18 "
            "b 6 18 6 30 6 34 "
            "b 6 38 12 42 12 50 "
            "b 12 58 6 62 6 66 "
            "b 6 70 6 82 18 82 "
            "l 82 82 "
            "b 94 82 94 70 94 66 "
            "b 94 62 88 58 88 50 "
            "b 88 42 94 38 94 34 "
            "b 94 30 94 18 82 18 ")
    dash = "m 60 22 l 60 40 l 60 60 l 60 78"
    return body + " " + dash


def _cloud():
    return ("m 22 70 b 10 70 6 60 14 54 "
            "b 10 42 24 34 34 40 "
            "b 38 28 58 26 64 38 "
            "b 78 34 90 44 84 56 "
            "b 92 62 86 70 78 70 l 22 70")


def _wind():
    # 三道卷曲的风纹，任何底色上都能看清（云在白天空上会糊掉）
    return ("m 6 30 b 20 30 30 20 42 20 b 54 20 58 32 48 36 b 40 39 34 33 37 27 "
            "m 10 54 b 28 54 38 44 54 44 b 70 44 72 58 62 62 b 54 65 48 59 51 53 "
            "m 18 78 b 32 78 40 70 52 70 b 62 70 64 80 56 83")


def _note():
    head1 = _bezier_circle(28, 76, 14)
    head2 = _bezier_circle(70, 64, 14)
    stem1 = "m 42 76 l 42 24 l 14 24"
    stem2 = "m 84 64 l 84 12 l 56 12"
    beam = "m 42 24 l 84 12"
    return head1 + " " + head2 + " " + stem1 + " " + stem2 + " " + beam


BUILDERS = {
    "heart": (_heart, False),
    "sun": (_sun, False),
    "balloon": (_balloon, True),
    "bubble": (_bubble, True),
    "star": (_star, False),
    "ticket": (_ticket, False),
    "cloud": (_cloud, True),
    "wind": (_wind, False),
    "note": (_note, False),
}

# 图案填充色：都用饱和一点的暖色，配深褐描边，
# 这样在亮天空和暗夜景上都能看清。纯米白在亮背景上会糊掉。
COLORS = {
    "heart": (232, 112, 95),      # 玫瑰红
    "sun": (247, 178, 62),        # 琥珀
    "balloon": (127, 184, 168),   # 薄荷
    "bubble": (150, 206, 222),    # 淡青
    "star": (250, 205, 90),       # 浅金
    "ticket": (252, 250, 244),    # 纸白
    "cloud": (198, 216, 230),     # 蓝灰
    "wind": (127, 184, 168),      # 薄荷
    "note": (240, 160, 80),       # 橙
}

# ---------------------------------------------------------------- 意象匹配
# 顺序即优先级：一句里命中多个时取前两个
RULES = [
    ("balloon", ["气球", "汽球"]),
    ("sun", ["大太阳", "艳阳", "太阳", "阳光"]),
    ("heart", ["爱上", "喜欢", "心动", "爱你"]),
    ("ticket", ["入场券", "门票", "票"]),
    ("bubble", ["泡", "透明", "琉璃", "玻璃"]),
    ("note", ["歌", "唱", "音乐", "旋律"]),
    ("wind", ["风", "形状"]),
    ("cloud", ["云"]),
    ("star", ["星光", "星", "闪", "烟火", "烟花"]),
]

MAX_PER_LINE = 2


def detect(text):
    """返回该句应出现的小图案名字列表（最多 MAX_PER_LINE 个）。"""
    t = "".join(c for c in (text or "") if c.strip())
    hits = []
    for name, keys in RULES:
        if any(k in t for k in keys):
            hits.append(name)
        if len(hits) >= MAX_PER_LINE:
            break
    return hits


def build(name, size=80):
    """返回 (路径, 是否浮动, 填充色)。路径已按 size 缩放，原点在图案左上角。"""
    fn, floaty = BUILDERS[name]
    raw = fn()
    s = size / 100.0
    return _scale(raw, s), floaty, COLORS[name]


def _scale(path, s):
    """把路径里的所有坐标乘以 s。"""
    out = []
    for tok in path.split():
        if tok in ("m", "l", "b", "c"):
            out.append(tok)
        else:
            try:
                out.append("%.2f" % (float(tok) * s))
            except ValueError:
                out.append(tok)
    return " ".join(out)


if __name__ == "__main__":
    for n in BUILDERS:
        p, f, c = build(n, 80)
        print("%-8s floaty=%-5s color=%s len=%3d" % (n, f, c, len(p)))
    for s in ["气球在我手上 我牵着你瞎逛", "我顶着大太阳 只想为你撑伞",
              "我手中那张入场券 陪我数羊", "冷空气跟琉璃在清晨很有透明感"]:
        print(detect(s), "<-", s)
