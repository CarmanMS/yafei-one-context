---
name: loop-engineering
description: |
  引导式构建「可循环任务」的脚手架。当用户想让一个任务"自己跑起来、循环推进到达标为止"，
  而不是赌一把完美提示词时使用本 skill。它本身不循环——通过渐进提问把模糊的循环意图固化成
  一份合规的 loop.yaml 规格，再按规格编译出对应运行时(/loop / Workflow)的可执行入口。
  Triggers: "建一个 loop", "loop engineering", "循环工程", "让它自己跑", "Ralph loop",
  "生成-评估-规划循环", "自动跑到测试全绿", "构建可循环任务", "loop.yaml"。
  核心硬门槛:没有可判定的验证命令(如 pytest/lint)就拒绝建 loop。
arguments:
  - name: loop_id
    description: loop 的 kebab-case 标识(可选,缺省时引导中询问)
    required: false
---

# Loop Engineering Skill — 引导式构建可循环任务的脚手架

> 设计源：`features/core/skill-loop-engineering/`（spec.md / tech_design.md）。

## 这个 Skill 是什么

**Loop Engineering(循环工程)**：给 Agent 一个「目标 + 验证信号 + 继续/停止/回滚 + 人工交接」的**闭环**，
让任务在循环中推进，而不是押注一条完美提示词。

本 skill 是**引导式脚手架**，它本身不循环。职责只有两件：

1. **逼出一份合规规格**——通过强制顺序的提问，把用户脑子里模糊的循环意图固化成 `loops/<id>/loop.yaml`。
2. **编译出可执行入口**——按 `(driver × topology)` 选择编译器，生成 `entry.*` 并打印一行拉起命令。

> ⚠️ **编译器不是执行器**。Skill 不能直接调用 `/loop` / `Workflow` / `CronCreate` 工具(它们是主循环工具，
> 不是 skill 内可 `exec` 的 CLI)。本 skill 只产出「入口产物 + 拉起命令」，真正拉起由用户或后续 Claude 回合执行。

---

## 不可逾越的硬门槛(Loop Engineering 的立身之本)

整个引导流程里**只有一道关卡不可跳过**：

> **没有可判定的验证命令，就不建 loop。**

- `verifier.kind` 只接受 `command`。
- 必须给出一条 shell 命令(如 `pytest`、`npm test`、`lint`、`render-verify`)，其**退出码或输出可机器判定**通过/失败。
- **模型自评("我觉得对了")、人工目测，都不能作为终判验证器。** 这是 Loop Engineering 与"反复刷提示词"的根本区别。

遇到用户给不出可判定命令时,**STOP**,不写 loop.yaml,按下文 S1 的话术拒绝。

---

## 核心模型:两个正交维度相乘

「loop 有哪几种类型」= **driver(运行时) × topology(单轮结构)**，相乘 9 种，**首版做 2 格**。

### 维度 A · driver(执行入口 / 运行时)

| driver | 本质 | 运行时工具 | 入口产物 | 首版 |
|--------|------|-----------|----------|------|
| `session` | 会话内自驱，关终端即停 | `/loop` + `ScheduleWakeup` | 循环 prompt + 唤醒约定 | ✅ |
| `cron` | 定时外驱，无状态延续 | `CronCreate` | cron 注册 + enqueue prompt | ⏳ 待补 |
| `workflow` | 程序(非模型)决定循环 | `Workflow`(JS 脚本) | `.js` 编排脚本 | ✅(仅 triad) |

### 维度 B · topology(单轮内部结构)

| topology | 说明 | 首版 |
|----------|------|------|
| `solo` | 单 agent 自循环(生成→自评→继续) | ✅(仅 session) |
| `triad` | 生成器 / 评估器 / 规划器，评估器看真实信号 | ✅(仅 workflow) |
| `team` | 多角色，委托 team-executor | ⏳ 待补(运行时不可行,见末节) |

### 首版支持矩阵(只有 2 格放行)

|              | solo | triad | team |
|--------------|:----:|:-----:|:----:|
| **session**  | ✅ C1 | ⏳ | ⏳ |
| **cron**     | ⏳ | ⏳ | ⏳ |
| **workflow** | ⏳ | ✅ C2 | ⏳(后置) |

