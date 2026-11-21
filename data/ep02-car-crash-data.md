# 第二集（各种速度撞车）数据采集

整理时间 2026-11-20 上午。只收了我读到原文的数字；标"计算值"的是我用公式算的；标"没查到"的就是没查到。

## 1. 同一辆车、三个速度的真实碰撞试验（最有用的一组）

IIHS、AAA 交通安全基金会、Humanetics 联合做的。2019-10-28 到 30 日试验，2021-01-28 发布。
车：三辆 2010 款 Honda CR-V EX。方式：驾驶侧 40% 偏置正碰。假人：Hybrid III 50 百分位男性。

| | 40 mph（64 km/h） | 50 mph（80 km/h） | 55.9 mph（90 km/h） |
|---|---|---|---|
| 动能（相对第一档） | 基准 | +56% | +95% |
| 乘员舱 | 几乎没有侵入 | 门框、仪表台、脚部空间明显变形 | 门框收窄 4 英寸，舱内侵入比第一档多 5 到 16 英寸 |
| 方向盘位移 | 前 1 英寸、上 1 英寸 | 后 1 英寸、上 4 英寸 | 后 3 英寸、上 7 英寸 |
| 气囊 | 正常 | 头穿过气囊撞到方向盘 | 同左 |
| 面部骨折和严重脑损伤风险 | 没给 | 52% 到 67%（两档合并给的区间） | 同左 |
| 严重颈部损伤风险 | 没给 | 没给 | 19% |
| 综合重伤及以上风险 | 15% | 59% | 78% |

要点：速度只加了 40%，重伤风险从 15% 到 78%。这就是这一集的故事线。

## 2. 56 km/h 正面全宽撞刚性墙的减速度曲线（校准用）

Locey 等 2012，1,094 辆 2000 到 2010 年款车，NHTSA 和加拿大运输部的试验。

| 车型 | 峰值减速度 g | 峰值出现时刻 ms | 整个过程 ms |
|---|---|---|---|
| 小型车 | 43.5 | 47.5 | 91.3 |
| 中型车 | 40.6 | 51.5 | 98.7 |
| 大型车 | 38.1 | 54.6 | 105.7 |
| 小型 SUV | 46.0 | 42.7 | 90.8 |
| 中型 SUV | 43.9 | 44.0 | 98.0 |
| 大型 SUV | 40.0 | 51.9 | 112.9 |
| 小皮卡 | 42.7 | 38.2 | 97.2 |
| 大皮卡 | 39.9 | 43.3 | 109.3 |
| MPV | 36.6 | 50.5 | 111.8 |

逐车型的数是从论文表格里转述的，范围（36.6 到 46.0 g，90.8 到 112.9 ms）是论文原文。
计算值：56 km/h 是 15.6 m/s，100 毫秒停下来，平均约 16 g，车头压掉约 0.78 m。
对比第一集：飞机是 342 km/h、峰值 521 g。汽车正常碰撞试验是 40 g 上下、0.1 秒。

## 3. 速度和能量（计算值，公式 E = ½mv²，等效坠落高度 h = v²/2g）

| 速度 km/h | 动能（56 km/h 为 1） | 相当于从多高掉下来 |
|---|---|---|
| 30 | 0.29 | 3.5 m |
| 56 | 1.00 | 12 m（约 4 层楼） |
| 64 | 1.31 | 16 m |
| 80 | 2.04 | 25 m |
| 90 | 2.58 | 32 m（约 10 层楼） |
| 120 | 4.59 | 57 m |
| 160 | 8.16 | 101 m |
| 200 | 12.8 | 157 m（约 50 层楼） |

## 4. 伤亡风险和速度变化量

