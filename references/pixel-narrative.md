# 横版像素剧情游戏（pixelstory）：从参考视频到生成规范

`pixelstory` 用于情感、回忆、错过、日常关系等歌词叙事。它不是“街机横版 `pixel`”，也不是“3/4 俯视田园 `stardew`”。核心公式：

**横版侧视 + Q 版 sprite + 少量场景反复复用 + 2–4 个游戏状态通道 + 关键道具插页 + 开场/结算闭环。**

本规范来自对一支《开不了口》参考 MV 的逐帧分析。原视频、截图和角色不进入技能资产库；以下区分可观察证据与工程建议。

## 一、参考样本提供的有效机制

### 可观察证据

- 开场显示 `1P START`，结尾显示 `RESULT`，形成完整的游戏流程。
- 顶部 `WORLD` 推进章节，`SCORE` 随进程变化，`2P` 在部分段落出现灰/红状态差异；没有证据表明必须让 1P 持续扣血。
- 信纸只写下“我”，旁边标注“未送达”，把“几句话却办不到”变成可见的道具状态。
- 结尾结算为“照顾 OK / 逗笑 OK / 告白 ...”，说明主角并非处处失败，而是唯独没有完成告白。
- 公交/车窗、雨伞和左右分隔反复构成人物距离；同一批夜街、卧室、公交等场景通过人物、天气、光照和 HUD 改变含义。
- 连续帧中可见主角手臂姿态变化；其他段落主要依赖云层、星光、车辆等环境运动。并非所有画面都在做同等密度的角色动画。

### 不能从样本直接断言的内容

- 不能断言唯一原生画布、像素块尺寸、制作引擎或统一动画 FPS。
- 不能把“白昼一定是回忆、夜晚一定是现实”当成所有项目的规则；只能在单个项目内保持映射一致。
- 不能照搬 `1P/2P`、信件或 RESULT 文本到每首歌。应继承“状态叙事功能”，再替换为符合歌词的对象。

## 二、风格锁定

### 画面与角色

- 使用固定横版侧视或横向卷轴，保留清楚的地面活动带、建筑立面、车窗、门口等关系空间。
- 角色采用统一的 Q 版比例、有限色板和稳定脚点。先制作方向性 sprite，再合成场景；不要每镜重新生成一个长相相近的人。
- 世界层在原生低分辨率制作，再整数倍最近邻放大。工程可选：320×180 ×6 → 1920×1080，或 256×144 ×4 → 1024×576；它们不是参考视频的已证实内部参数。
- 地图设计可使用 16×16 网格，画面边缘允许部分 tile。角色素材框按项目记录，不强制与地图格等宽。
- 字幕和 HUD 使用独立屏幕空间层，不随世界光照、位移或缩放变形。

### 场景复用矩阵

不要以“新增多少背景”衡量丰富度。先为每个地点建立状态矩阵：

`地点｜现实/回忆｜昼夜/天气｜人物数量｜人物位置｜道具状态｜WORLD/SCORE/关系状态｜局部环境循环`

同一夜街至少可以表达：独自等待、对方乘车离开、与他人共伞、公交从旁经过、空手返回。复唱应优先推进状态，而不是只换色调或重复第一次构图。

## 三、状态通道比 HUD 更重要

选择 **2–4 个**可持续读取的通道，超过 4 个观众难以跟踪：

| 通道类型 | 示例 | 叙事功能 |
|---|---|---|
| 章节 | WORLD 1-1 → 4-1 | 标记关系阶段，不等于成功攻略 |
| 第二人状态 | 2P 灰/红、头像亮/暗 | 表示第二人是否加入、可获得性或关系变化 |
| 道具 | 空白信 → 写一字 → 未送达 → 收好 | 把抽象迟疑变成可见对象 |
| 时间/天气 | 白昼/夜晚、晴/雨 | 区分现实与回忆、内外情绪状态 |
| 分数/结果 | SCORE、照顾/逗笑/告白 | 在结尾核对“做到了什么、没做到什么” |

`1P/2P` 只是可选实现。若歌词没有双人游戏语义，可改成“车票、未读消息、门口灯、共同物品”等通道，但必须保持可读的状态轨迹。

**反例：**全片挂一套爱心和 SCORE，数字却与人物和剧情无关；这只是装饰 HUD，不是 pixelstory。

## 四、动作与局部环境

### 主动作