落到 ⏳ 的组合：**标注「待补」并 STOP**，引导用户改用最近的可行格(通常建议 `session×solo` 或 `workflow×triad`)。

---

## 引导状态机(强制顺序,逐状态执行)

按 S0→S8 顺序推进。**每个状态收齐答案再进下一个**，不要一次性抛所有问题。S1 是门禁，不过则全程 halt。

### ⛔ 交互纪律(不可违反——本 skill 的引导价值全靠它)

1. **禁止脑补、禁止替用户拍板。** 即使用户的初始描述里"看起来"已包含某字段，也**必须逐项回读确认**，不得直接填入 loop.yaml。
   猜错 `driver`/`topology`/`verifier.cmd` → 编译出的入口完全错误，代价远高于多问一句。
2. **禁止跳问、禁止合并提问。** 严格 S0→S8 一个一个走;不要在一条消息里把 goal/verifier/stop/... 全抛出来让用户"一次填完"。
3. **关键选择项必须用 `AskUserQuestion` 工具做结构化选择题**，不许用开放式自然语言代替：
   - **S4 `driver`**(session/cron/workflow)、**S5 `topology`**(solo/triad/team) → **强制 `AskUserQuestion`**(见各状态)。
   - 这两个是最容易猜错、且决定编译走向的二/三选一，绝不能靠"我从上下文推断"。
4. **未收齐当前状态的答案,不得进入下一状态;不得提前创建任何文件。** loop.yaml 只在 S7 一次性落盘。
5. 选项默认值(如 max_iterations=20)**只能作为"建议默认"呈现给用户确认**,不能静默采用。

### S-pre · spec 数据源旁路(可选，先于 S0)

如果用户给出了关联需求目录（`features/.../REQ-xxx/spec.md`），或当前上下文已锁定某需求，**先读它的 `## Acceptance Criteria` 章节**，把验收标准作为 S0/S1 的候选喂入——这是 `/pm` 体系产出的结构化验收块，能省去用户重新口述：

1. 解析 spec.md `## Acceptance Criteria` 下的 fenced-yaml `acceptance:` 块（字段：`id/desc/kind/signal/pass_when/status`）。
   - 块不存在 / 是旧的 `- [ ] 纯文本`格式 → 没有可用数据源，**直接走标准 S0**，不强求。
2. **goal 候选**：从 spec 的 User Story / 标题派生一句目标终态，按 S0 纪律**回读让用户确认**，不直接默认。
3. **verifier 候选**：取块内 `kind=command 且 status=ready` 的条目作为 `verifier.cmd` 候选：
   - 恰好一条 → 回读确认后带入 S1（仍受 S1 门禁约束）。
   - 多条 → 用 `AskUserQuestion` 让用户选一条，或确认用 `&&` 串联。
   - 只有 `status=tbd`（命令未就绪）→ 提示「spec 里的验证命令还是占位（tbd），需先补实再建 loop」，回到 S1 标准门禁让用户给可判定命令。
4. **artifact / manual 条目**：明确告知用户「这些项不纳入 loop 自动循环门禁（loop 只认 command 终判），需人工/产物核验」，**不**把它们写进 verifier。

> ⚠️ S-pre 只是「自动喂入候选」，**不绕过 S1 门禁**：候选命令仍要满足"退出码/输出可机器判定"。spec 没有可用 command 时，照常在 S1 拒绝/追问。

### S0 · 采集目标(goal)

问：**"这个 loop 要达成什么？用一句话描述目标终态。"**

- 收一段非空自然语言。空 → 追问，不进 S1。
- 例："把 auth 模块拆成独立 service，且现有测试全绿"。
- ⚠️ 即使用户在最初的需求里已经隐含了目标，**也要把你理解的 goal 回读一句让用户确认**(如"我把目标定为 X，对吗?")，不要直接默认。

### S1 · 采集验证器(verifier)【门禁】

问：**"用哪条命令判定『达标了』？给一条退出码/输出可机器判定的命令(如 pytest / npm test / lint)。"**

