# 排错手册

按"现象 → 原因 → 处理"排列。都是实际踩过的。

## 时间线

### 字幕/画面整体错位，越到后面偏得越多

**原因**：`--total` 与音频真实时长不一致，或者某段素材时长探测错了。

**处理**：
```bash
ffmpeg -hide_banner -i final.mp4 2>&1 | grep Duration
ffmpeg -hide_banner -i song.mp3  2>&1 | grep Duration
```
两者差应 < 0.1s。`build_base.py` 会自动探测每段素材，如果报"缺少素材"就是路径问题。

### 某一镜之后时间线全乱

**原因**：那一段素材比「镜头时长 + 叠化」短。`trim=duration=X` 在素材不够时
只输出已有部分，导致后续 xfade 的 offset 全部错位。

**处理**：`build_base.py` 会自动慢放补齐并打印警告。若仍异常，检查是不是
某段素材只有 5.04s 而镜头设置了 6.5s。

### xfade 报错 `First input link ... parameters ... do not match`

**原因**：两路输入的分辨率、像素格式、时基不一致。

**处理**：每路都要有完整的规整链：
```
trim → setpts=PTS-STARTPTS → fps=24 → format=yuv420p → settb=AVTB
```
少任何一个都会在长链的某处炸掉。报错不会告诉你是哪一段，需要逐段二分排查。

### 切点不在拍点上

**检查**：`build_base.py` 会打印每个切点距拍点的偏移，应在 ±0.005s 内。

**原因**：分镜表的 `t1` 与前一行 `t0` 不连续（中间有缝或重叠）。
脚本只取每行 `t0` 当切点，所以 `t1` 只用于判断首尾。

## 字幕

### 字体不对，变成默认黑体，且不报错

**原因**：`fontsdir` 用了相对路径。这是最隐蔽的坑——ffmpeg 不报错，直接退回默认字体。

**处理**：改成绝对路径。
```bash
ass=subs.ass:fontsdir='/abs/path/to/fonts'
```
`make_subs.py` 会在结尾直接打印可粘贴的正确滤镜串。

### 整句字幕只剩最后一两个字

**原因**：`CHUNK_MAX` 太小，句子被拆成多段轮流显示。

**处理**：`CHUNK_MAX` ≥ 最长句字数。中文歌词设 18 基本够。

### 每个字各占一块底色，整句像一排方块

**原因**：`BorderStyle=3`（色块）。每字独立事件 + 色块底 = 一排方块。

**处理**：改 `--theme cut`（`BorderStyle=1` 描边）。

### 片尾署名看不清就被画面淡出吃掉

**原因**：署名用了逐字弹出。三个字按拍点要 2.2 秒才齐。
或者画面淡出开始得太早。

**处理**：
1. 署名条目加 `"title": true`（整块出现）
2. 画面淡出延后：`fade=t=out:st=X` 的 X 要晚于署名出现时刻 1.5s 以上

### 标题压住人脸

**原因**：全局行高（`ROW_Y` / `TROW_Y`）固定，但每个镜头的构图不同。

**处理**：给标题条目单独指定 `"y"`。不要改全局常量——那会影响所有字幕。

### 字幕行位置全片一样，没有跟着镜头变

**原因**：`lines.json` 里所有条目 `place` 都是同一个值。

**处理**：确认 `build_lines.py` 读到了 `shots.tsv` 的 `place` 列，
并且歌词时间确实跨了多个镜头。检查方法：

```bash
python -c "
import json,collections
a=json.load(open('out/lines.json'))
print(collections.Counter(x.get('place') for x in a))"
```
应该至少有两个不同的值。

## 歌词

### ASR 出来的歌词是乱码一样的字

正常。演唱识别就是这么差，别试图调参数修好它。改用「人工写词 + ASR 边界当锚点」。

### 歌词改了字，字幕时间全乱了

**原因**：时间轴按字数比例分配，字数变了分配就变。

**处理**：正常，重新跑 `lyrics_timing.py → build_lines.py → make_subs.py` 即可。
重新渲染前必须重建整条链，不能只重跑字幕脚本。

### 某几句显示特别快或特别慢

**原因**：对应的组边界估错了（把两句并成一组，或把一句拆成两组）。

**处理**：`lyrics_timing.py` 会打印 `s/字` 并标出偏离中位数 45% 以上的行，
直接改 `groups.json` 里那几组的时间或行数。

## 出图 / 出视频

### 并发出图，后一张覆盖了前一张

**原因**：出图工具按提示词前缀命名文件，前缀相同就会互相覆盖。

**处理**：每张提示词加镜头号前缀 `S01 …`、`S02 …`。

### 出图工具的 output_dir 不生效

已知行为。产物会落到默认目录，自己去那里找。不要依赖 `output_dir` 参数。

### 图生视频报 `HTTP 429 code 14018 额度已用尽`

**处理**：
1. 先确认是不是真用尽（等一会重试一次）
2. 兜底：静帧 + `zoompan` 缓推（见 ffmpeg-recipes.md 第 3 节）
3. **交付时主动说明**哪几镜是静帧替代的

### 图生视频提示 `socket hang up`

偶发网络问题，直接重试一次通常就成。

### 生成的视频时长不是 6 秒

同一个模型可能返回 5.04s 或 6.04s（24fps 下分别是 121 / 145 帧）。
不要硬编码 6.04，用 `build_base.py` 自动探测。

### 人物在不同镜头里长得不一样

**原因**：没用角色设计图做图生图的锚。

**处理**：先出一张角色设计图，后续每张都以它为参考图，提示词明确写
"Keep the SAME characters with IDENTICAL designs. Now place them in a NEW scene"。
`input_fidelity` 不能太高，否则模型拒绝换场景。

## 音频

### 成片音量比原曲小很多

**原因**：`loudnorm` 的参数或后续处理把它压下去了。

**检查**：
```bash
ffmpeg -i final.mp4 -af volumedetect -vn -f null - 2>&1 | grep mean_volume
```
目标 −14 ~ −15dB。低于 −18 说明有问题。

### 音频文件体积异常大

**原因**：`loudnorm` 把采样率升到 96kHz 后没转回来。

**处理**：`loudnorm` 后面必须跟 `aresample=44100`。

### 音画不同步，音频比画面长

**原因**：`-t` 参数与 `atrim` 的时长不一致。

**处理**：视频用 `-t <总时长>`，音频用 `atrim=0:<总时长>`，两个值必须字面相同。

## 环境

### `ffprobe: command not found`

很多精简安装的 ffmpeg 不带 ffprobe。用 `ffmpeg -i` 读 stderr，本 skill 的脚本
全部按这个方式实现。

### 复杂滤镜命令报 `decisionRecord missing actual resource subject`

某些沙箱/权限层在遇到超长或含嵌套引号的命令时会拒绝执行。

**处理**：把命令拆成单条、把变量内联成绝对路径、把滤镜写进
`-filter_complex_script` 文件而不是 `-filter_complex "..."`。
本 skill 的脚本全部走文件方式，就是为了绕开这个。

### TSV 读取报 `KeyError: 'id'`

**原因**：`shots.tsv` 带 UTF-8 BOM（Excel / Numbers 另存时常有）。

**处理**：用 `encoding="utf-8-sig"` 读。本 skill 的脚本已经这么做了。
