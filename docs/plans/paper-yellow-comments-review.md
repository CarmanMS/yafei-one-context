# PDF 黄色批注意见修改需求

来源 PDF：`C:/Users/wucha/Documents/WeChat Files/wxid_olmrpijkrjlw21/FileStorage/File/2026-06/-1724755.pdf`

目标：逐条判断编辑黄色批注是否有道理；尽量少改论文，但每一处处理都要理由充分、可向编辑解释。

## 总结

共识别到 5 条实质性批注意见。4 条建议采纳并做最小修改；1 条需要作者确认单位信息。

| 页码 | 黄色标注 | 编辑意见 | 判断 | 最小处理 |
|---|---|---|---|---|
| 第 1 页 | `Zhejiang International Studies University` | 是否补充学院、系、研究院等二级单位。 | 有一定道理，但不能编造。若作者正式署名有二级单位，应补；若没有，可保留现状并说明。 | 向作者确认官方二级单位。 |
| 第 3、14 页 | `2.2. Off-Policy Evaluation` 与 `6.1. Off-Policy Evaluation` | 两个小节标题相同，确认是否正确。 | 有道理。2.2 是理论/定义背景，6.1 是实验部分，标题重复会降低清晰度。 | 把 6.1 改为 `Off-Policy Evaluation Experiments`。 |
| 第 17 页 | `Table 2. Percentage` | 正文没有明确引用 Table 2。 | 有道理。表后文字讨论了结果，但没有显式写 `Table 2`。 | 在表后相关段落开头加 `As shown in Table 2, ...`。 |
| 第 19 页 | 参考文献 `[13]`、`[14]` | 这两条参考文献正文未引用。 | 有道理。抽取全文后，`[13]`、`[14]` 只出现在参考文献列表。 | 优先补充准确引用位置，避免删除文献导致后续编号大改。 |
| 第 15 页 | `Appendix D` | 文中没有 Appendix D。 | 编辑正确。附录只有 A、B、C，没有 D。 | 删除或改写 `Appendix D` 说法；不要凭空新增附录 D。 |

## 建议修改

### 1. 作者单位

原文：

`Zhejiang International Studies University, Hangzhou, China`

待确认后可改为：

`<School/College/Institute>, Zhejiang International Studies University, Hangzhou, China`

如果确实没有二级单位，不建议硬加。可回复编辑：

`The affiliation is the author's official affiliation, and no secondary unit is used for this manuscript.`

### 2. 小节标题重复

原文：

`6.1. Off-Policy Evaluation`

建议改为：

`6.1. Off-Policy Evaluation Experiments`

理由：第 2.2 节是在介绍 off-policy evaluation 的定义和假设；第 6.1 节是在报告实验设置与结果。改标题即可消除重复，不动正文内容。

### 3. Table 2 文中引用

表后相关段落可由：

`These results also show GQ(σ, λ) achieves the best performance ...`

改为：

`As shown in Table 2, these results also show that GQ(σ, λ) achieves the best performance ...`

理由：这是最小改法，直接满足编辑要求，不改变结论。

### 4. 参考文献 [13]、[14] 未引用

建议不要直接删除，除非作者确认这两篇确实不需要。更小的改法是补到准确位置：

- `[13]`：放在第 2.1 节 Bellman operator / Bellman equation 的说明附近。该文献是 Dynamic Programming and Optimal Control，放在 Bellman 方程背景处是合理的。
- `[14]`：放在第一次实质性提到 Expected Sarsa 的位置，例如 `then update (3) is Expected Sarsa` 这一句。

理由：这样能回应“正文未引用”的问题，又避免删除参考文献后重排编号。注意不要为了凑引用把文献放到无关句子里。

### 5. Appendix D 不存在

原文：

`Due to the limitation of space, we present all the details of domains, features setting, target policy and behavior policy in Appendix D.`

建议改为：

`We summarize the domains, feature settings, target policy and behavior policy below.`

理由：论文实际只有 Appendix A、B、C。第 6.1 节本身已经在介绍实验环境和策略设置，所以最稳妥的最小修改是去掉错误的 Appendix D 指向。

## 待确认

Yafei Zhao 的正式二级单位是什么？例如 School、College、Faculty、Institute、Academy、Department。没有就不补。

