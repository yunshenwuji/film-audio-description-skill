# 更新日志

简体中文 | [English](CHANGELOG.md)

本文件记录所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 和[语义化版本](https://semver.org/lang/zh-CN/)。

## [0.6.0] - 2026-11-03

### 新增

- 新增 merge_draft.py：从分段 cue 构建规范事实源 `script/merged-draft.json`（逐条带 `derivation` 出处、覆盖并集、互压检测），`merged_edits` 护栏防止未编辑稿被静默重建。
- 新增 converge_identities.py：应用协调者身份映射，吸收 provisional id，按掩码优先顺序改写标签，登记带校验的 `label_variants`，生成 `qc/identity-convergence.json`（单 `review_range` 或并集覆盖批次的 `review_ranges` 分块）。
- 新增 optimize_placement.py：在合并稿上按“先移动、再缩短、最后提语速”顺序落位并记录每次尝试。
- 新增 continuity_editor.py：按 cue id（绝不按排序位置）应用可审计的改写/删除/移动。
- 新增 contact_sheet.py：基于 Pillow 的带标签联络表（避开 FFmpeg `drawtext`/`pattern_type glob` 兼容性陷阱）。
- 新增 segment_brief.py：从工作包生成不含 sha 的紧凑代理简报。
- 新增 merge_bible.py：`collect`/`apply` 把分段 bible 提案合并为规范 bible 文件。
- init_project.py 新增 `--script-only`（仅出稿输出），问卷新增交付形态题。
- audit_project.py 新增按 mtime+size 的哈希缓存（`qc/hash-cache.json`），不再每次全量重读几 GB 源文件。
- prepare_segment.py 现在校验 `segment-NNN` 命名、把近尾采样钳制到最后可解码帧之前（ffprobe）、末采样失败自动前移重试、`--force` 重建时清理孤儿帧、并把 bible 快照规范化为对象带键形状。
- finalize_segment.py 现在校验段 id、透传 `displacement_justification` 并在位移超标时告警。
- 所有内置脚本把 stdout/stderr 重配置为 UTF-8，适配 Windows 控制台。

### 变更

- `script/merged-draft.json` 成为规范脚本工件：审计对合并 cue 检查对白重述、总结漂移、位移、字幕卡匹配、身份标签与审稿文件对齐，分段文件保持为只读证据层；合并 cue 必须带 `derivation` 出处。
- 密度漂移闸门改用叙事分段中位数做基准，片头/片尾字幕段豁免漂移比较。
- 证据回收判定只罚同主体复用；一帧多主体可按主体分别建观察。
- `first_speech_once` 模式下主要人物必须建立 `first_spoken_line_time` 或留 `speech_evidence_reviewed` 记录，静默省略视为审计失败。
- 已登记 `label_variants` 残留在 cue 文本中产生审计警告；过短或泛称变体在收敛时被拒绝。
- bible 文件统一为对象带键顶层形状；init/merge_bible 写入新形状，prepare 做规范化，审计仍兼容旧列表。
- 收敛报告允许以 `review_ranges` 分块覆盖单个审稿批次（分块必须连续，内部空洞会被审计拦截）。
- 审稿阶段审计报错附带修复提示；新增 `scene_table_too_fine` 警告防场景表过细。
- 对下游消费者的契约变更：审计报告 schema_version 升至 3；全部脚本 stdout/stderr 重配置为 UTF-8（旧代码页下的 subprocess 消费者请设 PYTHONIOENCODING=utf-8）。
- optimize_placement.py 实际执行“先移动、再缩短、最后提语速”；拆分是协调者的语义判断，经 continuity_editor.py 手动执行，不再自动发明。
- 首说话身份分层闸门（character_speech_timing_unestablished）只在审稿阶段强制执行。

### 修复

- 非 `segment-*` 命名的分段不再被审计静默跳过——工具在打包入口直接拒绝。
- 合并稿编辑不再需要脆弱的回写步骤，也不再误报 `review_srt_text_or_id_mismatch`。
- `displacement_justification` 在整条管线中可表达，不再只存在于审计代码里。
- 重打包加密度后的孤儿帧会被清理，不再污染按目录 glob 的下游。
- 末采样抽取不再让 FFmpeg mjpeg 编码器在文件尾崩溃。
- 2 分钟的片头字幕单元不再抬高全片漂移基准、逼片尾滚动区灌覆盖记录。
- 修复末采样重试路径写到旧文件名后读取不存在路径的崩溃：重试帧先改名再入索引。
- 修复掩码替换在被引用人物的标签互为子串时（如 衬衫男人/花衬衫男人）串号：所有标签按长度全局降序掩码。
- 修复被吸收的 provisional id 残留在 cue subject_character_ids：收敛时原位改写成 canonical id。
- 修复 merge_bible apply 先写后验：孤儿校验通过前不再覆盖规范 bible。
- 修复收敛范围闸门放过内部空洞，审计新增 nonstandard_segment_directory 告警而非静默忽略非标目录。
- 修复哈希缓存忽略 ctime、提语速路径 review_duration/available_slot 不同步、联络表索引忽略 --timestamps 覆盖值。

### 验证

- 新增管线工具测试（合并出处、掩码收敛、落位顺序、简报、bible 合并、连贯性编辑）与新审计闸门测试（中位数漂移、同帧不同主体、出处、变体、收敛分块、说话人分层、哈希缓存、过细场景表）。

## [0.5.0] - 2026-11-01

### 新增

- 新增 prepare_segment.py：选择分段镜头、截取对白上下文、快照 Bible、抽取并散列证据帧，生成可直接分析的工作包。
- 新增 finalize_segment.py：把精简分析展开成标准 manifest、观察、口述、证据提案和 Bible 提案，并自动计算对白交集。
- 新增 analysis-input.json，作为分段代理正常情况下唯一需要编辑的文件。
- 每个审稿批次必须完成人物身份收敛，合法结果为 confirmed、not_yet_revealed 或 unresolved_after_evidence_review。
- 涉及人物的口述通过 subject_character_ids 引用统一人物 ID。

### 变更

- 中性称呼只作为分析脚手架；达到允许揭晓时间后，审稿稿件必须使用正式姓名，仍无法确认时必须向用户公开疑问。
- 协调者生成审稿 SRT 前必须合并重复临时 ID、别名、安全称呼和证据轨迹。
- awaiting_user_review 会冻结后续工作包和分析波次，直到当前批次获批或修正被吸收。
- 分段代理专注看片和写作，不再编写 FFmpeg、哈希、格式拼装或 JSON 生成脚本。
- 覆盖审计严格裁剪到当前审稿批次；没有当前批次时，使用已完成分段范围。
- 观察空白检查先合并真实起止区间，再寻找未覆盖时间。

### 修复

- 修复分批审稿时检查当前批次以外镜头的问题。
- 修复只比较观察起点，导致长观察被误判为中间空白。
- 修复人物已确认并达到允许揭晓时间后仍使用过期中性称呼。
- 修复重复或临时人物记录进入审稿 Bible。
- 修复分段代理创建一次性程序；未登记的分段可执行文件现在会导致审计失败。

### 验证

- 测试扩展至 19 项并全部通过，包括分段工具、身份收敛、审稿范围、跨界镜头和长区间回归测试。

## [0.4.0] - 2026-11-01

### 新增

- 将标准 SRT 设为主要审稿件，并新增确定性生成器和证据映射。
- 支持只有影片、验证后的外部字幕、演员角色表、对白脚本、定妆照和人物参考图等材料组合。
- 新增材料来源与哈希、视觉证据索引、批准记录、对白事件、试听记录、duck 包络和可复现音频测量。
- 新增项目级证据、场景、对白相似度、摘要漂移、Bible、合并范围和状态审计。

### 变更

- 验证合格的外部 SRT 可替代重复完整转写；人物参考只能加速而不能代替片内绑定。
- 批准同时绑定实际审阅的 SRT 和对应合并 cue 文件。
- 对白重叠由真实口述可听区间自动计算。
- 最终 QC 必须有试听、duck 包络和原声/成片测量，不能只检查容器。

### 修复

- 防止任意时间戳、重复帧、未验证字幕、无标签照片、自写批准和模型自称试听被当成证据。

## [0.3.0] - 2026-11-01

### 新增

- 新增对白避让和混音规则、有限时间中文压缩、片内身份依据，以及片头片尾硬覆盖要求。
- 新增公司名、片名、“演员饰角色”和其他主创字幕清单。

### 变更

- 与对白冲突时依次尝试邻近空隙、改写、拆分和实测调速，最后才允许有限覆盖。
- 人名、数字、线索、笑点、耳语、情感台词和行动命令受到保护。

### 修复

- 防止用户选择的片头片尾被静默省略、防止外部常识直接确定身份、防止过长 duck 尾巴持续压低原声。

## [0.2.0] - 2026-11-01

### 新增

- 新增视觉证据优先观察、口述证据关联、防摘要门禁和确定性项目审计。
- 新增 8–15 分钟按场景分析段，并与约 20 分钟审稿批次区分。
- 新增覆盖、对白复述、摘要措辞、密度漂移、Bible、合并范围、空分段和批准状态检查。

### 修复

- 防止稀疏抽帧和嘈杂 ASR 退化成剧情摘要。
- 防止把已由声音表达的广播、任务和因果解释重新口述。
- 防止把固定审稿批次当作粗分析单元。

## [0.1.0] - 2026-10-31

### 新增

- 初始开源的交互式影视口述影像技能。
- 新增自适应问卷、短片/长片路径、结构化项目、长片编排和 TTS/混音前强制批准。
- 新增自然神经语音、动态语速、独立口述母带、cue/成片检查、临时渲染，以及只在口述期间压低原声的规则。
- 新增中英文文档、MIT 许可证、安装说明和推荐工具链。

说明：最初公开版本没有标签；正式发布标签从 v0.2.0 开始。

[0.5.0]: https://github.com/wangru2025/film-audio-description-skill/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/wangru2025/film-audio-description-skill/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/wangru2025/film-audio-description-skill/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/wangru2025/film-audio-description-skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/wangru2025/film-audio-description-skill/commit/b45d22a
