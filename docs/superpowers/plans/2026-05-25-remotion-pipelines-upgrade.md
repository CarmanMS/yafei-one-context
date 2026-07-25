# remotion-pipelines 升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 remotion-video-skill 的场景组件模式替换 remotion-pipelines 的 Region/manifest 渲染链路，保留 A/B 音频策略可切换能力。

**Architecture:** SRT + WAV 通过 generate-audioconfig.mjs 生成 audioConfig.ts（单一数据源），Scene 组件按此渲染，Audio 适配层根据 audioFile 字段自动选择 single/split 模式。Remotion 原生 render 一步输出含音频的 MP4。

**Tech Stack:** Remotion 4, React 18, TypeScript, Node.js (ESM), ffprobe/ffmpeg

---

## File Structure

### 新建文件

| 文件 | 职责 |
|------|------|
| `skills/remotion-pipelines/scripts/generate-audioconfig.mjs` | SRT 解析 → audioConfig.ts 生成器（策略 A/B） |
| `skills/remotion-pipelines/src/Root.tsx` | Remotion Composition 注册 |
| `skills/remotion-pipelines/src/audioConfig.ts` | 生成器输出，SceneConfig 接口 + SCENES 数组 + 辅助函数 |
| `skills/remotion-pipelines/src/scenes/index.tsx` | 主视频组件：Scene 编排 + Audio 适配层 |
| `skills/remotion-pipelines/src/hooks/useCurrentSceneIndex.ts` | 根据当前帧号返回场景索引 |

### 删除文件

| 文件 | 原因 |
|------|------|
| `skills/remotion-pipelines/src/index.tsx` | 旧入口，被 Root.tsx + scenes/index.tsx 替代 |
| `skills/remotion-pipelines/src/composition.tsx` | 旧 Composition，不再使用 |
| `skills/remotion-pipelines/src/manifest-loader.ts` | manifest Zod schema，不再使用 |
| `skills/remotion-pipelines/src/components/*.tsx` (10 个 Region) | 被 Scene 组件替代 |
| `skills/remotion-pipelines/src/backgrounds/*.tsx` (6 个) | 不迁移，按需新建 |
| `skills/remotion-pipelines/src/diagrams/*.tsx` (7 个) | 不迁移，按需新建 |
| `skills/remotion-pipelines/scripts/slabs-to-manifest.mjs` | 被 generate-audioconfig.mjs 替代 |
| `skills/remotion-pipelines/scripts/finalize-ffmpeg.mjs` | 不再需要 FFmpeg 后合成 |
| `skills/remotion-pipelines/scripts/render-still-test.mjs` | 不再需要 |
| `skills/remotion-pipelines/public/render-input.json` | 不再需要 |
| `skills/remotion-pipelines/public/render-props.json` | 不再需要 |
| `skills/remotion-pipelines/public/cosmic-bg.js` | 不再需要 |
| `skills/remotion-pipelines/cli.js` | 旧 CLI，重建 |
| `skills/remotion-pipelines/manifest-schema.md` | 不再使用 manifest |

### 修改文件

| 文件 | 变更 |
|------|------|
| `skills/remotion-pipelines/package.json` | 更新 scripts、调整依赖 |
| `skills/remotion-pipelines/remotion.config.ts` | 简化配置 |
| `skills/remotion-pipelines/tsconfig.json` | 确保 module/node16 兼容 |
| `skills/remotion-pipelines/SKILL.md` | 重写 |

---

### Task 1: 清理旧文件

