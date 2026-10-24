# music-mv 增强记录

> 基线：`wangyaruo/music-mv@main`（2026-10-21）
> 分支：`enhance/production-playbook`
> 日期：2026-10-24

## 目标

保留原有的逐字卡拍、中文歌词校订、字幕与分镜联动，不改写技术路线。
吸收同类优秀项目的生产方法：导演草稿与试制确认、逐镜生产台账、自动 QA 与联系表、
多画幅重排版、零额度可重复 demo。方法借鉴，不复制其他项目代码。

## 一、修复的实测问题

### 时间线

- 修复 xfade 链输出固定少 `fade/2`：链尾增加 `tpad` + `trim=duration=<total>`。
- `build_base.py` 新增实测时长验收，超过 0.1s 非零退出，并写 `build_report.json`。
- 吸附后出现零时长/过短镜头时立即报错，指出镜头号与最短限制，不再生成坏滤镜。
- `--grid-div` 默认值统一为 4，与文档及歌词网格一致。
- 新增 `--max-slow`（默认 1.3），超过时要求拆镜或换素材；`0` 为显式关闭限制。
- `--audio` 可自动探测总时长，不再必须手填 `--total`。
- `--width/--height` 可统一分辨率、等比缩放并补边。

### 字幕与合成

- `make_subs.py` 新增 `--width/--height`：重算 PlayRes、字号、行位置、字距、居中与装饰尺寸。
- 长句/长标题超过 92% 可用宽度时自动收缩，避免竖屏出框。
- 旧的"网格最大偏离"自检替换为真实指标：首字相对句起点、末字落点/句长。
- `mix_final.py` 的 `delogo` 默认改为 `off`，只有显式给坐标才处理水印。
- ASS 路径增加滤镜级转义；`--fps` 参数化。

## 二、新增生产能力

| 文件 | 用途 |
|---|---|
| `scripts/manifest.py` | 从分镜生成导演草稿；登记每镜提示词、来源、状态、成本；列出静帧兜底与缺失素材 |
| `scripts/qa_check.py` | 时长、切点/歌词对齐、字幕重叠、长句、素材缺失、响度等自动验收 |
| `scripts/check_repeat.py` | 显式指定两遍句区间，校验复唱恒定偏移；可生成修正版时间轴 |
| `scripts/contact_sheet.py` | 分镜风格总览与成片抽帧联系表；缩略图按首帧比例自适应 |
| `scripts/make_cover.py` | 从分镜图或成片抽帧生成横竖屏封面 |
| `scripts/asr_segments.py` | 可选 faster-whisper 分段，只取段落边界，不采用 ASR 歌词文本 |
| `references/production-playbook.md` | 两道确认门、manifest、QA、多画幅与交付纪律 |
| `examples/make_demo.py` | 程序生成音频与画面，零 AI 额度跑通完整工具链，可重复执行 |
| `tests/test_pipeline.py` | 时间线、ASR 分配、复唱、manifest、竖屏与标题出框回归 |
| `.github/workflows/ci.yml` | 编译、单元测试、完整 demo 与产物检查 |
| `docs/images/` | README 可展示的 demo 联系表与封面 |

## 三、验证结果

### 单元测试

```text
Ran 9 tests — OK
```

覆盖：零时长镜头拒绝、末尾补帧裁齐、可选分辨率链、短素材慢放、
ASR 边界分配、复唱偏移、manifest 镜头命名、竖屏 PlayRes、长标题不出框。

### 时间线回归

同一组 3 镜头素材，`--total 6`：

| fade | 修复前 | 修复后 |
|---|---|---|
| 0.30 | 5.88s | 6.000s |
| 0.60 | 5.75s | 6.000s |
| 1.00 | 5.54s | 6.000s |

两个相近切点吸到同一格时，旧版生成 0 时长镜头；新版明确报错并非零退出。

### 真实示例的复唱回归

用仓库原有 `groups.example.json` 生成时间轴后，`check_repeat.py` 检出偏移极差
**3.560s** 并判 FAIL；生成修正版后，与真实分镜的切点最大偏差从 **2.783s**
降至 **0.074s**。修正结果保存为 `assets/lines_timing.fixed.example.json`，
使用方法见 `assets/README.md`。

### 端到端 demo

以下两条均在本地完整跑通，且可重复执行：

```bash
python examples/make_demo.py --out out/demo
python examples/make_demo.py --out out/demo_916 --width 360 --height 640
```

横屏与竖屏 QA 均为 **9 项 PASS、2 项 INFO、0 项 FAIL/WARN**：

- 基片 12.000s / 目标 12.000s；
- 成片 12.000s / 音频 12.000s；
- 切点与歌词起点最大偏差 0.000s；
- 无字幕重叠、无缺失素材、无未完成镜头；
- 响度 mean −13.6dB、max −2.7dB。

## 四、文档同步

- `SKILL.md`：把草稿确认、试制、manifest、QA、封面、多画幅纳入实际步骤，
  不再只是独立脚本。
- `README.md`：新增 demo、完整命令、脚本清单、已知限制与版权合规说明。
- `pipeline.md`：补充 xfade 时长补偿的数学原因。
- `subtitle-styling.md`：说明 1080p 基准与多分辨率换算。
- `troubleshooting.md`：移除恒真型网格验收口径。

## 五、尚未假装完成的事项

- 13 种视觉风格并不等于 13 套字幕主题；当前字幕主题仍只有 `cut` / `box`，
  README 已明确标注，避免过度承诺。
- `beat_sync.py` 的 BPM 估计仍可能出现半速/倍速，生产前必须人工核对；
  本次未加入新的 BPM 模型。
- `asr_segments.py` 的分配逻辑已做单元测试，但本次未下载 Whisper 模型做真实音频识别；
  它属于可选依赖，输出仍必须人工核对。
- 本次使用程序合成素材和仓库示例数据验证，没有消耗真实 AI 出图/视频额度。
- GitHub 仓库描述、topics、社交预览图需要在网页端设置，不在 Git 补丁范围内。

## 六、建议推送方式

```bash
git add .
git commit -m "Add production playbook, QA, multi-aspect rendering and reproducible demo"
git push origin enhance/production-playbook
```

推送后运行一次 GitHub Actions；再在仓库网页补充 description、topics 与一张真实成片封面。
