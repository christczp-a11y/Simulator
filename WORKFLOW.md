# 每集固定工作流（Chris 2026-11-26 定，必须遵守，不许跳步、不许换顺序）

十步按顺序做。每一步开头先加载这一步写的技能，结尾交出“产出”，标了 **停** 的地方必须等 Chris 点头才能进下一步。
本集文件夹 `Out\epNN-名字\`，下面的路径都相对它。每步做完更新本集网页墙。细则见频道制作指南和 `Out\错题本.md`。

| # | 步骤 | 必须用 | 产出 | 关口 |
|---|---|---|---|---|
| 1 | 选题、写故事 | 网上核实；空间事实（谁在哪侧、往哪走）至少两个机位或两个来源互证 | `story.md`（故事 + 事实表，每个数字带来源，没公开的标 ILLUSTRATIVE）| **停** |
| 2 | ElevenLabs 做旁白 | ElevenLabs MCP（未连上就先问 Chris）；声音 Daniel - Steady Broadcaster | `vo\` 旁白音频；稿子念一遍删重复词 | |
| 3 | Whisper 逐词时间 | Whisper（word timestamps）| `vo\words.json`（每个词的起止时间）；按它排 `shots.csv` 镜头表：每 2–3 秒换画面，5–8 秒一个转折，前 3 秒是钩子 | **停**：旁白 + 镜头表给 Chris |
| 4 | 角色、造型 | Skill：blender-core → blender-character-rigging / blender-clothing → blender-asset-qa；现成模型优先（带真服装，不许光身人体刷颜色）| `chars\` 每个角色正、侧、背三视图 | **停** |
| 5 | three.js 预演 | three.js（浏览器里跑，简单体块按真实尺寸）| `previz\index.html`：每个镜头的物体路线和相机怎么走，时间轴对齐 `words.json`；`previz\shots.json`（相机和物体轨迹，第 6 步 Blender 直接读）；`previz\selfcheck.md` 自检记录 | **停**：自检改到没毛病再给 Chris |
| 6 | 造 3D 世界 | Skill：blender-core、blender-scene-setup、blender-pbr-materials、blender-lighting-lookdev、blender-environment-kits，交前跑 blender-asset-qa | 按 `previz\shots.json` 搭场景；每镜一张风格帧 + 单帧耗时；逻辑检查（见下）| **停** |
| 7 | 渲染 | Skill：blender-rendering；Colab | 开渲前 `render_estimate.md`：每镜测 1 帧 × 帧数，全片 ≤ 1 小时 | **停**：估算给 Chris，点头才开渲 |
| 8 | 音效 | Skill：sound-effects + ElevenLabs MCP（不许自写脚本打 API）| `sfx\`：只给画面里看得见的东西配声，每种 3 版测频谱挑；混音时**音效在旁白之下**：有旁白时音效比旁白低 10–12 dB（自动压低），没旁白时回到正常 | |
| 9 | 字幕 | Remotion | 字幕时间用 `words.json`；Shorts 安全区；一句只淡入一次不许闪；真字体量宽不许出画 | |
| 10 | 全部组装 | Remotion | 成片（-14 LUFS，峰值 ≤ -1.5 dBFS）+ 手机版 < 20 MB + 缩略图 + 发布文案 + README；交片前按错题本逐条自查 | **停**：交 Chris |

## 第 5 步自检（预演必须查完这些，有一条不过就改，改完重查）
1. 空间关系：谁在左、谁在右、谁在前，路线方向和事实表一致；出一张俯视图对照。
2. 比例：车、人、道具按真实尺寸；人和车没有穿模、没有悬空、没有陷进地面。
3. 镜头：主体在画面里、没被挡、不出画；字幕区（y 1180–1400）和 Shorts 界面遮挡区没压到关键内容。
4. 时间：每个镜头起止对上 `words.json` 里那句话；单个画面不超过 3.5 秒；前 3 秒有动作和危险感。
5. 逻辑：因果先后对、物理方向对（车往哪飞、影子朝哪）。
自检记录写进 `previz\selfcheck.md`：每条“过 / 改了什么”。

## 第 6 步逻辑检查
错题本第一类（空间关系和比例）逐条过；光三关（材质反射、光有设计、近景经得起放大）；blender-asset-qa 报告零问题才出风格帧。

## 卡通风格（toon\，11-26 从 ricksclips 风格包引入）每步用哪个工具
这十步就是照这个风格包的流程定的。卡通风格的项目放在 `toon\projects\<名字>\`；风格和质量标准是 `toon\RULEBOOK.md`（英文，和十步冲突时以十步为准，见 `toon\CLAUDE.md` 开头）。
| 步 | 工具 |
|---|---|
| 1 | `toon\docs\02_SCRIPT_WRITING.md`、`03_HOOK_WRITING.md`：一个人、一个诡计、一个反转；三段式钩子 |
| 2 | ElevenLabs（MCP 优先），一条只录一次，先报花费；`tools\tighten_voice.py` 只剪静音，不许剪到字 |
| 3 | `python tools\timing.py voice.wav script.txt --out work`（Whisper，CPU）→ `work\words.json` |
| 4 | `characters\rick.js` 画 2D 角色卡；每集新角色，先出设计稿 |
| 5 | 网页引擎 `story.js` 排镜头和相机；`node render_pc.mjs`（Edge 显卡，约 0.5 秒/帧）出每镜中间一帧拼总览；`tools\study\qa_motion.py` 动态质检必须 PASS |
| 6 | `blender\parts\` 建 3D 场景（卡通材质 + 描边），读引擎导出的 frames.json |
| 7 | `RENDER_BLENDER.bat` 或网页引擎整片渲染（闸门要求先有预演自检和渲染估算）|
| 8 | ElevenLabs MCP 音效：约每 10 秒 8 个，比旁白低约 12 dB |
| 9 | Remotion 字幕：画面正中、一次 1–3 个词 |
| 10 | 合成 + 柔光（screen 0.4）+ -14 LUFS；交片前过 RULEBOOK 末尾的检查清单 |

## 闸门（系统自动执行，不靠自觉）
`.claude\hooks\gate.py` 会拦下：
- 没先加载 blender-core 技能就跑 Blender（本机、Blender MCP、Colab）。
- 本集没有 `previz\selfcheck.md` 和 `render_estimate.md` 就开渲整段动画。
- 自写脚本直接调 ElevenLabs 音效接口；没加载 sound-effects 技能就用 MCP 出音效。
