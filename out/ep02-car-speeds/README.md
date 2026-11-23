# 第二集交付状态

查看驾驶舱可直接打开工作区的 `work/cabin-motion/ep02-cabin-six-poses.blend`（80.5 MB）。用左右方向键切换六个变形姿态，五个机位和内饰都可编辑。完整 281 帧工程与缓存也已打包在 `work/cabin-motion/ep02-cabin-motion.zip`（2.45 GB）。[六个姿态预览](cabin/motion/portable-poses.jpg) · [双机位对照与重建说明](cabin/motion/)

驾驶位和仪表台采用同款车的 CCSA 精细版 v2j 作为几何依据。驾驶舱饰件、参考来源、静帧和本机重建命令见[模型说明](cabin/README.md)。

56 km/h 粗网格工况已算完 140 ms。驾驶座 CFC 60 峰值为 60.66 g，碰墙后 47.30 ms 到峰，最大能量残差为 6.42%。能量超过验收线，其他速度待物理复核。[分段数据](physics/56kmh-checkpoints.csv) · [工具版本与恢复步骤](../../PROGRESS.md)

| 56 km/h 验收项 | 公开比较值或验收线 | 本集结果 |
| --- | --- | --- |
| CFC 60 峰值与时刻 | 小型车 43.5 g、47.5 ms | 60.66 g，47.30 ms |
| 脉冲持续时间 | 小型车 91.3 ms | 68.01 ms（有限窗口估计） |
| 总能量漂移 | 小于 5% | 6.42% |
| 沙漏能 / 内能 | 小于 10% | 0.00% |

全局沙漏能通道不含 QEPH 壳单元的数值稳定阻尼。另将 923 个零件的 HE 通道求和，其与全局内能的比值最高为 5.55%。壁障纵向冲量为 23.57 kN·s，能量残差在接触后约 53.0 ms 首次超过 5%。[全时程数据](physics/56kmh-history.csv) · [HE 定义](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/th_part_starter_r.htm)

这些公开数字是车队统计。指定车型的全宽壁障试验包括 39.8 和 56.3 km/h。拟制作的 90 和 120 km/h 均超出这组试验范围；另一车型的 90 km/h 偏置试验不能直接验证本片。详见[数据和来源](../../data/ep02-car-crash-data.md)。

车速、座椅安装点加速度和粗网格变形均来自求解器。方向盘中心至驾驶座靠背的初始距离为 597.83 mm，19.0 ms 时为 592.77 mm。行驶振动、6 Hz 阻尼比 0.4 的头部弹簧和峰后震颤是摄影规则。静态建模画面的道路、墙面、光照和可见饰件来自 Blender。

已测量 32 条现有 ElevenLabs 片段的全频与 300 Hz 以上电平。第二集专用的车内行驶、金属压溃、玻璃碎裂和零件落地声仍缺。现有金属及玻璃片段可剪用，行驶声和落地声留空。成片的时间表、响度和手机频段电平差须用最终剪辑实测。[素材电平表](asset-levels.csv)

## 56 km/h 复核

独立读取求解器写出的总能量通道，最大漂移 6.41968%。末帧有 13.122 kJ 摩擦接触能，前壁和四个地面的纵向总冲量与动量变化相差 1.49 N·s。重启段终端的 ERROR 采用另一个公式，不能替代全程验收。[能量与冲量复算](physics/56kmh-energy-audit.json)

同款轿车 5677 实车壁障力的峰值按 CCSA 图约 530 kN / 26 ms。原作者有限元按图约 594 kN / 43 ms，本次两段前壁合力经 CFC 60 后为 624 kN / 44.6 ms。[同车型整墙反力对照](physics/56kmh-wall-reference.png)

用同一个 45 ms 重启文件将积分步长从约 0.996 µs 限至 0.498 µs，算到 55 ms。最后一个共同采样时刻为 54.900 ms，原步长漂移 5.136%，半步长漂移 5.441%。这两条曲线都超过 5%。TYPE25 接触的罚刚度项也依赖步长，此试验衡量整套计算对步长设置的敏感性。[步长对照图](physics/56kmh-step-study.png) · [逐点数据](physics/56kmh-step-study.csv)

原包的内部接触卡控制 14 个零件。三次 Starter 对照确认这 14 个实体属性的畸变控制已启用。以八个几何高斯点检查 281 个输出状态，3,848 个相关砖单元的最小局部体积比为 0.523，没有观察到翻转。能量残差的来源仍未定位到具体零件或界面。原包仅含输入卡和说明，校方验证报告给出的曲线没有各零件及界面逐时能量明细。[实体检查](physics/56kmh-interior-contact.json)

## 模型来源与使用说明

采用乔治梅森大学 CCSA 的 2010 Yaris 粗网格 v1l（2016-12），以及原包内配套的 NCAP 刚性墙。原包 README 记载项目由 FHWA 资助，要求使用者自行验证结果，CCSA 和 FHWA 对有效性、准确性及适用性不承担责任，并请求在使用模型的论文与出版物中致谢 GMU CCSA 和 FHWA。未将原包或提取的几何写入 Git。[原始下载](https://media.ccsa.gmu.edu/model/2010-toyota-yaris-coarse-v1l.zip)

物理求解器使用 [OpenCourant 稳定版 20261011](https://github.com/OpenCourant/OpenCourant/releases/tag/latest-20261011)。试算与最终可发布结果的区别见根目录进度。

[驾驶位构图试片](studies/approach-framing.png) 使用原车初始网格和美术道路、墙面及灯光。仅用于评估驾驶位构图。

## 从已验收的物理解算生成画面

在仓库根目录运行。输入为正式工况的逐帧缓存、原模型零件表及 10 kHz 历程。工作目录内生成的 `driver-seat.blend` 含原模型几何，保留在本机。启用精细驾驶舱后，检查工程名为 `driver-60ms.blend`。

```bash
python3 scripts/ep02_render.py proof 56 out/ep02-car-speeds/physics/56kmh-history.csv work/cached56 --cabin work/cabin-model/ep02-cabin.blend
```

这条命令生成两套各六张静帧、实速并排回放、相机朝向表、角速度图及间距表。实速对照同步播放三次，左侧是头部响应，右侧固定在座椅横梁。合适的 GPU 可加 `--gpu`。正式素材使用 `film`、1080×1920、Cycles 降噪，按每档已完成的工况执行。以下命令展示单档流程，多档合成时在 `ep02_picture.py` 命令末尾依次列出已渲染的速度。

```bash
python3 scripts/ep02_render.py film 56 out/ep02-car-speeds/physics/56kmh-history.csv work/cached56 --cabin work/cabin-model/ep02-cabin.blend --gpu
python3 scripts/ep02_picture.py work/picture work/picture/film.json 56
node remotion/render-car.mjs work/picture/film.json work/picture out/ep02-car-speeds/ep02-silent.mp4
python3 scripts/ep02_sound.py mix work/picture/film.json work/picture/mix.wav out/ep02-car-speeds/sound-cues.csv
python3 scripts/ep02_master.py work/picture/film.json out/ep02-car-speeds/ep02-silent.mp4 work/picture/mix.wav out/ep02-car-speeds/ep02.mp4 out/ep02-car-speeds/qa.json
```
