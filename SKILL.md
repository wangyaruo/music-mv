---
name: music-mv
description: 把一首歌做成卡拍点、逐字弹字幕、字幕跟镜头联动的动画风 MV。当用户给出音频/歌曲，要求「做 MV / 音乐视频 / 歌词视频 / 卡点视频 / 给歌配画面 / 逐句配动画 / 字幕跟着画面走」，或需要分析歌曲 BPM 与拍点、切分歌词时间轴、批量出分镜图与图生视频、把多段素材按拍点拼成成片时使用。产出 16:9 或 9:16 的 MP4 + 封面。
---

# 音乐 MV 生成

把一首歌变成一支成片级别的动画 MV。核心链路：

```
听歌定拍 → 定风格 → 校歌词 → 定分镜 → 出图 → 图生视频 → 卡拍剪时间线 → 逐字弹字幕 → 混音出片
```

本 skill 提供这条链路上的全部可执行脚本，以及一份"哪些地方必须人工判断"的清单。

## 四条核心原则

整条流水线的设计都围绕这四条。理解了它们，每一步的"为什么"就都能推出来。

**一、时间是骨架，所有东西都吸附到同一个网格上。**
拍点网格是音乐的时间坐标。切点、歌词起止、每个字的出字时刻，全部吸到
1/8 拍或 1/4 拍网格上。观众感知到的"卡点"不来自精确到毫秒的对齐，
而来自**所有元素用同一套坐标**。

**二、一句歌词 = 一个镜头，切点就是这句的起点。**
不要把镜头时长当作约束去挪切点，也不要让一个镜头跨两句。
一旦开始"为了压到 6 秒而微调"，误差就会累积成"字幕换了画面还没切"。

**三、风格必须在出第一张图之前锁死。**
返工成本 = 全片成本。风格由三样东西锁定：角色设计图（人物锚）、
提示词里的文字复述（可辨识特征）、以及"主体不能太小"这条硬约束
（主体一小，模型就会退化成写实风景）。详见
[references/visual-style.md](references/visual-style.md)。

**四、每一步都要能机械验收。**
切点偏差、复唱偏移、响度、时长差——这些都应该是脚本打印出来的数字，
不是"看着差不多"。凡是只能靠眼睛判断的，就写一条命令把它变成数字。

## 什么时候用

用户给你一首歌（mp3/wav/m4a），或者一首歌的名字加一句"做成 MV"，就走这套流程。

**不适用**：纯剪辑已有视频素材（那不需要出图）、纯字幕翻译、纯音频处理。

## 硬性前提

- `ffmpeg`（带 `ass` / `xfade` / `zoompan` / `loudnorm` / `delogo` 滤镜）
- Python 3.9+，`numpy`
- 出图 / 图生视频能力（本 skill 调用 ImageGen / VideoGen）
- 字体：`assets/fonts/ZCOOLKuaiLe-Regular.ttf`（随仓库附带，SIL OFL）

`ffprobe` 不要求，脚本用 `ffmpeg -i` 的 stderr 读时长。

## 工程目录约定

```
project/
├── song.mp3
├── lyrics.txt
├── out/
│   ├── beats.json            # 拍点表
│   ├── groups.json           # 歌词分组（人工）
│   ├── lines_timing.json     # 逐句时间轴
│   ├── shots.tsv             # 分镜表（人工）
│   ├── cards.json            # 片头/片尾标题卡（可选）
│   ├── lines.json            # 字幕条目
│   ├── subs.ass              # 字幕文件
│   ├── filter_base.txt       # 时间线滤镜脚本
│   └── base.mp4              # 无字幕无音轨的基片
├── images/raw/  images/c16/  # 出图原图 / 统一裁切到 1920x1080
├── clips/                    # 每镜一段 mp4
└── 成片.mp4
```

## 第 0 步：定规格，别猜

开工前必须问清三件事，缺一个就停下来问：

1. **画幅** 16:9 / 9:16 / 1:1 —— 决定所有出图与出视频的比例，中途改等于重做
2. **风格** 用 `style_advisor.py` 给 3 个候选让用户选，**不要自己拍板**
3. **规模** 全曲逐句，还是只做副歌？全曲逐句通常 30-45 镜，成本要提前说清

风格一旦定了就不能中途换——换风格意味着 41 张图 + 41 段视频全部重做。
本 skill 的血泪教训：黏土风做完被一句"这种不好看"整片返工。

## 第 1 步：听歌定拍