**Files:**
- Delete: `skills/remotion-pipelines/src/components/*.tsx`
- Delete: `skills/remotion-pipelines/src/backgrounds/*.tsx`
- Delete: `skills/remotion-pipelines/src/diagrams/*.tsx`
- Delete: `skills/remotion-pipelines/src/manifest-loader.ts`
- Delete: `skills/remotion-pipelines/src/composition.tsx`
- Delete: `skills/remotion-pipelines/src/index.tsx`
- Delete: `skills/remotion-pipelines/scripts/slabs-to-manifest.mjs`
- Delete: `skills/remotion-pipelines/scripts/finalize-ffmpeg.mjs`
- Delete: `skills/remotion-pipelines/scripts/render-still-test.mjs`
- Delete: `skills/remotion-pipelines/public/render-input.json`
- Delete: `skills/remotion-pipelines/public/render-props.json`
- Delete: `skills/remotion-pipelines/public/cosmic-bg.js`
- Delete: `skills/remotion-pipelines/cli.js`
- Delete: `skills/remotion-pipelines/manifest-schema.md`

- [ ] **Step 1: 删除旧源码文件**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
rm -rf src/components src/backgrounds src/diagrams src/manifest-loader.ts src/composition.tsx src/index.tsx
```

- [ ] **Step 2: 删除旧脚本和公共文件**

```bash
rm -f scripts/slabs-to-manifest.mjs scripts/finalize-ffmpeg.mjs scripts/render-still-test.mjs
rm -f public/render-input.json public/render-props.json public/cosmic-bg.js
```

- [ ] **Step 3: 删除旧 CLI 和 schema 文档**

```bash
rm -f cli.js manifest-schema.md
```

- [ ] **Step 4: 清空残留的空目录**

```bash
rmdir src/components src/backgrounds src/diagrams 2>/dev/null; true
```

- [ ] **Step 5: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add -u skills/remotion-pipelines/
git commit -m "chore(remotion-pipelines): remove old Region/manifest source files"
```

---

### Task 2: 编写 generate-audioconfig.mjs（SRT 解析 + audioConfig.ts 生成）

**Files:**
- Create: `skills/remotion-pipelines/scripts/generate-audioconfig.mjs`

- [ ] **Step 1: 编写 generate-audioconfig.mjs**