判定逻辑：
```
if 用户给不出 command  或  给的是"我来看"/"模型自己判断"/"跑完手动检查":
    REJECT 并 STOP:
    "❌ Loop Engineering 要求可判定验证器。
     请提供一条命令(如 `python -m pytest -x -q`、`npm test`、`ruff check .`),
     其退出码或输出可机器判定通过/失败。
     模型自评、人工目测不能作为终判验证器——否则这只是『反复刷提示词』,不是循环工程。
     补上可判定命令后我们再继续。"
    # 不写 loop.yaml,不进入 S2
else:
    记录 verifier.kind=command / verifier.cmd / verifier.pass_when(默认 exit_code == 0) / verifier.cwd(默认 ".")
```

### S2 · 采集停止条件(stop)

问：**"什么时候停？"** 逐项把三个默认值**呈现给用户确认**(不是静默采用)：
- `on_pass`(建议默认 true)：验证器绿即停。
- `max_iterations`(建议默认 20)：上限轮数。
- `max_wall`(建议默认 4h)：墙钟上限。

> 话术示例:"建议 on_pass=true、max_iterations=20、max_wall=4h——直接用这套默认，还是要调整哪一项?"
> 用户说"用默认"即可,但**必须给过这次确认机会**,不能跳过。
> ⚠️ 同时提醒：**session 驱动单次唤醒 ≤1h、关会话即停**，没有"挂 3 天无人值守"的能力，别把 `max_wall` 设过长。

### S3 · 采集人工交接(handoff)

问：**"什么情况必须停下叫人？"** 收一个 `when` 条件列表(可空)。
- 空也允许，但提示风险："不设交接 = loop 可能在错误方向上空转到耗尽 max_iterations。建议至少加『验证器连续 N 轮不变绿』。"
- 典型项："验证器连续 3 轮不变绿"、"触碰 migrations/ 等高危路径"、"需要外部凭证/审批"。

### S4 · 选 driver【强制 AskUserQuestion】

**必须调 `AskUserQuestion` 让用户三选一**，不许从上下文推断替用户选：
- question: "这个 loop 用哪种运行时来驱动？"
- header: "运行时"
- 选项：
  1. `session — 会话内自驱` — "你守着会话、想随时看进度、任务能在数小时内收敛。首版最成熟，验证强度最高(主循环亲读退出码)。"
  2. `workflow — 脚本编排` — "确定性后台跑、要『生成-评估-规划』三角色分工。注意评估器由 agent 自报退出码，门禁弱于 session 一档。"
  3. `cron — 定时外驱(首版未支持)` — "⏳ 首版未支持，列为下一顺位。选此将 STOP 并建议改用 session。"

收到选择后：
- 选 `cron` → **STOP**："⏳ cron 驱动首版未支持(列为下一顺位)。当前可改用 `session`(你来定节奏)。"
- 选 `session` / `workflow` → 记录 driver，进 S5。

### S5 · 选 topology【强制 AskUserQuestion】

**必须调 `AskUserQuestion` 让用户三选一**，不许替用户拍板：
- question: "一次迭代内部是单 agent 自循环，还是拆成多角色？"
- header: "单轮结构"
- 选项：
  1. `solo — 单 agent 自循环` — "一个 agent 生成→自评→继续。验证由主循环亲跑命令读退出码，**无谎报空间(门禁最硬)**。"
  2. `triad — 生成/评估/规划三角色` — "生成器改代码、评估器跑你的 verifier.cmd、规划器基于失败重规划。多角色分工，但评估器自报退出码，门禁弱 solo 一档。"
  3. `team — 多角色协作(首版后置)` — "⏳ 运行时不可行(team 是 skill 非 subagent type)。选此将 STOP 并建议改 triad。"

收到选择后：
- 选 `team` → **STOP**：
  "⏳ team 拓扑首版后置:`team`/`team-executor` 是 skill,不是 Workflow 能拉起的 subagent type,
   委托路径在运行时不成立(详见末节)。建议改用 `triad`——同样多角色分工,但用 workflow 原生 agent 编排。"
