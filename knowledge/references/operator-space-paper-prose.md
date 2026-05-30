# 算子空间论文英文表述规范（风格对齐，无原文摘录）

> 来源：[Introduction to Operator Space Theory](https://doi.org/10.1017/CBO9780511546211)（London Mathematical Society Lecture Note Series 294, Cambridge University Press）  
> 作者：Gilles Pisier  
> 发布日期：2003（以剑桥版权页为准）  
> 收录日期：2026-05-05  
>
> **补充**：叙述语气与结构对齐本地工作副本 `repos/research/paperwork/archive/20201107/revisedoperatorspace.tex`（私用修订稿，不外传全文）。本文 **不包含** 该书或 `.tex` 的原文摘抄，仅保留可执行的写作规则。

---

## 1. 总原则

- **语言**：正文、定理陈述、备注与证明中的解释句一律 **英文**；术语与缩写首次出现时给出标准定义或指向前文编号。
- **语气**：学术记叙，**直入主题**；少用元话语铺垫（少写「本文旨在」「值得注意的是」类空话）。
- **精简**：能合并的句子合并；删掉不改变数学内容的从句；证明内每一步 **一行一意**，避免叠床架屋的Qualifiers。
- **适用范围**：**整稿**（引言、定义、命题定理、证明、备注）均遵守本节；不仅限于引言。

## 2. 结构与衔接

- **定义**：先给对象与上下文（范畴、空间、范数），再给等价刻画或基本性质；避免「我们先回顾一下众所周知的事实」之类 unless 后面紧跟精确的 bibliographic pointer。
- **定理 / 命题**：假设（Hypotheses）条目化时用 `(i)(ii)` 或 `Assume that ...`；结论一句说清 **quantifiers**（对谁成立、常数依赖什么）。
- **证明**：常见起手：`Fix ...`，`Let ... denote ...`，`We claim that ...`；关键步骤用 **Therefore / Hence / It follows that**；避免每段都以 `Moreover` / `Furthermore` 机械堆砌。
- **备注（Remark）**：仍用完整句；可稍自由，但不改用科普腔或清单式「要点三条」代替论证。

## 3. 术语与符号习惯（算子空间语境）

- **一致性**：`CB`（completely bounded）、`MIN`/`MAX`、Ruan's theorem、Effros–Ruan 等写法全文统一；矩阵层级与 `M_n` 记号前后一致。
- **范数与嵌入**：指明空间与所用 norm（`||·||_{cb}` 等）；嵌入或等同在同构意义下时要 **写明常数是否绝对** 或依赖维数。
- **量化**：`\varepsilon`–口径、`n`-dependence、`constants independent of ...` 写清楚，避免模糊形容词代替定量。

## 4. 禁止或慎用（兼作「去 AI 味」）

以下在 **定稿式学术英文** 中默认禁用或极度精简：

- 套话：**plays a crucial / pivotal role**，**in today's landscape**，**delve into**，**It goes without saying**，**needless to say**，**At the end of the day**，**robust framework**（无数学含义时）。
- 结构性废话：**In this paper we will ...** 若占一整段而无信息；可改为一句定位问题 + 一句主定理指针。
- 过度定性：**very natural / profound / beautiful**（除非引用他人综述且有出处）。
- **清单式 AI 排版**：用大段 `- item` 代替本应连续的论证（Markdown 草稿若用列表，转入 LaTeX 时应改写为命题链或分段）。

## 5. 精简操作清单（给人与模型共用）

1. 删除不改变逻辑的连接词与重复主语。  
2. 同一概念第二轮提及用 **代词或缩写**，勿重复整句定义。  
3. 证明中若某句仅为修辞，删。  
4. 长句拆两句的条件：**only if** 两句各有独立引用价值（如一步一行公式）。

## 6. 与范本的关系

写稿或改写时，可将 `revisedoperatorspace.tex` **局部打开对照章节节奏**（定义长度、定理后是否立即给 remark），但 **禁止** 把该书英文原句复制进自己的论文。数学内容独创性与版权声明由作者自负。