```javascript
#!/usr/bin/env node
/**
 * generate-audioconfig.mjs
 *
 * 从 SRT + WAV 生成 audioConfig.ts
 *
 * 策略 A (默认): SRT 时间戳 → durationInFrames，audioFile 统一指向完整 WAV
 * 策略 B (--mode split): ffmpeg 按 SRT 切分 WAV → ffprobe 测时长 → per-scene audioFile
 *
 * 用法:
 *   node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav
 *   node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav --mode split
 *   node scripts/generate-audioconfig.mjs --srt script.srt --audio voiceover.wav --out src/
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { parse as pathParse, dirname, join, basename } from "path";
import { execSync } from "child_process";

// ── CLI 参数解析 ──────────────────────────────────────────

function parseArgs(argv) {
  const args = { srt: "", audio: "", mode: "single", out: "src" };
  for (let i = 2; i < argv.length; i++) {
    switch (argv[i]) {
      case "--srt":   args.srt = argv[++i]; break;
      case "--audio": args.audio = argv[++i]; break;
      case "--mode":  args.mode = argv[++i]; break;  // "single" | "split"
      case "--out":   args.out = argv[++i]; break;
    }
  }
  if (!args.srt || !args.audio) {
    console.error("用法: generate-audioconfig.mjs --srt <file> --audio <file> [--mode single|split] [--out dir]");
    process.exit(1);
  }
  return args;
}

// ── SRT 解析 ──────────────────────────────────────────────

function parseSrtTime(ts) {
  // "00:01:23,456" → 毫秒
  const [hms, ms] = ts.trim().replace(",", ".").split(".");
  const [h, m, s] = hms.split(":").map(Number);
  return ((h * 3600 + m * 60 + s) * 1000) + Math.floor(Number(`0.${ms}`) * 1000);
}

function parseSrt(content) {
  const blocks = content.trim().replace(/\r\n/g, "\n").split(/\n\n+/);
  const scenes = [];

  for (const block of blocks) {
    const lines = block.split("\n");
    if (lines.length < 3) continue;

    const seq = parseInt(lines[0], 10);
    if (isNaN(seq)) continue;

    const timeLine = lines[1];
    const match = timeLine.match(
      /(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/
    );
    if (!match) continue;

    const startMs = parseSrtTime(match[1]);
    const endMs = parseSrtTime(match[2]);
    const text = lines.slice(2).join("\n").trim();

    // 场景 ID: 01, 02, ... 两位序号
    const id = String(seq).padStart(2, "0");
    // 标题: 取第一行文本的前 20 字符
    const title = text.split("\n")[0].slice(0, 20);

    scenes.push({ seq, id, title, startMs, endMs, text });
  }

  return scenes;
}

// ── 策略 A: SRT → frames，单 WAV ──────────────────────────

function generateSingle(args, scenes) {
  const FPS = 30;
  const audioBasename = basename(args.audio);
  const audioPublicPath = `audio/${audioBasename}`;

  // 确保 WAV 文件在 public/audio/ 下
  const publicAudioDir = join(dirname(args.out), "public", "audio");
  mkdirSync(publicAudioDir, { recursive: true });
  const destWav = join(publicAudioDir, audioBasename);
  if (!existsSync(destWav)) {
    // 如果源文件不在 public/audio/ 下，复制过去
    const srcAbs = args.audio.startsWith("/") ? args.audio : join(process.cwd(), args.audio);
    if (srcAbs !== destWav) {
      execSync(`cp "${srcAbs}" "${destWav}"`);
      console.log(`📋 复制 ${audioBasename} → public/audio/`);
    }
  }

  const entries = scenes.map((s) => ({
    id: s.id,
    title: s.title,
    durationInFrames: Math.ceil((s.endMs - s.startMs) / 1000 * FPS),
    audioFile: audioPublicPath,
  }));

  return entries;
}

// ── 策略 B: 切分 WAV + ffprobe ────────────────────────────

function generateSplit(args, scenes) {
  const FPS = 30;
  const publicAudioDir = join(dirname(args.out), "public", "audio");
  mkdirSync(publicAudioDir, { recursive: true });

  const audioAbs = args.audio.startsWith("/") ? args.audio : join(process.cwd(), args.audio);
  const entries = [];

  for (const scene of scenes) {
    const outFile = join(publicAudioDir, `${scene.id}.mp3`);
    const audioPublicPath = `audio/${scene.id}.mp3`;

    if (!existsSync(outFile)) {
      const startSec = scene.startMs / 1000;
      const durationSec = (scene.endMs - scene.startMs) / 1000;
      execSync(
        `ffmpeg -y -i "${audioAbs}" -ss ${startSec} -t ${durationSec} -vn -ar 32000 -ac 1 "${outFile}" 2>/dev/null`
      );
      console.log(`✂️ 切分 ${scene.id}.mp3`);
    } else {
      console.log(`⏭️ 跳过 ${scene.id}.mp3 (已存在)`);
    }

    // ffprobe 测时长
    const probeOut = execSync(
      `ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${outFile}"`,
      { encoding: "utf-8" }
    ).trim();
    const duration = parseFloat(probeOut) || 0;
    const frames = Math.max(1, Math.ceil(duration * FPS));

    entries.push({
      id: scene.id,
      title: scene.title,
      durationInFrames: frames,
      audioFile: audioPublicPath,
    });
  }

  return entries;
}

// ── 生成 audioConfig.ts ──────────────────────────────────

