# 生产手册：把"会做一镜"变成"能稳定交付整片"

本 skill 原有的优势是逐字卡拍、中文歌词校订、字幕与分镜联动。本手册补上同类优秀项目普遍具备、但原仓库缺失的生产机制。**以下是方法借鉴，没有复制其他项目代码。**

## 一、两道确认门，避免全片返工

### Gate A：导演草稿确认（在出第一张分镜图之前）

```bash
python scripts/manifest.py init --shots out/shots.tsv --audio song.mp3 \
  --style cel --width 1920 --height 1080 -o out/manifest.json
```

同时生成：

- `out/storyboard.md`：画幅、风格、镜头表、成本、确认清单。
- `out/manifest.json`：后续所有生成与验收的生产台账。

必须让用户确认的不只是"风格名称"，而是：**参考图、角色设计、分镜、字幕位置、成本量级**。风格名称本身无法防止"做完后说不好看"。

### Gate B：试制确认（在做完 40 镜之前）

先做 2–3 个代表镜头：一个特写、一个中景、一个空景；拼 10–15 秒样片并叠上字幕。确认以下问题后再批量生产：

- 人物设计与画风是否稳定；
- 主体尺度是否足够大，字幕是否有位置；
- 图生视频是否换衣服、推镜是否可接受；
- 逐字字幕的 `REVEAL` 是否适合这首歌。

试制的意义是把"全片返工"改成"两镜返工"。`stardew` 试制还必须包含完整步态与
工具接触动作，并通过 `pixel_spec.py` 的配置、sprite 轮廓和整数缩放检查；
只确认静态场景，不能证明像素动画路线可行。`pixelstory` 还要验证陌生观众能否
读出状态变化和人物距离，并检查关键道具插页与结尾结算是否属于同一套规则。

## 二、逐镜 manifest：可复现、可续做、可交代

每镜完成生成后立即登记，不要等到最后凭记忆补：

```bash
python scripts/manifest.py update -m out/manifest.json --shot s01 \
  --status done --source i2v --credits 93 \
  --image-prompt "S01 ..." --video-prompt "Animate ..."
```

静帧兜底也必须登记：

```bash
python scripts/manifest.py update -m out/manifest.json --shot s02 \
  --status done --source still --note "429，静帧 zoompan 兜底"
```

交付前：

```bash
python scripts/manifest.py report -m out/manifest.json
```

它会列出未完成镜头、缺失素材、实际成本、以及**必须主动告诉用户的静帧镜头**。`source` 只有四种：`pending / i2v / still / reuse`，不要用自由文本，方便 QA 汇总。

## 三、自动 QA：只验收可能失败的指标

```bash
python scripts/qa_check.py --project . --audio song.mp3 --final 成片.mp4
```

硬失败项：

- 基片与目标时长差 > 0.1s；
- 成片与音频时长差 > 0.1s；
- 切点与歌词起点最大偏差 > 0.1s；
- 相邻歌词字幕重叠；
- manifest 标记完成但素材缺失。

警告项：长句可能拆段、字幕位置全片单一、未完成镜头、响度偏离参考区间。

**不要把"对已吸附网格再计算网格距离"当验收。**那类指标在数学上恒真，无法发现错误。本 skill 现在把吸附位移列为 INFO，把真正可能失败的"切点 vs 歌词起点"列为验收。

复唱段落单独校验，不再对半猜：

```bash
python scripts/check_repeat.py --timing out/lines_timing.json \
  --first 1-18 --second 19-36
```

需要修正时加 `--fix-out out/lines_timing.fixed.json`。脚本以"第一遍 + 中位偏移"重建第二遍，写新文件，人工抽查后再替换。

## 四、视觉 QA：风格总览 + 成片联系表

```bash
python scripts/contact_sheet.py --images 'images/c16/s*.png' \
  --out out/qa/style_sheet.png --cols 7
python scripts/contact_sheet.py --video 成片.mp4 \
  --out out/qa/film_sheet.png --count 12 --cols 4
```

第一张看风格孤岛、人物一致性、色带；第二张看字幕压脸、逐字出字、片头片尾、黑帧与转场。抽帧取各等分区间中点，避开首尾淡入淡出。

## 五、多画幅：重排版，不拉伸

```bash
python scripts/build_base.py ... --width 1080 --height 1920
python scripts/make_subs.py ... --width 1080 --height 1920 -o out/subs_916.ass
```

- `build_base.py` 会等比缩放并补边，统一分辨率与 SAR。
- `make_subs.py` 会重算 PlayRes、行位置、字号、字距、装饰图案尺寸与居中坐标；
  长句或长标题超过 92% 可用宽度时自动收缩，避免出框。
- 横屏与竖屏要分别生成 ASS；不要拿 1920×1080 的字幕直接压到 1080×1920 上。
- 分镜阶段的 `place` 仍要按各画幅实际构图确认，不能机械复用。

## 六、封面与零额度回归

```bash
python scripts/make_cover.py --image images/c16/s12.png \
  --title "歌名" --artist "歌手" --out out/cover.png
python examples/make_demo.py --out out/demo
```

demo 用程序生成音频与画面，不调用任何 AI 服务，完整跑通分镜、字幕、时间线、混音、封面、联系表、manifest 与 QA。修改脚本后先跑它，再把改动用于真实歌曲。

## 七、交付说明必须包含

1. 成片、封面、QA 报告、联系表；
2. 实际时长与音频时长差；
3. 静帧兜底与复用镜头清单；
4. 实际成本与预估成本的差异；
5. 歌词多源核对的分歧点；
6. 音乐、歌词与素材的授权边界。去除 AI 平台标识前，先确认该平台服务条款允许。
