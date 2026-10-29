---
name: music-mv
description: 把一首歌做成卡拍点、逐字弹字幕、字幕跟镜头联动的动画风 MV。当用户给出音频/歌曲，要求「做 MV / 音乐视频 / 歌词视频 / 卡点视频 / 给歌配画面 / 逐句配动画 / 字幕跟着画面走」，或需要分析歌曲 BPM 与拍点、切分歌词时间轴、批量出分镜图与图生视频、把多段素材按拍点拼成成片时使用。产出 16:9 或 9:16 的 MP4 + 封面。
agent_created: true
---

# 音乐 MV 生成

把一首歌变成一支成片级别的动画 MV。核心链路：

```
听歌定拍 → 校歌词 → 导演构思与风格锁定 → 定分镜 → 草稿/试制确认 → 出图 → 图生视频 → 卡拍剪时间线 → 逐字弹字幕 → 混音出片 → 自动 QA
```

本 skill 提供这条链路上的全部可执行脚本，以及一份"哪些地方必须人工判断"的清单。

## 五条核心原则

整条流水线的设计都围绕这五条。理解了它们，每一步的"为什么"就都能推出来。

**一、时间是骨架，所有东西都吸附到同一个网格上。**
拍点网格是音乐的时间坐标。切点、歌词起止、每个字的出字时刻，全部吸到
1/8 拍或 1/4 拍网格上。观众感知到的"卡点"不来自精确到毫秒的对齐，
而来自**所有元素用同一套坐标**。

**二、一句歌词 = 一个镜头，切点就是这句的起点。**
不要把镜头时长当作约束去挪切点，也不要让一个镜头跨两句。
一旦开始"为了压到 6 秒而微调"，误差就会累积成"字幕换了画面还没切"。

**三、导演构思先于物件与分镜。**
先理解歌词语义、情绪和节奏，再由 AI 提出视觉概念、角色、场景、物件、动作和衔接。
不要从预设物件或地点清单反推剧情；抽象歌词也要形成有递进的视觉结构。详见
[references/director-storytelling.md](references/director-storytelling.md)。

**四、风格必须在出第一张图之前锁死。**
返工成本 = 全片成本。风格由三样东西锁定：角色设计图（人物锚）、
提示词里的文字复述（可辨识特征）、以及"主体不能太小"这条硬约束
（主体一小，模型就会退化成写实风景）。详见
[references/visual-style.md](references/visual-style.md)。
走代码渲染路线时"锁死"的对象不同——锁的是调色板、逻辑画布尺寸和 sprite 网格，
改一个数字重渲只要几秒；返工成本几乎为零，但一致性风险换了个地方（见原则五）。

**五、每一步都要能机械验收。**
切点偏差、复唱偏移、响度、时长差——这些都应该是脚本打印出来的数字，
不是"看着差不多"。凡是只能靠眼睛判断的，就写一条命令把它变成数字。

## 什么时候用

用户给你一首歌（mp3/wav/m4a），或者一首歌的名字加一句"做成 MV"，就走这套流程。

**不适用**：纯剪辑已有视频素材（那不需要出图）、纯字幕翻译、纯音频处理。

**另一种走法：不出图。** 如果整片能落成「像素场景 + UI 界面 + 文字卡」这类
几何可描述的画面，改走 [references/procedural-pixel.md](references/procedural-pixel.md)
的代码渲染路线——每一帧由 Python 画出来，零出图、零图生视频，成本为零，
代价是一次性的编码时间。先按那份文档第一节的分工表确认适配，再决定要不要开工；
不适配就回到默认的 AI 出图路线，不要硬套。

## 硬性前提

