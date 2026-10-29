"""纯代码像素渲染的最小骨架。不调任何出图能力，只用 Pillow 画。

    python3 skeleton.py          # 出三张图到 out/

要看懂的只有四件事，其余都是填场景：

  1. 底图在 256x144 的逻辑画布上画，最后整数倍 NEAREST 放大。
     所有坐标必须是整数；小数经放大后会出现只在个别帧可见的 1px 缝。

  2. 半透明一律画在独立图层上再 alpha_composite。直接在 RGBA 图上用
     ImageDraw.Draw(img, "RGBA") 填半透明，alpha 会被替换而不是混合，
     得到一块死色。见 overlay()。

  3. 题字有两条路线。底图是像素的，字**不必**是像素的：在放大后的
     原生分辨率上排矢量字，加高斯模糊投影，比像素字耐看得多。见 title()。
     真要像素字，字高低于 32px 的中文会糊成一团墨，且蒙版必须二值化。
     见 pixel_line()。

  4. 封面不要从成片抽帧。同一套场景函数换参数、换画幅、重排题字即可，
     验收标准是缩到 320x180 还能认出歌名。

要开工，改 PAL（色阶）、scene()（物件）和下面 H_ART / H_TITLE 三处。
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

LW, LH = 256, 144          # 逻辑画布
SCALE = 4                  # 整数倍放大
W, H = LW * SCALE, LH * SCALE

HOR = 62                   # 地平线（逻辑像素）
WATER_BOT = 96             # 岸线

PAL = dict(
    # 天空七个色阶：整张画的冷暖都由这七个值决定，改这里就是换时间
    sky=("#4b2340", "#803653", "#b64a63", "#dd6d78", "#f5998c", "#ffc0a6", "#ffe4cd"),
    water=("#ffb299", "#b2748c"),      # 水面：靠岸亮、近处暗
    ripple=("#ffe0cc", "#d99ab0"),     # 波纹
    glint=("#fff4e0", "#ffb492"),      # 太阳底下的碎金
    sun=("#ffcf9e", "#ffe4bd", "#fff4de"),   # 三层由外向内变亮，反了就成光环
    far="#a86a72", shore="#f0c4a8", ground="#c78c74", seam="#b97f68",
)

FONT_CANDIDATES = (
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


# ------------------------------------------------------------------ 工具
def font(px):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    raise SystemExit("找不到中文字体，改 FONT_CANDIDATES 指向一个 .ttc/.ttf")


def overlay(img):
    """半透明专用：返回一张透明图层和它的画笔，画完 alpha_composite 回去。"""
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def mix(a, b, k):
    """两个十六进制色按 k 混合。k 只能是 0..1 的有限档，像素画不做连续插值。"""
    ca = tuple(int(a[i:i + 2], 16) for i in (1, 3, 5))
    cb = tuple(int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(ca[i] + (cb[i] - ca[i]) * k) for i in range(3))


def up(img, s=SCALE):
    return img.resize((img.width * s, img.height * s), Image.Resampling.NEAREST)


def ramp(stops, k):
    """在一串色阶上按 k(0..1) 取色。像素画的渐变靠档数，不靠逐行连续插值。"""
    k = min(max(k, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(k), len(stops) - 2)
    return mix(stops[i], stops[i + 1], k - i)


# ------------------------------------------------------------------ 场景
def scene(w=LW, h=LH, hor=HOR, wb=WATER_BOT):
    """一张黄昏河岸。所有坐标都是整数。

    尺寸全部走参数，不读全局——横版 256x144 和竖版 108x192 要共用这一个函数。
    """
    img = Image.new("RGBA", (w, h), PAL["sky"][0])
    d = ImageDraw.Draw(img)

    # 1) 天空：从七个色阶里采出十几档。档太少会看到一条条硬色带，
    #    档太多就变成「低清图」——像素画的渐变靠档数，不靠连续插值。
    n = max(10, hor // 3)
    for i in range(n):
        d.rectangle((0, hor * i // n, w, hor * (i + 1) // n),
                    fill=ramp(PAL["sky"], i / (n - 1)))

    # 2) 太阳压在远岸后面：先画太阳，再画那一小条岸线，它就「落下去」了。
    #    三层要由外向内变亮——顺序反了就画成一圈光环（像日食）。
    sx, sy = int(w * .86), hor - 9
    for r, c in zip((12, 9, 6), PAL["sun"]):
        d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=c)

    # 3) 远岸：一小条就够，太厚会变成山
    d.rectangle((0, hor - 3, w, hor), fill=PAL["far"])

    # 4) 水面底色：先铺，再叠波纹。漏了这一步，波纹会浮在天空色上——
    #    看起来像一条深紫色的带子，而不是水。六段色阶就够，逐个像素插值是多余的。
    nb = 6
    for i in range(nb):
        y0 = hor + (wb - hor) * i // nb
        y1 = hor + (wb - hor) * (i + 1) // nb
        d.rectangle((0, y0, w, y1),
                    fill=mix(PAL["water"][0], PAL["water"][1], (i + .5) / nb))

    # 5) 波纹：行距和步长都随深度变。等距排会浮出一层均匀虚线网格。
    y, i = hor, 0
    while y < wb:
        k = (y - hor) / (wb - hor)
        wd, step = 3 + int(k * 7), 17 + (i * 7) % 11
        col = mix(PAL["ripple"][0], PAL["ripple"][1], k)
        for x in range((i * 37) % step, w, step):
            d.line((x, y, x + wd, y), fill=col)
        y += 2 + int(k * 4)
        i += 1

    # 6) 太阳底下的碎金：短横条聚成柱。单像素点 + 隔三取一放大后像撒开的彩纸。
    for i, y in enumerate(range(hor + 1, wb, 2)):
        k = (y - hor) / (wb - hor)
        half = 2 + int(k * 7)
        for t2 in range(max(2, half // 2)):
            off = ((t2 * 7 + i * 3) % (2 * half + 1)) - half
            d.line((sx + off, y, sx + off + 1 + (t2 + i) % 3, y),
                   fill=mix(PAL["glint"][0], PAL["glint"][1], k))

    # 7) 铺装：上沿亮一线 + 错缝石板，否则会是一块死平的色
    d.rectangle((0, wb, w, h), fill=PAL["ground"])
    d.rectangle((0, wb, w, wb + 1), fill=PAL["shore"])
    for i, yy in enumerate(range(wb + 5, h, 7)):
        for x in range((i * 5) % 11, w, 13):
            d.rectangle((x, yy, x + 4, yy), fill=PAL["seam"])

    # 8) 长椅：四根横档、档间留 1 像素缝，透出后面的地面。实心背板像木箱。
    seat, feet = wb + 18, h - 6
    bx0, bx1 = int(w * .16), int(w * .16) + 46
    d.rectangle((bx0 - 2, feet, bx1 + 2, feet), fill="#a8735c")          # 影子
    for px in (bx0 + 1, bx1 - 4):
        d.rectangle((px, seat - 16, px + 3, seat + 4), fill="#6f4834")
        d.rectangle((px, seat - 16, px + 3, seat - 16), fill="#d49a6a")
    for yy in (seat - 16, seat - 12, seat - 8, seat - 4):
        d.rectangle((bx0 + 1, yy, bx1 - 1, yy + 2), fill="#6f4834")
        d.rectangle((bx0 + 1, yy, bx1 - 1, yy), fill="#d49a6a")
    d.rectangle((bx0 - 3, seat, bx1 + 3, seat + 3), fill="#6f4834")
    d.rectangle((bx0 - 3, seat, bx1 + 3, seat), fill="#d49a6a")
    d.rectangle((bx0 + 2, seat + 4, bx0 + 6, feet), fill="#4a3024")
    d.rectangle((bx1 - 6, seat + 4, bx1 - 2, feet), fill="#4a3024")

    # 9) 底边压暗（半透明 → 必须独立图层）
    lay, dl = overlay(img)
    top = wb + 22
    for y in range(top, h):
        k = (y - top) / max(1, h - top - 1)
        dl.line((0, y, w, y), fill=(0x38, 0x20, 0x1a, int(90 * k)))
    img.alpha_composite(lay)
    return img


# ------------------------------------------------------------------ 题字
def _mask(size, text, fnt, track, cy, cx=None):
    """排一行字，返回 L 蒙版。cx 为 None 时水平居中。"""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    ws = [d.textlength(ch, font=fnt) for ch in text]
    total = sum(ws) + track * (len(text) - 1)
    x = (size[0] - total) / 2 if cx is None else cx - total / 2
    for ch, w in zip(text, ws):
        d.text((x, cy), ch, font=fnt, fill=255)
        x += w + track
    return m


def _stamp(img, m, color, alpha=255):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    lay.paste(Image.new("RGBA", img.size, color + (255,)), (0, 0),
              m.point(lambda v: v * alpha // 255))
    return Image.alpha_composite(img, lay)


def title(img, lines):
    """路线 B：底图是像素的，字不是。投影用高斯模糊，不用描边——
    亮而软的天空上，硬描边像贴纸。"""
    out = img.convert("RGBA")
    for ln in lines:
        m = _mask(out.size, ln["t"], font(ln["px"]), ln.get("track", 0), ln["cy"])
        if ln.get("blur"):
            sh = Image.new("L", out.size, 0)
            sh.paste(m, (0, ln.get("dy", 12)))
            sh = sh.filter(ImageFilter.GaussianBlur(ln["blur"]))
            out = _stamp(out, sh, (0x38, 0x20, 0x1a), ln.get("sa", 120))
        out = _stamp(out, m, ln.get("c", (255, 255, 255)), 255)
    return out.convert("RGB")


def pixel_line(d, text, px, cx, cy, size, color=(255, 244, 230)):
    """路线 A：真像素字。只画在逻辑画布上，跟着底图一起放大。
    蒙版必须二值化，否则抗锯齿的灰边被 NEAREST 放大成一圈色晕。"""
    m = _mask(size, text, font(px), max(1, px // 8), cy, cx)
    m = m.point(lambda v: 255 if v >= 128 else 0)
    d.bitmap((0, 0), m, fill=color)


# ------------------------------------------------------------------ 出图
# 横版题字：风景像素、题字矢量，是两条路线里更耐看的一条
H_TITLE = [
    dict(t="简单爱", px=132, track=8, cy=40, blur=16, dy=12, sa=135),
    dict(t="周杰伦", px=36, track=16, cy=192, c=(0x5a, 0x2a, 0x3e), blur=6, dy=4, sa=70),
]
# 竖版 9:16：同一套 scene()，换画幅和排版。比例不同，字要重排，不能照抄
V_TITLE = [
    dict(t="简单爱", px=210, track=10, cy=520, blur=22, dy=16, sa=135),
    dict(t="周杰伦", px=64, track=20, cy=770, c=(0x5a, 0x2a, 0x3e), blur=8, dy=6, sa=70),
]

if __name__ == "__main__":
    os.makedirs("out", exist_ok=True)

    # 横版 256x144 x4
    title(up(scene(), 4), H_TITLE).save("out/out_frame.png")

    # 竖版 108x192 x10：直接按 108 宽画，不要先画横版再裁（左沿必须是整数倍）
    vw, vh = 108, 192
    title(up(scene(vw, vh, hor=104, wb=138), 10), V_TITLE).save("out/out_cover.png")

    # 像素字三档对照：14 / 20 / 28px，放大 8 倍看自己的下限
    probe = Image.new("RGB", (200, 108), PAL["sky"][1])
    pd = ImageDraw.Draw(probe)
    for i, px in enumerate((14, 20, 28)):
        pd.rectangle((0, i * 36, 200, i * 36 + 35), fill=PAL["sky"][1 + i])
        pixel_line(pd, "简单爱", px, 100, i * 36 + 6, (200, 108))
    up(probe, 8).save("out/out_text_probe.png")

    for f in ("out_frame.png", "out_cover.png", "out_text_probe.png"):
        print(f, Image.open("out/" + f).size)
