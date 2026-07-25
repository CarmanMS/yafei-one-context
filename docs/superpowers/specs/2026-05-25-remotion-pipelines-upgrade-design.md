# remotion-pipelines 升级设计：替换渲染链路

## 背景

现有 `skills/remotion-pipelines` 使用 Region/manifest 声明式布局 + FFmpeg 后合成架构。用户希望替换整个渲染链路，采用 `repos/reference/remotion-video-skill` 的场景组件模式，保留其原生能力不被魔改。

## 核心决策

- 采用 remotion-video-skill 原生的 Scene 组件开发模式
- 不迁移任何旧视觉资产（backgrounds/diagrams/Regions），全部新建
- 用 `audioConfig.ts` 作为单一数据源，格式与 remotion-video-skill 完全一致
- 音频策略支持 A/B 切换：A=SRT 时间戳映射完整 WAV，B=拆分 WAV + ffprobe

## 整体架构

```
                        ┌──────────────────────┐
                        │  audioConfig 生成器    │
                        │  generate-audioconfig │
  SRT + 完整WAV ───────▶│                      │──▶ audioConfig.ts ──▶ 原生链路
                        │  策略 A: srt→frames   │     (Scene组件
                        │  策略 B: split+ffprobe│      + <Audio>
                        └──────────────────────┘      + Remotion render)
                                                       → MP4
```

## audioConfig 生成器

脚本路径：`scripts/generate-audioconfig.mjs`

### 策略 A：SRT → frames（默认）

```
输入：script.srt + voiceover.wav
      ↓
SRT 解析 → 每个序号段的时间戳
      ↓
时间戳 × FPS → durationInFrames
      ↓
输出 audioConfig.ts（audioFile 统一指向 voiceover.wav）
```

SRT 时间戳换算：
- 格式：`00:00:01,500 --> 00:00:04,200`
- `durationInFrames = Math.ceil((endMs - startMs) / 1000 * FPS)`
- FPS = 30

SRT 段与场景 1:1 映射，SRT 编号顺序 = 场景顺序。

### 策略 B：split + ffprobe

```
输入：script.srt + voiceover.wav
      ↓
ffmpeg 按 SRT 时间戳切分 WAV → public/audio/01-intro.mp3, 02-xxx.mp3, ...
      ↓
ffprobe 逐文件测时长 → durationInFrames
      ↓
输出 audioConfig.ts（audioFile 指向 per-scene 文件）
```

### CLI 接口

```bash
# 策略 A（默认）
node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav

# 策略 B
node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav --mode split

# 指定输出目录
node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav --out src/
```

输出的 `audioConfig.ts` 格式两种策略完全一致，只有 `audioFile` 字段值不同。

## Scene 组件 + Audio 适配层

### 目录结构

```
src/
├── Root.tsx                     # Composition 注册
├── audioConfig.ts               # 生成器输出，不手改
├── scenes/
│   ├── index.tsx                # 主组件：场景编排 + Audio 适配
│   ├── SceneCover.tsx           # 封面场景（示例）
│   ├── SceneSplit.tsx           # 分栏场景
│   └── ...                      # AI 按需生成
├── hooks/
│   └── useCurrentSceneIndex.ts  # 从 remotion-video-skill 引入
└── backgrounds/                 # 按需新建
```

### Audio 适配层

`scenes/index.tsx` 中根据 audioFile 是否统一自动判断模式：

```tsx
const isSingleAudio = new Set(SCENES.map(s => s.audioFile)).size === 1;

// 方案 A：完整 WAV，从第 0 帧播放
{isSingleAudio && <Audio src={staticFile(SCENES[0].audioFile)} />}

// 方案 B：per-scene 音频，跟随 Sequence
{!isSingleAudio && SCENES.map((scene, idx) => (
  <Sequence key={scene.id} from={getSceneStart(idx)}>
    <Audio src={staticFile(scene.audioFile)} />
  </Sequence>
))}
```

不需要额外 config 字段，从数据本身推断。从方案 A 切到方案 B，Scene 组件代码零改动。

### SceneRouter

根据场景 ID 路由到对应组件，AI 生成新场景只需加一个 case。

### SRT 段与场景映射

SRT 编号顺序 = 场景顺序，1:1 映射。SRT 中每个段的序号作为 scene.id，格式 `01-cover`、`02-concept` 等。

## 资产处理

全部不迁移，从零构建：

| 类别 | 处理 |
|------|------|
| backgrounds/ | 不迁移，按需用 remotion-video-skill 推荐方式新建 |
| diagrams/ | 不迁移，场景内直接写动画 |
| Region 组件 | 不迁移，被 Scene 组件替代 |
| remotion.config.ts | 不复用，用新项目标准配置 |
| tsconfig.json | 新项目标准配置 |
| SKILL.md | 重写 |

### 删除清单

| 删除 | 原因 |
|------|------|
| `src/manifest-loader.ts` | 不再用 manifest |
| `src/components/*.tsx` (10个 Region) | 被 Scene 组件替代 |
| `scripts/slabs-to-manifest.mjs` | 被 generate-audioconfig.mjs 替代 |
| `scripts/finalize-ffmpeg.mjs` | 不再需要 FFmpeg 后合成 |
| `public/render-input.json` / `render-props.json` | 不再需要渲染输入 |
| `public/cosmic-bg.js` | HTML 预览被 Remotion Studio 替代 |
| `cli.js` 中的 validate/slabs/render 命令 | 重建新 CLI |

## 更新后的 Pipeline 步骤

| 步骤 | 内容 | 变化 |
|------|------|------|
| 1. Download | 原始 Markdown | 不变 |
| 2. Structure | content-structure.md | 不变 |
| 3. Script | script.srt | 不变 |
| 4. TTS | voiceover.wav | 不变 |
| 5. AudioConfig | 生成 audioConfig.ts | 替代原 Dual-Write |
| 6. Scenes | AI 生成场景组件代码 | 替代原 Review |
| 7. Render | `npx remotion render` 一步出 MP4 | 替代原两步渲染 |
| 8. Publish | 交付物 | 不变 |

### Step 5：AudioConfig

```bash
node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav
```

输出：`src/audioConfig.ts`

### Step 6：Scenes

- AI 读取 SRT 内容 + audioConfig，为每个场景生成对应的 React 组件
- 放入 `src/scenes/` 目录
- 更新 `scenes/index.tsx` 中的 SceneRouter

### Step 7：Render

```bash
npx remotion render MyVideo out/final.mp4
```

一步完成，音频片子同步输出。

## SKILL.md 更新要点

- 移除 Region/manifest/dual-write 相关描述
- 移除 slabs-to-manifest、finalize-ffmpeg 流程
- 新增 generate-audioconfig 用法
- 新增场景组件开发指南（引用 remotion-video-skill 的 3B1B 风格）
- Audio 适配层说明（single/split 自动判断）
- CLI 简化为 `generate-audioconfig` + `remotion render` 两条命令