```bash
python scripts/beat_sync.py song.mp3 -o out/beats.json
```

输出 BPM、`beat_period`、`offset`、全部拍点时刻、以及 1/2/4/8 分拍网格。
后续**所有**切点与字幕时刻都对到这个网格上，这是"卡点"的来源。

配合结构分析：

```bash
python scripts/song_structure.py --audio song.mp3 -o out/structure.json
```

它给段落边界和分镜数量建议，但**只当参考**。已知缺陷：长副歌会被判成一整段 90 秒的
"chorus"，据此算出的分镜数会离谱偏多。分镜表要人工定。

## 第 2 步：定风格

```bash
python scripts/style_advisor.py --audio song.mp3 --lyrics lyrics.txt --title "歌名"
```

给 3 套候选 + 打分 + 理由 + 建议单镜时长与叠化时长。拿给用户选，选定后记下
`shot` 与 `fade` 两个参数，后面直接套用。

## 第 3 步：先把歌词的字搞对

**这是最容易翻车的一步。** 详见 [references/lyrics-accuracy.md](references/lyrics-accuracy.md)。

三条铁律：

1. **不要相信 ASR 的中文歌词**。演唱中的咬字、拖腔、和声会让识别结果面目全非
   （真实案例：「被我收得好好的」→「被我收远不尔斯坦」）。
2. **不要相信记忆**。歌名对得上不等于字对得上，必须联网核对至少两个权威来源
   （百度百科 / 搜狗百科 / 互动百科 / 正规歌词站），不一致的以多数派为准并记录分歧。
3. **中文歌词大约每 4-8 句就有 1 处错字**。逐字对着音频念一遍，别只看首尾。

ASR 唯一可靠的产出是**段落边界**，用它把歌词切成"组"，组内按字数比例分配时间：

```bash
# 先人工写 groups.json（结构见 assets/groups.example.json）
python scripts/lyrics_timing.py --groups out/groups.json --beats out/beats.json \
    -o out/lines_timing.json
```

脚本会输出每句的 `s/字`，并**自动标出语速异常的行**——那通常意味着某个组边界估错了。

### 复唱段落必须做恒定偏移校验（最容易漏的一步）

流行歌的主歌/副歌通常走两遍。**同一句歌词在两遍里的出现时刻，差值必须是一个常数。**

如果按字数比例去分第二遍的组，误差会逐句累积：本案例里第二遍从 +1.2s 一路涨到 +2.8s，
表现为"从某一句开始字幕、音乐、画面全对不上"，而且越往后越严重。

校验方法：

```bash
# 打印每句的 s/字，两遍同一句应当接近
python -c "
import json
L=json.load(open('out/lines_timing.json'))
for a,b in zip(L[:len(L)//2], L[len(L)//2:]):
    print('%6.2f %6.2f  差 %+.2f  %s' % (a['start'], b['start'], b['start']-a['start'], a['text'][:14]))
"
```

差值是常数（本案例 94.5s）才对。**发现逐句递增，就说明第二遍的组边界估早了**，
直接把第二遍改成 `第一遍 + 常数`，不要重新分配。

更硬的校验方法见 [references/lyrics-accuracy.md](references/lyrics-accuracy.md) 的
"用 OCR 读原片歌词"一节。

## 第 4 步：定分镜

写 `out/shots.tsv`，制表符分隔，UTF-8，列固定：

```
id      t0      t1      place   lyric   scene   motion
s01     0.00    10.50   T               牌坊下的黄昏              镜头缓慢推进
```

- `id` 从 `s01` 连续编号，**素材文件名对应 `v01.mp4`**（去掉字母前缀）
- **单镜不超过 6 秒**（图生视频的物理上限），超过就拆
- `place` 是这一镜字幕该放的位置：`T` 顶部 / `M` 中部 / `B` 底部。
  判断依据是**画面里人站在哪**——人在下方就放 `T`，人在中间就放 `B`，别压脸
- 前奏与尾奏也要占镜头，不能空着

### 有配词的镜头，切点直接等于该句歌词的起点

不要"为了控制单镜时长"去挪切点。挪一次，误差就累积一次：本案例里
为了压到 6 秒以内反复微调，导致后半段 7 个镜头的切点比歌词晚 0.37–0.98 秒，
表现就是"字幕已经换了、画面还停在上一个镜头"。

规则：

