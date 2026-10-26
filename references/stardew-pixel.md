# 星露谷式像素：从参考资料到可执行视频规则

本参考用于 `stardew` 风格：农场、村镇、四季、日常劳动和温暖叙事。目标是从公开画面提炼生产规则，不是复制游戏素材，也不是给高清图加一层马赛克。

研究日期：2026-10-26。下文将 **可核验事实** 与 **工程建议** 分开；工程阈值不是开发者公布的官方规范。

## 一、参考资料

### 官方视频

| 来源 | 用途 | 注意事项 |
|---|---|---|
| [Stardew Valley Trailer — ConcernedApe](https://www.youtube.com/watch?v=ot7uXNQskhs) | 正式版户外投影、人物与建筑比例、工具动作、HUD 同屏关系 | 预告有剪辑，不用镜头持续时间推算动画帧率 |
| [Multiplayer Update — Trailer & Release Date](https://www.youtube.com/watch?v=-vlBE3vSfNU) | 多角色独立动作、农场功能分区、树与建筑遮挡 | 标注版本；不要当成当前版全部内容 |
| [Stardew Valley 1.1 Launch Trailer](https://www.youtube.com/watch?v=xf9e3c-nMRA) | 农场布局、水体、道路与建筑组织 | 仅作 1.1 时期画面参考 |

抽帧时按“动作开始 / 接触 / 恢复 / 场景切换”取点，不要只按固定秒数盲抽。

### 官方截图与开发资料

| 来源 | 可核验内容 |
|---|---|
| [Steam 官方商店与截图](https://store.steampowered.com/app/413150/Stardew_Valley/) | 3/4 俯视、农田行列、建筑屋顶与正立面、树木成簇、道路负空间、局部光源与像素边缘 |
| [Steam 官方截图数据](https://store.steampowered.com/api/appdetails?appids=413150&l=english) | 获取全尺寸官方截图，避免第三方压缩图 |
| [ConcernedApe 开发日志：9/26/12](https://stardewvalley.blogspot.com/2012/09/92612.html) | 作者明确写到 “smoother animations” 和 “Twice as many frames as before”，并发布行走/跑步 GIF；证明真实姿态帧的重要性，不能外推当前版帧率 |
| [1.6 Update Full Changelog](https://www.stardewvalley.net/stardew-valley-1-6-update-full-changelog/) | 季节性地图、瀑布、环境动物、秋季落叶、室内昼夜照明过渡、窗户光源与灯具状态 |

### Wiki 技术资料（社区模组文档，不冒充开发者规范）

| 来源 | 可核验内容 |
|---|---|
| [Modding: Editing XNB files](https://stardewvalleywiki.com/Modding:Editing_XNB_files) | spritesheet 的规则网格；地图 tilesheet 的 16×16 tile |
| [Modding: Maps](https://stardewvalleywiki.com/Modding:Maps) | Back / Buildings / Paths / Front / AlwaysFront 图层；树等对象按角色南北位置改变前后遮挡；tile animation |
| [Modding: Farmer sprite](https://stardewvalleywiki.com/Modding:Farmer_sprite) | 农夫基础素材框 16×32；下/上/左右方向；左右镜像；走、跑、工具和钓鱼等动作索引与逐帧停留时长 |
| [Day Cycle](https://stardewvalleywiki.com/Day_Cycle) | 入夜随季节变化、室外逐渐变暗、室内窗户和灯具响应、日期/天气/时间等屏幕空间信息 |

**不要编造**“全游戏统一动画 FPS”“固定总颜色数”或“唯一官方内部分辨率”。Wiki 中的具体动作时长只用于对应动作参考，不设为全片统一节奏。

## 二、先锁定投影与像素坐标

### 可核验事实

- 地图 tile 为 16×16；农夫基础素材框为 16×32。素材框、可见身体、脚点和碰撞区域不是同一个概念。
- 场景依靠多个图层和脚点前后关系形成遮挡，不是把全部物件画在一张平面背景里。
- 行走、跑步、浇水、重工具、钓鱼等使用不同方向性 sprite 序列；左右可复用镜像。

### 工程建议

- 使用正交、偏高的 **3/4 俯视**：同时读出可行走地面、屋顶与建筑正立面。不要生成等距菱形世界，也不要压成只有一条地面带的横版关卡。
- 横屏推荐在 **480×270** 的世界层制作，Nearest Neighbor **×4** 到 1920×1080；竖屏可用 270×480 → 1080×1920。它们是 MV 工程规格，不是游戏官方内部分辨率。
- 以 16×16 为地图设计坐标；农夫型主角采用 16×32 素材框，并以脚点落地。其他角色可调整，但必须显式记录框尺寸和脚点。
- 相机只允许固定、原生像素坐标取整的平移、拍点硬切。禁止轨道环绕、透视推拉和连续非整数缩放。
- 世界层先完成像素对齐，再整数放大；光照、HUD 和字幕作为独立层处理，不纳入世界色块的统一性检查。

## 三、场景不是均匀撒细节

从官方画面归纳以下生成规则：

1. **功能分区**：农田用行列，建筑与围栏组织边界，道路连接动作目标。入口到目标之间至少保留一条宽一格的连续通路。
2. **簇状细节**：树、灌木、石块、花草形成有边界的簇；岸边使用过渡块。不要每个 tile 都塞满不同杂物，也不要全屏均匀撒草点。
3. **负空间**：角色操作区、道路和门口保持连续可读。装饰不能堵住浇水、收获或对话的位置。
4. **材料色板**：草地、土壤、木材、石、水面分别控制明暗层级；使用清晰色块和有选择的边缘线，不做全屏均匀黑描边或随机抖动噪点。
5. **分层遮挡**：拆出地面、道路/杂物、建筑、角色、前景遮挡、独立环境动画、光照、HUD、字幕。树冠、屋顶前缘和大型家具按脚点前后关系遮挡角色。

## 四、动作必须发生，不用 zoompan 冒充

### 行走与待机

- 星露谷式行走采用“中立—一侧迈步—中立—另一侧迈步”的交替逻辑。Wiki 当前记录的行走循环为 `0,1,0,2`，含三种不同姿态；这是一项具体参考，不是所有像素游戏的强制标准。
- 一个完整步态周期至少有 **3 个可区分的轮廓**，并出现左右腿交替。整体平移、上下正弦浮动、呼吸拉伸或 zoompan 不计入姿态数。
- 待机以稳定脚点为主，可按参考加入眨眼或小型次级动作；不要默认整个角色上下漂浮。

### 工具与劳动

- 工具动作至少拆成 **准备 → 接触 → 恢复** 三个语义阶段，手臂和工具轮廓必须真实变化。
- 浇水、砍伐、锄地等还必须出现目标反馈，例如水落在土壤、碎屑飞溅、地面状态改变。只挥动手臂而目标毫无变化，判失败。
- 音乐重拍优先对齐工具接触、脚步落地或剪辑点，通过调整关键姿态停留时间同步；不要给所有动作套一个固定 FPS。
- 动作实现优先级：显式 sprite 姿态序列 → 关键姿态驱动短视频 → 纯文本直接生成整段动作。若模型只输出推拉或整体漂移，退回 sprite 合成。

### 环境动画

- 水、叶、天气、小动物、烟雾等使用局部独立循环；不要让整张背景同步扭动。
- 一个短镜头只设一个主动作，例如“走到田边”或“浇水”，不要同时要求走、转、浇、捡、挥手。

## 五、季节、时间与光照是状态系统

- 每镜头显式记录 `season / time / weather`。复唱若表现时间流逝，应改变实际状态，而非只换背景。
- 季节变化至少同时检查植被、地面、作物、装饰和色板；不能将“整图换一个 LUT”当成完整季节系统。
- 昼夜变化分离环境变暗、局部光源、窗户/灯具状态和 UI。夜景出现灯具或窗户时，要有局部光照响应；仅整帧变蓝变暗，判失败。
- 光照可以平滑过渡，不必强行做成硬像素阶梯。世界素材层与光照层分开验收。

## 六、镜头动作合同与提示词

在出图前为每镜填写 `out/pixel_spec.json`。可从 `assets/pixel_spec.stardew.example.json` 复制，字段包括：

`地点｜季节/时间/天气｜参考图｜角色朝向｜起始姿态｜动作循环/关键阶段｜目标反馈｜环境循环｜脚点与遮挡｜相机｜连续通路`

### 场景探索提示词

```text
[SHOT ID] original cozy farming-life pixel art, three-quarter top-down
orthographic view. Square tile-map logic, readable walkable ground, farmhouse
roof AND front facade, clustered trees and crops, clear paths and functional
zones. [season/time/weather]. Restrained material-specific colors, crisp native
pixel clusters, no isometric diamond grid, no side-scroller ground strip,
no photorealism, no text, no logo, no watermark.
```

AI 图只作 tile 和构图候选；入库前必须在原生网格中清理、重绘和对齐。高清 AI 图直接缩小或像素化后，不得冒充原生像素资产。

### Sprite 姿态提示词

```text
[SHOT ID / POSE ID] same original farmer sprite, same 16:32 frame ratio,
three-quarter top-down character design, [direction], [neutral / left step /
right step / tool prepare / contact / recover]. Stable foot anchor, solid chroma
background, no ground shadow, no camera change, no body squash-and-stretch,
no extra limbs, no text, no watermark.
```

模型输出仍是姿态候选。按脚点配准、去除底色和紫边、核对轮廓差异后，才进入 sprite sheet。

## 七、机械验收

先复制并修改规格：

```bash
cp assets/pixel_spec.stardew.example.json out/pixel_spec.json
python scripts/pixel_spec.py check out/pixel_spec.json
```

图像级检查：

```bash
# 步态轮廓、透明背景与脚点漂移；检查真实图像，不读取自报“已做三帧”
python scripts/pixel_spec.py audit-sprites images/farmer_walk.png \
  --frame-width 16 --frame-height 32 --cycle 0,1,0,2 --min-distinct 3

# 世界素材层在光照、HUD、字幕和 video 编码之前检查；只接受 PNG 等无损源
python scripts/pixel_spec.py audit-scale images/world_layer.png --scale 4
```

以下任一项失败，先修资产或镜头，不用模糊、胶片颗粒或调色遮盖：

| ID | 失败条件 |
|---|---|
| R1 投影 | 变成横版地面带、等距菱形世界，或同镜头投影突变 |
| R2 网格与脚点 | 地图不能叠加到设计网格；用头中心定位；把素材框当碰撞箱 |
| R3 整数缩放 | 世界层未按指定整数倍最近邻放大，或出现平滑插值边缘 |
| R4 真像素资产 | 只能提交高清母图加马赛克，无法提交原生 tile/sprite/关键姿态 |
| R5 真实行走 | 步态少于 3 个可区分轮廓，或差异只来自整体平移/缩放/上下浮动 |
| R6 工具动作 | 缺少准备/接触/恢复，或缺少目标处反馈 |
| R7 待机和环境 | 脚点漂移、整体正弦浮动、整背景同步扭动 |
| R8 镜头 | 动作镜的主要运动是 zoompan、环绕或连续非整数缩放 |
| R9 遮挡 | 穿墙、穿树干、树根无条件盖住角色，或遮挡与脚点关系相反 |
| R10 季节与光照 | 季节标签与植被/作物冲突；灯具和窗户无局部光照响应 |
| R11 通路 | 入口到目标之间没有至少一格宽的连续通路 |
| R12 UI 与字幕 | HUD 随世界移动、伪文字乱码、字幕被世界光照一起染色 |
| R13 伪精确参数 | 无参考依据地声称“官方统一 FPS”“官方固定颜色数” |

## 八、版权边界

官方视频、截图和 GIF 仅作分析与内部抽帧参考，不直接打包进本技能或生成资产库。生成原创 tile、角色和场景；不要输出可识别为复制官方角色、地图或 UI 的素材。
