#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星露谷与横版像素剧情规格、图像级审计的回归测试。"""

import copy
import json
import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import pixel_spec  # noqa: E402
import style_advisor  # noqa: E402


def example_spec():
    with open(os.path.join(ROOT, "assets", "pixel_spec.stardew.example.json"),
              encoding="utf-8") as f:
        return json.load(f)


def pixelstory_spec():
    with open(os.path.join(ROOT, "assets", "pixel_spec.pixelstory.example.json"),
              encoding="utf-8") as f:
        return json.load(f)


class PixelSpecTests(unittest.TestCase):
    def test_example_spec_is_valid(self):
        self.assertEqual(pixel_spec.validate_spec(example_spec()), [])

    def test_side_scroller_is_rejected(self):
        spec = example_spec()
        spec["projection"] = "side_scroller"
        self.assertTrue(any("projection" in e for e in pixel_spec.validate_spec(spec)))

    def test_non_integer_output_scale_is_rejected(self):
        spec = example_spec()
        spec["output"]["width"] = 1919
        self.assertTrue(any("输出尺寸" in e for e in pixel_spec.validate_spec(spec)))

    def test_zoompan_is_not_a_walking_camera(self):
        spec = example_spec()
        spec["shots"][0]["camera"] = "zoompan"
        self.assertTrue(any("相机" in e for e in pixel_spec.validate_spec(spec)))

    def test_walk_requires_three_distinct_pose_indices(self):
        spec = example_spec()
        spec["shots"][0]["cycle"] = [0, 1, 0, 1]
        self.assertTrue(any("3 个不同姿态" in e for e in pixel_spec.validate_spec(spec)))

    def test_tool_requires_contact_and_target_feedback(self):
        spec = example_spec()
        spec["shots"][1]["stages"] = ["prepare", "recover"]
        spec["shots"][1]["target_feedback"] = ""
        errors = pixel_spec.validate_spec(spec)
        self.assertTrue(any("prepare/contact/recover" in e for e in errors))
        self.assertTrue(any("目标处反馈" in e for e in errors))


class PixelStorySpecTests(unittest.TestCase):
    def test_pixelstory_example_is_valid(self):
        self.assertEqual(pixel_spec.validate_spec(pixelstory_spec()), [])

    def test_pixelstory_rejects_top_down_projection(self):
        spec = pixelstory_spec()
        spec["projection"] = "three_quarter_top_down"
        self.assertTrue(any("projection" in e for e in pixel_spec.validate_spec(spec)))

    def test_pixelstory_requires_two_to_four_state_channels(self):
        spec = pixelstory_spec()
        spec["narrative"]["state_channels"] = ["score"]
        self.assertTrue(any("2–4 个状态通道" in e for e in pixel_spec.validate_spec(spec)))

    def test_pixelstory_requires_visible_state_change(self):
        spec = pixelstory_spec()
        spec["shots"][0]["state_change"] = {}
        self.assertTrue(any("state_change" in e for e in pixel_spec.validate_spec(spec)))

    def test_pixelstory_requires_relationship_composition(self):
        spec = pixelstory_spec()
        spec["shots"][0]["composition"] = {}
        self.assertTrue(any("distance" in e for e in pixel_spec.validate_spec(spec)))

    def test_pixelstory_gesture_requires_real_poses(self):
        spec = pixelstory_spec()
        shot = copy.deepcopy(spec["shots"][0])
        shot.update(action="gesture", gesture="wave", key_poses=[4, 4], characters=1,
                    composition={})
        spec["shots"].append(shot)
        self.assertTrue(any("2 个不同姿态" in e for e in pixel_spec.validate_spec(spec)))

    def test_pixelstory_prop_requires_result_state(self):
        spec = pixelstory_spec()
        spec["shots"][1]["prop_state_after"] = ""
        self.assertTrue(any("prop_state_after" in e for e in pixel_spec.validate_spec(spec)))