- **有配词的镜头**：`t0 = 该句歌词的 start`，一个镜头对一句，不要一镜跨两句
- **无配词的镜头**（前奏、间奏、尾奏）：随便切，按节奏铺
- `t1` 永远等于下一镜的 `t0`，不要手写

自检：

```bash
python -c "
import json, csv
L=[x for x in json.load(open('out/lines.json')) if x.get('shot')]
S={r['id']:(float(r['t0']),float(r['t1'])) for r in csv.DictReader(open('out/shots.tsv'),delimiter='\t')}
d=[abs(S[x['shot']][0]-x['start']) for x in L]
print('切点与歌词起点最大偏差 %.4fs' % max(d))"
```

大于 0.1s 就要返工。`build_base.py --grid-div 4` 会把切点吸到 1/4 拍网格，
和歌词起点同一网格，残差能压到 0.005s 以内。

分镜数量参考：全曲逐句 = 歌词句数 + 前奏 1-3 镜 + 尾奏 0-2 镜。

## 第 5 步：出图

每镜一张。画风怎么锁死、主体太小为什么一定会跑偏，见
[references/visual-style.md](references/visual-style.md)。核心四条：

- 先出一张**角色设计图**，后续每张都以它为 `image1` 做图生图，提示词里
  用**文字复述可辨识特征**（"栗棕色齐耳短发 + 铁锈红背带裙 / 凌乱黑发 + 灰蓝T恤"），
  只给图不复述，模型会只继承"两个小孩"这个抽象概念
- 每张提示词**加镜头号前缀**（`S01 …`）。并发出图时没有前缀会互相覆盖
- **人物永远保持在能辨认服饰的尺度**。写"两个很小的孩子站在远处"，
  模型会退化成写实风景照——这是最隐蔽的画风跑偏原因
- 出图工具的 `output_dir` 参数经常被忽略，产物会落到默认目录，别指望它

出完统一裁到目标分辨率（`images/c16/`），避免时间线里再缩放。

## 第 6 步：图生视频

每镜一段。要点：

- 提示词只描述**运动**（"the cake splits, jam stretches"），外观由输入图决定，
  不要把风格词重复堆进去
- 用固定句式锚住构图：`Animate the input image with subtle motion only.
  Keep the EXACT same composition, framing, camera distance and colors as the input.`
  再加 `Do not change their clothes, do not change the camera, do not zoom in.`
- 输出时长不稳定：同一个模型可能给 **5.04s** 也可能给 **6.04s**。
  不要假设，`build_base.py` 会自动探测每段真实时长
- 加负向提示：
  `color shift, costume change, outfit change, different clothes, photorealistic,
  3D render, text, watermark, extra limbs, deformed hands, flicker, jitter, morphing`
- 即使写了"不要推近"，模型仍会轻微推近。通常构图更紧凑，可接受——
  验收看"服装颜色和人物设计有没有变"，不是"构图是否逐像素一致"
- 额度会用尽（HTTP 429 `code 14018`）。**兜底方案**：用静帧 + `zoompan` 缓推，
  能撑住时间线，但那一镜没有真实运动——要在交付时主动说明

## 第 7 步：卡拍剪时间线

```bash
python scripts/build_base.py --shots out/shots.tsv --clips-dir clips \
    --beats out/beats.json --total 255.814 --fade 0.45 \
    --fill-ids s02,s10,s04,s27 -o out/base.mp4
```

它做的事：

1. 取每镜起点当切点，**吸附到 1/4 拍网格**（`--grid-div 4`，和歌词同一网格）
2. 叠化中点压在切点上（`xfade offset = 切点 − fade/2`）
3. **逐段探测素材真实时长**并按需慢放。不要写死 6.04s——某段只有 5.04s 时，
   `trim=duration` 会提前结束，xfade 链在那里断掉，后续镜头被静默丢弃
   （本案例里这个 bug 让成片短了 26 秒）
4. 尾奏（歌词唱完之后那几十秒）用 `--fill-ids` 指定的镜头循环填满。
   填充镜头本身要够长，否则会被大幅慢放

`--total` 必须等于音频时长，否则音画会错位。

## 第 8 步：逐字弹字幕

```bash
python scripts/build_lines.py --timing out/lines_timing.json --shots out/shots.tsv \
    --cards out/cards.json -o out/lines.json
python scripts/make_subs.py --lines out/lines.json --beats out/beats.json -o out/subs.ass
```

