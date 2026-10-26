#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星露谷式像素规格、sprite 轮廓与整数缩放校验。

三个命令互不替代：
- check：只检查 pixel_spec.json 的结构与动作合同，不证明画面合格。
- audit-sprites：检查真实透明 sprite sheet 的轮廓差异和脚点漂移。
- audit-scale：检查无损世界素材层是否保持整数倍纯色像素块。
"""

import argparse
import json
import os
import struct
import subprocess
import sys
import zlib

import numpy as np

PROJECTION = "three_quarter_top_down"
CAMERAS = {"fixed", "pixel_pan", "cut"}
LAYERS = {"back", "buildings", "paths", "actors", "front", "always_front",
          "lighting", "hud", "subtitles"}


def validate_spec(spec):
    """返回配置错误；通过此项不代表图像或视频已经通过视觉验收。"""
    errors = []
    if spec.get("style") != "stardew":
        errors.append("style 必须为 stardew；其他像素子风格应使用独立规格")
    if spec.get("projection") != PROJECTION:
        errors.append("projection 必须为 three_quarter_top_down，禁止横版或等距投影")

    world = spec.get("world", {})
    output = spec.get("output", {})
    try:
        ww, wh = int(world["width"]), int(world["height"])
        scale = int(world["scale"])
        ow, oh = int(output["width"]), int(output["height"])
        if ww <= 0 or wh <= 0 or scale < 2:
            errors.append("世界尺寸必须为正，scale 必须为 >=2 的整数")
        if (ow, oh) != (ww * scale, wh * scale):
            errors.append("输出尺寸必须等于世界尺寸 × 整数 scale")
    except (KeyError, TypeError, ValueError):
        errors.append("world.width/height/scale 与 output.width/height 必须为整数")
        scale = 1
    if str(scale) != str(world.get("scale", scale)):
        errors.append("scale 必须为整数，不能是非整数缩放")
    if world.get("tile") != 16:
        errors.append("stardew 地图设计 tile 必须为 16×16")

    sprite = spec.get("farmer_sprite", {})
    if (sprite.get("frame_width"), sprite.get("frame_height")) != (16, 32):
        errors.append("农夫型主角素材框必须为 16×32")
    anchor = sprite.get("foot_anchor")
    if (not isinstance(anchor, list) or len(anchor) != 2 or
            not all(isinstance(v, int) for v in anchor) or
            not (0 <= anchor[0] < 16 and 0 <= anchor[1] < 32)):
        errors.append("foot_anchor 必须是素材框内的整数 [x,y] 脚点")

    layers = set(spec.get("layers", []))
    missing = sorted(LAYERS - layers)
    if missing:
        errors.append("缺少独立图层: " + ", ".join(missing))

    shots = spec.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots 必须是非空列表")
        return errors
    for i, shot in enumerate(shots):
        sid = shot.get("id", "shots[%d]" % i)
        for field in ("season", "time", "weather", "action", "camera"):
            if not shot.get(field):
                errors.append("%s 缺少 %s" % (sid, field))
        camera = shot.get("camera")
        if camera and camera not in CAMERAS:
            errors.append("%s 相机 %s 不合格；仅允许 fixed/pixel_pan/cut" % (sid, camera))
        action = shot.get("action")
        if action in {"walk", "run"}:
            cycle = shot.get("cycle", [])
            if len(cycle) < 3 or len(set(cycle)) < 3:
                errors.append("%s 完整步态至少需要 3 个不同姿态索引" % sid)
            ms = shot.get("frame_ms", [])
            if len(ms) != len(cycle) or any(not isinstance(v, (int, float)) or v <= 0 for v in ms):
                errors.append("%s frame_ms 必须与 cycle 等长且全部为正数" % sid)
        elif action == "tool":
            stages = shot.get("stages", [])
            if stages != ["prepare", "contact", "recover"]:
                errors.append("%s 工具动作必须按 prepare/contact/recover 排列" % sid)
            if not shot.get("target_feedback"):
                errors.append("%s 工具动作缺少目标处反馈" % sid)
        elif action == "idle":
            if not shot.get("idle_foot_lock"):
                errors.append("%s 待机必须锁定脚点，禁止整体正弦浮动" % sid)
        elif action == "environment":
            if not shot.get("environment_loops"):
                errors.append("%s 环境镜头必须指定局部动画区域" % sid)
        elif action not in {"walk", "run", "tool", "idle", "environment", None}:
            errors.append("%s 未知 action: %s" % (sid, action))
        if action in {"walk", "run", "tool"}:
            if shot.get("path_clear") is not True:
                errors.append("%s 必须确认至少一格宽的连续通路" % sid)
            if shot.get("occlusion") != "foot_y_sort":
                errors.append("%s 必须按脚点前后关系处理遮挡" % sid)
        if shot.get("background_morph"):
            errors.append("%s 禁止整背景同步扭动" % sid)
    return errors


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def read_png_rgba(path):
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("图像检查只接受无损 PNG，避免 JPEG 压缩噪声干扰")
    width, height = struct.unpack(">II", header[16:24])
    raw = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                          "-i", path, "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         stdout=subprocess.PIPE, check=True).stdout
    expected = width * height * 4
    if len(raw) != expected:
        raise ValueError("PNG 解码尺寸不匹配：期望 %d 字节，实际 %d" % (expected, len(raw)))
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)


def write_png(path, arr):
    """用标准库写 RGBA PNG，供测试与小型像素工具复用。"""
    arr = np.asarray(arr, dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("数组必须为 H×W×4 RGBA")
    height, width = arr.shape[:2]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(height))
    data = (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def audit_sprite_array(arr, frame_width, frame_height, cycle,
                       min_distinct=3, max_foot_drift=1):
    """检查 alpha 轮廓，不把换色、整体平移或透明底框当成新姿态。"""
    errors = []
    height, width = arr.shape[:2]
    report = dict(ok=False, frame_size=[frame_width, frame_height], cycle=cycle,
                  distinct=0, foot_drift=None, errors=errors)
    if arr.ndim != 3 or arr.shape[2] != 4:
        errors.append("sprite 数组必须为 H×W×4 RGBA")
        return report
    if width % frame_width or height % frame_height:
        errors.append("sprite sheet 尺寸不能被素材框整除")
        return report
    cols, rows = width // frame_width, height // frame_height
    if not cycle:
        errors.append("cycle 不能为空")
        return report
    if any(not isinstance(v, int) or v < 0 or v >= cols * rows for v in cycle):
        errors.append("cycle 含越界或非整数帧索引")
        return report

    signatures, bottoms = [], []
    for index in cycle:
        x, y = (index % cols) * frame_width, (index // cols) * frame_height
        frame = arr[y:y + frame_height, x:x + frame_width]
        mask = frame[:, :, 3] > 0
        if not mask.any():
            errors.append("帧 %d 是空帧" % index)
            continue
        ys, xs = np.where(mask)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        silhouette = mask[y0:y1, x0:x1]
        signatures.append((silhouette.shape, silhouette.tobytes()))
        bottoms.append(y1)
    if np.all(arr[:, :, 3] == 255):
        errors.append("sprite sheet 必须使用透明背景；不透明底框无法审计轮廓")
    report["distinct"] = len(set(signatures))
    if report["distinct"] < min_distinct:
        errors.append("完整循环只有 %d 个可区分轮廓，要求至少 %d 个" %
                      (report["distinct"], min_distinct))
    if bottoms:
        report["foot_drift"] = int(max(bottoms) - min(bottoms))
        if report["foot_drift"] > max_foot_drift:
            errors.append("脚底漂移 %dpx，超过允许的 %dpx" %
                          (report["foot_drift"], max_foot_drift))
    report["ok"] = not errors
    return report


def audit_sprite_sheet(path, frame_width, frame_height, cycle,
                       min_distinct=3, max_foot_drift=1):
    return audit_sprite_array(read_png_rgba(path), frame_width, frame_height,
                              cycle, min_distinct, max_foot_drift)


def audit_scale_array(arr, scale, threshold=1.0):
    """统计 scale×scale 非纯色块；仅用于光照/字幕/编码前的世界素材层。"""
    errors = []
    height, width = arr.shape[:2]
    report = dict(ok=False, scale=scale, uniform_ratio=None,
                  threshold=threshold, errors=errors)
    if scale < 2 or int(scale) != scale:
        errors.append("scale 必须为 >=2 的整数")
        return report
    scale = int(scale)
    if height % scale or width % scale:
        errors.append("图像宽高不能被 scale 整除")
        return report
    if not 0 < threshold <= 1:
        errors.append("threshold 必须位于 (0,1]")
        return report
    blocks = arr.reshape(height // scale, scale, width // scale, scale, arr.shape[2])
    blocks = blocks.transpose(0, 2, 1, 3, 4)
    uniform = np.all(blocks == blocks[:, :, :1, :1, :], axis=(2, 3, 4))
    ratio = float(uniform.mean())
    report["uniform_ratio"] = ratio
    if ratio < threshold:
        errors.append("整数像素块一致率 %.4f，低于阈值 %.4f；存在插值或非整数网格" %
                      (ratio, threshold))
    report["ok"] = not errors
    return report


def audit_scale(path, scale, threshold=1.0):
    return audit_scale_array(read_png_rgba(path), scale, threshold)


def parse_cycle(text):
    try:
        return [int(v) for v in text.split(",") if v.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError("cycle 必须为逗号分隔的非负整数")


def emit(report):
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="只校验 pixel_spec.json 结构与动作合同")
    check.add_argument("spec")
    sprites = sub.add_parser("audit-sprites", help="审计真实 sprite 轮廓和脚点")
    sprites.add_argument("image")
    sprites.add_argument("--frame-width", type=int, default=16)
    sprites.add_argument("--frame-height", type=int, default=32)
    sprites.add_argument("--cycle", type=parse_cycle, required=True)
    sprites.add_argument("--min-distinct", type=int, default=3)
    sprites.add_argument("--max-foot-drift", type=int, default=1)
    scale = sub.add_parser("audit-scale", help="审计整数倍最近邻像素块")
    scale.add_argument("image")
    scale.add_argument("--scale", type=int, required=True)
    scale.add_argument("--threshold", type=float, default=1.0)
    args = ap.parse_args()

    if args.command == "check":
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)
        errors = validate_spec(spec)
        return emit(dict(ok=not errors, mode="config_only", errors=errors))
    if args.command == "audit-sprites":
        return emit(audit_sprite_sheet(args.image, args.frame_width, args.frame_height,
                                       args.cycle, args.min_distinct, args.max_foot_drift))
    return emit(audit_scale(args.image, args.scale, args.threshold))


if __name__ == "__main__":
    sys.exit(main())