function writeAudioConfig(entries, outDir) {
  const scenesLines = entries.map((e) =>
    `  { id: "${e.id}", title: "${e.title.replace(/"/g, '\\"')}", durationInFrames: ${e.durationInFrames}, audioFile: "${e.audioFile}" }`
  );
  const scenesContent = scenesLines.join(",\n");

  const totalFrames = entries.reduce((sum, e) => sum + e.durationInFrames, 0) + 60;

  const content = `// 场景配置（由 generate-audioconfig.mjs 自动生成，请勿手动修改）

export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

export const SCENES: SceneConfig[] = [
${scenesContent},
];

// 计算场景起始帧
export function getSceneStart(sceneIndex: number): number {
  return SCENES.slice(0, sceneIndex).reduce((sum, s) => sum + s.durationInFrames, 0);
}

// 总帧数（加上尾部缓冲）
export const TOTAL_FRAMES = SCENES.reduce((sum, s) => sum + s.durationInFrames, 0) + 60;

// 帧率
export const FPS = 30;
`;

  const outPath = join(outDir, "audioConfig.ts");
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, content);
  console.log(`\n📝 已生成 ${outPath}`);
  console.log(`   场景数: ${entries.length}, 总帧数: ${totalFrames}`);
}

// ── 主流程 ────────────────────────────────────────────────

function main() {
  const args = parseArgs(process.argv);

  console.log(`🎬 generate-audioconfig`);
  console.log(`   SRT: ${args.srt}`);
  console.log(`   Audio: ${args.audio}`);
  console.log(`   Mode: ${args.mode}`);
  console.log("");

  const srtContent = readFileSync(args.srt, "utf-8");
  const scenes = parseSrt(srtContent);

  if (scenes.length === 0) {
    console.error("❌ SRT 解析失败：未找到有效的字幕段");
    process.exit(1);
  }

  console.log(`📄 解析到 ${scenes.length} 个字幕段`);

  const entries = args.mode === "split"
    ? generateSplit(args, scenes)
    : generateSingle(args, scenes);

  writeAudioConfig(entries, args.out);

  console.log("✅ 完成");
}

main();
```

- [ ] **Step 2: 创建测试用 SRT 文件验证解析**

手动构造一个 3 段的测试 SRT：

```bash
mkdir -p /tmp/audioconfig-test
cat > /tmp/audioconfig-test/test.srt << 'EOF'
1
00:00:00,000 --> 00:00:03,500
开场介绍

2
00:00:03,500 --> 00:00:08,200
核心概念讲解

3
00:00:08,200 --> 00:00:12,000
总结与展望
EOF
```

运行生成器（无音频文件，策略 A 会尝试复制，先测解析部分）：

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
touch /tmp/audioconfig-test/voiceover.wav
node scripts/generate-audioconfig.mjs --srt /tmp/audioconfig-test/test.srt --audio /tmp/audioconfig-test/voiceover.wav --out /tmp/audioconfig-test/src
```

Expected: 生成 `/tmp/audioconfig-test/src/audioConfig.ts`，包含 3 个场景，帧数分别为 105、141、114。

- [ ] **Step 3: 验证生成的 audioConfig.ts 内容**

```bash
cat /tmp/audioconfig-test/src/audioConfig.ts
```

Expected: SceneConfig 接口 + SCENES 数组 + getSceneStart + TOTAL_FRAMES + FPS。

- [ ] **Step 4: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/scripts/generate-audioconfig.mjs
git commit -m "feat(remotion-pipelines): add generate-audioconfig script (SRT→audioConfig.ts, strategy A/B)"
```

---

### Task 3: 编写 useCurrentSceneIndex hook

**Files:**
- Create: `skills/remotion-pipelines/src/hooks/useCurrentSceneIndex.ts`

- [ ] **Step 1: 创建 hook**

```typescript
import { useCurrentFrame } from "remotion";
import { SCENES } from "../audioConfig";

/**
 * 根据当前全局帧号返回场景索引。
 * 全局帧号 = Sequence 的 from 偏移 + Sequence 内部的 local frame，
 * 但此处直接用 useCurrentFrame() 的全局帧来查找。
 */
export function useCurrentSceneIndex(): number {
  const frame = useCurrentFrame();
  let accumulated = 0;
  for (let i = 0; i < SCENES.length; i++) {
    accumulated += SCENES[i].durationInFrames;
    if (frame < accumulated) return i;
  }
  return SCENES.length - 1;
}
```

- [ ] **Step 2: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/src/hooks/useCurrentSceneIndex.ts
git commit -m "feat(remotion-pipelines): add useCurrentSceneIndex hook"
```