- 选 `triad` → **必须明确告知**(在进 S6 前):"⚠️ triad 的评估器由 agent 自报 exitCode，验证强度弱于 solo 一档
  (solo 是主循环亲读退出码,无谎报空间)。若你要『最硬的门禁』,回退用 session×solo。" 用户确认后再进 S6。
- 选 `solo` → 记录 topology，进 S6。

### S6 · 校验组合是否首版支持

查首版支持矩阵：
- `session×solo` → C1，放行。
- `workflow×triad` → C2，放行。
- 其余全部 → **标注「待补」并 STOP**，给出最近可行格的改用建议：
  - 想要单 agent → `session×solo`
  - 想要多角色 → `workflow×triad`

### S7 · 写 loops/<id>/loop.yaml

> ⚠️ **路径基准**：本文档所有 `loops/<id>/` 均指**项目根（CWD）下的 `loops/`**，
> **不是** skill 自身安装目录（如 `skills/loop-engineering/` 或适配后的 `.claude/skills/loop-engineering/`）下的 loops。
> 产物（loop.yaml / entry.* / runs/ / 验证脚本）与 `loops/_template/` 同级，落在仓库根 `loops/`。
> 验证脚本路径也按项目根写（如 `node loops/<id>/verify.js`、`cwd: "."`）。

- `id` 缺省则询问(kebab-case，等于目录名)。
- 用 `loops/_template/loop.yaml` 为骨架，填入 S0-S6 收集的字段。
- 写到 `loops/<id>/loop.yaml`（项目根 loops/）。
- 创建空目录 `loops/<id>/runs/`。

### S8 · 调对应编译器 → 写 entry.* + 打印拉起命令

按组合调 C1 或 C2(见下「编译器规则」)。产物落 `loops/<id>/entry.*`，最后**打印一行拉起命令**供用户复制。

---

## 编译器规则(首版 C1 + C2)

编译器 = 本 SKILL.md 内的生成规则。统一契约：

```
输入:  已校验的 loop.yaml
输出:  写 loops/<id>/entry.{loop.md | workflow.js}  +  打印一行拉起命令
副作用: 确保 loops/<id>/runs/ 目录存在
```

### C1 · session×solo → `entry.loop.md`

以 `templates/entry.loop.md` 为骨架，把 loop.yaml 的 goal / verifier.cmd / stop / handoff 实例化。产物是一段**循环 prompt 正文**，语义：

- 每轮：执行 `verifier.cmd`(在 `verifier.cwd`)→ 读真实退出码。
- 退出码满足 `pass_when` → **停**(达成目标)。
- 否则：基于失败信息推进一步，把本轮结果写 `loops/<id>/runs/<n>.json`。
- 命中任一 `handoff.when` → **停下等人**，不要自作主张越过高危操作。
- 达 `max_iterations` 或 `max_wall` → **停**并报告需人工交接。

**验证落点(最高强度)**：由 Claude 主循环亲自跑 Bash、亲眼读 exit code，无模型谎报空间。

**拉起命令**(打印给用户)：
```
在会话中执行 /loop，把 loops/<id>/entry.loop.md 的正文作为循环 prompt 粘入。
长任务用 ScheduleWakeup 自定节奏(单次唤醒 ≤1h、关会话即停——别指望无人值守长跑)。
```

### C2 · workflow×triad → `entry.workflow.js`

以 `templates/entry.workflow.js` 为骨架，把 goal / verifier.cmd / pass_when / max_iterations 实例化。脚本结构：

- `meta.phases = [Generate, Evaluate, Plan]`。
- 循环 `max_iterations` 轮：
  - **Generate**：agent 按当前 plan 执行。
  - **Evaluate**：agent 被要求**实际执行 `verifier.cmd`**(经其 Bash 权限)，回报结构化 `VERDICT_SCHEMA{ exitCode, passed, log, runs_path }`；脚本只信 `passed=(exitCode==0)`。
  - 通过 → return。否则 **Plan**：agent 基于失败重规划，进下一轮。
