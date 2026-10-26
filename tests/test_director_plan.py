#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导演视觉规划的结构、覆盖和反机械堆砌测试。"""

import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import director_plan  # noqa: E402


def example_plan():
    with open(os.path.join(ROOT, "assets", "director.example.json"), encoding="utf-8") as f:
        return json.load(f)


def example_lyrics():
    return director_plan.read_lyrics(os.path.join(ROOT, "assets", "lyrics.director.example.txt"))


class DirectorPlanTests(unittest.TestCase):
    def test_valid_example_passes_structure_and_coverage(self):
        self.assertEqual(director_plan.validate_plan(example_plan(), len(example_lyrics())), [])

    def test_emotional_arc_requires_three_stages(self):
        plan = example_plan()
        plan["emotional_arc"].pop()
        self.assertTrue(any("emotional_arc" in e for e in director_plan.validate_plan(plan)))

    def test_no_characters_requires_absence_strategy(self):
        plan = example_plan()
        plan["absence_strategy"] = ""
        self.assertTrue(any("absence_strategy" in e for e in director_plan.validate_plan(plan)))

    def test_motif_requires_state_progression(self):
        plan = example_plan()
        plan["motifs"][0]["states"] = ["被雨遮蔽"]
        self.assertTrue(any("2 个不同状态" in e for e in director_plan.validate_plan(plan)))

    def test_every_lyric_must_be_covered(self):
        plan = example_plan()
        plan["coverage"].pop()
        errors = director_plan.validate_plan(plan, len(example_lyrics()))
        self.assertTrue(any("缺少歌词行" in e for e in errors))

    def test_duplicate_lyric_coverage_is_rejected(self):
        plan = example_plan()
        plan["coverage"][1] = copy.deepcopy(plan["coverage"][0])
        self.assertTrue(any("不能重复" in e for e in director_plan.validate_plan(plan)))

    def test_each_motif_only_once_is_mechanical_stacking(self):
        plan = example_plan()
        base = plan["motifs"][0]
        plan["motifs"] = []
        for i in range(4):
            motif = copy.deepcopy(base)
            motif["id"] = "m%d" % i
            plan["motifs"].append(motif)
        for i, row in enumerate(plan["coverage"]):
            row["motif_ids"] = ["m%d" % i]
        self.assertTrue(any("逐句换物件" in e for e in director_plan.validate_plan(plan)))

    def test_transition_requires_continuity(self):
        plan = example_plan()
        plan["transitions"][0]["continuity"] = ""
        self.assertTrue(any("continuity" in e for e in director_plan.validate_plan(plan)))

    def test_selected_concept_must_be_an_alternative(self):
        plan = example_plan()
        plan["selected_concept"] = "未比较过的方案"
        self.assertTrue(any("selected_concept" in e for e in director_plan.validate_plan(plan)))

    def test_scaffold_tracks_lyrics_without_inventing_creative_content(self):
        plan = director_plan.scaffold(example_lyrics(), "测试")
        self.assertEqual(len(plan["coverage"]), 4)
        self.assertEqual(plan["coverage"][0]["lyric_text"], "雨停在没说出口的午后")
        self.assertEqual(plan["logline"], "")
        self.assertTrue(director_plan.validate_plan(plan, 4))

    def test_review_exposes_emotion_rhythm_and_lyric_coverage(self):
        text = director_plan.render_review(example_plan())
        self.assertIn("情绪与节奏", text)
        self.assertIn("逐句视觉覆盖", text)
        self.assertIn("房间里的时间", text)

    def test_srt_reader_ignores_indices_and_timestamps(self):
        with tempfile.NamedTemporaryFile("w", suffix=".srt", encoding="utf-8", delete=False) as f:
            f.write("1\n00:00:01,000 --> 00:00:03,000\n第一句\n\n"
                    "2\n00:00:03,000 --> 00:00:05,000\n第二句\n")
            path = f.name
        try:
            self.assertEqual(director_plan.read_lyrics(path), ["第一句", "第二句"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
