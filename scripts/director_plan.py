#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导演视觉规划的脚手架、结构校验与用户审阅。

scaffold 只生成空白结构和逐句清单；AI 必须自行完成创意。
check 校验结构、状态轨迹和歌词覆盖，不评价审美质量。
"""

import argparse
import json
import os
import re
import sys

PLACEHOLDERS = {"", "todo", "tbd", "待填", "待定", "...", "…"}


def nonempty(value):
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def read_lyrics(path):
    """读取纯文本、LRC 或 SRT，返回非空歌词行，不把时间轴当歌词。"""
    ext = os.path.splitext(path)[1].lower()
    lines = []
    with open(path, encoding="utf-8-sig") as f:
        raw_lines = f.read().splitlines()
    for raw in raw_lines:
        text = raw.strip()
        if not text:
            continue
        if ext == ".srt":
            if text.isdigit() or "-->" in text:
                continue
        elif ext == ".lrc":
            text = re.sub(r"\[[^\]]+\]", "", text).strip()
        else:
            if re.fullmatch(r"\[[^\]]+\]", text):
                continue
        if text and not text.startswith("#"):
            lines.append(text)
    return [x for x in lines if x]


def _check_rows(rows, fields, label, errors, min_count=1):
    if not isinstance(rows, list) or len(rows) < min_count:
        errors.append("%s 至少需要 %d 项" % (label, min_count))
        return False
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append("%s[%d] 必须是对象" % (label, i))
            continue
        for field in fields:
            if not nonempty(row.get(field)):
                errors.append("%s[%d] 缺少或未完成 %s" % (label, i, field))
    return True


def validate_plan(plan, lyric_count=None):
    """返回结构错误；通过不代表语义、审美或最终画面已经验收。"""
    errors = []
    for field in ("title", "logline", "semantic_thesis", "selected_concept"):
        if not nonempty(plan.get(field)):
            errors.append("缺少或未完成 %s" % field)
    themes = plan.get("themes")
    if not isinstance(themes, list) or not 1 <= len(themes) <= 3:
        errors.append("themes 必须包含 1–3 个核心主题")
    elif any(not nonempty(x) for x in themes):
        errors.append("themes 不能包含空项")

    _check_rows(plan.get("emotional_arc"),
                ("stage", "emotion", "visual_strategy", "music_evidence"),
                "emotional_arc", errors, 3)
    _check_rows(plan.get("rhythm_arc"),
                ("section", "energy", "shot_density", "motion", "transition_rule"),
                "rhythm_arc", errors, 2)

    world = plan.get("visual_world", {})
    if not isinstance(world, dict):
        errors.append("visual_world 必须是对象")
        world = {}
    for field in ("setting", "palette", "texture", "style_anchor"):
        if not nonempty(world.get(field)):
            errors.append("visual_world 缺少或未完成 %s" % field)

    roles = plan.get("character_roles")
    if not isinstance(roles, list):
        errors.append("character_roles 必须是列表")
        roles = []
    if not roles and not nonempty(plan.get("absence_strategy")):
        errors.append("无人物时必须填写 absence_strategy，说明由什么承担主体")
    for i, role in enumerate(roles):
        if not isinstance(role, dict):
            errors.append("character_roles[%d] 必须是对象" % i)
            continue
        for field in ("name", "function", "visual_anchor", "action_logic"):
            if not nonempty(role.get(field)):
                errors.append("character_roles[%d] 缺少或未完成 %s" % (i, field))

    scenes = plan.get("scenes")
    scene_ids = set()
    if _check_rows(scenes, ("id", "purpose", "emotion", "action", "change"),
                   "scenes", errors, 3):
        for i, scene in enumerate(scenes):
            sid = scene.get("id")
            if sid in scene_ids:
                errors.append("scenes[%d] id 重复: %s" % (i, sid))
            scene_ids.add(sid)
            if not isinstance(scene.get("visual_elements"), list) or not scene["visual_elements"]:
                errors.append("scenes[%d] 必须列出 visual_elements" % i)

    motifs = plan.get("motifs")
    motif_ids = set()
    if not isinstance(motifs, list):
        errors.append("motifs 必须是列表")
        motifs = []
    if len(motifs) > 4:
        errors.append("核心母题最多 4 个，避免机械堆砌")
    if not motifs and not nonempty(plan.get("non_object_strategy")):
        errors.append("无核心物件/母题时必须填写 non_object_strategy")
    for i, motif in enumerate(motifs):
        if not isinstance(motif, dict):
            errors.append("motifs[%d] 必须是对象" % i)
            continue
        for field in ("id", "kind", "meaning", "function"):
            if not nonempty(motif.get(field)):
                errors.append("motifs[%d] 缺少或未完成 %s" % (i, field))
        mid = motif.get("id")
        if mid in motif_ids:
            errors.append("motifs[%d] id 重复: %s" % (i, mid))
        motif_ids.add(mid)
        states = motif.get("states")
        if not isinstance(states, list) or len(set(states)) < 2:
            errors.append("motifs[%d] 至少需要 2 个不同状态" % i)
        recurrence = motif.get("recurrence")
        minimum = 2 if motif.get("function") == "anchor" else 1
        if not isinstance(recurrence, int) or recurrence < minimum:
            errors.append("motifs[%d] recurrence 至少为 %d" % (i, minimum))

    _check_rows(plan.get("transitions"),
                ("from", "to", "trigger", "technique", "continuity"),
                "transitions", errors, 2)
    rules = plan.get("coherence_rules")
    if not isinstance(rules, list) or len(rules) < 3 or any(not nonempty(x) for x in rules):
        errors.append("coherence_rules 至少需要 3 条有效的角色/空间/物件/风格规则")

    alternatives = plan.get("alternatives_considered")
    if _check_rows(alternatives, ("title", "premise", "visual_strategy"),
                   "alternatives_considered", errors, 2):
        titles = {x.get("title") for x in alternatives}
        if plan.get("selected_concept") not in titles:
            errors.append("selected_concept 必须来自 alternatives_considered")

    coverage = plan.get("coverage")
    coverage_ids, motif_usage = [], {}
    if not isinstance(coverage, list) or not coverage:
        errors.append("coverage 必须覆盖每句歌词")
        coverage = []
    for i, row in enumerate(coverage):
        if not isinstance(row, dict):
            errors.append("coverage[%d] 必须是对象" % i)
            continue
        lyric_id = row.get("lyric_id")
        if not isinstance(lyric_id, int) or lyric_id <= 0:
            errors.append("coverage[%d] lyric_id 必须为正整数" % i)
        coverage_ids.append(lyric_id)
        for field in ("visual_intent", "change", "scene_id"):
            if not nonempty(row.get(field)):
                errors.append("coverage[%d] 缺少或未完成 %s" % (i, field))
        if scene_ids and row.get("scene_id") not in scene_ids:
            errors.append("coverage[%d] 引用了不存在的 scene_id" % i)
        row_motifs = row.get("motif_ids", [])
        if not isinstance(row_motifs, list):
            errors.append("coverage[%d] motif_ids 必须是列表" % i)
            row_motifs = []
        for mid in row_motifs:
            if motif_ids and mid not in motif_ids:
                errors.append("coverage[%d] 引用了不存在的 motif_id: %s" % (i, mid))
            motif_usage[mid] = motif_usage.get(mid, 0) + 1
    if len(coverage_ids) != len(set(coverage_ids)):
        errors.append("coverage 中 lyric_id 不能重复")
    if lyric_count is not None:
        expected = set(range(1, lyric_count + 1))
        actual = set(coverage_ids)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append("coverage 缺少歌词行: %s" % missing)
        if extra:
            errors.append("coverage 包含超出歌词范围的行: %s" % extra)
    if len(coverage) >= 4 and motif_usage and not any(v >= 2 for v in motif_usage.values()):
        errors.append("所有母题都只用一次，属于逐句换物件，缺少贯穿视觉线索")
    return errors


def scaffold(lyrics, title):
    empty_arc = [dict(stage="", emotion="", visual_strategy="", music_evidence="")
                 for _ in range(3)]
    empty_rhythm = [dict(section="", energy="", shot_density="", motion="",
                         transition_rule="") for _ in range(2)]
    alternatives = [dict(title="", premise="", visual_strategy="") for _ in range(2)]
    coverage = [dict(lyric_id=i, lyric_text=text, visual_intent="", change="",
                     scene_id="", motif_ids=[]) for i, text in enumerate(lyrics, 1)]
    return {
        "title": title,
        "logline": "",
        "semantic_thesis": "",
        "themes": [],
        "emotional_arc": empty_arc,
        "rhythm_arc": empty_rhythm,
        "visual_world": dict(setting="", palette="", texture="", style_anchor=""),
        "character_roles": [],
        "absence_strategy": "",
        "scenes": [],
        "motifs": [],
        "non_object_strategy": "",
        "transitions": [],
        "coherence_rules": [],
        "alternatives_considered": alternatives,
        "selected_concept": "",
        "coverage": coverage,
        "_instructions": "由 AI 以导演视角填写全部创意字段；先提出并比较 2–3 套概念，不得留空或机械堆砌物件。"
    }


def render_review(plan):
    lines = ["# 导演视觉总纲：《%s》" % plan["title"], "",
             "> 本文件用于用户确认。结构校验不替代审美与语义评审。", "",
             "## 核心阐述", "", plan["logline"], "",
             "**主题潜台词：**" + plan["semantic_thesis"], "",
             "**核心主题：**" + "、".join(plan["themes"]), "",
             "**选定概念：**" + plan["selected_concept"], "",
             "## 情绪与节奏", "",
             "| 阶段 | 情绪 | 视觉策略 | 音乐证据 |", "|---|---|---|---|"]
    for row in plan["emotional_arc"]:
        lines.append("| %s | %s | %s | %s |" %
                     (row["stage"], row["emotion"], row["visual_strategy"], row["music_evidence"]))
    lines += ["", "| 段落 | 能量 | 镜头密度 | 动作 | 转场规则 |", "|---|---|---|---|---|"]
    for row in plan["rhythm_arc"]:
        lines.append("| %s | %s | %s | %s | %s |" %
                     (row["section"], row["energy"], row["shot_density"],
                      row["motion"], row["transition_rule"]))
    world = plan["visual_world"]
    lines += ["", "## 视觉世界", "",
              "- **场景体系：**" + world["setting"],
              "- **色板：**" + world["palette"],
              "- **材质：**" + world["texture"],
              "- **风格锚点：**" + world["style_anchor"], ""]
    if plan["character_roles"]:
        lines += ["## 角色", "", "| 角色 | 功能 | 视觉锚点 | 动作逻辑 |", "|---|---|---|---|"]
        for role in plan["character_roles"]:
            lines.append("| %s | %s | %s | %s |" %
                         (role["name"], role["function"], role["visual_anchor"], role["action_logic"]))
    else:
        lines += ["## 无人物主体策略", "", plan["absence_strategy"]]
    lines += ["", "## 场景与动作", "", "| 场景 | 目的 | 动作 | 可见变化 |", "|---|---|---|---|"]
    for scene in plan["scenes"]:
        lines.append("| %s | %s | %s | %s |" %
                     (scene["id"], scene["purpose"], scene["action"], scene["change"]))
    if plan["motifs"]:
        lines += ["", "## 贯穿母题", "", "| 母题 | 功能 | 含义 | 状态 |", "|---|---|---|---|"]
        for motif in plan["motifs"]:
            lines.append("| %s | %s | %s | %s |" %
                         (motif["id"], motif["function"], motif["meaning"], " → ".join(motif["states"])))
    else:
        lines += ["", "## 非物件表达", "", plan["non_object_strategy"]]
    lines += ["", "## 转场", "", "| 从 | 到 | 触发 | 方法 | 连续性 |", "|---|---|---|---|---|"]
    for tr in plan["transitions"]:
        lines.append("| %s | %s | %s | %s | %s |" %
                     (tr["from"], tr["to"], tr["trigger"], tr["technique"], tr["continuity"]))
    lines += ["", "## 连贯性规则", ""]
    lines += ["- " + rule for rule in plan["coherence_rules"]]
    lines += ["", "## 逐句视觉覆盖", "", "| 歌词 | 视觉意图 | 可见变化 | 场景 |", "|---|---|---|---|"]
    for row in plan["coverage"]:
        lines.append("| %s | %s | %s | %s |" %
                     (row.get("lyric_text", row["lyric_id"]), row["visual_intent"],
                      row["change"], row["scene_id"]))
    lines += ["", "## 已比较的备选概念", ""]
    for alt in plan["alternatives_considered"]:
        lines.append("- **%s：**%s（%s）" % (alt["title"], alt["premise"], alt["visual_strategy"]))
    lines.append("")
    return "\n".join(lines)


def emit(errors):
    print(json.dumps(dict(ok=not errors, mode="structure_and_coverage_only", errors=errors),
                     ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    sc = sub.add_parser("scaffold", help="生成空白导演结构和逐句清单")
    sc.add_argument("--lyrics", required=True)
    sc.add_argument("--title", required=True)
    sc.add_argument("-o", "--output", required=True)
    for name in ("check", "review"):
        cmd = sub.add_parser(name, help="校验导演规划" if name == "check" else "生成用户审阅稿")
        cmd.add_argument("plan")
        cmd.add_argument("--lyrics")
        cmd.add_argument("-o", "--output")
    args = ap.parse_args()

    if args.command == "scaffold":
        lyrics = read_lyrics(args.lyrics)
        if not lyrics:
            raise SystemExit("歌词文件没有可用歌词行")
        plan = scaffold(lyrics, args.title)
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("已生成空白导演结构：%s（%d 句，创意字段需由 AI 完成）" % (args.output, len(lyrics)))
        return 0

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    count = len(read_lyrics(args.lyrics)) if args.lyrics else None
    errors = validate_plan(plan, count)
    if args.command == "check":
        return emit(errors)
    if errors:
        return emit(errors)
    review = render_review(plan)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(review)
        print("导演审阅稿：", args.output)
    else:
        print(review)
    return 0


if __name__ == "__main__":
    sys.exit(main())
