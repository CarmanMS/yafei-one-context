// entry.workflow.js 模板 — workflow × triad 循环入口(C2)
// 由 loop-engineering skill 按 loops/<id>/loop.yaml 编译生成。
// <尖括号> 占位符在编译时替换为 loop.yaml 实际值。
// 拉起: Workflow({ scriptPath: "loops/<id>/entry.workflow.js" })
//
// 三角色 triad: Generate(执行) / Evaluate(跑 verifier.cmd) / Plan(基于失败重规划)。
// 强制验证: Evaluate agent 实际执行 verifier.cmd 并自报 exitCode;脚本只信 passed=(exitCode==0)。
// 注意: Workflow 脚本无文件系统访问,runs/ 由 evaluate agent 经 Bash 落盘并回填 runs_path。

export const meta = {
  name: '<id>',
  description: '<goal>',
  phases: [
    { title: 'Generate' },
    { title: 'Evaluate' },
    { title: 'Plan' },
  ],
}

// ── 结构化输出契约 ────────────────────────────────────────────────
const WORK_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string', description: '本轮做了什么' },
    changedFiles: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary'],
}

// 评估器:必须实际跑 verifier.cmd,回报真实 exitCode + 关键错误片段(非机械取尾部) + runs 落盘路径
const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    exitCode: { type: 'integer', description: '<verifier.cmd> 的真实退出码' },
    passed: { type: 'boolean', description: '是否满足 <pass_when>' },
    log: { type: 'string', description: '命令输出中最能定位失败的关键片段(原文,勿编造)。注意不一定在尾部:node --check/Python traceback/部分 linter 的核心错误常在前部,尾部多是堆栈噪声' },
    runs_path: { type: 'string', description: '本轮 runs/<i>.json 的写入路径' },
  },
  required: ['exitCode', 'passed', 'log'],
}

const PLAN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: { plan: { type: 'string', description: '下一轮的具体计划' } },
  required: ['plan'],
}

// ── 循环主体 ──────────────────────────────────────────────────────
const MAX_ITER = <max_iterations>
let plan = args?.seedPlan ?? '<goal>'

for (let i = 0; i < MAX_ITER; i++) {
  phase('Generate')
  const work = await agent(
    `按计划执行下一步,目标是达成最终目标。\n计划: ${plan}\n目标: <goal>`,
    { label: `gen#${i + 1}`, phase: 'Generate', schema: WORK_SCHEMA },
  )

  phase('Evaluate')
  // 评估器 = 实际跑可判定命令,不是模型自评
  const verdict = await agent(
    [
      '你是评估器。必须【实际执行】下面这条验证命令(用你的 Bash 权限),不准凭空判断:',
      '  命令: <verifier.cmd>',
      '  工作目录(cwd): <verifier.cwd>',
      '  通过判定: <pass_when>',
      '回报真实 exitCode、是否 passed、命令输出中最能定位失败的关键片段(log,原文)。注意核心错误不一定在尾部(node --check/Python traceback/部分 linter 在前部),勿机械取尾部。',
      `另外把本轮结果写入 loops/<id>/runs/${i + 1}.json:`,
      `  { "iteration": ${i + 1}, "verifier_exit": <code>, "passed": <bool>,`,
      '    "verifier_tail": "<关键错误片段,同 log>", "plan_next": "", "handoff_triggered": false }',
      '并在 runs_path 字段回填该文件路径。',
    ].join('\n'),
    { label: `eval#${i + 1}`, phase: 'Evaluate', schema: VERDICT_SCHEMA },
  )

  // 脚本只信结构化 exitCode,不信模型口头结论
  if (verdict.passed && verdict.exitCode === 0) {
    if (!verdict.runs_path) log(`⚠️ iteration ${i + 1}: runs/ 留痕缺失(passed 但未回填 runs_path)`)
    return { ok: true, iterations: i + 1, lastLog: verdict.log }
  }
  if (!verdict.runs_path) log(`⚠️ iteration ${i + 1}: runs/ 留痕缺失,留痕不可靠`)

  phase('Plan')
  const replan = await agent(
    `验证未通过(exitCode=${verdict.exitCode})。失败输出:\n${verdict.log}\n基于失败重新规划下一轮的具体步骤。`,
    { label: `plan#${i + 1}`, phase: 'Plan', schema: PLAN_SCHEMA },
  )
  plan = replan.plan
}

return { ok: false, reason: 'max_iterations 用尽,需人工交接', iterations: MAX_ITER }