`build_lines.py` 的职责是**把字幕位置绑到镜头上**：每句歌词按中点落在哪个镜头，
就继承那个镜头的 `place`。这是"字幕跟画面联动、不是固定一行"的实现方式。

字幕样式与踩坑见 [references/subtitle-styling.md](references/subtitle-styling.md)，五个必须记住的：

1. `CHUNK_MAX = 18`。设成 12 的话，13 字的句子会被拆成 12+1，最后孤零零一个字
2. `BorderStyle=1`（描边）而不是 `3`（色块）。色块模式下每个字自带一块底，
   整句会被切成一排方块，很难看
3. `fontsdir=` 必须绝对路径，相对路径**静默失败**，字体无声退回默认字体
4. 片头歌名/片尾署名必须用 `title:true` 或 `block:true`（整块出现）。
   逐字弹出的话，"周杰伦"三个字要 2.2 秒才齐，等齐时画面已经淡出了
5. **出字只占句长的前 `REVEAL`（0.78）**，剩下 22% 让末字停在长音上。
   把字铺满整句，前半句唱得快的句子会明显滞后——这是"字幕跟不上声音"的
   最常见原因，且与整句边界无关，光看边界查不出来

### 句尾不要再额外留白

`hold` 已经是 0.06s。`REVEAL` 之后的 22% 就是末字的停留时间，再留 0.3s
会和下一句重叠 0.3 秒——看起来正是"字幕和画面没对上"。

## 第 9 步：混音出片

```bash
python scripts/mix_final.py --base out/base.mp4 --audio song.mp3 --subs out/subs.ass \
    --duration 255.58 --out "成片.mp4"
```

（或者按 [references/ffmpeg-recipes.md](references/ffmpeg-recipes.md) 手写滤镜串）

关键顺序：`delogo → eq → vignette → ass → fade → format`，音频侧
`loudnorm → afade → aresample=44100`。`loudnorm` 会把采样率升到 96k，
**必须**补一个 `aresample` 回到 44.1k。

验收线：`mean_volume` 约 −14~−15dB，`max_volume` ≤ −1.0dB。

## 第 10 步：交付前自查

**机械项**（脚本会打印，看数字即可）

- [ ] 音频时长与视频时长差 < 0.1s
- [ ] 切点与歌词起点最大偏差 < 0.1s（见第 4 步的自检命令）
- [ ] 复唱段落两遍的偏移是常数（见第 3 步，不是递增就不是常数）
- [ ] 切点全部落在 1/4 拍网格上（`build_base.py` 打印误差应 < 0.005s）
- [ ] 音量：`mean` 约 −14~−15dB，`max` ≤ −1.0dB

**目视项**（必须真的看图，不能靠推断）

- [ ] 全片风格总览：`ffmpeg -pattern_type glob -i 'images/c16/s*.png' -vf "scale=248:140,tile=7x6" -frames:v 1 sheet.png`，
      逐格扫一遍，没有风格孤岛
- [ ] 逐句抽查 3 个时间点，字幕、唱词、画面三者一致
- [ ] 字幕没有压住人脸（重点看特写镜）
- [ ] 片头歌名、歌手名完整出现且停留 ≥ 3s，不被淡出吃掉
- [ ] 片尾署名整块出现，不被画面淡出切掉
- [ ] 抽帧看四角没有残留水印

## 排错

见 [references/troubleshooting.md](references/troubleshooting.md)。最常见的几个：

| 现象 | 原因 |
|---|---|
| 字幕字体不对，变成默认黑体 | `fontsdir` 用了相对路径 |
| 整句字幕只剩最后一个字 | `CHUNK_MAX` 太小，句子被拆段 |
| 时间线断在某一镜，成片变短 | 那段素材比「镜头时长+叠化」短，`trim` 提前结束让 xfade 链断掉 |
| 从某一句起字幕/音乐/画面全错位，越往后越严重 | 复唱段落按字数重分配了，应改成「第一遍 + 常数」 |
| 字幕已经换了，画面还停在上一个镜头 | 该镜切点晚于歌词起点 |
| 字幕比唱词慢半拍，但整句起点是对的 | 出字铺满了整句，`REVEAL` 没生效 |
| 某一镜画风突变（写实/油画感） | 该镜主体太小，模型退化成风景照 |

## 成本预期

全曲逐句（约 40 镜）：40 张图 + 40 段 5-6s 视频。按常见额度，
出图约 8 credits/张，出视频约 85 credits/段，合计约 **4000 credits**。
开工前把量级告诉用户，别做完才说。