- `ffmpeg`（带 `ass` / `xfade` / `zoompan` / `loudnorm` / `delogo` 滤镜）
- Python 3.9+，`numpy`
- 出图 / 图生视频能力（本 skill 调用 ImageGen / VideoGen）。
  走[纯代码渲染路线](references/procedural-pixel.md)时这两样都不需要，只要 Pillow
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
│   ├── director.json         # AI 导演构思：语义/情绪/节奏/场景/母题/转场/逐句覆盖
│   ├── director.md           # 给用户确认的导演视觉总纲
│   ├── shots.tsv             # 分镜表（从导演总纲展开）
│   ├── storyboard.md         # 导演草稿（生成前确认门）
│   ├── manifest.json         # 逐镜提示词、来源、成本与状态
│   ├── pixel_spec.json       # 像素项目专用：投影、网格、动作合同与状态层
│   ├── cards.json            # 片头/片尾标题卡（可选）
│   ├── lines.json            # 字幕条目
│   ├── subs.ass              # 字幕文件
│   ├── filter_base.txt       # 时间线滤镜脚本
│   ├── timeline_report.json  # 吸附后切点、位移与慢放记录
│   ├── build_report.json     # 基片实测时长验收
│   ├── qa_report.json        # 交付前自动验收
│   └── base.mp4              # 无字幕无音轨的基片
├── images/raw/  images/c16/  # 出图原图 / 统一裁切到 1920x1080
├── clips/                    # 每镜一段 mp4
└── 成片.mp4
```

## 第 0 步：定规格，别猜

开工前必须问清三件事，缺一个就停下来问：

1. **画幅** 16:9 / 9:16 / 1:1 —— 决定所有出图与出视频的比例，中途改等于重做
2. **风格偏好** 用 `style_advisor.py` 给 3 个候选让用户选，**不要自己拍板**；此时只是候选，最终风格在导演视觉总纲确认后锁定
3. **规模** 全曲逐句，还是只做副歌？全曲逐句通常 30-45 镜，成本要提前说清

**不要要求用户预选具象物件、界面装置或“纯氛围”。**先由 AI 在导演阶段理解歌词并提出
视觉概念，再决定是否需要人物、实物、UI 或非具象表达。

导演总纲确认后风格不能中途换——换风格意味着 41 张图 + 41 段视频全部重做。
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

给 3 套候选 + 打分 + 理由 + 建议单镜时长与叠化时长。先作为导演构思的候选，
不要只凭风格名称直接批量出图；最终 `shot`、`fade` 和风格锚点随导演总纲一起确认。

### 像素风先锁子类型与动作合同

不要只写“像素风”。先确定投影、原生网格、角色素材框、脚点、整数缩放和动作实现方式；
星露谷式田园像素使用独立的 `stardew` 候选，横版情感叙事使用 `pixelstory`，
三者不要与街机横版 `pixel` 混用。

选择 `stardew` 时必读 [references/stardew-pixel.md](references/stardew-pixel.md)，并先完成
`out/pixel_spec.json`：

```bash
cp assets/pixel_spec.stardew.example.json out/pixel_spec.json
# 按实际分镜修改后，先做配置检查；这不代表图像已经合格
python scripts/pixel_spec.py check out/pixel_spec.json
```

硬约束：3/4 俯视而非横版或等距菱形；16×16 地图格、16×32 农夫型素材框、
脚点定位、独立前景遮挡；行走至少 3 个真实轮廓；工具动作有准备/接触/恢复和目标反馈；
世界层整数倍最近邻放大。高清图缩小、像素化滤镜和 zoompan 不能代替这些资产与动作。

选择 `pixelstory` 时必读 [references/pixel-narrative.md](references/pixel-narrative.md)，
使用 `assets/pixel_spec.pixelstory.example.json`。先写每镜 `story_state` 与
`state_change`，再写画面：选择 2–4 个状态通道，保留一个关键道具及其结果状态，
用开场与结算形成闭环。多人镜头必须明确距离/遮挡；关键手势和道具动作必须有真实姿态，
不能只给静态街景挂爱心和 SCORE。

### 第三种像素走法：procedural（不出图，用代码画）

上面两种都是「AI 出图 → 图生视频」。若画面**能用矩形和线描述出来**——像素场景、
UI 界面、文字卡、地图、HUD、数值——就不要出图，用 Python 直接画每一帧。
全片零张 AI 图、零次图生视频，成本为零，可以为了一个字晚 80ms 重渲十次，
且每一帧都能被脚本逐帧检查。

代价是开发时间：第一支最贵，第二支起几乎免费。只做一支片，AI 路线更快。
判断标准、四层结构、五个必踩的坑见
[references/procedural-pixel.md](references/procedural-pixel.md)；
可跑骨架在 `assets/procedural_skeleton/skeleton.py`（`python3 skeleton.py` 直接出三张图）。

选这条路时**跳过第 5、6 步**，第 7 步退化为「核对 scenes 首尾相接 + ffmpeg 封装」。

## 第 3 步：先把歌词的字搞对

**这是最容易翻车的一步。** 详见 [references/lyrics-accuracy.md](references/lyrics-accuracy.md)。

三条铁律：

1. **不要相信 ASR 的中文歌词**。演唱中的咬字、拖腔、和声会让识别结果面目全非
   （真实案例：「被我收得好好的」→「被我收远不尔斯坦」）。
2. **不要相信记忆**。歌名对得上不等于字对得上，必须联网核对至少两个权威来源
   （百度百科 / 搜狗百科 / 互动百科 / 正规歌词站），不一致的以多数派为准并记录分歧。
3. **中文歌词大约每 4-8 句就有 1 处错字**。逐字对着音频念一遍，别只看首尾。

ASR 唯一可靠的产出是**段落边界**，用它把歌词切成"组"，组内按字数比例分配时间。
可选分段器会安装独立依赖，并且只输出边界、不采用识别文本：

```bash
python -m pip install -r scripts/requirements-asr.txt
python scripts/asr_segments.py --audio song.mp3 --lyrics lyrics.txt -o out/groups.json
# 也可以完全人工写 groups.json（结构见 assets/groups.example.json）
python scripts/lyrics_timing.py --groups out/groups.json --beats out/beats.json \
    -o out/lines_timing.json
