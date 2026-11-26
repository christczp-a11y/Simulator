# 每集固定十步工作流（最高优先，必须照做）

1 选题写故事 → 2 ElevenLabs 旁白 → 3 Whisper 逐词时间 → 4 角色造型 → 5 three.js 预演并自检到没毛病 → 6 造 3D 世界（无逻辑错误）→ 7 渲染 → 8 ElevenLabs MCP 音效（压在旁白之下）→ 9 Remotion 字幕 → 10 全部组装。
每步的工具、产出、停下等 Chris 的关口和自检全文见 WORKFLOW.md（下一行自动载入；正本在 Chris 电脑 C:\YouTubeNeuropolis\WORKFLOW.md）。第一条回复要说明本集现在在第几步。本机有闸门 hook 强制执行，云端会话没有闸门，更要自觉照做。
**卡通风格（新风格，11-26 起）**：开工先加载技能 toon-style（只在 Chris 电脑上有）；所有已定规矩汇总在交接文件第十六节。

@WORKFLOW.md

# 开工必读（每个新会话先做，不许跳过）

1. 先读 next-episode-brief.md 全文（仓库根目录，下面最后一行会自动载入），和频道制作指南 https://claude.ai/artifact/8q1ada16EKEkmmgW33xHBo （迭代记录表 + 「渲染预算」一节）。
2. 第一条回复里列出本集要落实的条目（引用文件里的编号）。
3. 开渲前报全片估算（单帧耗时 × 帧数）。超过 1 小时不开渲，先找 Chris。单帧超过 2 秒的镜头当场改做法。
4. 每集结束把「留下的教训」补进这两份文件。
5. 不动 api-keys.env、harbor-radio、SHORT 里的私人视频；装任何东西先问 Chris。
6. Chris 说「结束会话」时：先自动总结本集的修改和提高，写进频道制作指南（第一节迭代表补一行，相关章节更新规则），同步到 next-episode-brief.md，再结束会话。

注意：交接文件的正本是 Chris 电脑上的 C:\YouTubeNeuropolis\Out\next-episode-brief.md；仓库根目录的 next-episode-brief.md 是副本。谁改了其中一份，就同步另一份（云端会话改仓库副本并提交推送到 main，本机会话再拉下来同步回 Out\）。

@next-episode-brief.md
