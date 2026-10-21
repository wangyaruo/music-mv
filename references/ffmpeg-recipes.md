# FFmpeg 配方

MV 制作中用到的全部关键滤镜写法。每条都经过实测，可以直接抄。

环境提醒：很多机器上**没有 ffprobe**。读时长、读分辨率一律用
`ffmpeg -hide_banner -i file 2>&1 | grep Duration`。

## 1. 搭 xfade 时间线

`xfade` 的关键是 `offset`：它是**前一段开始淡出的时刻**，不是切点。

```
offset = 切点 − fade/2
```

因为叠化从 `offset` 开始、持续 `fade` 秒，中点才落在切点上，视觉上"切"的感觉
正好压住拍子。

每一路输入必须先规整：

```
[0:v]trim=duration=6.49,setpts=PTS-STARTPTS,fps=24,format=yuv420p,settb=AVTB[v1]
```

四点必须都写：

- `trim` 裁到需要的长度
- `setpts=PTS-STARTPTS` 归零时间戳，否则 xfade 的 offset 全错
- `fps=24` 统一帧率
- `settb=AVTB` 统一时基 —— 不写会在长链上累积误差

**顺序不能换**：`trim` 会重置 `frame_rate`，所以 `fps` 必须放在 `trim` 之后。

拼接：

```
[v1][v2]xfade=transition=fade:duration=0.45:offset=6.05[x1];
[x1][v3]xfade=transition=fade:duration=0.45:offset=12.10[out]
```

## 2. 素材太短：慢放补齐

图生视频给的时长不稳定（5.04s / 6.04s），而镜头可能需要 6.5s。

```bash
# factor = 需要的时长 / 素材时长
setpts=1.107*PTS,minterpolate=fps=24:mi_mode=blend,trim=duration=5.58
```

`minterpolate` 的 `mi_mode=blend` 是帧混合，比直接丢帧平滑。
10% 以内的慢放在慢镜头画面上几乎看不出来；超过 30% 会明显"拖"。

**更好的办法**：让单个镜头不超过素材时长，从分镜阶段就控制住。

## 3. 用静帧兜底（视频额度用尽时）

图生视频失败时，用静帧 + 缓慢推进撑住时间线：

```bash
ffmpeg -y -loop 1 -i still.png \
  -vf "scale=2880:-1,zoompan=z='min(1.0+0.0009*on,1.13)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=145:s=1920x1080:fps=24,format=yuv420p" \
  -frames:v 145 -c:v libx264 -crf 16 -pix_fmt yuv420p -an clip.mp4
```

要点：

- 先把图放大（`scale=2880`）再 `zoompan`，否则推进会糊
- `z` 从 1.0 到 1.13，`d=145` 帧（6.04s @ 24fps），缓推幅度 13% 以内
- **交付时必须说明这一镜没有真实运动**，不要装作是生成的

## 4. 去 AI 水印

生成图常在左上角带 "AI生成" 标记，位置约 `x=4,y=6,w=134,h=62`。

```bash
delogo=x=4:y=6:w=134:h=62:show=0
```

定位方法：

```bash
# 放大左上角 260x110，叠网格看边界
ffmpeg -i img.png -vf "crop=260:110:0:0,scale=1040:-1,drawgrid=w=40:h=40:t=1:c=red@0.8" corner.png
```

`delogo` 必须放在调色之前，否则色偏会让插值痕迹更明显。

## 5. 调色与暗角

```bash
eq=contrast=1.04:saturation=1.06,vignette=a=PI/9
```

- `contrast` 1.03-1.06：轻微提对比，暗部不发灰
- `saturation` 1.05-1.08：动画画面容易发灰，加一点饱和度
- `vignette=a=PI/9`：约 20° 的暗角，把注意力收到画面中心。
  `PI/5` 太重，`PI/12` 几乎看不出

## 6. 叠字幕

```bash
ass=subs.ass:fontsdir='/absolute/path/to/fonts'
```

`fontsdir` 必须是绝对路径。相对路径不报错，但字体会静默退回默认黑体。

`ass` 要在 `fade` **之前**，这样淡出时字幕跟着一起暗。

## 7. 响度标准化

```bash
loudnorm=I=-14:TP=-1.0:LRA=11,aresample=44100
```

- `I=-14`：流媒体常用目标（YouTube/Spotify 约 −14 LUFS）
- `TP=-1.0`：真峰值上限，留 1dB 余量防止转码削波
- `LRA=11`：响度范围，流行歌合适

**`loudnorm` 会把采样率升到 96kHz**，必须补 `aresample=44100` 回到常规采样率，
否则输出文件体积翻倍且部分播放器不兼容。

验收：

```bash
ffmpeg -i final.mp4 -af volumedetect -vn -f null - 2>&1 | grep -E "mean_volume|max_volume"
# 期望 mean ≈ -14~-15 dB，max ≤ -1.0 dB
```

## 8. 首尾淡入淡出

```bash
fade=t=in:st=0:d=1.2,fade=t=out:st=252.5:d=3.1
```

- 淡入 1.2s：给片头标题卡留出浮现时间
- 淡出 3.1s：`st` 要**晚于**片尾署名出现的时刻，否则署名还没读完画面就黑了

配套音频侧：

```bash
afade=t=in:st=0:d=0.8,afade=t=out:st=251.2:d=4.2
```

音频淡出要比画面**长**一点，听起来才自然（画面先暗，声音最后收）。

## 9. 抽帧验收

```bash
# 单帧
ffmpeg -ss 100 -i final.mp4 -frames:v 1 check.png

# 从 247s 起连抽 8 秒做片尾检查
ffmpeg -ss 247 -i final.mp4 -frames:v 192 -an -c:v libx264 -crf 20 end.mp4
```

**注意**：`-ss` 放在 `-i` 前面是输入 seek，时间戳会归零。
此时叠加带绝对时间轴的 ASS 字幕会"什么都没显示"。

两种解法：

```bash
# 方案一：把时间戳补回去（快）
ffmpeg -ss 247 -i base.mp4 -vf "setpts=PTS+247/TB,ass=subs.ass" -frames:v 1 out.png

# 方案二：输出 seek（慢，要解码前面的全部内容）
ffmpeg -i base.mp4 -ss 247 -frames:v 1 out.png
```

## 10. 读取时长（无 ffprobe）

```bash
ffmpeg -hide_banner -i file.mp4 2>&1 | grep -E "Duration|Stream #"
```

Python 里：

```python
import re, subprocess
p = subprocess.run(["ffmpeg", "-hide_banner", "-i", path],
                   capture_output=True, text=True)
m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr)
```