```

脚本会输出每句的 `s/字`，并**自动标出语速异常的行**——那通常意味着某个组边界估错了。

### 复唱段落必须做恒定偏移校验（最容易漏的一步）

流行歌的主歌/副歌通常走两遍。**同一句歌词在两遍里的出现时刻，差值必须是一个常数。**

如果按字数比例去分第二遍的组，误差会逐句累积：本案例里第二遍从 +1.2s 一路涨到 +2.8s，
表现为"从某一句开始字幕、音乐、画面全对不上"，而且越往后越严重。

校验方法（句号区间按歌曲实际结构填写，不要对半猜）：

```bash
python scripts/check_repeat.py --timing out/lines_timing.json \
    --first 1-18 --second 19-36
```

差值是常数（本案例 94.5s）才对。**发现逐句递增，就说明第二遍的组边界估早了**。
需要修正时加 `--fix-out out/lines_timing.fixed.json`，脚本会按
`第一遍 + 中位偏移` 重建第二遍；人工抽查后再替换，并重建整条字幕/时间线链。

更硬的校验方法见 [references/lyrics-accuracy.md](references/lyrics-accuracy.md) 的
"用 OCR 读原片歌词"一节。

## 第 3.5 步：AI 导演构思与视觉总纲

不要先列物件、地点或“每句配什么图”。先读 [references/director-storytelling.md](references/director-storytelling.md)，
综合校订歌词、`beats.json`、`structure.json`、风格候选和用户约束，完成两轮创作：

**第一轮：提出 2–3 套真正不同的视觉概念。**每套写清 logline、情绪弧线、视觉世界、
主体选择、关键场景、贯穿母题、节奏与转场规则，以及整首歌词的覆盖方式。差异必须来自
叙事视角和视觉机制，不是同一方案换色板。AI 主动设计角色、场景、物件和动作；
不强制用户先选物件，也不强制出现人物或爱情剧情。

**第二轮：按用户选定的概念展开 `director.json`。**必须包含：
- 主题与潜台词、至少 3 阶段情绪弧线、节奏弧线及音乐证据
- 视觉世界、角色功能或 `absence_strategy`、场景动作与可见变化
- 0–4 个核心母题及状态轨迹；没有实物时填写 `non_object_strategy`
- 转场的语义/情绪/节奏/视觉/空间连续性，以及角色、空间和风格连贯规则
- 每句歌词的 `visual_intent`、`change`、`scene_id` 与可选 `motif_ids`

```bash
# 脚本只生成空白结构；创意内容必须由 AI 根据歌曲完成，不能照抄示例
python scripts/director_plan.py scaffold --lyrics lyrics.txt --title "歌名" -o out/director.json
python scripts/director_plan.py check out/director.json --lyrics lyrics.txt
python scripts/director_plan.py review out/director.json --lyrics lyrics.txt -o out/director.md
```

先让用户确认 `director.md`，再展开 `shots.tsv`。`check` 只验证结构和覆盖，不替代
语义与审美评审；抽象歌词可改用心理空间、自然材料、身体局部或视觉规则，不能拼随机空镜。
需要量化 UI 时再选 `references/ui-narrative.md` 中的装置，不把界面装置当默认答案。

## 第 4 步：定分镜

从已确认的 `director.json` 展开 `out/shots.tsv`：每句先保留视觉意图和可见变化，
再确定场景、角色/物件动作、构图和转场，不得退化为逐句换地点或逐句换物件。
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

自检（此时只有 `lines_timing.json`，不要引用第 8 步才生成的 `lines.json`）：

```bash
python -c "
import json, csv
L=json.load(open('out/lines_timing.json'))
R=[r for r in csv.DictReader(open('out/shots.tsv',encoding='utf-8-sig'),delimiter='\t') if r['lyric'].strip()]
d=[abs(float(r['t0'])-l['start']) for r,l in zip(R,L)]
print('配词镜头数',len(R),'歌词句数',len(L),'切点最大偏差 %.4fs' % max(d))"
```

配词镜头数必须等于歌词句数，偏差大于 0.1s 就要返工。`build_base.py --grid-div 4`
会把切点吸到与歌词相同的 1/4 拍网格；吸附后的真实偏差由第 10 步
`qa_check.py` 使用 `timeline_report.json` 再验一次。

分镜数量参考：全曲逐句 = 歌词句数 + 前奏 1-3 镜 + 尾奏 0-2 镜。

### 出图前先过两道确认门

**Gate A：导演草稿。** 生成 `storyboard.md` 和逐镜 `manifest.json`：

```bash
python scripts/manifest.py init --shots out/shots.tsv --audio song.mp3 \
    --style cel --width 1920 --height 1080 -o out/manifest.json