- evaluate agent 还需把本轮结果写 `loops/<id>/runs/<i>.json` 并回填 `runs_path`；脚本只能核对 `runs_path` 是否回填(无 fs 访问,无法验证文件真实存在),缺失则 `log()` 告警,不中断。

**验证落点(中等强度)**：verifier.cmd 由 evaluate agent 执行并**自报** exitCode，理论上可谎报。
缓解：结构化 schema + 贴命令关键错误片段(`log`,非机械取尾部) + 落 runs/。**比 C1 弱一档,已在 S5 告知用户。**

**拉起命令**(打印给用户)：
```
Workflow({ scriptPath: "loops/<id>/entry.workflow.js" })
```

---

## runs/ 留痕(上下文腐烂对策)

每轮一文件 `loops/<id>/runs/<seq>.json`：
```json
{ "iteration": 3, "verifier_exit": 1, "passed": false,
  "verifier_tail": "2 failed, 18 passed", "plan_next": "修复 token 过期分支",
  "handoff_triggered": false }
```
- 用途：刷新计划 / 压缩历史时，新一轮只读最近 N 条而非全量上下文。
- **整个 `loops/<id>/` 实例不入 git**(`.gitignore` 配 `loops/*`，只保留 `loops/.gitkeep` 与 `loops/_template/` 骨架)。
  loop 实例(含 `loop.yaml` / `entry.*` / `runs/`)是**本地运行产物**，按需自行版本化；入库的是 skill 本体与模板骨架。
- **谁写**：C1 由主循环每轮直接写(最可靠)；C2 由 evaluate agent 经 Bash 写,脚本仅核对 `runs_path` 是否回填(无法验证文件真实存在)。

---

## 规格层 = 唯一事实源

`loops/<id>/loop.yaml` 是唯一手填文件；`entry.*` 与 `runs/` 全部由它派生。
**改 loop 行为 = 改 yaml 后重新编译，绝不手改 entry.*。**

---

## workflow×team 为何后置(运行时不可行复盘)

原设想：`while(!pass && !handoff){ 调 team-executor 跑一轮 }`，单轮多角色委托给 `team-executor` skill。**不成立**：

- **根因**：`Workflow` 的 `agent(_, {agentType})` 从 **Agent 工具的 subagent 注册表** 解析 agentType
  (`general-purpose / Explore / code-reviewer …`)；`team` / `team-executor` 是 **skill**，不在此表。
  skill 由主循环 `Skill` 工具调用，subagent 由 `agent()` 拉起——两套机制。
- **后果**：`agentType:'team-executor'` 解析失败，更可能直接抛错中断整个 workflow，而非静默降级。

**后续正解(待另立小迭代)**：
1. **`workflow()` 嵌套**——把多角色协作沉淀为 workflow 脚本(非 skill)，由 loop 外壳合法嵌套(仅一层)。
2. **自管多角色编排**——loop 脚本自己用多个 `agent()`(不同 prompt/label)扮不同角色，本质是 triad 的角色扩展。

→ 首版 S5/S6 遇 `team` 一律标注「待补」并 STOP，提示改用 `triad`。

---

## 后置补齐顺位(供未来迭代参考)

1. `cron×solo` — `CronCreate` 现成，巡检场景高频，编译成本低，**第一顺位**。
2. `workflow×team` — 走上面两条正解之一，需先定方向。
3. 其余组合按需。

---

## 自检清单(交付前)

- [ ] **逐项问过、没脑补**：S0–S5 每个字段都向用户回读/提问确认过，没有从初始描述直接猜填。
- [ ] **S4 driver、S5 topology 用了 `AskUserQuestion` 结构化选择题**，不是开放式提问代替。
- [ ] **stop 的默认值给过用户确认机会**(不是静默采用 20/4h)。
- [ ] S1 门禁真的会拒绝"无可判定命令"——给空/给"人工判断"时不放行。
- [ ] 落到非首版格(任何 cron、任何 team、session×triad 等)会 STOP 并给改用建议，不产出错误入口。
- [ ] 产物只写进 `loops/<id>/`，不污染其他目录。
- [ ] 打印了可复制的拉起命令。
- [ ] 提醒了 session 的时长限制 / triad 的验证强度弱于 solo。