---

### Task 4: 编写 scenes/index.tsx（主视频组件 + Audio 适配层）

**Files:**
- Create: `skills/remotion-pipelines/src/scenes/index.tsx`

- [ ] **Step 1: 创建 scenes/index.tsx**

```tsx
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
} from "remotion";
import { SCENES, getSceneStart, TOTAL_FRAMES } from "../audioConfig";
import { useCurrentSceneIndex } from "../hooks/useCurrentSceneIndex";

/**
 * Audio 适配层：根据 SCENES 中 audioFile 的一致性自动判断模式。
 * - 所有 scene 的 audioFile 相同 → single 模式（方案 A）：播放一个完整 WAV
 * - 不同 → split 模式（方案 B）：每场景播放各自的音频
 */
const isSingleAudio = new Set(SCENES.map((s) => s.audioFile)).size === 1;

/**
 * 场景路由器：根据 scene.id 路由到对应的场景组件。
 * AI 生成新场景时在此添加 case。
 */
function SceneRouter({ id, index }: { id: string; index: number }) {
  // 占位场景：所有未匹配的 id 使用默认渲染
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0b",
        color: "#f1efea",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 64,
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 120, color: "#e8a090", marginBottom: 24 }}>
          {String(index + 1).padStart(2, "0")}
        </div>
        <div>{SCENES[index]?.title ?? id}</div>
      </div>
    </AbsoluteFill>
  );
}

/**
 * 主视频组件：场景编排 + Audio 适配
 */
export const Video: React.FC = () => {
  useCurrentSceneIndex(); // 预加载 hook，确保帧驱动正常

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0b" }}>
      {/* 场景组件 */}
      {SCENES.map((scene, idx) => (
        <Sequence
          key={scene.id}
          from={getSceneStart(idx)}
          durationInFrames={scene.durationInFrames}
        >
          <SceneRouter id={scene.id} index={idx} />
        </Sequence>
      ))}

      {/* Audio 适配层 */}
      {isSingleAudio ? (
        // 方案 A：完整 WAV
        <Audio src={staticFile(SCENES[0].audioFile)} />
      ) : (
        // 方案 B：per-scene 音频
        SCENES.map((scene, idx) => (
          <Sequence key={scene.id} from={getSceneStart(idx)} durationInFrames={scene.durationInFrames}>
            <Audio src={staticFile(scene.audioFile)} />
          </Sequence>
        ))
      )}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/src/scenes/index.tsx
git commit -m "feat(remotion-pipelines): add scenes/index.tsx with Audio adapter (single/split auto-detect)"
```

---

### Task 5: 编写 Root.tsx（Composition 注册）

**Files:**
- Create: `skills/remotion-pipelines/src/Root.tsx`

- [ ] **Step 1: 创建 Root.tsx**

```tsx
import React from "react";
import { Composition } from "remotion";
import { Video } from "./scenes/index";
import { TOTAL_FRAMES, FPS } from "./audioConfig";

const CANVAS_W = 1920;
const CANVAS_H = 1080;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="SlideVideo"
      component={Video}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={CANVAS_W}
      height={CANVAS_H}
    />
  );
};
```

- [ ] **Step 2: 创建 src/index.ts（Remotion 入口）**

```typescript
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

- [ ] **Step 3: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/src/Root.tsx skills/remotion-pipelines/src/index.ts
git commit -m "feat(remotion-pipelines): add Root.tsx composition registration + index.ts entry"
```

---

### Task 6: 放置占位 audioConfig.ts + 更新 package.json 和配置文件