Funk、Cormier、Gabler 2008，美国 NASS-CDS 1997 到 2006 年 11,483 例正面碰撞（89% 系安全带）。
速度变化量约 50 km/h 时：中度以上伤约 50%，重伤以上约 25%，死亡约 5%。
同一篇指出事故数据库里的速度变化量平均比行车记录仪低 19%，所以真实风险对应的速度更高一些。
其他速度点的风险只在论文图里，文字没给，我没读到。

## 5. 高速碰撞的实拍（没有可用数字）

Fifth Gear 2011 年把一辆旧款 Ford Focus 以 120 mph（193 km/h）撞向不可移动的障碍。
我读到的报道只说"彻底毁坏"，没有减速度、压溃长度、时间这些数字。没查到更多。
也就是说 90 km/h 以上没有公开的定量试验数据可以对，超过这个速度的画面只能算外推，片里要写明。

## 6. 公开的整车模型（不用自己建车）

美国 NHTSA 委托乔治梅森大学 CCSA 做的整车有限元模型，公开下载，LS-DYNA 格式。

| 模型 | 质量 | 规模 | 下载大小 | 算 200 ms 要多久 |
|---|---|---|---|---|
| 2010 Toyota Yaris 粗网格 | 1,078 kg | 919 个零件，358,457 个壳单元 | 11.2 MB | LS-DYNA、16 核，1 小时 32 分 |
| 2010 Toyota Yaris 细网格 | 1,078 kg | 150 多万单元 | 40.2 MB | 没给 |
| 2012 Toyota Camry 细网格 | 1,452 kg | 1,086 个零件，2,257,280 个单元 | 58.5 MB | 120 ms、16 核约 11 小时 |

- Yaris 粗网格对过的实车试验：正面全宽撞墙 NHTSA 5677（56.3 km/h）、6221（56.2 km/h）、6069（39.8 km/h），偏置 IIHS CEF0610（64.7 km/h），还有侧碰。
- NHTSA 页面上还有 Silverado、Explorer、Taurus、Accord、Caravan、F-250、Neon、RAV4 等。
- 使用条款：这几个页面上没写。发布前要再查一次，片里不出现车标和车名比较稳妥。
- 开源求解器 OpenRadioss 的官方文档有"Yaris/Camry Impact Model in LS-DYNA format"的例子页（页面要登录，我没读到内容）。第三方实测（CIQ 2022）：Camry 细网格在 i7-12700 上用 8 个进程跑了约 15 到 22 小时，内存约 13 GB，结果转成 VTK 用 ParaView 看。
- 云端下载不了：ccsa.gmu.edu、nhtsa.gov、github.com 都被这边的网络策略挡住（403）。

## 7. 同类内容的现状

- BeamNG 是这个题材的主流，速度对比有先例：@oldtenderman 做过 10、30、50、80、120、200、300 mph。
- 它被批评的点（The Drive 2023）：车不是真车的数据，改装模型没有厂家的溃缩区和材料数据。
- 被当成真实试验传播过，需要电视台辟谣（KGW Verify）。

## 来源

- https://www.iihs.org/news/detail/new-crash-tests-show-modest-speed-increases-can-have-deadly-consequences
- https://aaafoundation.org/wp-content/uploads/2021/01/Speed-and-Injury-Fact-Sheet.pdf
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3503406
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3256761
- https://www.autoblog.com/2011/10/20/fifth-gear-crashes-a-ford-focus-at-120-mph/
- https://www.nhtsa.gov/crash-simulation-vehicle-models
- https://www.ccsa.gmu.edu/models/2010-toyota-yaris/
- https://www.ccsa.gmu.edu/wp-content/uploads/2016/11/2010-toyota-yaris-coarse-validation-v1.pdf
- https://www.ccsa.gmu.edu/models/2012-toyota-camry
- https://ciq.com/blog/running-camry-impact-model-in-ls-dyna-format-using-openradioss-and-apptainer
- https://supercarblondie.com/impact-of-crash-varying-speeds
- https://www.thedrive.com/news/no-those-viral-beamng-crash-test-videos-arent-realistic
