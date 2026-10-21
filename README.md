# music-mv

把一首歌做成卡拍点、逐字弹字幕、字幕跟镜头联动的动画 MV。

一套可执行的流水线：**听歌定拍 → 定风格 → 校歌词 → 定分镜 → 出图 → 图生视频 →
卡拍剪时间线 → 逐字弹字幕 → 混音出片**。

产出的片子是 16:9 / 9:16 的 MP4 + 封面，字幕**逐镜排布**——人物在哪一侧、
画面哪里是空的，字幕就避开哪里，而不是全片固定一行。

## 它解决什么问题

手工做一支 MV，最难的不是出图，是三件容易翻车的事：

1. **字幕不卡拍**。字幕出现时刻是估的，跟音乐对不上，整支片子就显得业余。
2. **中文歌词抄错**。ASR 对演唱几乎不可用，凭记忆写会补全出"更像歌词"的错版本。
3. **字幕和画面打架**。固定一行字幕，遇到特写就压脸，遇到广角又显得悬空。

这套工具对三件事都有具体对策：字幕每字吸附到 1/8 拍网格；歌词走"多源核对 +
段落锚点"流程；字幕位置由分镜表的 `place` 列逐镜决定。

## 安装

```bash
git clone https://github.com/wangyaruo/music-mv.git
cd music-mv
pip install numpy
```

需要 `ffmpeg`（含 `ass` / `xfade` / `zoompan` / `loudnorm` / `delogo` 滤镜）。
不需要 `ffprobe` —— 脚本用 `ffmpeg -i` 的 stderr 读时长。

字体 `assets/fonts/ZCOOLKuaiLe-Regular.ttf` 随仓库附带（SIL OFL 1.1）。

## 快速开始

```bash
# 1. 拍点
python scripts/beat_sync.py song.mp3 -o out/beats.json

# 2. 风格建议（给用户选）
python scripts/style_advisor.py --audio song.mp3 --lyrics lyrics.txt --title "歌名"

# 3. 歌词时间轴（先人工写 out/groups.json）
python scripts/lyrics_timing.py --groups out/groups.json --beats out/beats.json \
    -o out/lines_timing.json

# 4. 字幕条目（先把歌词位置绑到镜头上）
python scripts/build_lines.py --timing out/lines_timing.json --shots out/shots.tsv \
    --cards out/cards.json -o out/lines.json
python scripts/make_subs.py --lines out/lines.json --beats out/beats.json -o out/subs.ass

# 5. 卡拍拼接
python scripts/build_base.py --shots out/shots.tsv --clips-dir clips \
    --beats out/beats.json --total 255.814 --fade 0.45 \
    --fill-ids s02,s10,s04,s27 -o out/base.mp4

# 6. 合成成片
python scripts/mix_final.py --base out/base.mp4 --audio song.mp3 --subs out/subs.ass \
    --duration 255.58 --out "成片.mp4"
```

出图与图生视频由调用方（Agent / 人）完成，产物按 `clips/v01.mp4` 命名即可。

## 脚本

| 脚本 | 作用 |
|---|---|
| `beat_sync.py` | BPM 与拍点网格（频谱通量 + 自相关 + 相位搜索） |
| `song_structure.py` | 段落边界与分镜数量参考（**只作参考**，长副歌会误判） |
| `style_advisor.py` | 按 tempo / 能量 / 亮度 / 歌词意象推荐 3 套画风 |
| `lyrics_timing.py` | 歌词分组 → 逐句时间轴（锚点 + 字数比例 + 拍点吸附） |
| `build_lines.py` | 把字幕位置绑到镜头上，合并片头尾标题卡 |
| `make_subs.py` | 逐字弹的 ASS 字幕（每字独立事件、独立动画） |
| `make_timeline.py` | xfade 滤镜脚本，切点吸拍点 + 叠化中点压拍 |
| `build_base.py` | 探测素材时长、搭 xfade 链、渲染无字幕基片 |
| `mix_final.py` | 叠字幕 + 调色 + 去水印 + 响度标准化 + 首尾淡化 |

## 文档

- [SKILL.md](SKILL.md) —— 完整工作流与每个环节的判断依据
- [references/pipeline.md](references/pipeline.md) —— 数据结构、时间线数学、成本模型、真实案例复盘
- [references/visual-style.md](references/visual-style.md) —— 画风锁定：从设计稿到 40 镜不跑偏
- [references/lyrics-accuracy.md](references/lyrics-accuracy.md) —— 歌词校对，以及用 OCR 读原片歌词做时间轴校准
- [references/subtitle-styling.md](references/subtitle-styling.md) —— ASS 版式、逐字节奏（`REVEAL`）、踩坑
- [references/ffmpeg-recipes.md](references/ffmpeg-recipes.md) —— 滤镜配方
- [references/troubleshooting.md](references/troubleshooting.md) —— 现象 / 原因 / 处理

## 示例数据

`assets/` 下有全套真实数据可对照：`beats.example.json`、`groups.example.json`、
`shots.example.tsv`、`cards.example.json`、`lines.example.json`。

## 已知限制

- **ASR 对演唱中的中文歌词基本不可用**。工具链的设计前提就是"人工写准歌词，
  只用 ASR 的段落边界"。不要试图调参修好识别率。
- `song_structure.py` 会把长副歌判成一整段，分镜数量需要人工定。
- 图生视频单段上限约 6 秒，更长的镜头靠慢放补齐，超过 30% 慢放会看出来。
- 逐字字幕需要 `libass` 支持内联标签，极老的 ffmpeg 可能有问题。

## 许可

代码 MIT。字体 ZCOOL KuaiLe 为 SIL Open Font License 1.1（见
`assets/fonts/OFL.txt`）。