**Files:**
- Create: `skills/remotion-pipelines/src/audioConfig.ts` (占位)
- Modify: `skills/remotion-pipelines/package.json`
- Modify: `skills/remotion-pipelines/remotion.config.ts`
- Modify: `skills/remotion-pipelines/tsconfig.json`

- [ ] **Step 1: 创建占位 audioConfig.ts**

```typescript
// 占位：运行 generate-audioconfig.mjs 后会被覆盖
export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

export const SCENES: SceneConfig[] = [
  { id: "01", title: "占位", durationInFrames: 90, audioFile: "audio/placeholder.wav" },
];

export function getSceneStart(sceneIndex: number): number {
  return SCENES.slice(0, sceneIndex).reduce((sum, s) => sum + s.durationInFrames, 0);
}

export const TOTAL_FRAMES = 150;
export const FPS = 30;
```

- [ ] **Step 2: 确保 public/audio/ 目录存在**

```bash
mkdir -p /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines/public/audio
touch /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines/public/audio/.gitkeep
```

- [ ] **Step 3: 更新 package.json**

替换整个文件为：

```json
{
  "name": "remotion-pipelines",
  "version": "2.0.0",
  "description": "Scene-based video pipeline for Remotion (audioConfig-driven)",
  "main": "src/index.ts",
  "type": "module",
  "scripts": {
    "dev": "remotion studio src/index.ts",
    "render": "remotion render src/index.ts SlideVideo out/final.mp4",
    "generate-config": "node scripts/generate-audioconfig.mjs"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "remotion": "^4.0.0"
  },
  "devDependencies": {
    "@remotion/cli": "^4.0.0",
    "@types/react": "^18.2.0",
    "typescript": "^5.3.0"
  }
}
```

注意：去掉了 three/fiber/drei/zod，因为不迁移旧背景和图表。

- [ ] **Step 4: 更新 remotion.config.ts**

```typescript
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setChromiumOptions({ gl: "angle" });
```

- [ ] **Step 5: 确认 tsconfig.json 兼容**

读取当前 tsconfig.json，确保 compilerOptions.module 为 "ESNext" 或 "NodeNext"，jsx 为 "react-jsx"：

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "resolveJsonModule": true,
    "declaration": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 6: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/src/audioConfig.ts skills/remotion-pipelines/public/audio/.gitkeep skills/remotion-pipelines/package.json skills/remotion-pipelines/remotion.config.ts skills/remotion-pipelines/tsconfig.json
git commit -m "feat(remotion-pipelines): add placeholder audioConfig, update package.json and configs for v2"
```

---

### Task 7: 安装依赖并验证 Remotion Studio 启动

**Files:**
- Modify: `skills/remotion-pipelines/package-lock.json` (npm install 生成)

- [ ] **Step 1: 删除旧的 node_modules 和 lock 文件，重新安装**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
rm -rf node_modules package-lock.json
npm install
```

Expected: 安装成功，无报错。

- [ ] **Step 2: 验证 Remotion Studio 能启动**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
npx remotion studio src/index.ts
```

Expected: 浏览器打开 Remotion Studio，显示占位场景（01 序号 + "占位" 标题）。如果缺少音频文件会有 Audio 警告但不影响渲染。按 Ctrl+C 关闭。

- [ ] **Step 3: 提交 lock 文件**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/package-lock.json
git commit -m "chore(remotion-pipelines): reinstall dependencies for v2"
```

---

### Task 8: 端到端验证（SRT → audioConfig → render）

**Files:**
- No new files

- [ ] **Step 1: 准备测试数据**

使用 Task 2 中创建的测试 SRT，再创建一个静音 WAV 作为占位：

```bash
ffmpeg -f lavfi -i anullsrc=r=32000:cl=mono -t 12 -f wav /tmp/audioconfig-test/voiceover.wav
```