class SpriteAuditTests(unittest.TestCase):
    @staticmethod
    def frame(variant):
        frame = np.zeros((32, 16, 4), dtype=np.uint8)
        frame[3:16, 4:12] = (220, 180, 130, 255)
        if variant == 0:
            frame[16:32, 5:8] = (60, 80, 150, 255)
            frame[16:32, 9:12] = (60, 80, 150, 255)
        elif variant == 1:
            frame[16:27, 5:8] = (60, 80, 150, 255)
            frame[24:32, 1:5] = (60, 80, 150, 255)
            frame[16:31, 10:13] = (60, 80, 150, 255)
        else:
            frame[16:27, 9:12] = (60, 80, 150, 255)
            frame[24:32, 12:16] = (60, 80, 150, 255)
            frame[16:31, 3:6] = (60, 80, 150, 255)
        return frame

    def sheet(self, third_distinct=True):
        return np.concatenate([self.frame(0), self.frame(1),
                               self.frame(2) if third_distinct else self.frame(1)], axis=1)

    def test_three_real_silhouettes_pass(self):
        report = pixel_spec.audit_sprite_array(self.sheet(), 16, 32, [0, 1, 0, 2])
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["distinct"], 3)
        self.assertLessEqual(report["foot_drift"], 1)
        json.dumps(report)  # NumPy 标量也必须能写入 CLI 的 JSON 报告

    def test_recolor_or_duplicate_does_not_count_as_third_pose(self):
        sheet = self.sheet(third_distinct=False)
        sheet[3:16, 36:44] = (220, 170, 130, 255)
        report = pixel_spec.audit_sprite_array(sheet, 16, 32, [0, 1, 0, 2])
        self.assertFalse(report["ok"])
        self.assertEqual(report["distinct"], 2)

    def test_opaque_sheet_is_rejected(self):
        sheet = self.sheet().copy()
        sheet[:, :, 3] = 255
        report = pixel_spec.audit_sprite_array(sheet, 16, 32, [0, 1, 0, 2])
        self.assertFalse(report["ok"])
        self.assertTrue(any("透明背景" in e for e in report["errors"]))


class ScaleAuditTests(unittest.TestCase):
    def test_nearest_neighbor_integer_scale_passes(self):
        low = np.array([[[255, 0, 0, 255], [0, 255, 0, 255]],
                        [[0, 0, 255, 255], [255, 255, 255, 255]]], dtype=np.uint8)
        high = np.repeat(np.repeat(low, 4, axis=0), 4, axis=1)
        report = pixel_spec.audit_scale_array(high, 4)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["uniform_ratio"], 1.0)

    def test_interpolated_or_damaged_pixel_block_fails(self):
        low = np.zeros((2, 2, 4), dtype=np.uint8)
        low[:, :, 3] = 255
        high = np.repeat(np.repeat(low, 4, axis=0), 4, axis=1)
        high[0, 0] = (128, 128, 128, 255)
        report = pixel_spec.audit_scale_array(high, 4)
        self.assertFalse(report["ok"])
        self.assertLess(report["uniform_ratio"], 1.0)


class StyleRegistrationTests(unittest.TestCase):
    def test_stardew_is_separate_from_arcade_pixel(self):
        self.assertIn("stardew", style_advisor.STYLES)
        self.assertIn("pixel", style_advisor.STYLES)
        self.assertLess(style_advisor.STYLES["stardew"]["bpm"][0],
                        style_advisor.STYLES["pixel"]["bpm"][0])

    def test_pixelstory_is_registered_with_its_own_projection(self):
        self.assertIn("pixelstory", style_advisor.STYLES)
        self.assertEqual(pixel_spec.STYLE_RULES["pixelstory"]["projection"],
                         "side_scrolling")
        self.assertNotEqual(pixel_spec.STYLE_RULES["pixelstory"]["projection"],
                            pixel_spec.STYLE_RULES["stardew"]["projection"])


if __name__ == "__main__":
    unittest.main()
