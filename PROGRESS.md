# EP02 制作进度

**驾驶舱已完成静态建模和 56 km/h 变形绑定，281 个求解样本可在 Blender 中逐帧检查。** [六组双机位对照](out/ep02-car-speeds/cabin/motion/) · [同机位改模前后](out/ep02-car-speeds/cabin/driver-comparison.jpg) · [图库与重建方法](out/ep02-car-speeds/cabin/README.md)

56 km/h 粗网格已算完 140 ms，最大能量残差 6.42%，超过 5% 验收线。其余速度和视频合成暂停。

## 官方模型和输入检查

- [CCSA 模型页面](https://www.ccsa.gmu.edu/models/2010-toyota-yaris/) 与 [v1l 原包](https://media.ccsa.gmu.edu/model/2010-toyota-yaris-coarse-v1l.zip) 恢复可读。2016 年 12 月粗网格版，SHA-384 与官网一致：`4f2b837ba0c85c2ef123a75201ac341c5de6763fb2768b818d41ec4c027af921aabea83f0069bfa8b457a56c44c34ed0`。本地 SHA-256：`aff8194c456726a678d6cc11f644316ca70f3d9b37c4db622726b7b2985b0451`。
- 原始车身关键字卡独立计数并与修正后的 NumPy 网格比对：919 个零件，393,165 个节点，358,457 个壳，15,234 个实体，4,685 个梁。另有 19 个离散单元和 155 个质量单元；官网的 378,376 是壳、实体、梁之和。解析器已能处理原包中的空坐标字段和梁端点。
- 原包自带全宽 NCAP 刚性壁障、初速、轮速和测点。网页标称车重 1,078 kg，v1l 卡片注释为 1,100 kg，Starter 所报含配重及壁障的完整系统质量 1,256.152 kg。保留官方配重，不能用网页车重替代计算质量。
- 首次导入发现焊点转换强制要求单位元数据，已按原包说明声明 mm、s、t。试配时发现替换终止时间误及一处摩擦参数，已中止该次运行并排除其数据。正式试算由 `scripts/ep02_prepare.py` 从已校验原包重新生成，只定点改速度、时长和输出配置。右下 B 柱取右侧内板节点 2274453，其余采用原车测点。固定的刚性墙在 x=50 mm。
- Starter 报告材料、圆柱铰及约束等警告。单位声明解决了输入错误；验收仍须核对应变率曲线解释、能量和实际脉冲，不能凭 Starter 成功判定模型已验证。

## 已核实

- 基线提交 `46a0e60`，工作分支 `ep02-car-speeds`。第一集预览已用 FFmpeg 验证完整解码，并抽看从进场到结束卡的时间序列。文件实际是 1080×1920、30 fps，视频长 23.67 秒。倒计时和数据位于上方暗区，实速回放之后切黑再到网点结束卡。
- 本实例 `nproc` 为 5，cgroup CPU 配额为 4 核，内存上限 32 GiB，无交换空间。开始时可用磁盘约 60 GiB。未发现 NVIDIA 设备、DRI 设备或 nvidia-smi。渲染使用 Cycles CPU。
- 复用预装 Blender 4.3.2（系统包 4.3.2+dfsg-2），可执行文件 SHA-256 为 `0dfe9af0f3e67643ecf15327fa5e14e7315f61d1a81afdcafe76a71b1918e2b4`。
- OpenRadioss 原仓库的 latest release 页面本次返回 404；这不足以确认关停原因或日期。OpenCourant 官方 latest 指向稳定构建 `latest-20261011`，下载 Linux x86-64 ZIP 到 `work/`。本机 SHA-256 与发布页一致，均为 `6cb419677ca36d73acb96218cc0cf5e4f7d50494d9c7812ba27935e3c0f8ec94`。Starter 报告源码提交 `cb760c206e346eff12161a2268b134ef9d48a4ef`。Starter 和 OpenMP Engine 均通过版本启动检查。[官方发布页](https://github.com/OpenCourant/OpenCourant/releases/tag/latest-20261011)
- 没有发现名称含 ELEVEN 的环境变量。本次未调用音效 API。

## 恢复顺序

1. 将官方 ZIP 保存在 `work/yaris.zip`。从仓库根目录用 `python3 scripts/ep02_prepare.py work/yaris.zip work/validated56-5ms --speed 56 --ms 5` 准备新的试算目录，已存在的目录会受到保护。
2. 从仓库根目录执行下面的环境设置。先做 56 km/h 的 5 ms 试算，记录墙钟时间和磁盘占用，据此估算四档预算。本机 5 ms 实测与外推预算见下节。
3. 跑完 56 km/h，验收 CFC 60 曲线、时刻、脉冲持续时间、总能量漂移与沙漏能占比。通过后再做六张静帧、头部与固定相机对照和抖动小样。
4. 依次评估 90、40、120 km/h。完成三帧渲染基准、画面、界面、混音和全片验收后再提供发布材料。

```bash
export OPENRADIOSS_PATH="$PWD/work/OpenCourant"
export RAD_CFG_PATH="$OPENRADIOSS_PATH/hm_cfg_files"
export LD_LIBRARY_PATH="$OPENRADIOSS_PATH/extlib/hm_reader/linux64:$OPENRADIOSS_PATH/extlib/h3d/lib/linux64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$OPENRADIOSS_PATH/exec/starter_linux64_gf" -v
"$OPENRADIOSS_PATH/exec/engine_linux64_gf" -v
```

## 已独立验证的后期环节

- 在 `remotion/` 按锁文件安装了 247 个包。指定的 `npx remotion browser ensure` 下载浏览器时无法解析 remotion.media；使用本机 Chromium 成功渲染了第一集第 690 帧结束卡。复查命令为 `npx --no-install remotion still src/index.ts Short ../work/ep01-end-check.png --frame=690 --browser-executable=/usr/bin/chromium --scale=0.25`。这个检查只覆盖 Remotion 合成环境。
- 已在原音效清单末尾加入四条汽车专用提示词。生成器已改为仅从环境变量取密钥，并拒绝 HTTP 重定向。在没有密钥的本机运行，脚本在发出请求前退出，已有 MP3 可继续复用。

### 初速度复核与修正

- 第一帧 VTK 显示，普通车身节点达到 15,555.6 mm/s，但部分转向节和轮毂刚体被导入成零速。0.5 ms 时转向节只前移约 2.04 mm，车身侧板已前移 7.75 mm。已舍弃这次试算。
- 在同一原模上用 `scripts/ep02_rigid_velocity.py` 给 20 个独立刚体显式传入原速度场，另外两件并在转向节中。旋转件的质心速度由原轴线、半径 303 mm 和 Starter 输出的质心计算。未改材料、质量、铰链和接触参数。
- 在有效的 `work/corrected56/` 工况中，逐点核对原模型全部壳、梁和实体的初速，最大向量误差 0.0702 mm/s（VTK 文本精度）。初始驾驶座横梁和重心的纵向速度与 56 km/h 一致。
- 已用两张真实求解动画测试分帧缓存，保留原生时间、单元/节点/零件 ID、拓扑与逐帧侵蚀状态；不会将整段动画堆入内存。通过官方转换器同时读取 T01 和 T01_TITLES，验证可提取座椅、左右 B 柱、重心、壁障反力和能量通道。首帧单位检查不代表全程通过。
- 复跑时先对新工况运行 Starter，再从同工况的报告运行刚体速度脚本，再次运行 Starter 生成正式重启文件，最后执行 Engine。官方程序与模型留在 work/。分支已建[草稿 PR #1](https://github.com/christczp-a11y/Simulator/pull/1)。

## 56 km/h 基准与时间预算

- Engine 正常完成 5,023 个循环，5 ms 实耗 787.57 秒。Starter 和 Engine 合计 802.77 秒。第一段有 50 个约 0.1 ms 间隔的历程样本，最后一个在 4.900249 ms；5 ms 边界之后的历程由续段接管。第一个非零正面壁障反力样本出现在 0.600457 ms。短窗最大能量残差 0.0071%，这个短窗不足以估计冲击峰值、持续时间和最终舱内侵入量。[原始通道节选](out/ep02-car-speeds/physics/56kmh-first-5ms.csv)
- 按相同计算速度，每档 120–160 ms 的墙钟时间外推为 5.25–7.00 小时，四档约 21.0–28.0 小时，只含求解。后段接触复杂度可能改变耗时。优先完成 56 km/h 验收，未验收前不启动其他档。
- 56 km/h 已从 5 ms 接续，计划写出 20、45、70、95、120、140 ms 的原生重启文件。进程结束后确认各段实际终止状态。如果受中断，先检查最后正常完成的段及其 RST；相同进程仍在时勿重复启动。
- 构图试片中确认当前机带的 Blender 缺少 OpenImageDenoise。已从 [Blender 官方 4.5 LTS 目录](https://download.blender.org/release/Blender4.5/) 下载 4.5.16 Linux 版，SHA-256 与官方清单相符：`23432b064977908beb1ab4b7f32f024e7331105c875c187dce002aff84b10c11`。实车 VTK 中 21,481 个三角形有四个索引（末尾重复），已按实际连接表宽度读取。
- [驾驶位构图试片](out/ep02-car-speeds/studies/approach-framing.png) 使用已核对的初始 FE 网格，整车沿道路向后放置 8 m，用于检查挡风玻璃、方向盘和顶部暗区。沥青、混凝土、材质和光照是美术设置。此图不是碰撞变形验收帧。官方模型没有完整的量产车内饰纹理。

### 验收与镜头准备

- 恢复环境后已核实 5 ms 原生重启有效。后续 Engine 从 5.0008 ms 接续。检查第一段末帧，壁障有效范围内车身最前点为 x=50.0 mm，未见超过墙面 1 mm 的车身节点。
- 读到 CCSA 原始验证报告。物理试验 5677 是 2007 年四门轿车，6221 是 2008 年三门掀背车；报告第 10 页列出的加载质量分别为 1,271、1,245 kg，原作者 FE 工况为 1,263 kg。本次完整模型的 Starter 质量比原作者工况低约 0.54%。报告第 14–15 页的加速度位置是左右后座，已纳入单独的测量通道，不与驾驶座横梁混用。[CCSA 报告](https://www.ccsa.gmu.edu/wp-content/uploads/2016/11/2010-toyota-yaris-coarse-validation-v1.pdf)（下载件 SHA-256：`577cef33ad4344926cea9d94fba08727743691d7a6f7b1ad3a3d24dc3b86598e`）
- Locey 的 43.5 g、47.5 ms 和 91.3 ms 是小型车队列模型均值。原论文在 CFC18 曲线上以 0–200 ms 平均值定位下降尾段，再取峰值的 5% 交点定义持续时间。本次若提前结束则报告实际均值窗口并注明近似。[Locey 原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC3503406/)
- 驾驶位空间量采用初始方向盘上下左右四个边缘节点的中心，沿车身纵向与驾驶座靠背前表面相交，随后追踪相同的方向盘节点和同一个面上的材料点。初始距离 **597.83 mm**，原始靠背单元 2173449。该数是初始间距，舱内损失量另按各求解时刻计算。
- 官方转换器写出的前两帧已验证可跟踪测点与侵蚀状态。缓存进程按 Engine 已写完的文件逐帧转换，已缓存帧与原动画用 SHA-256 对应，便于中断恢复。真实速度镜头的 180° 快门已用 Cycles 的五次物理时间采样和线性 EXR 合成试渲通过。界面样张已在系统 Chromium 验证；求解开始以前，加速度位置显示短横线。

### 20 ms 检查点

- 从 5 ms 到 20 ms 的 Engine 正常完成 15,064 个循环，墙钟 44 分 20 秒，已写入 686 MiB 原生重启文件。累计最大能量残差 0.2133%。19.0 ms 时方向盘中心至靠背测点的间距为 592.77 mm，相比初始缩短了 5.06 mm。[分段测量表](out/ep02-car-speeds/physics/56kmh-checkpoints.csv)
- 已核对原卡片中左右后座传感器分别为 5000390 和 5000398。CCSA 报告第 14–15 页的曲线按图读数，试验 5677 左后座约 52 g / 52 ms，右后座约 55 g / 37 ms。试验 6221 对应约 45 g / 35 ms 和 48 g / 38 ms。后续用本次同位置传感器分别对照；驾驶座仍独立与 Locey 数据比较。
- 已实测 32 条现有 ElevenLabs 音效。旧金属声的开头有 205 ms 接近静音，已裁掉再对齐碰墙帧，防止慢放时拖后约 0.6 秒。用第一集画面检验本集混音与编码流程，253 帧完整解码，测得 −13.45 LUFS 和 −1.70 dBTP。本集的交付值须用实际剪辑重新测量。[单条素材电平](out/ep02-car-speeds/asset-levels.csv)
- 三帧 CPU 基准均使用实际模型、车身固定相机、1080×1920、Cycles 8 采样及降噪。接近镜头 195.71 秒，0.501 ms 的接触前一帧 212.02 秒，16.001 ms 的加载帧 206.40 秒。含启动与导入的均值为 204.71 秒。按 660 次单曝光粗估约 37.5 小时；实速帧另有五次快门采样。测速时求解器并行运行，Blender 仅用两线程，批量渲染可摊薄启动开销。先保证 56 km/h 两套静帧及 360×640 每侧的真实速度对照，保留 GPU 正式渲染入口。[三帧渲染取样](out/ep02-car-speeds/studies/56kmh-render-benchmark.jpg)

### 56 km/h 全时程测量

56 km/h 已算完 140 ms。驾驶座 CFC 60 峰值 60.66 g，碰墙后 47.30 ms 到峰，最大能量残差 6.42%。脉冲结束 68.01 ms，首次纵向速度过零 53.90 ms。全局沙漏能 / 内能最大值 0.00%。逐零件 HE 含壳单元的数值稳定阻尼，923 个通道求和后除以全局内能，最大值为 5.55%。能量残差在接触后约 53.0 ms 首次超过 5%。持续时间按实际 139.30 ms 窗口近似。[曲线与通道](out/ep02-car-speeds/physics/)

### 驾驶舱建模

- 原构图直接画出了碰撞模型的支架和简化壳面，旧门板背筋、裸露轮芯、仪表空腔和脚舱开口在近景里很明显。按频道主的新优先级，先完成可编辑的驾驶舱静态场景。
- 从 CCSA 下载并核对 2016 年 10 月发布的精细版 v2j。SHA-384 与官方一致，`f68913788cbe520709323f76214054f16bdbeeb2b7ddd6dad3f4defccb15a2b6e9df62d50146d17809e4155a786082c7`。读入 1,488,581 个节点、1,254,993 个壳、259,792 个实体、4,802 个梁和 940 个零件，三类单元合计 1,519,587，与 CCSA 公布数量一致。[官方模型](https://www.ccsa.gmu.edu/models/2010-toyota-yaris/)
- 展示场景保留 474 个相关原壳件和零件编号。方向盘包覆、喇叭盖、仪表、中控面板及叶片、门板外皮、手排饰件、脚舱和顶棚均可在 Blender 内单独编辑。制作中用三个机位抽查了仪表台及以下的首个可见表面，修复了旧模型里从脚舱看到路面、轮辋和清洗液壶的开口。[副驾驶方向的静态近景](out/ep02-car-speeds/cabin/passenger.jpg)
- 工程位于 `work/cabin-model/ep02-cabin.blend`。模型的重建脚本和静帧随分支交付。命令为 `bash scripts/build_ep02_cabin.sh --width 1500 --samples 40`。驾驶舱展示采用未变形状态，饰件暂未绑定到粗网格求解历程。
- 中控两侧已延伸至原仪表台下方，补齐上沿和仪表罩接缝。已检查五张最终静帧，驾驶位为 1080×1920，中控为 1500×1275，副驾驶、方向盘和全舱为 1500×1020。独立 Blender 进程重开工程，读取到 5 台相机和 29 组共 448 个饰件对象，外部资源缺失数为 0。已实测移动和还原方向盘包覆件的网格顶点，并从重开的工程渲出驾驶位小样。[最终图库](out/ep02-car-speeds/cabin/)

### 56 km/h 总能量独立复核

逐段读取全部 1,400 个原生历程样本。此版本转换器将全局第 23 通道标为 `NO NAME`。按对应版本 Engine 的写出公式，复算值与该直接通道最大只差 0.11 J。初始为 156.877 kJ，末帧为 166.932 kJ，最大漂移 6.41968%，出现在仿真起点后 108.600 ms。各重启段终端打印的 ERROR 范围为 −1.8% 到 +0.1%，该公式的分子不含接触能，且每次启动采用本段初值。完整时间历程仍超出 5% 验收线。[原生能量写出](https://github.com/OpenCourant/OpenCourant/blob/cb760c206e346eff12161a2268b134ef9d48a4ef/engine/source/output/th/hist2.F#L315) · [终端 ERROR 公式](https://github.com/OpenCourant/OpenCourant/blob/cb760c206e346eff12161a2268b134ef9d48a4ef/engine/source/output/ecrit.F#L499)

已核对 mm、s、t 单位和两个 x=50 mm 的有限壁面，壁面摩擦系数均为 0.6。自接触转换后的系数为 0.1 + 0.1 exp(−0.001 v)，与原输入的静摩擦 0.2、动摩擦 0.1 和衰减 0.001 相符。末帧接触能为 14.204 kJ，其中摩擦为 13.122 kJ。计入四个地面和两个正面壁障后，纵向冲量与全局动量变化的差额为 1.49 N·s，相对正面壁障冲量约 0.0063%。这些结果排除了简单的漏加纵向反力和摩擦常数误读，尚不能把能量增量归因于某一个接触或材料。保持原参数。[复算数据](out/ep02-car-speeds/physics/56kmh-energy-audit.json)

CCSA 验证报告第 18 页还给出了同款四门轿车的整墙反力。按图每 1 ms 读取一次，5677 实车的主峰约 530 kN / 26 ms，CCSA 原版 LS-DYNA 的主峰约 594 kN / 43 ms。本次两段前壁反力之和经 CFC 60 滤波为 624 kN / 44.6 ms。原版有限元的晚峰在移植前就已存在，移植工况的晚峰又高约 30 kN。原图时间取自图轴，本次以首次采到正面墙力为零。报告未在图上给出滤波参数，逐点数据为近似读图，不能当作原始仪器记录。[整墙反力对照图](out/ep02-car-speeds/physics/56kmh-wall-reference.png) · [读图数据](out/ep02-car-speeds/physics/56kmh-wall-reference.csv)

### 驾驶舱运动绑定

已将 474 个精细版壳零件与 448 个外观饰件绑定到 v1l 的原生节点运动。重开 Blender 并校准 PC2 的起始帧后，从首帧到第 281 帧抽查了六个时刻，五个零件在这些帧中与烘焙坐标逐点一致，风挡也按求解状态隐去了细面。完整工程在 `work/cabin-motion/timeline/`。另有头部与固定机位各六张诊断静帧。该工况的方向盘中心到靠背间距最多缩短 8.64 cm。饰件运动是基于同零件支承的重建。[双机位静帧、工况限制与测量](out/ep02-car-speeds/cabin/motion/)
