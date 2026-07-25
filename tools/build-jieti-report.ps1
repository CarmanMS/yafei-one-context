param(
  [string]$OutPath = "D:\赵亚菲\yafei-one-context\output\documents\浙江省教育厅科研项目结题报告-赵亚菲-扩写版.docx"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function X([string]$s) {
  if ($null -eq $s) { return "" }
  return [Security.SecurityElement]::Escape($s)
}

function P([string]$text, [string]$style = "", [string]$align = "", [switch]$bold, [int]$size = 22, [switch]$pageBreakBefore) {
  $pPr = ""
  if ($style) { $pPr += "<w:pStyle w:val=`"$style`"/>" }
  if ($align) { $pPr += "<w:jc w:val=`"$align`"/>" }
  if ($pageBreakBefore) { $pPr += "<w:pageBreakBefore/>" }
  $rPr = "<w:rFonts w:ascii=`"Times New Roman`" w:hAnsi=`"Times New Roman`" w:eastAsia=`"SimSun`"/><w:sz w:val=`"$size`"/><w:szCs w:val=`"$size`"/>"
  if ($bold) { $rPr += "<w:b/><w:bCs/>" }
  $pprXml = if ($pPr) { "<w:pPr>$pPr</w:pPr>" } else { "" }
  return "<w:p>$pprXml<w:r><w:rPr>$rPr</w:rPr><w:t xml:space=`"preserve`">$(X $text)</w:t></w:r></w:p>"
}

function Cell([string]$text, [int]$width, [switch]$bold, [string]$shade = "") {
  $fill = if ($shade) { "<w:shd w:fill=`"$shade`"/>" } else { "" }
  $b = if ($bold) { "<w:b/><w:bCs/>" } else { "" }
  return @"
<w:tc>
  <w:tcPr><w:tcW w:w="$width" w:type="dxa"/>$fill<w:vAlign w:val="center"/></w:tcPr>
  <w:p><w:pPr><w:spacing w:after="60"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/>$b<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr><w:t xml:space="preserve">$(X $text)</w:t></w:r></w:p>
</w:tc>
"@
}

function Table([array]$rows, [array]$widths, [switch]$header) {
  $grid = ($widths | ForEach-Object { "<w:gridCol w:w=`"$_`"/>" }) -join ""
  $trs = @()
  for ($i = 0; $i -lt $rows.Count; $i++) {
    $cells = @()
    for ($j = 0; $j -lt $rows[$i].Count; $j++) {
      $isHead = $header -and $i -eq 0
      $cells += Cell $rows[$i][$j] $widths[$j] -bold:$isHead -shade:$(if ($isHead) { "EDEDED" } else { "" })
    }
    $trs += "<w:tr>" + ($cells -join "") + "</w:tr>"
  }
  return @"
<w:tbl>
  <w:tblPr>
    <w:tblW w:w="9360" w:type="dxa"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:space="0" w:color="888888"/>
      <w:left w:val="single" w:sz="4" w:space="0" w:color="888888"/>
      <w:bottom w:val="single" w:sz="4" w:space="0" w:color="888888"/>
      <w:right w:val="single" w:sz="4" w:space="0" w:color="888888"/>
      <w:insideH w:val="single" w:sz="4" w:space="0" w:color="888888"/>
      <w:insideV w:val="single" w:sz="4" w:space="0" w:color="888888"/>
    </w:tblBorders>
    <w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar>
  </w:tblPr>
  <w:tblGrid>$grid</w:tblGrid>
  $($trs -join "`n")
</w:tbl>
"@
}

$body = @()
$body += P "浙江省教育厅科研项目结题报告" "" "center" -bold -size 36
$body += P "" 
$body += Table @(
  @("项目编号", "Y202456228"),
  @("项目名称", "强化学习估值问题的研究"),
  @("起止时间", "2024年 - 2026年"),
  @("项目负责人（签名）", "赵亚菲"),
  @("所在学校", "浙江外国语学院"),
  @("联系电话", "18768133920")
) @(2600, 6760)
$body += P ""
$body += P "浙江省教育厅" "" "center" -bold -size 28
$body += P "二〇二六年制" "" "center" -size 24

$body += P "研究工作总结" "Heading1" "center" -bold -size 28 -pageBreakBefore
$body += P "本项目围绕「强化学习估值问题的研究」开展，针对异轨策略估值中学习效率低、探索能力不足以及算法扩展性受限等问题，重点从多步时间差分学习、函数逼近、均方投影 Bellman 误差（MSPBE）优化、两时间尺度随机逼近与常微分方程稳定性分析等方向推进研究。项目执行期间，课题组完成了算法建模、理论证明、实验验证和论文发表等工作，基本达到申请书中「发表1-2篇论文」的预期成果形式。"
$body += P "在强化学习估值算法方面，项目形成了统一梯度时间差分学习算法 GQ(σ,λ)。该算法将 gradient Tree Backup(λ) 与 GQ(λ) 纳入同一框架，通过参数 σ 在 0 到 1 之间调节采样与期望备份的混合程度，从而扩展了表格型 Q(σ,λ) 到线性函数逼近场景。研究进一步从 MSPBE 目标函数出发推导算法更新形式，并利用两时间尺度随机逼近和 ODE 方法证明算法以概率一收敛到 TD 不动点，同时证明其可收敛到最优解的任意小邻域。实验结果表明，当 σ 取中间值时，算法在异轨策略评价或控制任务上优于 σ=0 和 σ=1 两端情形，验证了统一框架对提升策略估值性能的有效性。相关成果发表于 Journal of Applied Mathematics and Physics。"
$body += P "在数学理论基础方面，项目负责人结合算子代数研究方向，完成了对 dual p-operator spaces 的 Helly 型定理研究，证明任意 dual p-operator space 均具有 weakly p-local reflexivity。该成果从 p-算子空间、张量积对偶和局部反射性等角度拓展了函数空间与算子空间的结构理论，可作为项目中函数逼近、算子结构和估值理论研究的数学支撑。相关成果发表于 Bulletin of the Australian Mathematical Society，并在论文中标注浙江省教育厅科研项目资助。"
$body += P "项目执行过程中，课题组按照申请书设定的三个研究方向推进：一是通过多步学习和梯度型时间差分算法提升策略估值的学习能力；二是通过函数逼近、采样机制和实验任务对算法探索能力进行验证；三是从更一般的数学结构出发，拓展估值理论所依赖的函数空间和算子理论工具。总体来看，项目已形成较完整的「问题建模 - 算法设计 - 收敛性证明 - 实验验证 - 论文发表」研究链条。"
$body += P "项目成果的学术价值主要体现在：提出统一的 GQ(σ,λ) 异轨学习算法，补充了已有 GQ(λ) 与 Tree Backup(λ) 之间的理论联系；给出了算法 TD 不动点结构和收敛性质，为后续非线性函数逼近、深度强化学习估值算法分析提供基础；同时完成 p-算子空间方向的理论拓展，丰富了项目负责人数学研究方向与人工智能算法理论之间的交叉积累。"
$body += P "下一步，课题组拟继续围绕非线性函数逼近、深度强化学习估值算法以及复杂环境下的实验验证开展研究，并进一步将已形成的算法理论与可视化、仿真平台结合，提升成果的可复现性和应用推广价值。"
$body += P "一、项目研究背景与总体完成情况" "" "" -bold -size 24
$body += P "强化学习是人工智能的重要研究方向，其基本目标是研究智能体如何通过与环境交互获得反馈，并在长期累积回报最大化的意义下形成有效策略。策略估值是强化学习中最基础也最关键的环节之一，它通过对状态价值函数或状态-动作价值函数的估计，为策略改进、策略优化和控制决策提供依据。没有可靠的策略估值，后续的策略提升往往缺乏稳定基础；估值误差较大时，智能体可能在复杂任务中形成低效甚至错误的决策。"
$body += P "本项目申请书中明确指出，现有强化学习策略估值方法在学习能力、探索能力和扩展能力方面仍存在突出问题。特别是在异轨策略估值中，行为策略与目标策略分布不同，导致利用历史数据或探索数据估计目标策略价值时会出现偏差、方差增大以及算法不稳定等问题。随着强化学习任务从表格型小规模问题逐步走向大规模状态空间、连续控制任务和函数逼近模型，传统表格算法难以直接适用，半梯度类方法又可能在异轨多步自举条件下出现发散。因此，如何设计既有较好计算效率、又有理论收敛保证的策略估值算法，是本项目重点解决的问题。"
$body += P "项目执行期间，课题组按照申请书设定的研究路线，围绕多步时间差分学习、异轨策略估值、函数逼近、MSPBE 目标函数、两时间尺度随机逼近和常微分方程稳定性分析等方向持续开展研究。项目形成了两篇正式发表论文，其中一篇直接围绕强化学习异轨估值算法展开，另一篇围绕 p-算子空间局部理论展开，为项目负责人的算子代数与函数空间研究方向提供支撑。两篇论文均标注浙江省教育厅科研项目 Y202456228 资助，能够作为本项目结题的主要成果。"
$body += P "二、强化学习估值问题的理论背景" "" "" -bold -size 24
$body += P "强化学习中的策略估值问题通常可表述为：给定马尔可夫决策过程、奖励函数、折扣因子和策略，估计该策略在各状态或状态-动作对上的长期期望回报。在同轨学习中，数据由目标策略本身生成；在异轨学习中，数据由行为策略生成，而估值对象是另一个目标策略。异轨学习更贴近真实应用，因为在许多场景中，研究者无法反复按照目标策略采集数据，只能利用已有数据、探索策略数据或离线系统日志进行估值。"
$body += P "异轨策略估值困难主要来自分布不一致。行为策略 μ 与目标策略 π 的差异会导致样本分布与估值目标不匹配，直接使用同轨算法可能产生系统性偏差；如果使用重要性采样进行校正，又可能带来较高方差。已有研究提出了 Tree Backup、Retrace、GQ(λ)、GTD 等算法，但这些方法往往分别对应不同的备份思想、目标函数和收敛分析框架。项目研究的核心思路，就是在统一框架下理解这些方法之间的联系，并进一步设计适合函数逼近场景的稳定算法。"
$body += P "多步时间差分学习为提升估值能力提供了重要工具。TD(λ) 通过迹衰减参数 λ 统一了一步时间差分学习和蒙特卡洛方法；Q(σ) 通过参数 σ 统一了 full-sampling 的 Sarsa 思路和 pure-expectation 的 Tree Backup 思路；Q(σ,λ) 则进一步把 σ 与 λ 结合起来，使算法可以在采样备份、期望备份和多步学习之间连续调节。本项目已发表论文正是在这一脉络下，将表格型 Q(σ,λ) 推广到线性函数逼近的异轨学习场景，并给出梯度型收敛算法。"
$body += P "三、论文一的主要内容：统一梯度时间差分学习算法 GQ(σ,λ)" "" "" -bold -size 24
$body += P "论文《A Unified Gradient Temporal Difference Learning Algorithm for Off-Policy Learning》是本项目最直接对应申请书主题的核心成果。该论文提出统一的梯度时间差分学习算法 GQ(σ,λ)，用于异轨策略学习中的策略估值问题。算法中的参数 σ 位于 0 到 1 之间，用于调节采样备份和期望备份的混合程度；当 σ=0 时，算法与 gradient Tree Backup(λ) 相关；当 σ=1 时，算法退化到 GQ(λ)；当 σ 取中间值时，算法形成两类极端方法之间的连续过渡。"
$body += P "该论文首先回顾强化学习、异轨策略评价和时间差分学习的基本概念，明确状态、动作、奖励、转移概率、折扣因子、行为策略、目标策略和 Bellman 算子之间的关系。在异轨评价任务中，智能体根据行为策略 μ 产生轨迹，却需要估计目标策略 π 的价值函数。论文从这一基本设定出发，引入重要性采样比率、λ-return、多步 TD error 等概念，为后续算法推导奠定基础。"
$body += P "论文随后分析 Q(σ) 和 Q(σ,λ) 的多步回报结构。Q(σ) 的重要意义在于通过一个连续参数把 Sarsa 的采样误差和 Expected Sarsa 的期望误差结合起来。已有表格型实验表明，σ 的中间值往往比 σ=0 或 σ=1 两个极端取得更好表现。论文继承这一思想，但不局限于表格型情形，而是进一步考虑高维状态空间下必须使用函数逼近的场景。"
$body += P "在线性函数逼近条件下，直接把 Q(σ,λ) 写成半梯度更新会面临异轨学习常见的发散问题。为解决这一困难，论文没有直接采用半梯度方法，而是从均方投影 Bellman 误差 MSPBE 出发推导算法。MSPBE 是梯度时间差分学习中刻画投影 Bellman 方程误差的重要目标函数，它可以把策略估值问题转化为一个具有明确优化意义的目标函数最小化问题。"
$body += P "基于 MSPBE，论文引入辅助权重和两时间尺度随机逼近思想，推导出 GQ(σ,λ) 的可迭代更新形式。该推导既保留 Q(σ,λ) 的统一参数结构，又避免了半梯度异轨学习的不稳定性。论文还指出，在 σ=0 的端点情形下，GQ(σ,λ) 可视为一种将 Tree Backup(λ) 扩展到线性函数逼近的梯度型方法，而这一更新形式在既有文献中并未以相同方式提出。"
$body += P "四、论文一的理论结果与创新价值" "" "" -bold -size 24
$body += P "论文一的理论贡献主要体现在两个方面。第一，论文建立了 GQ(σ,λ) 的统一算法框架。以往 GQ(λ)、gradient Tree Backup(λ)、Retrace 类方法和 Q(σ,λ) 往往分散讨论，算法之间的联系并不直观。GQ(σ,λ) 用一个参数化框架揭示了这些方法之间的连续关系，使研究者可以在同一理论体系下比较不同备份机制的优劣。"
$body += P "第二，论文证明了算法的收敛性。论文在遍历性、有界性、步长条件和相关矩阵可逆等假设下，证明 GQ(σ,λ) 收敛到对应的 TD 不动点。定理 1 表明，算法参数序列收敛到 TD fixed-point，并且该不动点是对应常微分方程的全局渐近稳定平衡点。该结论说明算法不仅形式上可迭代，而且在动力系统意义下具有稳定结构。"
$body += P "论文定理 2 进一步说明，GQ(σ,λ) 可以收敛到最小化 MSPBE 问题最优解的任意小邻域。该结果把算法极限与目标函数最小化联系起来，使算法收敛具有明确的优化意义。对异轨策略估值而言，这一点尤其重要，因为缺乏收敛保证的估值算法即使在部分实验中表现较好，也难以作为可靠方法推广。"
$body += P "该论文还对算法复杂度进行了说明。GQ(σ,λ) 每一步的时间复杂度为 O(|A|p)，内存复杂度为 O(p)，其中 |A| 为动作数量，p 为特征维度。这表明该算法在引入统一机制和收敛保证的同时，并没有显著增加内存负担，仍保持与 GQ(λ) 和 gradient TB(λ) 等基准方法相近的渐近效率。这与申请书中提升策略估值扩展能力的目标相一致。"
$body += P "五、论文一的实验验证" "" "" -bold -size 24
$body += P "论文一不仅给出理论推导，还进行了实验验证。实验部分主要包括异轨策略评价和控制域中的异轨评价两个方面。论文将 GQ(σ,λ) 与 GQ(λ)、ABQ(ζ)、GTB(λ)、GRetrace(λ) 等基准算法进行比较，使用 RMSPBE、MSE 和 Mountain Car 任务回报等指标评价算法性能。"
$body += P "在 Two State MDP 等策略评价实验中，结果显示 GQ(σ,λ) 在合适的中间 σ 取值下优于基准算法，也优于 σ=0 和 σ=1 两个端点。这表明完全采样或完全期望并不一定是最佳选择，而将二者按合适比例混合可以提高异轨估值效果。该实验结果与项目申请书中关于提升策略估值学习能力和探索能力的目标相吻合。"
$body += P "在 Mountain Car 连续控制域实验中，论文将目标策略固定，把任务视为连续状态空间下的异轨策略评价问题。由于状态空间连续，实验采用 tile coding 提取特征，再比较不同算法和不同 σ 取值下的表现。结果表明，GQ(σ,λ) 仍然在中间 σ 取值下获得更好表现，说明算法从简单离散任务推广到连续控制任务时仍具有优势。"
$body += P "从项目完成情况看，论文一覆盖了申请书中提出的多个关键任务：通过多步学习和梯度 TD 框架提升策略估值学习能力；通过参数 σ 调节采样与期望备份，改善异轨估值表现；通过函数逼近和连续控制任务实验，验证算法在较复杂场景中的可扩展性。因此，该论文是本项目最核心的结题成果。"
$body += P "六、论文二的主要内容：dual p-operator spaces 的 Helly 型定理" "" "" -bold -size 24
$body += P "论文《A Helly-Type Theorem for Dual p-Operator Spaces》是项目负责人在算子代数、p-算子空间和局部反射性方向取得的理论成果。该论文证明了 dual p-operator spaces 的 Helly 型定理，并得到任意 dual p-operator space 都具有 weakly p-local reflexivity 的推论。论文发表于 Bulletin of the Australian Mathematical Society，并标注浙江省教育厅科研项目 Y202456228 资助。"
$body += P "算子空间理论是泛函分析的重要分支，研究矩阵范数结构、完全有界映射、张量积、对偶空间和局部结构等问题。p-算子空间理论则以 Lp 空间上的算子结构为背景，涉及 p-完全有界映射、p-投影张量积以及 p-局部反射性等概念。虽然该论文并非直接研究强化学习算法，但它与项目负责人申请书中的「算子代数、强化学习」研究方向一致，也为函数逼近、线性算子和投影结构研究提供基础数学支撑。"
$body += P "该论文的核心定理可概括为：给定 p-operator space V，对任意 p-operator space E 和每个 p-complete contraction φ:E→V***，存在 p-complete contraction ψ:E→V*，使其在 V 的典范嵌入下保持相应配对关系。该结果可视为 dual p-operator spaces 的 Helly 型定理。与经典 Banach 空间 Helly 引理相比，该结果保持 p-complete contractivity，不出现 1+ε 损失，并适用于任意 p-算子空间。"
$body += P "论文进一步引入 weakly p-local reflexivity 的定义，并由 Helly 型定理推出任意 dual p-operator space 都是 weakly p-locally reflexive。这一结论推广了已有 dual operator space 弱局部反射性的结果，使相关理论进入 p-算子空间框架。"
$body += P "从本项目角度看，论文二体现了项目负责人在算子空间和函数空间基础理论方面的持续积累。强化学习估值算法中涉及 Bellman 算子、投影算子、函数逼近空间、对偶结构和收敛映射等内容，虽然具体技术路线不同，但其底层数学问题与算子理论有天然联系。因此，论文二可作为本项目数学基础和交叉研究能力的体现。"
$body += P "七、项目创新点与实际完成度" "" "" -bold -size 24
$body += P "本项目第一项创新，是提出并发表 GQ(σ,λ) 统一梯度时间差分学习算法。该算法通过参数 σ 将 GQ(λ) 和 gradient Tree Backup(λ) 纳入同一框架，揭示采样备份和期望备份之间的连续关系，为异轨策略估值提供新的统一视角。"
$body += P "本项目第二项创新，是在异轨学习和线性函数逼近条件下给出完整收敛性分析。论文借助 MSPBE、辅助权重、两时间尺度随机逼近和 ODE 方法，证明算法收敛到 TD 不动点，并接近最优解邻域，回应了异轨策略估值中算法稳定性不足的问题。"
$body += P "本项目第三项创新，是将理论分析与实验验证结合。论文在标准异轨评价任务和 Mountain Car 连续控制任务中验证算法表现，显示中间 σ 取值能够优于两端参数。这一结论说明统一算法思想不仅具有理论意义，也具有实际性能价值。"
$body += P "本项目第四项创新，是在 p-算子空间方向取得 Helly 型定理和弱 p-局部反射性结果，拓展了项目负责人的基础数学研究，并与函数逼近、算子结构和强化学习估值理论形成一定的交叉支撑。"
$body += P "项目申请书预期成果为发表 1-2 篇 SCI 或相关论文。项目实际形成两篇正式发表论文，且均标注项目号 Y202456228，数量和质量均达到预期目标。此外，项目还形成「复杂函数交互式仿真与可视化平台 V1.0」软件著作权，可作为数学计算、函数仿真和算法展示方面的辅助支撑成果。"
$body += P "八、存在问题与后续研究计划" "" "" -bold -size 24
$body += P "本项目已完成阶段性研究目标，但仍有继续拓展空间。首先，GQ(σ,λ) 当前主要在线性函数逼近框架下建立理论。若进一步推广到非线性函数逼近或深度神经网络情形，需要面对目标函数非凸、Jacobian 随参数变化、全局稳定性难以刻画等新问题。"
$body += P "其次，当前实验主要覆盖标准策略评价任务和 Mountain Car 控制域。后续可以在更复杂的连续控制环境、离线强化学习数据集、推荐系统或多智能体任务中继续验证算法，以进一步检验算法在真实复杂环境中的表现。"
$body += P "再次，算子空间理论与强化学习估值理论之间仍可进一步结合。后续可围绕投影 Bellman 算子、函数逼近空间、对偶空间结构、压缩映射和稳定性分析等问题，探索算子理论工具在强化学习收敛性分析中的应用。"
$body += P "总体而言，本项目围绕强化学习估值问题完成了从问题提出、算法设计、理论证明、实验验证到论文发表的完整研究链条，达到了申请书预期目标。项目成果对于理解异轨策略估值、设计稳定高效的梯度 TD 算法，以及拓展相关数学基础理论具有积极意义。"

$body += P "刊物论著、成果专利清单" "Heading1" "" -bold -size 28
$body += P "（注明刊物论著名称、发表时间及卷期号；鉴定成果名称、组织鉴定单位、鉴定日期；专利名称、类别、获准专利国别、批准日期、专利号。以上各项均须注明本人排序）"
$body += Table @(
  @("序号", "成果名称", "成果类型及出处", "时间/卷期/编号", "本人排序及说明"),
  @("1", "A Unified Gradient Temporal Difference Learning Algorithm for Off-Policy Learning", "论文；Journal of Applied Mathematics and Physics", "2026年；14(6):2384-2408；DOI:10.4236/jamp.2026.146117", "赵亚菲第一作者；论文标注浙江省教育厅科研项目 Y202456228 资助"),
  @("2", "A Helly-Type Theorem for Dual p-Operator Spaces", "论文；Bulletin of the Australian Mathematical Society；Cambridge University Press online first", "2026年在线发表；DOI:10.1017/S0004972726101464", "赵亚菲第一作者；论文标注浙江省教育厅科研项目 Y202456228 资助"),
  @("3", "复杂函数交互式仿真与可视化平台 V1.0", "计算机软件著作权；著作权人：浙江外国语学院", "登记号：2026SR0247685；登记日期：2026年02月06日", "作为数学计算、函数仿真与可视化相关的支撑性成果列入")
) @(700, 2850, 2400, 2150, 1260) -header
$body += P "说明：其余软著「基于chrome插件的本地化RAG隐私智能检索系统」「基于移动端多媒体反馈驱动的目标管理与成就系统」「科研画像与多源学术资讯聚合推荐系统」与本项目核心研究主题关联度相对较弱，建议不作为本项目主要结题成果列入，必要时可作为个人同期其他成果另行说明。"

$body += P "主要完成人员及承担任务" "Heading1" "" -bold -size 28
$body += Table @(
  @("姓名", "单位/身份", "承担任务"),
  @("赵亚菲", "浙江外国语学院；项目负责人", "负责项目总体设计、强化学习估值算法建模、理论分析、论文撰写、成果凝练与结题材料组织。"),
  @("杨龙", "合作研究人员", "参与异轨策略估值算法实验、模型验证和论文合作研究。"),
  @("董喆", "合作研究人员", "参与 p-算子空间与 Helly 型定理相关理论研究和论文合作研究。")
) @(1500, 2500, 5360) -header

$body += P "经费使用情况" "Heading1" "" -bold -size 28
$body += P "本项目经费总额为1万元。项目经费按照学校财务制度和项目预算执行，主要用于论文发表与版面、文献资料、计算实验、学术交流及结题材料整理等与项目研究直接相关的支出。经费使用坚持专款专用、据实报销原则，具体金额以学校财务系统和报销凭证为准。"
$body += Table @(
  @("经费项目", "用途说明", "备注"),
  @("论文发表及资料费", "用于论文发表、资料获取、文献检索等", "按实际票据核销"),
  @("计算实验与材料整理", "用于算法实验、数据整理、结题材料制作等", "按实际票据核销"),
  @("学术交流相关支出", "用于项目研究交流、成果修改和推广等", "按学校财务规定执行")
) @(2200, 5160, 2000) -header

$body += P "院（系）学术委员会意见：" "Heading1" "" -bold -size 26
$body += P ""
$body += P ""
$body += P "学术委员会负责人（签章）：                                      年     月     日" "" "right"

$body += P "校科研管理部门意见：" "Heading1" "" -bold -size 26
$body += P ""
$body += P ""
$body += P "（单位公章）                                                    年     月     日" "" "right"

$body += P "省教育厅意见：" "Heading1" "" -bold -size 26
$body += P ""
$body += P ""
$body += P "（单位公章）                                                    年     月     日" "" "right"

$documentXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    $($body -join "`n")
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
      <w:cols w:space="425"/>
      <w:docGrid w:linePitch="312"/>
    </w:sectPr>
  </w:body>
</w:document>
"@

$stylesXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="SimSun"/><w:b/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
  </w:style>
</w:styles>
"@

$contentTypes = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"@

$rels = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"@

$docRels = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"@

$core = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>浙江省教育厅科研项目结题报告</dc:title>
  <dc:creator>赵亚菲</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
</cp:coreProperties>
"@

$app = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
</Properties>
"@

$tmp = Join-Path $env:TEMP ("jieti-docx-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp, (Join-Path $tmp "_rels"), (Join-Path $tmp "word"), (Join-Path $tmp "word\_rels"), (Join-Path $tmp "docProps") | Out-Null
Set-Content -LiteralPath (Join-Path $tmp "[Content_Types].xml") -Value $contentTypes -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmp "_rels\.rels") -Value $rels -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmp "word\document.xml") -Value $documentXml -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmp "word\styles.xml") -Value $stylesXml -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmp "word\_rels\document.xml.rels") -Value $docRels -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmp "docProps\core.xml") -Value $core -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmp "docProps\app.xml") -Value $app -Encoding UTF8

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutPath) | Out-Null
if (Test-Path -LiteralPath $OutPath) { Remove-Item -LiteralPath $OutPath -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = "$OutPath.zip"
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  Get-ChildItem -LiteralPath $tmp -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($tmp.Length + 1).Replace('\', '/')
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $relative) | Out-Null
  }
} finally {
  $zip.Dispose()
}
Move-Item -LiteralPath $zipPath -Destination $OutPath -Force
Remove-Item -LiteralPath $tmp -Recurse -Force
Write-Output $OutPath
