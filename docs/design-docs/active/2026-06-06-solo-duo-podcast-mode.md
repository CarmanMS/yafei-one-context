# Solo/Duo 播客模式设计

> 日期: 2026-06-06 | 状态: draft | 作者: 水猿

## 背景

content-pipeline 当前默认且唯一的 TTS 路径是 `volc-podcast-tts action=0`（双人播客）。
用户希望支持单人旁白模式，在立项时选择 solo/duo，pipeline 各环节自动适配。

## 现状分析

| 环节 | 现在 | 与人数的关系 |
|------|------|-------------|
| spec frontmatter | `tts.engine: volc-podcast-tts`, `action: 0` | 隐式绑定双人 |
| TTS 引擎 | `volc-podcast-tts`（仅 action=0/3/4，全是双人） | 无单人能力 |
| 脚本输入 | `00-podcast-source.md`（长文给服务端改写） | 无人数约束 |
| SRT + WAV | Whisper 生成，时间轴真源 | speaker-agnostic |
| remotion-pipelines | audioConfig → Scene → render → burn-sub | 完全不区分人数 |

关键发现：`doubao-dialogue-tts --mono` 已支持单人朗读，无需新建 TTS skill。

## 设计方案（方案 A — spec mode 字段路由）

### 核心思路

在 `spec.md` 的 `tts` frontmatter 中新增 `mode: solo | duo` 字段，
PM 立项时选择模式，TTS 路由标准和代理门禁据此自动切换引擎和输入文件。

从 WAV+SRT 往下的所有环节（scene-boundaries → audioConfig → Remotion → burn-subtitles）
完全不改动。

### spec frontmatter 扩展

```yaml
tts:
  engine: volc-podcast-tts     # 最终使用的引擎（mode=solo 时自动覆盖为 doubao-dialogue-tts）
  mode: duo                     # solo | duo（新增，默认 duo，缺省等价 duo）
  action: 0                     # duo 专用；mode=solo 时忽略
  authority: wav_srt            # 不变
  override_reason: ""           # action≠0 时必填（duo 专用）
```

### 两条路径对比

| | duo（双人播客，默认） | solo（单人旁白） |
|---|---|---|
| TTS 引擎 | `volc-podcast-tts` | `doubao-dialogue-tts --mono` |
| TTS 输入 | `00-podcast-source.md`（长文要点） | `01-script.md`（逐字稿，纯文本） |
| 脚本格式 | 自由格式（服务端改写） | 纯文本，不带 `男：/女：` 前缀 |
| 输出 | `media/voiceover.wav` + Whisper→SRT | `media/voiceover.wav` + Whisper→SRT |
| 下游 | scene-boundaries → audioConfig → Remotion | 完全一样 |

### 代理门禁

```
1. 读 spec.md 的 tts.mode（缺省=duo）
2. mode=duo：
   - 现有逻辑不变（检查 action、00-podcast-source.md 等）
3. mode=solo：
   - 确认 01-script.md 存在且非空
   - 忽略 action / override_reason 字段
   - 使用 doubao-dialogue-tts --mono
4. 禁止：mode=solo 时不得使用 volc-podcast-tts
```

### PM 立项流程变化

PM agent 创建 content-pipeline feature 时：
1. 询问用户选择 solo 还是 duo
2. `mode: solo` → 提示用户准备 `01-script.md` 逐字稿
3. `mode: duo` → 现有流程不变，准备 `00-podcast-source.md`

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `features/_template/spec-content-pipeline.md` | frontmatter 加 `mode: duo` + 口播表增加 solo 说明 |
| `knowledge/standards/content-pipeline-tts-routing.md` | 增加 solo 路径、门禁规则、决策表 |
| `meta/agents.yaml` (PM agent instructions) | PM 立项时增加 solo/duo 选择引导 |

### 明确不改的文件

- `skills/remotion-pipelines/` — 全部不动（已 speaker-agnostic）
- `skills/volc-podcast-tts/` — 不动
- `skills/doubao-dialogue-tts/` — 不动（已有 --mono 能力）
- `src/scenes/index.tsx`、`audioConfig.ts` — 不动

## 向后兼容

- `mode` 字段缺省时等价 `duo`，所有已有 spec 无需修改
- duo 路径行为完全不变
- 零代码改动，全部是文档/模板/标准层

## 被排除的方案

| 方案 | 排除理由 |
|------|---------|
| B: 两套模板 (solo-template / duo-template) | 大量内容重复，维护成本翻倍 |
| C: 新建 solo-podcast-tts skill | doubao-dialogue-tts --mono 已够用，再包一层无必要 |