```

先让用户确认 `director.md` 中的主题理解、情绪弧线、视觉世界和逐句覆盖，再确认参考图、
角色设计、分镜、字幕位置和成本；不要只让用户确认一个风格名称或一个具象物件。
像素项目还必须确认 `pixel_spec.json` 中的投影、网格、角色比例与动作合同。

**Gate B：试制。** 先做 2-3 个代表镜头（特写 / 中景 / 空景）并拼 10-15 秒样片，
确认画风、主体尺度、字幕位置、图生视频稳定性和 `REVEAL`，再批量做全曲。
`stardew` 试制至少包含一个完整步态和一个工具接触动作；只展示静态场景不算通过。
`pixelstory` 试制至少包含一个关键手势、一个多人距离构图和一个道具状态插页，
并让用户复述其理解的关系变化；只读出“像素游戏”而不能读出剧情，不算通过。
这两道门把"全片返工"降级为"两镜返工"。完整执行细则见
[references/production-playbook.md](references/production-playbook.md)。

## 第 5 步：出图

按 `director.json` 决定每镜的场景、角色、物件及动作，不调用预设物件清单。
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

**像素项目改走资产管线，不执行“每镜一张高清图”的默认做法。**先准备原生 tile、
方向性 sprite、前景遮挡与局部环境动画层；AI 只探索构图和姿态，入库前必须清理到
原生网格并按脚点配准。`stardew` 使用 16×16 地图格、16×32 农夫型素材框和独立
`pixel_spec.json`，详细规则与提示词见 [references/stardew-pixel.md](references/stardew-pixel.md)。
`pixelstory` 还需先完成场景复用矩阵、2–4 个状态通道、多人距离构图和关键道具插页，
见 [references/pixel-narrative.md](references/pixel-narrative.md)。

**`procedural` 项目在这一步不出图。** 改做三件事：写 `art.py` 的 sprite 原语
（字符网格 + 参数化矩形）、把场景拼成一条 `world` 长卷、写 `storyboard.json`
让渲染器按 `kind` 分发。产出是代码而不是图片，样张用渲染器的 `--still <t>` 单帧导出。
规则与坑见 [references/procedural-pixel.md](references/procedural-pixel.md)。

每镜立即登记提示词与状态，便于只重做该镜：

```bash
python scripts/manifest.py update -m out/manifest.json --shot s01 \
    --status image_done --image images/c16/s01.png --image-prompt "S01 ..."
