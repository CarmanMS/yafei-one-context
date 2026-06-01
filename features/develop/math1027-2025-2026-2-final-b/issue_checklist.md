# 问题清单与交接 — MATH1027 B 卷（待高人接手）

> 记录日期：2026-05-30  
> 状态：**pilot 已出，定稿待用户验收**（`status: in_progress`）  
> **结论与核心心得**：`tech_design.md` →「核心心得」；可复用 skill：`skills/docx-mcp/lib/`

---

## 一、用户原始需求（硬约束）

| # | 要求 | 说明 |
|---|------|------|
| R1 | 基于 A 卷复制出 B 卷 | 保留学院 Word 版式：页眉、装订线、分值表、大题结构 |
| R2 | 结构与分值与 A 一致 | 选择 5×3、填空 5×3、计算 7×7、综合 3×7，满分 100 |
| R3 | **20 小题均不得与 A 卷相同** | 可平行变题；约 **35%** 换到相邻考点（见 `tech_design.md` 换题表） |
| R4 | 产出试卷 + 参考答案 | 见下方路径 |
| R5 | Word COM | **2026-05-30 用户允许**；用 OMath 行内重录，非旧 `build_math1027_b_exam.py` 纯文本 |
| R6 | 优先 docx-mcp | Skill：`skills/docx-mcp/` |

---

## 二、用户反馈的问题（按时间）

### 问题 1：`.bak` 文件是什么？没用就删

- **现象**：`exams/2025-2026-2/` 下出现 `…-B-paper.docx.bak`、`.bak2`、`.bak3` 及答案同名备份。
- **原因**：docx-mcp 每次 `save_document` 前自动备份上一版。
- **处理**：2026-05-30 已删除全部 6 个 `.bak*`；**定稿勿依赖这些文件**。
- **给接手人**：若再跑 MCP 保存，可能重新产生 `.bak`，可删。

### 问题 2：B 卷公式、版式「有点乱」

- **用户原话**：「公司啥的格式好像都有点乱了」（应为 **公式** 等格式）。
- **现象（用户 WPS 目视）**：题干/选项区排版异常、新旧内容叠在一起、不像定稿试卷。
- **代理漏检**：只查了 docx 内纯文本层，**未在 WPS 中打开验收**就勾选 spec 验收项。

### 问题 3：有几题看上去就是 A 卷题

