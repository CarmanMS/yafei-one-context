# Features index

在新建或归档需求时更新本表。`id` 建议与目录名 `features/<category>/<feature-id>/` 中的 `<feature-id>` 一致（或与 `spec.md` frontmatter 的 `id` 一致）。


| id                            | title                                                 | category | status | path                                              | primary_repo_id |
| ----------------------------- | ----------------------------------------------------- | -------- | ------ | ------------------------------------------------- | --------------- |
| agent-framework               | 智能体框架 — meta/agents.yaml + 适配器扩展 + worktree/deploy 约定 | core     | done   | `features/core/agent-framework/`                  | one-context     |
| auto-context-compression      | 自动上下文压缩 — 定时扫描 knowledge/features 等，去重与去陈旧            | core     | draft  | `features/core/auto-context-compression/`         | one-context     |
| agent-collaboration           | 智能体协作增强 — 状态流转、决策手册、条件知识、生成保护                         | core     | draft  | `features/core/agent-collaboration/`              | one-context     |
| profile-inheritance           | Profile 继承与 Mixin 机制                                  | core     | draft  | `features/core/profile-inheritance/`              | one-context     |
| claudecode-source-analysis    | Claude Code 源码解析知识整理                                  | knowledge | done   | `features/knowledge/claudecode-source-analysis/`    | one-context     |
| openclaw-source-analysis      | OpenClaw 源码解析知识整理                                     | knowledge | done   | `features/knowledge/openclaw-source-analysis/`      | one-context     |
| claude-caveman-mode           | 用穴居人模式让 Claude 省 Token                                | experiments | done   | `features/experiments/claude-caveman-mode/`           | one-context     |
| math-teacher-ai-platform      | 数学教师 AI 工作台 — Phase 1 可视化资产化与 AI 出题 MVP          | products | draft  | `features/products/math-teacher-ai-platform/`      | FunctionCanvas  |
| one-context-intro-short-video | one-context 中视频介绍（爆款口播框架）                             | content-pipeline  | archived | `features/content-pipeline/archive/one-context-intro-short-video/` | one-context     |
| hermes-agent-short-video      | Hermes Agent 短视频口播成片（wav-auto）                          | content-pipeline  | archived | `features/content-pipeline/archive/hermes-agent-short-video/`      | one-context     |
| anthropic-agent-harness-narration | Anthropic Agent Harness 哲学 — 口播稿                         | content-pipeline  | archived | `features/content-pipeline/archive/anthropic-agent-harness-narration/` | one-context |
| anthropic-ai-blueprint-dialogue-mid-video | Anthropic AI 公司蓝图对话拆解（中视频） | content-pipeline | archived | `features/content-pipeline/archive/anthropic-ai-blueprint-dialogue-mid-video/` | one-context |
| anthropic-boris-engineering-future-mid-video | 当顶尖工程师不再写代码：AI 重写软件开发未来（对话口播） | content-pipeline | archived | `features/content-pipeline/archive/anthropic-boris-engineering-future-mid-video/` | one-context |
| ai-agent-security-2026-revelations-mid-video | 2026 AI Agent 安全启示录（对话口播） | content-pipeline | archived | `features/content-pipeline/archive/ai-agent-security-2026-revelations-mid-video/` | one-context |
| claude-code-multi-agent-source-mid-video | Claude Code 多 Agent 机制源码解读（中视频口播） | content-pipeline | archived | `features/content-pipeline/archive/claude-code-multi-agent-source-mid-video/` | one-context |
| openai-enterprise-ai-scaling-five-actions-mid-video | OpenAI 企业 AI 规模化落地五要点（中视频口播） | content-pipeline | archived | `features/content-pipeline/archive/openai-enterprise-ai-scaling-five-actions-mid-video/` | one-context |
| markdown-html-claude-engineer-mid-video | Markdown 要被淘汰？Claude 工程师弃用真相（阿哲 / 小夏 对话口播） | content-pipeline | archived | `features/content-pipeline/archive/markdown-html-claude-engineer-mid-video/` | one-context |
| damai-ticket-bot              | 大麦抢票助手 — 浏览器插件 + CLI 集成 one-context skill                 | integrations | draft  | `features/integrations/damai-ticket-bot/`              | one-context     |
| operator-spaces-paper-analysis | 算子空间论文深度分析 — 发现证明漏洞与改进机会 | research | in_progress | `features/research/operator-spaces-paper-analysis/` | paperwork |
| pdf-math-exam-to-latex-skill-survey | 数学试卷 PDF → LaTeX 能力调研（Skill / 工具 / 开源） | research | in_progress | `features/research/pdf-math-exam-to-latex-skill-survey/` | one-context |
| voice-assistant-windows-cursor-cli-survey | Windows 端类小爱同学语音助手方案调研（语音唤醒 + 对话/命令经 Cursor CLI） | research | draft | `features/research/voice-assistant-windows-cursor-cli-survey/` | one-context |
| skill-windows-c-drive-cleanup | Windows C 盘空间清理 — 仓库内 Agent Skill                     | core     | done   | `features/core/skill-windows-c-drive-cleanup/`    | one-context     |
| skill-merge-to-main           | 选择性合并到主干（Agent Skill）                                  | core     | done   | `features/core/skill-merge-to-main/`               | one-context     |
| skill-script-deck-audit       | 口播稿与幻灯一致性校验（Agent Skill）                              | core     | done   | `features/core/skill-script-deck-audit/`           | one-context     |
| unified-adapter-rules         | 统一适配器规则源 — 声明式 manifest，消除 PROFILE_RULES 重复          | core     | done   | `features/core/unified-adapter-rules/`            | one-context     |
| skill-loop-engineering        | Loop Engineering Skill — 引导式构建可循环任务的脚手架            | core     | draft  | `features/core/skill-loop-engineering/`           | one-context     |
| skill-retrospective-evolution | Skill 跨会话回溯进化 — 从历史会话语料聚合诊断单个 Skill 并产出改进 PR | core     | phase1-done | `features/core/skill-retrospective-evolution/`    | one-context     |
| ai-mid-mgmt-video             | AI 中视频管理 — 素材与发布工具链                                       | content-pipeline  | archived | `features/content-pipeline/archive/ai-mid-mgmt-video/`             | one-context     |
| hermes-adapter                | Hermes Adapter — one-context 支持 Hermes Agent CLI                     | core     | draft  | `features/core/hermes-adapter/`                   | one-context     |
| gsd-integration               | GSD 集成 — one-context 上下文注入 GSD 工作流                              | core     | draft  | `features/core/gsd-integration/`                  | one-context     |
| trend-radar-integration        | TrendRadar 趋势雷达集成 — 热点情报 + MCP + 微信推送                         | integrations | in_progress | `features/integrations/trend-radar/`      | trend-radar    |
| short-video-reporting-paradigm | 短视频式汇报范式 — 用内容创作思路重塑职场汇报                             | content-pipeline | archived | `features/content-pipeline/archive/short-video-reporting-paradigm/` | one-context |
| ai-sme-opportunity             | 放下大厂滤镜：中小厂的 AI 机会（中视频）                                              | content-pipeline | archived | `features/content-pipeline/archive/ai-sme-opportunity/` | one-context |
| sandbox-agent-era-mid-video    | Agent时代下最被低估的技术——沙箱（中视频口播）                    | content-pipeline | archived | `features/content-pipeline/archive/sandbox-agent-era-mid-video/` | one-context |
| deepseek-v4-deploy-guide-mid-video | DeepSeek V4 部署与调用指南（中视频）                        | content-pipeline | archived | `features/content-pipeline/archive/deepseek-v4-deploy-guide-mid-video/` | one-context |
| agent亲和架构底层原理剖析 | Agent 亲和架构底层原理剖析（口播视频） | content-pipeline | archived | `features/content-pipeline/archive/agent亲和架构底层原理剖析/` | one-context |
| 软件中一切皆Worker | 软件中一切皆 Worker（口播视频） | content-pipeline | archived | `features/content-pipeline/archive/软件中一切皆Worker/` | one-context |
| claudecode-prompt-caching-mid-video | Prompt Caching Is Everything —— Claude Code 团队最新文章 | content-pipeline | archived | `features/content-pipeline/archive/claudecode-prompt-caching-mid-video/` | one-context |
| claudecode-sandbox-concurrency-mid-video | Claude Code 沙箱与并发机制解析 | content-pipeline | archived | `features/content-pipeline/archive/claudecode-sandbox-concurrency-mid-video/` | one-context |
| keycompute-ai-gateway-rust-mid-video | Rust 构建 AI 算力中枢：KeyCompute 架构解析（中视频） | content-pipeline | archived | `features/content-pipeline/archive/keycompute-ai-gateway-rust-mid-video/` | one-context |
| ai-era-rust-language-mid-video | AI 时代为何 Rust 语言崛起（中视频） | content-pipeline | archived | `features/content-pipeline/archive/ai-era-rust-language-mid-video/` | one-context |
| claude-code-large-codebase-mid-video | Claude Code 大型代码库最佳实践 —— Anthropic 博客深度解析 | content-pipeline | archived | `features/content-pipeline/archive/claude-code-large-codebase-mid-video/` | one-context |
| claude-code-workflows-enterprise-mid-video | Claude Code Workflows：企业 AI 落地（Remotion 技术播客） | content-pipeline | archived | `features/content-pipeline/archive/claude-code-workflows-enterprise-mid-video/` | one-context |
| openhuman-ai-super-assistant-mid-video | OpenHuman爆火口播稿：不用教的AI超级助手来了！ | content-pipeline | archived | `features/content-pipeline/archive/openhuman-ai-super-assistant-mid-video/` | one-context |
| karpathy-autoresearch-software-dev-mid-video | 像 Karpathy 一样开发软件：AutoResearch 全自动多 Agent 交叉审核系统深度解析 | content-pipeline | archived | `features/content-pipeline/archive/karpathy-autoresearch-software-dev-mid-video/` | one-context |
| anthropic-founders-playbook-mid-video | Anthropic 创始人手册：AI 原生创业公司从零到 IPO 全过程拆解 | content-pipeline | archived | `features/content-pipeline/archive/anthropic-founders-playbook-mid-video/` | one-context |
| anthropic-next-gen-claude-eight-tips-mid-video | Anthropic 打造下一代 Claude 的 8 个硬核干货（男女对话中视频） | content-pipeline | archived | `features/content-pipeline/archive/anthropic-next-gen-claude-eight-tips-mid-video/` | one-context |
| anthropic-cfo-ai-revolution-mid-video | Anthropic CFO 播客：两年 120 倍与 AI 革命三道刹车（Remotion 中视频） | content-pipeline | draft | `features/content-pipeline/anthropic-cfo-ai-revolution-mid-video/` | one-context |
| anthropic-how-we-claude-code-mid-video | Anthropic「How We Claude Code」工程实践拆解（中视频） | content-pipeline | archived | `features/content-pipeline/archive/anthropic-how-we-claude-code-mid-video/` | one-context |
| openai-acquires-ona-mid-video | OpenAI 收购 Ona：Codex 与云端 Agent 任务控制中心（中视频） | content-pipeline | draft | `features/content-pipeline/openai-acquires-ona-mid-video/` | one-context |
| claude-code-boris-programmer-endgame-mid-video | 程序员的终局：Claude Code 负责人 Boris 的 5 个硬核洞察（中视频） | content-pipeline | draft | `features/content-pipeline/claude-code-boris-programmer-endgame-mid-video/` | one-context |
| skillclaw-agent-skill-evolution-mid-video | SkillClaw：Agent Skills 自动进化与跨端共享深度解析（中视频） | content-pipeline | archived | `features/content-pipeline/archive/skillclaw-agent-skill-evolution-mid-video/` | one-context |
| deepseek-code-harness-mid-video | 模型之外全是决胜局——DeepSeek 造中国版 Claude Code（Harness）中视频 | content-pipeline | archived | `features/content-pipeline/archive/deepseek-code-harness-mid-video/` | one-context |
| ai-companies-build-ai-mid-video | AI 正在「自己造自己」——巨头用 AI 造 AI（Remotion Pipelines 中视频） | content-pipeline | archived | `features/content-pipeline/archive/ai-companies-build-ai-mid-video/` | one-context |
| ai-collective-emergence-mid-video | 集体涌现：当几百万 AI 代理凑在一起（Remotion 中视频） | content-pipeline | draft | `features/content-pipeline/ai-collective-emergence-mid-video/` | one-context |
| ai-companies-self-evolution-remotion-mid-video | AI 公司用 AI 造下一代 AI（已并入 build-ai 归档） | content-pipeline | archived | `features/content-pipeline/archive/ai-companies-build-ai-mid-video/` | one-context |
| skill-srt-to-deck | SRT 驱动的动画级幻灯自动生成（srt-to-deck） | core | developing | `features/core/skill-srt-to-deck/` | one-context |
| skill-remotion-pipelines-anime | Remotion Pipelines × Anime.js 可选动画层 | core | approved | `features/core/skill-remotion-pipelines-anime/` | one-context |
| skill-remotion-pipelines-gsap-layer | Remotion Pipelines × GSAP 可选动画层 | core | draft | `features/core/skill-remotion-pipelines-gsap-layer/` | one-context |
| skill-info-radar | 信息雷达 Skill — 多源技术文章追踪 + AI 评估 + content-pipeline 自动转化 | core | draft | `features/core/skill-info-radar/` | one-context |
| claudecode-skill-auto-evolution | Claude Code 技能自进化机制调研与集成设计 | core | draft | `features/core/claudecode-skill-auto-evolution/` | one-context |
| pc-switch-emulator-200-controller-mid-video | 电脑 + 200 元手柄畅玩 Switch 游戏（教程中视频） | content-pipeline | draft | `features/content-pipeline/pc-switch-emulator-200-controller-mid-video/` | one-context |
| pc-switch-emulator-200-controller-setup | 电脑 + 200 元手柄畅玩 Switch — 软件安装与配置任务 | develop | draft | `features/develop/pc-switch-emulator-200-controller-setup/` | one-context |
| github-info-radar-survey | GitHub 信息雷达开源项目调研 | research | done | `features/research/github-info-radar-survey/` | one-context |
| skill-eval-driven-dev-survey | Skill 评测驱动研发框架调研（GitHub 开源项目） | research | done | `features/research/skill-eval-driven-dev-survey/` | one-context |
| skill-eval-runner | Skill 评测驱动研发框架 — onecxt eval CLI + tmp 目录隔离 + LLM rubric（承接 skill-eval-driven-dev-survey 落地） | core | draft | `features/core/skill-eval-runner/` | one-context |
| skill-self-evolution-survey | Skill 自进化项目调研（GitHub 开源项目） | research | blocked | `features/research/skill-self-evolution-survey/` | one-context |
| ai-slower-better-code-mid-video | AI 编码慢即是快 —— Nolan Lawson「用 AI 更慢地写更好的代码」深度解析（中视频） | content-pipeline | archived | `features/content-pipeline/archive/ai-slower-better-code-mid-video/` | one-context |
| agent-long-term-memory-alibaba-cloud-mid-video | Agent长期记忆如何选？阿里云选型指南 | content-pipeline | archived | `features/content-pipeline/archive/agent-long-term-memory-alibaba-cloud-mid-video/` | one-context |
| mcp-server-freelance-moat-mid-video | 月入10万建 MCP Server？自由职业者的风口与护城河 | content-pipeline | archived | `features/content-pipeline/archive/mcp-server-freelance-moat-mid-video/` | one-context |
| agent-harness-engineering-survey-mid-video | Agent Harness: 权威论文告诉你怎么做（Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/agent-harness-engineering-survey-mid-video/` | one-context |
| claude-code-daily-driver-mid-video | Claude Code 日常驾驶全指南：Claude.md / Skills / Subagents / MCP 生态（中视频） | content-pipeline | draft | `features/content-pipeline/claude-code-daily-driver-mid-video/` | one-context |
| postgres-ai-agent-default-db-mid-video | AI 时代 Postgres 怎么成了 Agent 脚手架里的默认数据库（中视频） | content-pipeline | archived | `features/content-pipeline/archive/postgres-ai-agent-default-db-mid-video/` | one-context |
| ai-era-last-interview-mid-video | 最后的面试：AI时代的面试终结（Steve Yegge · Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/ai-era-last-interview-mid-video/` | one-context |
| codegraph-claude-code-mid-video | CodeGraph：让 Claude Code 少烧 57% Token（Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/codegraph-claude-code-mid-video/` | one-context |
| llm-ai-friendly-architecture-mid-video | AI Friendly 架构：面向 LLM 的架构设计（Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/llm-ai-friendly-architecture-mid-video/` | one-context |
| google-skillos-self-evolving-agent-mid-video | SkillOS：谷歌自进化智能体技能治理框架（Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/google-skillos-self-evolving-agent-mid-video/` | one-context |
| andrew-ng-fde-ai-engineer-mid-video | 吴恩达谈 FDE：驻场工程师与 AI 工程师的未来（中视频） | content-pipeline | archived | `features/content-pipeline/archive/andrew-ng-fde-ai-engineer-mid-video/` | one-context |
| fde-on-the-ground-mid-video | 驻场工程师（FDE）到底在干什么？定义、一周工作流与公开案例（中视频） | content-pipeline | archived | `features/content-pipeline/archive/fde-on-the-ground-mid-video/` | one-context |
| skill-self-evolution-loop | Skill 使用后异步自评估闭环（AI 自学 rubric + markdown 改进建议） | core | draft | `features/core/skill-self-evolution-loop/` | one-context |
| tencent-super-team-mid-video | 从超级个体到超级团队——腾讯研究院报告深度解读（中视频） | content-pipeline | archived | `features/content-pipeline/archive/tencent-super-team-mid-video/` | one-context |
| rl-bandit-skill-evolution | 强化学习老虎机算法驱动 Skill 自进化可行性研究 | research | draft | `features/research/rl-bandit-skill-evolution/` | one-context |
| claude-code-dynamic-workflows-mid-video | Claude Code 动态工作流该怎么用（Thariq · 机器之心 · 中视频） | content-pipeline | archived | `features/content-pipeline/archive/claude-code-dynamic-workflows-mid-video/` | one-context |
| dingtalk-one-inside-mid-video | 置身钉内：钉钉 ONE 与无招回归（中视频） | content-pipeline | draft | `features/content-pipeline/dingtalk-one-inside-mid-video/` | one-context |
| openclaw-self-improving-autoskill-mid-video | OpenClaw 双轨自进化：Self-Improving + AutoSkill（Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/openclaw-self-improving-autoskill-mid-video/` | one-context |
| agent-arena-373k-ranking-mid-video | 37万次真实会话 Agent 榜单：GPT-5.5 第一 Claude 最稳（Remotion 中视频） | content-pipeline | archived | `features/content-pipeline/archive/agent-arena-373k-ranking-mid-video/` | one-context |
| claude-code-loop-engineering-mid-video | Loop Engineering：Claude Code 之父与龙虾创始人力捧的新范式（Remotion 中视频） | content-pipeline | draft | `features/content-pipeline/claude-code-loop-engineering-mid-video/` | one-context |
| claude-fable-5-mythos-mid-video | Claude Fable 5 发布：Mythos 级模型首秀 + 安全争议 + 用户实测（中视频） | content-pipeline | draft | `features/content-pipeline/claude-fable-5-mythos-mid-video/` | one-context |
| skill-html-video-complement | html-video 互补层 — 风格化片头/片尾 + 零侵入集成 | core | draft | `features/core/skill-html-video-complement/` | one-context |
| spacex-ai1-satellite-mid-video | SpaceX AI1 轨道数据中心：太空算力与百亿级订单的未来（中视频） | content-pipeline | draft | `features/content-pipeline/spacex-ai1-satellite-mid-video/` | one-context |
| chaoxing-essay-grading-automation | 超星作文批阅自动化 — CDP 浏览器控制 + 多模态手写识别 + 批量回填 | integrations | in_progress | `features/integrations/chaoxing-essay-grading-automation/` | one-context |
| dify-knowledge-agent | Dify 知识库智能体 — 阿里云部署，面向高校学生的知识库问答服务 | integrations | in_progress | `features/integrations/dify-knowledge-agent/` | — |


**Columns**

- **primary_repo_id**: `meta/repos.yaml` 里条目的 `id`（或主实现仓库）；无则填 `—`。
- **path**: 相对 one-context 根目录的路径，用反引号包起来便于复制。
