# 画风锁定：从设计稿到 40 镜不跑偏

一支 MV 有 30–40 个镜头。只要有一镜的画风和其他不一样，观众立刻出戏——
不是"稍微有点不协调"，是"这几秒换了个片"。

本文是把 41 镜全片画风做统一的完整方法，以及所有踩过的坑。

## 一、风格必须在出图前一次定死

返工成本 = 全片成本。

本 skill 的基准案例里，第一版选了黏土定格，41 张图 + 41 段视频做完，
被一句"这种不好看"全部推翻，重做成日系赛璐璐。等于付了两倍钱。

所以：**出第一张分镜图之前，必须让用户看到并确认 3 个候选风格**。
用 `style_advisor.py` 出候选，给参考图，让用户挑。挑完写进 `shots.tsv` 的
`scene` 里作为固定前缀，后面所有镜头照抄。

## 二、角色设计图是唯一的人物锚

第一张图不是分镜，是**角色设计图**：正面、侧面、背面，全身，纯色背景，
两人对照。这张图不进成片，只做参考。

后续每一张分镜图都以它作 `image1` 做图生图，提示词写明：

```
Keep the SAME two characters with IDENTICAL designs as the reference sheet:
<用文字复述关键特征>
```

**文字复述不能省**。只给参考图而不描述，模型可能只继承"两个小孩"这个抽象概念。
必须把可辨识特征写死：

- 女孩：栗棕色齐耳短发、铁锈红背带裙 + 白色泡泡袖衬衫
- 男孩：凌乱黑发、灰蓝色 T 恤、深色短裤、蓝色球鞋

`input_fidelity` 用 low / medium。调高会让模型死守原图、拒绝换场景。

## 三、提示词的三段式

```
[镜头号 + 画风声明] + [角色锁定] + [NEW scene 描述] + [材质/绘画约束]
```

实测模板：

```
S27 Japanese anime cel-shaded animation still, cinematic 16:9.
Keep the SAME two characters with IDENTICAL designs as the reference sheet:
a girl with a chestnut-brown bob in a rust-red pinafore dress over a white
puff-sleeve blouse, and a boy with messy black hair in a dusty-blue t-shirt
and dark shorts.
Now place them in a NEW scene: <场景、光线、构图>.
Clean thick line art, flat cel shading with subtle gradients, warm nostalgic
palette. No text, no watermark, no logo, no photorealism.
```

四个要素缺一不可：

1. **镜头号前缀**（`S27`）——并发出图时避免文件互相覆盖
2. **画风声明**——`cel-shaded`、`flat color`、`thick line art` 这类词要显式写
3. **材质约束**——反向声明"不是照片、不是油画"比正面描述更有效
4. **构图描述**——明确主体占画面的哪一部分，为字幕留位置

## 四、主体太小时模型一定会退化

**这是最隐蔽的跑偏原因。**

分镜写"两个很小的黏土小人站在远处草地上"，出图会给你一张写实厚涂的
黄昏风景照，人物变成两个看不出来的剪影。因为"小"这个描述让模型把注意力
放到了风景上，而风景的高质量解就是写实。

对策：**人物永远保持在能辨认服饰的尺度**。远景用"中景背影 + 长影子"来
暗示距离，而不是真的把人画小。

```
✗ 两个很小的孩子在远处的草地上
✓ 低机位广角，两人站在中景，背影，能看清铁锈红裙与牛仔蓝T恤，
  长影子朝镜头方向拉开
```

同样的坑还有：俯拍伞面、纯剪影、极远景。凡是要"氛围"的镜头，
用光影和构图做氛围，不要靠缩小主体。

## 五、图生视频：只描述运动

图生视频的输入图已经决定了外观，提示词只该管"怎么动"。

```
✗ 一个穿红裙子的女孩在夕阳下的集市里微笑   （重复描述外观，模型会重画）
✓ Animate the input image with subtle motion only. Keep the EXACT same
  composition, framing, camera distance and colors as the input.
  Motion: <具体动作>
```

有效句式：

- `Animate the input image with subtle motion only.`
- `Keep the EXACT same composition, framing, camera distance and colors`
- `Do not change their clothes, do not change the camera, do not zoom in.`

负向提示词固定加这一组，能挡掉大部分翻车：

```
color shift, costume change, outfit change, different clothes,
photorealistic, 3D render, text, watermark, logo,
extra limbs, deformed hands, flicker, jitter, morphing, camera shake
```

**即便如此，模型仍会轻微推近**。这不是错误，往往构图更紧凑。验收时看
"人物设计有没有变、颜色有没有变"，而不是"构图是否和原图逐像素一致"。

## 六、风格体检：一张图看全片

40 张图逐张看太慢。拼成一张总览，一次扫完：

```bash
ffmpeg -y -pattern_type glob -i 'images/c16/s*.png' \
  -vf "scale=248:140,tile=7x6:padding=4:color=0x101010" \
  -frames:v 1 out/qa/style_sheet.png
```

看三件事：

1. **有没有哪格明显不是同一种画法**（照片感、油画感、3D 感）
2. **人物是否每格都能认出是同一对**
3. **色彩是否落在同一条色带**（本案例是暖橙到薄荷绿的对照）

跑偏的那一格会非常显眼，像贴错了图。

## 七、跑偏了怎么修

只重做那一镜，不要动全片：

1. 备份 `images/raw/sNN.png`、`images/c16/sNN.png`、`clips/vNN.mp4`
2. 重写该镜提示词，把导致退化的因素去掉（通常是"主体太小"）
3. 重新出图 → 裁到目标分辨率 → 图生视频 → 转码
4. 重拼时间线 + 重合成

单镜返工约 5 分钟；全片返工约 3 小时。

## 八、水印

生成图普遍带「AI生成」水印，位置不固定（左上 / 右下都见过）。

- **优先用裁切解决**：把目标比例之外的部分正好盖住水印区
- 裁不掉再用 `delogo`。注意 `delogo` 在纹理复杂的区域（草地、水面）
  会留下明显模糊带，比水印本身还难看
- 先量位置再动手：`crop` 出角落 + `drawgrid` 叠加网格，读像素坐标

## 九、验收清单

- [ ] 全片总览图里没有风格孤岛
- [ ] 每个人物镜头都能认出服饰特征
- [ ] 没有残留水印
- [ ] 图生视频没有改变服装颜色
- [ ] 字幕落位处没有压住脸（逐镜看过 `place`）