- [ ] **Step 2: 运行 generate-audioconfig.mjs（策略 A）**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
node scripts/generate-audioconfig.mjs --srt /tmp/audioconfig-test/test.srt --audio /tmp/audioconfig-test/voiceover.wav
```

Expected: `src/audioConfig.ts` 更新为 3 个场景，`public/audio/voiceover.wav` 存在。

- [ ] **Step 3: 启动 Remotion Studio 验证预览**

```bash
npx remotion studio src/index.ts
```

Expected: 3 个场景依次显示序号 01/02/03 和标题。音轨播放静音 WAV。

- [ ] **Step 4: 渲染测试 MP4**

```bash
npx remotion render src/index.ts SlideVideo out/test.mp4 --concurrency=1
```

Expected: 生成 `out/test.mp4`，时长约 12 秒。

- [ ] **Step 5: 验证策略 B**

```bash
node scripts/generate-audioconfig.mjs --srt /tmp/audioconfig-test/test.srt --audio /tmp/audioconfig-test/voiceover.wav --mode split
```

Expected: `public/audio/` 下生成 `01.mp3`, `02.mp3`, `03.mp3`。`src/audioConfig.ts` 中每个场景 audioFile 不同。Remotion Studio 重新加载后预览正常。

- [ ] **Step 6: 切回策略 A 验证可切换**

```bash
node scripts/generate-audioconfig.mjs --srt /tmp/audioconfig-test/test.srt --audio /tmp/audioconfig-test/voiceover.wav --mode single
```

Expected: audioConfig.ts 恢复 single 模式。

---

### Task 9: 重写 SKILL.md

**Files:**
- Modify: `skills/remotion-pipelines/SKILL.md`

- [ ] **Step 1: 重写 SKILL.md**

```markdown
---
name: remotion-pipelines
description: >-
  场景组件驱动的 Remotion 视频流水线。audioConfig.ts 为单一数据源，SRT→音画同步，
  Remotion 原生 render 一步出 MP4。支持 A/B 音频策略切换。
  触发词：Remotion pipeline、视频生成、scene video、audioConfig、SRT 视频。
---

# Remotion Pipelines — Scene-Based Audio-Driven Video Engine

## 核心架构

```
SRT + WAV → generate-audioconfig → audioConfig.ts → Scene 组件 + <Audio> → Remotion render → MP4
```

关键设计：
1. **audioConfig.ts 是单一数据源** — 场景时长、音频文件、帧率全部在此
2. **音频驱动时长** — 策略 B 用 ffprobe 实测时长；策略 A 用 SRT 时间戳换算
3. **场景即章节** — 一个概念 = 一个 Scene 组件 = 一段 SRT 段
4. **Audio 自动适配** — single/split 模式由数据自动推断，Scene 代码零改动

## Pipeline 步骤

| Step | 名称 | 产物 |
|------|------|------|
| 1 | Download | 原始文章 Markdown |
| 2 | Structure | `content-structure.md` |
| 3 | Script | `script.srt` |
| 4 | TTS | `voiceover.wav` |
| 5 | AudioConfig | `src/audioConfig.ts` |
| 6 | Scenes | AI 生成场景组件代码 |
| 7 | Render | `final.mp4` |
| 8 | Publish | 交付物 |

### Step 5: AudioConfig

```bash
node scripts/generate-audioconfig.mjs --srt <path> --audio <path>
```

策略选择：
- 默认（策略 A）：SRT 时间戳映射帧数，播放完整 WAV
- `--mode split`（策略 B）：ffmpeg 切分 WAV + ffprobe 测时长

### Step 6: Scenes

AI 读取 SRT 内容 + audioConfig.ts，为每个场景生成 React 组件。

新建文件 `src/scenes/SceneXxx.tsx`，然后在 `scenes/index.tsx` 的 `SceneRouter` 中添加路由。

场景组件遵循 remotion-video-skill 的 3B1B 风格指南：逐步构建、颜色语义化、探索式叙事。

### Step 7: Render

```bash
npx remotion render src/index.ts SlideVideo out/final.mp4
```

一步输出含音频的 MP4，无需 FFmpeg 后合成。

