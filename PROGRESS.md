# EP02 制作进度

**停在检查点 1：求解器可以启动，官方车模尚未取得。** 56 km/h 验收、小样和成片均未完成。恢复时先检查 `work/` 里是否已有频道主提供的官方粗网格原包，再尝试下面两个入口。

## 已核实

- 基线提交 `46a0e60`，工作分支 `ep02-car-speeds`。第一集预览已用 FFmpeg 验证完整解码，并抽看从进场到结束卡的时间序列。文件实际是 1080×1920、30 fps，视频长 23.67 秒。倒计时和数据位于上方暗区，实速回放之后切黑再到网点结束卡。
- 本实例 `nproc` 为 5，cgroup CPU 配额为 4 核，内存上限 32 GiB，无交换空间。开始时可用磁盘约 60 GiB。未发现 NVIDIA 设备、DRI 设备或 nvidia-smi。按 CPU 渲染准备，尚无真实场景可做三帧基准。
- 复用预装 Blender 4.3.2（系统包 4.3.2+dfsg-2），可执行文件 SHA-256 为 `0dfe9af0f3e67643ecf15327fa5e14e7315f61d1a81afdcafe76a71b1918e2b4`。
- OpenRadioss 原仓库的 latest release 页面本次返回 404；这不足以确认关停原因或日期。OpenCourant 官方 latest 指向稳定构建 `latest-20261011`，下载 Linux x86-64 ZIP 到 `work/`。本机 SHA-256 与发布页一致，均为 `6cb419677ca36d73acb96218cc0cf5e4f7d50494d9c7812ba27935e3c0f8ec94`。Starter 报告源码提交 `cb760c206e346eff12161a2268b134ef9d48a4ef`。Starter 和 OpenMP Engine 均通过版本启动检查。[官方发布页](https://github.com/OpenCourant/OpenCourant/releases/tag/latest-20261011)
- 没有发现名称含 ELEVEN 的环境变量。本次未调用音效 API。

## 车模下载断点

[CCSA 粗网格所在页](https://www.ccsa.gmu.edu/models/2010-toyota-yaris/) 和 [NHTSA 镜像入口](https://www.nhtsa.gov/crash-simulation-vehicle-models) 在本实例通过代理的 CONNECT 请求均收到 403，授权重试也收到 403。没有拿到 ZIP，版本、散列、包内条款均待查。已将两个官方域名加入云环境配置草稿，生效前需在环境设置里审核、保存并发布；若官方下载另有重定向，再核对实际目的地。

## 恢复顺序

1. 在 `work/` 保存官方原包、最终下载 URL 和 SHA-256。核对包内条款、主文件和碰撞工况，检查坐标方向、单位制、试验配置及各输出测点。独立核对零件、节点、壳、实体、梁及总质量；现有解析脚本还不统计梁和整车质量。
2. 从仓库根目录执行下面的环境设置。先做 56 km/h 的 5 ms 试算，记录墙钟时间和磁盘占用，据此估算四档预算。现阶段没有实测耗时。
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