```

## 第 6 步：图生视频

**`procedural` 项目跳过这一步**——运动是周期函数（呼吸、眨眼、波纹、镜头横移），
不是生成出来的。要让某个动作更有生命力，改函数参数，不要改提示词。

每镜一段（AI 路线）。要点：

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
- **像素动作优先显式 sprite 序列，其次关键姿态驱动，最后才是纯文本生成整段。**
  标注走、跑、砍、锄、浇、钓的镜头，若主要运动只有 zoompan、整体漂移或上下浮动，
  直接判失败并退回 sprite 合成，不用更多提示词掩盖
- 额度会用尽（HTTP 429 `code 14018`）。普通镜头可用静帧 + `zoompan` 缓推兜底，
  但那一镜没有真实运动，必须在 manifest 和交付时主动说明；**像素动作镜不接受这种兜底**，
  应改用已验收的姿态帧或保持静态待机并重排动作

完成后登记来源；`still` 会在 QA 与交付报告中单独列出：

```bash
python scripts/manifest.py update -m out/manifest.json --shot s01 \
    --status done --source i2v --credits 93 --video-prompt "Animate ..."
# 静帧兜底时改为 --source still --note "429，zoompan 兜底"
```

## 第 7 步：卡拍剪时间线

**`procedural` 项目没有「一镜一段 clip」。** 渲染器按 `storyboard.json` 的
`start/end` 直接逐帧出图，切点由数据决定，不存在拼接误差、时长漂移和尾奏填充。
这一整步退化成两件事：确认 `scenes` 首尾相接、没有空隙与重叠；
用 ffmpeg 把帧序列和音轨封成 mp4。下面这套（AI 路线）用不上。

```bash
python scripts/build_base.py --shots out/shots.tsv --clips-dir clips \
    --beats out/beats.json --audio song.mp3 --fade 0.45 \
    --width 1920 --height 1080 \
    --fill-ids s02,s10,s04,s27 -o out/base.mp4
```

它做的事：

1. 取每镜起点当切点，**吸附到 1/4 拍网格**（`--grid-div 4`，和歌词同一网格）
2. 叠化中点压在切点上（`xfade offset = 切点 − fade/2`）
3. **逐段探测素材真实时长**并按需慢放。不要写死 6.04s——某段只有 5.04s 时，
   `trim=duration` 会提前结束，xfade 链在那里断掉，后续镜头被静默丢弃
   （本案例里这个 bug 让成片短了 26 秒）
4. 尾奏（歌词唱完之后那几十秒）用 `--fill-ids` 指定的镜头循环填满。
   填充镜头本身要够长，否则会被大幅慢放；默认超过 1.3 倍会中止，
   需要拆镜或换素材，不要用 `--max-slow 0` 掩盖问题
5. xfade 链末尾先补帧再裁到音频时长，修复旧版固定少 `fade/2` 的问题；
   实测时长写入 `out/build_report.json`，差超过 0.1s 会失败

`--audio` 会自动读取总时长；只有明确需要覆盖时才手填 `--total`。

## 第 8 步：逐字弹字幕

```bash
python scripts/build_lines.py --timing out/lines_timing.json --shots out/shots.tsv \
    --cards out/cards.json -o out/lines.json
python scripts/make_subs.py --lines out/lines.json --beats out/beats.json \
    --motifs --width 1920 --height 1080 -o out/subs.ass
```

竖屏用 `--width 1080 --height 1920` 重新生成 ASS，脚本会重算字号、行位置、
字距与装饰尺寸；不要把 16:9 的 ASS 直接拉伸到 9:16。脚本现在打印
"首字相对句起点"和"末字落点/句长"，它们替代旧版恒真的网格偏移自检。

`--motifs` 会按歌词意象在句子左侧挂矢量小图案（气泡/爱心/气球/太阳/票根…），
不需要图片素材。细节与扩展方法见
[references/subtitle-styling.md](references/subtitle-styling.md) 的"装饰层"一节。

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
    --out "成片.mp4"
```

（或者按 [references/ffmpeg-recipes.md](references/ffmpeg-recipes.md) 手写滤镜串）

关键顺序：`delogo → eq → vignette → ass → fade → format`，音频侧
`loudnorm → afade → aresample=44100`。`loudnorm` 会把采样率升到 96k，
**必须**补一个 `aresample` 回到 44.1k。

验收线：`mean_volume` 约 −14~−15dB，`max_volume` ≤ −1.0dB。
`--delogo` 现在默认 `off`；只有确认水印位置后才显式传 `x:y:w:h`，
不要对无水印素材默认抹一块。封面单独生成：

```bash
python scripts/make_cover.py --image images/c16/s12.png \
    --title "歌名" --artist "歌手" --width 1920 --height 1080 --out out/cover.png
```

## 第 10 步：交付前自查

先跑自动验收与视觉联系表：