- 普通行走至少准备 2 个真实姿态；关键挥手、递物、写字、撑伞等动作至少准备 2 个不同姿态，重要镜头推荐 3 个阶段。
- 工具动作沿用“准备 → 接触 → 恢复”，并要求目标处反馈。
- 道具动作必须登记 `prop_state_after`，例如 `blank_to_unsent`。只出现一封信却没有状态变化，不构成叙事动作。
- 待机锁定脚点，不用整体正弦浮动冒充生命感；整背景同步扭动直接判失败。
- 动作镜头的主要运动不能是 zoompan、整体漂移或缩放。优先显式 sprite 序列，其次关键姿态驱动，最后才是纯文本视频生成。

### 环境循环

云层、星光、雨、车辆、窗帘、灯光等使用局部独立循环。人物动作少的镜头可以用环境运动维持活性，但不能让环境动画替代关键叙事动作。

## 五、构图与插页

### 人物关系构图

多人镜头显式记录 `distance` 和可选 `barrier`：

- 主角在车外左侧，对方在车内右侧；
- 主角在雨外，另两人在同一把伞下；
- 主角与目标之间隔着窗、车门、道路、栏杆或画面边界。

这些关系比“人物站在一起然后换表情”更能表现错过和无法靠近。

### 道具插页与结果页

- 在关键歌词处插入全屏或近景道具，例如信纸、手机、车票、门口灯。插页必须改变道具状态，并保留足够阅读时间。
- 结尾使用结果清单、未完成任务、空白格或省略号收束主题。结果应忠于歌曲，不要为了“游戏胜利”强行复合。
- 开场与结尾尽量共享一套规则：开始于 `START / NEW GAME / 出发`，结束于 `RESULT / 未完成 / 继续`。不要把结尾换成另一套无关界面。

## 六、生产流程

1. **先写状态表**：列出每镜的 `story_state` 与 `state_change`，再写场景描述。
2. **准备资产包**：主角方向性 sprite、第二人/配角、少量场景、车辆、道具、局部环境循环。
3. **建立场景复用矩阵**：明确现实/回忆、昼夜、人物位置、遮挡和状态差异。
4. **制作代表动作**：至少一个行走、一个关键手势、一个道具状态插页。
5. **试制确认**：确认角色一致性、构图距离、字幕可读性和状态是否能被陌生观众读懂。
6. **分层合成**：背景、角色、前景、天气、HUD、字幕分别处理，世界层最后整数放大。
7. **验收并交付**：同时检查配置、真实 sprite、整数缩放和全片状态轨迹。

规格模板：

```bash
cp assets/pixel_spec.pixelstory.example.json out/pixel_spec.json
python scripts/pixel_spec.py check out/pixel_spec.json
```

图像级检查：

```bash
python scripts/pixel_spec.py audit-sprites images/hero_walk.png \
  --frame-width 24 --frame-height 32 --cycle 0,1,0,1 --min-distinct 2
python scripts/pixel_spec.py audit-sprites images/hero_gesture.png \
  --frame-width 24 --frame-height 32 --cycle 4,5,6 --min-distinct 3
python scripts/pixel_spec.py audit-scale images/world_layer.png --scale 6
```

`check` 只验证配置；`audit` 才检查真实图像。全片仍需逐镜目视验收。

## 七、提示词骨架

### 场景候选

```text
[SHOT ID] original side-scrolling narrative pixel-art scene, fixed side view,
clear walkable ground strip and readable building facades. [LOCATION].
[TIME/WEATHER/REALITY STATE]. Consistent Q-version character scale, clustered
material details, clear negative space for acting. Keep [BUS WINDOW / DOOR /
RAILING] as a visible relationship barrier. No top-down farm map, no isometric
world, no photorealism, no text, no watermark.
```

### 角色动作候选

```text
[SHOT ID / POSE ID] same original chibi pixel sprite, same proportions, clothes,
colors and foot anchor, side view facing [DIRECTION]. [POSE: neutral / walking /
offering / waving / writing / umbrella]. Real arm and leg silhouette changes,
no camera movement, no body squash, no extra limbs, solid chroma background,
no ground shadow, no text, no watermark.
```

AI 输出只作构图和姿态候选。入库前必须在原生网格中清理、配准、去色边并检查轮廓。

## 八、失败清单

- 把参考风格简化成“高清场景＋像素滤镜＋顶部 HUD”。
- 全部剧情发生在菜单或整屏面板，角色只存在于缩略图。
- 每句都换新背景，却没有人物、道具或关系状态推进。
- 行走、挥手、递物等动作只有整体平移、缩放或上下浮动。
- 2P、爱心、SCORE 等数字与人物行为无关，或复唱只重复第一次状态。
- 多人同框却没有距离、遮挡或视线关系。
- 道具插页只有装饰，没有“写不下、未送达、被收起”等状态结果。
- 为迎合游戏结局而强行成功，破坏原歌的遗憾和未完成感。
- 官方或参考视频的角色、场景、UI 被直接复制进生成资产库。