- **用户原话**：「有几题我看就是 A 的题啊，我不是说了不要和 A 一模一样吗？」
- **根因（XML 级已证实）**：
  - A 卷 **54 个 WPS 公式 OLE 嵌入对象**（非 OMML、非纯文本）。
  - docx-mcp 的 `replace_text` **只能改 `w:t` 中文壳**；**选项行里 (A)(B)(C)(D) 后的公式仍在 OLE 里**，内容仍是 A 卷（如换积分次序、\(y''-4y'+3y=0\) 等）。
  - 改题干后形成 **新 Unicode 文字 + 旧 A 卷 OLE 并存**，WPS 里像「还是 A 的题」且版式乱。

### 问题 4：代理「修复」后用户仍不满意

- **用户原话**：「还是解决不了问题……我要找高人帮忙了。」
- **代理最后一轮操作**：运行 `repos/teaches/tmp/fix_math1027_b_paper_ole.py`，去掉 B 卷全部 OLE，选择题 8 段选项改为 Unicode 线性公式。
- **用户侧仍可能不满意的原因**（待接手人 WPS 确认）：
  1. 公式变成 `e^{-x}`、`∫₀^x` 等 **纯文本/Unicode**，不是学院惯用的 **WPS 公式编辑器对象**，观感差。
  2. **B 卷答案**几乎未做同等清理（仍 **92 个 OLE**），与 B 题干不一致，含 A 卷解析残留。
  3. 去掉 OLE 后 **行距、选项对齐** 可能与 A 卷视觉不一致。
  4. 页眉「试卷类型 B」等是否完全正确，需目视确认。

---

## 三、技术根因摘要（给接手专家）

```
A 卷 docx
├── 版式层（页眉/表格/装订线）     ← 必须保留
├── 中文题干 w:t                  ← docx-mcp 可改
└── WPS Formula OLE（w:object×54）  ← docx-mcp replace_text 改不到；add_equation 是 OMML，与 WPS OLE 不兼容
```

| 手段 | 结果 |
|------|------|
| docx-mcp `replace_text` | 仅改题干中文壳；**选项公式仍为 A** |
| Word COM `build_math1027_b_word_eq_pilot.py` | **卡死，已 DEPRECATED** |
| **行内 OMML**（`skills/docx-mcp/lib/inline_omml.py`） | **2026-05-30 pilot 成功**；Word 打开 OK，7 条 OMML |
| docx-mcp `add_equation`（段后 OMML） | 结构 audit 通过；**用户不接受版式** |
| `pdf-exam-pipeline` / LaTeX 重排 | spec 明确 **非主路径**（版式难对齐学院模板） |
| `convert_to_pdf` | 本机无 LibreOffice，**未生成 PDF** |

---

## 四、当前文件状态（2026-05-30 扫描）

| 文件 | 大小 | OLE 数 | 说明 |
|------|------|--------|------|
| `…-final-A-paper.docx` | 96806 B | 54 | **母版，勿改** |
| `…-final-A-answer.docx` | — | — | A 卷答案参考 |
| `…-final-B-paper-inline-omml-pilot-v4.docx` | — | **7 OMML** | **完美被积函数消费逻辑，无虚线占位框的 v4 pilot**；待用户目视验收 |
| `…-final-B-answer.docx` | 121913 B | **92** | 选择表部分已改；**大量 A 卷 OLE + 旧解析残留** |

路径前缀：`repos/teaches/courses/MATH1027/exams/2025-2026-2/`

### B 卷 intended 内容

完整换题表与拟定选择答案 **B,A,B,A,A** 见 **`tech_design.md`**（勿仅看 docx 当前样子）。

---

## 五、已尝试步骤（避免重复踩坑）

1. 复制 A → B，docx-mcp 改「试卷类型 B」、逐题 `replace_text` 题干。
2. 同步改 B 答案：选择表、填空、计算/综合文字解答。
3. 遇文件锁：结束 WINWORD/wps 进程后另存。
4. 删除 draft/v2 中间文件及全部 `.bak*`。
5. XML 对比 A/B：确认选项段 paraId 与 A **完全相同且含 A 的 OLE**。
6. 运行 `fix_math1027_b_paper_ole.py` 清 B 卷 OLE 并重写 8 段选择题选项。

### 辅助脚本（`repos/teaches/tmp/`，非定稿）

| 脚本 | 用途 | 备注 |
|------|------|------|
| `build_math1027_b_exam.py` | Word COM 批量改 | **用户禁止** |
| `fix_math1027_b_paper_ole.py` | 删 OLE + 写 Unicode 选项 | 仅改 B-paper；用户仍不满意 |
| `B-paper-word-paras.txt` 等 | paraId 调试导出 | 可删 |

---

## 六、验收标准对照（诚实状态）

| spec 条目 | 代理自评 | **用户/事实** |
|-----------|----------|----------------|
| 页眉试卷类型 B | 已改 | 需 WPS 目视 |
| 20 题与 A 不同 | 曾勾选 | **用户否认**（OLE 期）；清 OLE 后需再验 |
| 35% 换考点 | 表已写 | 内容意图在 tech_design，**版式未达标** |
| 题量分值一致 | 是 | 结构未动 |
| B 答案对应 | 部分 | **答案 docx 仍大量 A 残留** |
| WPS 无乱码、公式可编辑 | 未勾选 | **用户反馈未解决** |

**结论：需求 status 应为 blocked / 待接手，不可视为 review 通过。**

---

## 七、建议接手路径（按推荐顺序）

1. **WPS 人工定稿（最稳）**  
   - 用 A 卷作版式参考，**新建或复制 B**；逐题用 **WPS 公式编辑器** 录入 `tech_design.md` 中 B 卷内容。  
   - 选择题四个选项 **整段重写**，勿保留 A 的 OLE。

2. **Microsoft Word + 公式（若环境有 Word）**  
   - 插入 → 公式（OMML），与 WPS 互开需试兼容性。

3. **docx-mcp + add_equation 试验**  
   - 对单题 pilot：删段内 OLE → `add_equation(latex=…)`；全卷 20 题工作量大，且 OMML 与学院 WPS 模板是否一致 **未知**。

4. **LaTeX / pdf-exam-pipeline**  
   - 仅当用户 **接受 PDF 或放弃学院 Word 版式** 时考虑。

### 接手人第一步 checklist

- [ ] WPS 打开 `B-paper.docx`，通读 20 题 + 选项，与 A 卷逐题对比
- [ ] 打开 `B-answer.docx`，核对选择 B,A,B,A,A 及是否仍含「牛顿冷却」「绝对收敛」等 A 卷表述
- [ ] 以 `tech_design.md` 为 **内容真源** 改 docx，不以当前 docx 为准
- [ ] 定稿后删除新生成的 `.bak*`
- [ ] 更新本 feature 的 `spec.md` status、`deliver.md`

---

## 八、相关文档与 Skill

| 资源 | 路径 |
|------|------|
| 换题真源 | `features/develop/math1027-2025-2026-2-final-b/tech_design.md` |
| 需求 spec | `features/develop/math1027-2025-2026-2-final-b/spec.md` |
| 课程元数据 | `repos/teaches/courses/MATH1027/course.yaml` |
| docx 改题约定 | `skills/docx-mcp/references/teaches-exams.md` |
| teaches 目录说明 | `repos/teaches/README.md` |

---

## 九、开放问题（留给接手人 / 用户）

1. 定稿是否 **必须** 为 WPS 公式对象，还是 OMML/线性 Unicode 可接受？
2. 是否需要 **PDF** 归档？（需 LibreOffice 或 WPS 另存）
3. 是否在 `meta/repos.yaml` 登记 `repos/teaches` 便于提交？
4. B 卷是否要从 **干净复制 A** 重来（推荐），还是在当前 `B-paper.docx` 上修？

---

## 十、问题追踪表（可勾选）

| ID | 问题 | 严重性 | 状态 |
|----|------|--------|------|
| I1 | 选择题选项曾为 A 卷 OLE 内容 | 阻塞 | B-paper OLE 已删；**公式排版待验收** |
| I2 | 题干与旧公式叠层、版式乱 | 阻塞 | 部分缓解；**用户仍不满意** |
| I3 | B 答案 92 OLE + A 解析残留 | 高 | **未修** |
| I4 | spec 验收项误勾选通过 | 中 | 待更正 spec |
| I5 | 无 PDF | 低 | 可选 |
| I6 | `.bak` 混淆 | 低 | 已删；可能再产生 |