```bash
python scripts/director_plan.py check out/director.json --lyrics lyrics.txt
python scripts/qa_check.py --project . --audio song.mp3 --final "成片.mp4"
python scripts/contact_sheet.py --images 'images/c16/s*.png' \
    --out out/qa/style_sheet.png --cols 7
python scripts/contact_sheet.py --video "成片.mp4" \
    --out out/qa/film_sheet.png --count 12 --cols 4
python scripts/manifest.py report -m out/manifest.json
```

像素项目追加以下检查；`check` 只验配置，两个 `audit` 才检查真实图像：

```bash
python scripts/pixel_spec.py check out/pixel_spec.json
python scripts/pixel_spec.py audit-sprites images/farmer_walk.png \
    --frame-width 16 --frame-height 32 --cycle 0,1,0,2 --min-distinct 3
# 在光照、HUD、字幕和视频编码前检查无损世界素材层
python scripts/pixel_spec.py audit-scale images/world_layer.png --scale 4
# pixelstory 普通行走至少 2 个轮廓；关键手势/道具动作另按合同提高要求
python scripts/pixel_spec.py audit-sprites images/hero_walk.png \
    --frame-width 24 --frame-height 32 --cycle 0,1,0,1 --min-distinct 2
```

`procedural` 项目追加以下四项；前三项只有代码渲染做得到，AI 路线跳过：

- [ ] **音画同步**：成片音轨与源音频的 8kHz 包络做互相关，`lag == 0` 且归一化相关 > 0.99
      （lag 不为 0 是 ffmpeg 有 offset；相关 < 0.95 说明混音改过动态）
- [ ] **帧格对齐**：所有抽帧时间点落在 `n / fps` 上。
      `19.25 × 30 = 577.5` 会抽到 577 号帧，造出 17ms 的假差异，然后你去修一个不存在的问题
- [ ] **半透明**：全部走独立图层 + `alpha_composite`，没有一整块死色
- [ ] **视差归属**：镜头横移时，人物与长椅/门/桌子的相对位置不变

**机械项**（由 `qa_check.py` 判定；FAIL 必须处理）

- [ ] 基片与目标时长差 < 0.1s；成片与音频时长差 < 0.1s
- [ ] 切点与歌词起点最大偏差 < 0.1s（优先使用吸附后的真实切点）
- [ ] 复唱段落两遍的偏移是常数（用 `check_repeat.py`，不要对半猜）
- [ ] 相邻歌词字幕不重叠，没有标记完成却缺失的素材
- [ ] 音量：`mean` 约 −14~−15dB，`max` ≤ −1.0dB
- [ ] 吸附位移只看 INFO 报告，不再把"对已吸附网格再算距离"当验收

**目视项**（必须真的看图，不能靠推断）

- [ ] 全片风格总览：逐格扫 `out/qa/style_sheet.png`，没有风格孤岛
- [ ] 逐句抽查 3 个时间点，字幕、唱词、画面三者一致
- [ ] 字幕没有压住人脸（重点看特写镜）
- [ ] 片头歌名、歌手名完整出现且停留 ≥ 3s，不被淡出吃掉
- [ ] 片尾署名整块出现，不被画面淡出切掉
- [ ] 抽帧看四角没有残留水印
- [ ] `stardew` 没有横版化、等距菱形化或高清图马赛克化；脚点、遮挡和连续通路正确
- [ ] 行走有真实左右腿交替；工具有接触动作与目标反馈；待机不漂浮、背景不整体扭动
- [ ] 季节/时间/天气与植被、作物、装饰一致；夜景灯具和窗户有局部光照响应
- [ ] `pixelstory` 的 2–4 个状态通道与人物行为一致，复唱有状态推进，不是只换背景
- [ ] 多人镜头能读出距离/遮挡；关键道具插页有结果；开场与结算共享同一套叙事规则
- [ ] 全片能回扣导演阐述和情绪弧线；每句有可见变化，没有机械堆砌物件或随机空镜
- [ ] 转场有语义/情绪/节奏/视觉/空间连续性；角色、物件、色板和空间逻辑前后一致

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
开工前把量级告诉用户，别做完才说。实际消耗逐镜写进 manifest，
交付时用 `manifest.py report` 对比预估，并列出静帧兜底与复用镜头。

## 零额度回归

每次改动脚本后，先运行 `python examples/make_demo.py --out out/demo`。
它用程序生成音频和画面，完整验证分镜、字幕、渲染、封面、联系表与 QA，
不消耗任何出图/视频额度。
