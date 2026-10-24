# 示例数据怎么用

这些文件有两种用途：对照数据结构，以及复现一个真实的复唱漂移问题。

## 正常输入

- `beats.example.json`：拍点与网格。
- `groups.example.json`：歌词分组输入。
- `shots.example.tsv`：分镜表。**它是早期黏土版案例，只用于数据结构对照**；
  不要照抄其中的画风或提示词，新的提示词必须遵循 `references/visual-style.md`。
- `cards.example.json`、`lines.example.json`：标题卡与字幕条目结构。

## 复唱漂移回归样本

`groups.example.json` 保留了第二遍按字数比例分配造成漂移的版本。
用它生成时间轴后，配词分镜与歌词起点的最大偏差为 **2.783s**：

```bash
python scripts/lyrics_timing.py --groups assets/groups.example.json \
  --beats assets/beats.example.json -o /tmp/lines_timing.json
python scripts/check_repeat.py --timing /tmp/lines_timing.json \
  --first 1-18 --second 19-36 --fix-out /tmp/lines_timing.fixed.json
```

预期结果：偏移极差约 **3.560s**，工具判定 FAIL，并生成修正版。

`assets/lines_timing.fixed.example.json` 就是这次修正的产物。它与
`shots.example.tsv` 的配词切点最大偏差降至 **0.074s**，低于 0.1s 验收线。
修正后仍要人工抽查，再重建 `lines.json → subs.ass → base.mp4`，不能只替换一个文件就交付。