## audioConfig.ts 格式

```typescript
export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

export const SCENES: SceneConfig[] = [...];
export function getSceneStart(sceneIndex: number): number { ... }
export const TOTAL_FRAMES = ...;
export const FPS = 30;
```

此文件由 generate-audioconfig.mjs 生成，不要手动编辑。

## Audio 适配层

`scenes/index.tsx` 自动判断模式：

```typescript
const isSingleAudio = new Set(SCENES.map(s => s.audioFile)).size === 1;
```

- **single**：一个 `<Audio src={staticFile(SCENES[0].audioFile)} />` 播放完整 WAV
- **split**：每个 `<Sequence>` 内嵌 `<Audio src={staticFile(scene.audioFile)} />`

切换策略只需重新运行 generate-audioconfig.mjs，Scene 组件代码不用动。

## 场景组件开发

参考 `repos/reference/remotion-video-skill/SKILL.md` 中的完整指南，包括：
- 3B1B 风格：Why→What、逐步构建、颜色语义化
- 过程动画：StepByStep、ValueFlyIn、SlidingWindow
- Scene 组件原则：单一职责、独立动画、延迟出现

## CLI 速查

```bash
# 生成 audioConfig（策略 A）
npm run generate-config -- --srt script.srt --audio voiceover.wav

# 生成 audioConfig（策略 B）
npm run generate-config -- --srt script.srt --audio voiceover.wav --mode split

# 预览
npm run dev

# 渲染
npm run render
```

## 文件结构

```
skills/remotion-pipelines/
├── SKILL.md
├── package.json
├── remotion.config.ts
├── tsconfig.json
├── scripts/
│   └── generate-audioconfig.mjs
├── src/
│   ├── index.ts              # Remotion 入口
│   ├── Root.tsx              # Composition 注册
│   ├── audioConfig.ts        # 自动生成，不手改
│   ├── scenes/
│   │   └── index.tsx         # 主视频组件 + Audio 适配 + SceneRouter
│   └── hooks/
│       └── useCurrentSceneIndex.ts
└── public/
    └── audio/                # WAV / MP3 音频文件
```
```

- [ ] **Step 2: 提交**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add skills/remotion-pipelines/SKILL.md
git commit -m "docs(remotion-pipelines): rewrite SKILL.md for scene-based v2 pipeline"
```

---

## Self-Review

1. **Spec coverage check:**
   - SRT→frames 策略 A ✅ (Task 2)
   - split+ffprobe 策略 B ✅ (Task 2)
   - audioConfig.ts 格式与 remotion-video-skill 一致 ✅ (Task 2, 6)
   - Audio 适配层 single/split 自动判断 ✅ (Task 4)
   - useCurrentSceneIndex hook ✅ (Task 3)
   - SceneRouter ✅ (Task 4)
   - Root.tsx Composition 注册 ✅ (Task 5)
   - 删除旧文件 ✅ (Task 1)
   - 不迁移旧资产 ✅ (Task 1)
   - 更新 package.json ✅ (Task 6)
   - 重写 SKILL.md ✅ (Task 9)
   - 端到端验证 ✅ (Task 8)

2. **Placeholder scan:** 无 TBD/TODO/implement later。所有代码步骤均包含完整内容。

3. **Type consistency:**
   - `SceneConfig` 接口: id/title/durationInFrames/audioFile — Task 2 生成器和 Task 4 消费端一致
   - `getSceneStart(sceneIndex)` — Task 2 定义、Task 4 使用，签名匹配
   - `TOTAL_FRAMES` / `FPS` — Task 2 定义、Task 5 使用，命名一致
   - `useCurrentSceneIndex()` — Task 3 定义、Task 4 使用，签名匹配
   - `Video` 组件 — Task 4 定义、Task 5 在 Root.tsx 中 import，命名匹配
   - Composition id `"SlideVideo"` — Task 5 定义、package.json render script 引用一致