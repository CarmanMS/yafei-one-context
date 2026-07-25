# AI 造 AI — 可选 Cosmic Cycle 昼夜星空背景

## 元数据

| 字段 | 值 |
|------|-----|
| 日期 | 2026-05-23 |
| 状态 | approved（用户确认：方案 1 + 插件可选 + 仅本 feature 启用） |
| 归属 feature | `features/content-pipeline/ai-companies-build-ai-mid-video` |
| 归属 skill | `skills/remotion-deck` |
| 非目标 | 全仓默认星空背景；HTML wav 成片；改口播 WAV |

## 1. 目标

1. **整片一条时间轴**：约 390s 内完成 **深夜 → 黎明 → 白昼 → 黄昏 → 深夜**（1 圈）。
2. **插件可选**：Skill 只提供通用「composition 级全局背景槽位」+ `plugins/cosmic-cycle` 包；未启用时行为与现网一致。
3. **本 feature 启用**：`content-slabs.json` 设 `"theme": "cosmic-cycle"`。

## 2. 架构

```
remotion-data.json
  themeId: cosmic-cycle
  customTheme.background.scope: global
  customTheme.background.plugin: cosmic-cycle
        │
        ▼
Video.tsx（composition 级 useCurrentFrame）
  └─ resolveBackgroundPlugin('cosmic-cycle') → CosmicCycleProvider
        │
        ▼
SlideShell：scope=global 时跳过 per-slide 背景（TransparentSlideProvider）
```

### Skill 改动（通用、向后兼容）

| 文件 | 改动 |
|------|------|
| `src/types.ts` | `background.scope`, `background.plugin`, `background.cycleCount` |
| `src/Video.tsx` | 全局背景层（仅 `scope === 'global'` 且 `plugin` 已注册） |
| `src/components/SlideShell.tsx` | 全局模式不渲染 slide 背景 |
| `src/backgrounds/TransparentSlideProvider.tsx` | slide 级透明占位 |
| `src/plugins/PluginRegistry.ts` | 插件 id → 组件 |
| `src/plugins/cosmic-cycle/` | 昼夜星空实现 + README |

### 插件包（可选启用）

| 插件 id | 路径 | 说明 |
|---------|------|------|
| `cosmic-cycle` | `plugins/cosmic-cycle/CosmicCycleProvider.tsx` | Nano Banana 式宇宙昼夜循环 |

### Feature 改动（仅 ai-companies）

| 文件 | 改动 |
|------|------|
| `production/timing/content-slabs.json` | `"theme": "cosmic-cycle"` |

其它选题 **不修改** `content-slabs.json` 则不受影响。

## 3. 昼夜时间轴（1 圈 / 全片）

```
phase 0.00–0.25  深空夜（星点亮）
phase 0.25–0.35  黎明过渡
phase 0.35–0.55  白昼（星点隐、天顶变亮）
phase 0.55–0.65  黄昏过渡
phase 0.65–1.00  回到深空夜
```

`phase = frame / totalFrames`（composition 级帧，翻页不重置）。

## 4. 主题 `cosmic-cycle`

- 基于 `tech-evolve` 可读字号与 glass 卡片，保证白昼阶段文字仍清晰。
- `background: { strategy: 'orbs', scope: 'global', plugin: 'cosmic-cycle', cycleCount: 1 }`
- accent 偏紫/靛/青，与星空叙事一致。

## 5. 渲染流程

```bash
node skills/remotion-deck/cli.js bridge --project features/content-pipeline/ai-companies-build-ai-mid-video/production
node skills/remotion-deck/cli.js still --project ... --frame 0
node skills/remotion-deck/cli.js still --project ... --frame 4000
node skills/remotion-deck/cli.js render --project ... --concurrency 4
```

## 6. 未来其它视频如何启用

1. `content-slabs.json` 设 `"theme": "cosmic-cycle"`，或
2. `timing/custom-theme.json` 设 `background.scope: global` + `background.plugin: cosmic-cycle`

无需 fork skill；未写上述配置则仍用各主题默认 per-slide 背景。
