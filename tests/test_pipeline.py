#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不依赖 AI 服务与大型素材的回归测试。"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import asr_segments  # noqa: E402
import check_repeat  # noqa: E402
import make_timeline  # noqa: E402
import manifest  # noqa: E402


class TimelineTests(unittest.TestCase):
    def test_zero_duration_shot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "零时长或过短镜头"):
            make_timeline.durations([0, 10.0, 10.0, 20], 0.45, 24)

    def test_final_filter_pads_and_trims_to_total(self):
        lines, durs, slow = make_timeline.build_filter(
            [0, 2, 4, 6], [3, 3, 3], 6, 0.3, 24)
        self.assertAlmostEqual(sum(durs), 6.0)
        self.assertIn("tpad=stop_mode=clone", lines[-1])
        self.assertIn("trim=duration=6.000", lines[-1])
        self.assertTrue(lines[-1].endswith("[out]"))

    def test_resize_chain_is_optional(self):
        self.assertEqual(make_timeline.resize_chain(0, 0), "")
        chain = make_timeline.resize_chain(1080, 1920)
        self.assertIn("scale=1080:1920", chain)
        self.assertIn("setsar=1", chain)

    def test_short_material_uses_slowdown(self):
        _, _, slow = make_timeline.build_filter([0, 4, 8], [3, 5], 8, 0.3, 24)
        self.assertIn(1, slow)
        self.assertGreater(slow[1], 1.3)


class AsrAllocationTests(unittest.TestCase):
    def test_human_lyrics_are_assigned_to_asr_boundaries(self):
        lines = ["第一句", "第二句长", "第三句"]
        segments = [dict(start=0, end=4), dict(start=4, end=8), dict(start=8, end=12)]
        groups = asr_segments.allocate(lines, segments)
        self.assertEqual(sum(len(g["lines"]) for g in groups), 3)
        self.assertEqual([g["t0"] for g in groups], sorted(g["t0"] for g in groups))
        self.assertTrue(all("text" not in g for g in groups))


class RepeatTests(unittest.TestCase):
    def test_constant_offset(self):
        lines = [dict(start=0, end=2, text="a"), dict(start=4, end=6, text="b"),
                 dict(start=10, end=12, text="a"), dict(start=14, end=16, text="b")]
        rows, offset, drift = check_repeat.compare(lines, [0, 1], [2, 3])
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(offset, 10.0)
        self.assertAlmostEqual(drift, 0.0)

    def test_drift_is_detected(self):
        lines = [dict(start=0, end=2, text="a"), dict(start=4, end=6, text="b"),
                 dict(start=10, end=12, text="a"), dict(start=15, end=17, text="b")]
        _, _, drift = check_repeat.compare(lines, [0, 1], [2, 3])
        self.assertAlmostEqual(drift, 1.0)


class ManifestTests(unittest.TestCase):
    def test_shot_id_and_storyboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            shots = os.path.join(tmp, "shots.tsv")
            with open(shots, "w", encoding="utf-8") as f:
                f.write("id\tt0\tt1\tplace\tlyric\tscene\tmotion\n")
                f.write("shot_12\t0\t4\tT\t歌词\t画面\t运动\n")
            rows = manifest.read_shots(shots)
            self.assertEqual(rows[0]["clip"], "clips/v12.mp4")
            board = manifest.storyboard_text(dict(shots=rows, cost_per_shot=93,
                                                  canvas=dict(width=1920, height=1080)))
            self.assertIn("导演草稿", board)
            self.assertIn("确认门", board)


class SubtitleCanvasTests(unittest.TestCase):
    def test_vertical_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = os.path.join(tmp, "lines.json")
            beats = os.path.join(tmp, "beats.json")
            out = os.path.join(tmp, "subs.ass")
            with open(lines, "w", encoding="utf-8") as f:
                json.dump([dict(start=0, end=2, text="测试歌词", place="T"),
                           dict(start=2, end=4, text="music-mv demo", title=True)], f,
                          ensure_ascii=False)
            with open(beats, "w", encoding="utf-8") as f:
                json.dump(dict(beat_period=0.5, offset=0), f)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "make_subs.py"),
                            "--lines", lines, "--beats", beats,
                            "--width", "1080", "--height", "1920", "-o", out],
                           check=True, capture_output=True, text=True)
            with open(out, encoding="utf-8") as f:
                ass = f.read()
            self.assertIn("PlayResX: 1080", ass)
            self.assertIn("PlayResY: 1920", ass)
            self.assertNotIn("PlayResX: 1920", ass)
            xs = [float(x) for x in re.findall(r"\\pos\(([\d.]+),", ass)]
            self.assertTrue(xs)
            self.assertTrue(all(0 <= x <= 1080 for x in xs), "标题或字幕超出画布")


if __name__ == "__main__":
    unittest.main()
