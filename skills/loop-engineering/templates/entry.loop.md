<!--
  entry.loop.md 模板 — session × solo 循环入口(C1)
  由 loop-engineering skill 按 loops/<id>/loop.yaml 编译生成。
  <尖括号> 占位符在编译时替换为 loop.yaml 实际值。
  拉起方式: 在会话中执行 /loop，把【循环 prompt 正文】粘入作为循环 prompt。
-->

# Loop: <id>

## 循环 prompt 正文(粘给 /loop)

你正在以 **Ralph 式单 agent 自循环**推进一个目标。严格按下面的规则跑，每一轮都做完整的"执行→验证→记录→判停"。

**目标(goal)**：
> <goal>

**每一轮(iteration)依次做**：

1. **执行**：基于当前状态朝目标推进一步(改代码 / 调试 / 补实现)。
2. **验证**：在目录 `<verifier.cwd>` 下运行验证命令，读取**真实退出码**：
   ```
   <verifier.cmd>
   ```
   - 满足 `<pass_when>`(默认退出码 0)→ **达成目标，停止循环**，报告成功。
3. **记录**：把本轮结果写入 `loops/<id>/runs/<本轮序号>.json`：
   ```json
   { "iteration": <n>, "verifier_exit": <真实退出码>, "passed": <bool>,
     "verifier_tail": "<命令输出中最能定位失败的关键片段——注意不一定在尾部:node --check/Python traceback/部分 linter 的核心错误常在前部,尾部多是堆栈噪声;摘取真正指明错因的那几行>", "plan_next": "<下一步打算>",
     "handoff_triggered": <bool> }
   ```
4. **判停**：满足任一条件即**停止**，不要继续：
   - 验证器通过(见上)。
   - 命中人工交接条件(handoff)——**停下等人，绝不自作主张越过高危操作**：
     <handoff.when 列表逐条展开>
   - 达到上限：`max_iterations = <max_iterations>` 轮，或墙钟 `max_wall = <max_wall>`。

**重要约束**：
- 验证的唯一依据是**命令真实退出码**，不是你的主观判断。不准在没跑命令的情况下宣称"应该过了"。
- ⚠️ **session 驱动单次唤醒 ≤1h、关闭会话即停**。这不是无人值守长跑——若需跨较长时间推进，
  用 `ScheduleWakeup` 自定节奏分次唤醒，并预期可能需要你回来续。
- 停止时,明确报告:停因(达标 / 交接 / 超限)、跑了几轮、最后一次验证的关键错误片段(非机械取尾部)、建议的下一步。

## 唤醒约定(长任务可选)

需要跨多次唤醒推进时，每轮结束用 `ScheduleWakeup` 安排下次继续：
- `delaySeconds`：被 clamp 到 [60, 3600]，按任务实际节奏选(轮询外部状态选短、纯等待选长)。
- `prompt`：把本「循环 prompt 正文」原样回传，以便下次唤醒继续同一个 loop。
- 关闭会话即终止;重开需重新 /loop。
