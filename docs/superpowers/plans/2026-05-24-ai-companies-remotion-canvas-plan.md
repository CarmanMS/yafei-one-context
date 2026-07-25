# ai-companies-build-ai-mid-video remotion-canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `skills/remotion-canvas` CLI to discover content-pipeline `production/` directories, add a "tech" dark-mode brand, and generate a silent MP4 from the existing `sub.srt` for `ai-companies-build-ai-mid-video`.

**Architecture:** Minimal invasive changes to the CLI file-discovery layer and style engine; leverage existing beat-level Remotion rendering pipeline.

**Tech Stack:** Node.js, TypeScript, Remotion, Zod

---

### Task 1: Add `tech` brand to match-style.ts

**Files:**
- Modify: `skills/remotion-canvas/src/pipeline/match-style.ts`

Add a `tech` brand entry to `DEFAULT_STYLES` with dark-mode colors.

```ts
// Add this to DEFAULT_STYLES record
  tech: {
    brand: "tech",
    brandLabel: "Tech",
    darkMode: true,
    colors: {
      canvas: "#0a0e1a",
      surface1: "#111827",
      surface2: "#1a2234",
      surface3: "#252f42",
      surface4: "#303b50",
      ink: "#e5e7eb",
      inkMuted: "#9ca3af",
      inkSubtle: "#6b7280",
      primary: "#0ea5e9",
      primaryHover: "#0284c7",
      primarySoft: "#0ea5e918",
      onPrimary: "#ffffff",
      success: "#22c55e",
      warning: "#f59e0b",
      error: "#ef4444",
      hairline: "#1e293b",
      hairlineStrong: "#334155",
    },
  },
```

- [ ] **Step 1:** Insert the `tech` entry above into the `DEFAULT_STYLES` map after the `apple` entry.
- [ ] **Step 2:** Update `detectBrandFromContent` to return `"tech"` when the content includes "AI", "coding", "engineer", "tech", or "programming".

```ts
function detectBrandFromContent(content: string): string {
  const text = content.toLowerCase();
  if (text.includes("netflix") || text.includes("streaming")) return "netflix";
  if (text.includes("apple") || text.includes("ios") || text.includes("mac")) return "apple";
  if (text.includes("ai") || text.includes("coding") || text.includes("engineer") || text.includes("tech") || text.includes("programming")) return "tech";
  return "claude";
}
```

- [ ] **Step 3:** Commit

```bash
git add skills/remotion-canvas/src/pipeline/match-style.ts
git commit -m "feat(remotion-canvas): add tech brand to match-style pipeline"
```

---

### Task 2: Make chip colors dynamic in buildCompleteStyle

**Files:**
- Modify: `skills/remotion-canvas/src/pipeline/match-style.ts`

In `buildCompleteStyle`, the chip text color and divider color are hardcoded to Claude warm tones. Make them respect the passed `base` colors.

Find these two blocks in `buildCompleteStyle`:

```ts
chip: {
  backgroundColor: dark ? "#cc785c25" : "#cc785c18",
  textColor: "#cc785c",
  rounded: 9999,
  paddingX: 16,
  paddingY: 6,
},
divider: {
  color: dark ? "#333333" : "#e0dcd6",
  thickness: 1,
},
```

Replace with:

```ts
chip: {
  backgroundColor: `${base.colors?.primary || "#cc785c"}${dark ? "25" : "18"}`,
  textColor: base.colors?.primary || "#cc785c",
  rounded: 9999,
  paddingX: 16,
  paddingY: 6,
},
divider: {
  color: dark ? (base.colors?.hairline || "#333333") : (base.colors?.hairline || "#e0dcd6"),
  thickness: 1,
},
```

Also update `elevation` in dark mode. Find the existing elevation object in `buildCompleteStyle`:

```ts
elevation: {
  level1: "0 1px 2px rgba(0,0,0,0.06)",
  level2: "0 2px 8px rgba(0,0,0,0.08)",
  level3: "0 4px 16px rgba(0,0,0,0.12)",
},
```

Replace with a dark-aware version:

```ts
elevation: dark
  ? {
      level1: "0 1px 2px rgba(0,0,0,0.4)",
      level2: "0 4px 12px rgba(0,0,0,0.5)",
      level3: "0 8px 24px rgba(0,0,0,0.6)",
    }
  : {
      level1: "0 1px 2px rgba(0,0,0,0.06)",
      level2: "0 2px 8px rgba(0,0,0,0.08)",
      level3: "0 4px 16px rgba(0,0,0,0.12)",
    },
```

- [ ] **Step 1:** Apply the three replacements above.
- [ ] **Step 2:** Commit

```bash
git add skills/remotion-canvas/src/pipeline/match-style.ts
git commit -m "fix(remotion-canvas): make chip colors and elevation dark-aware in buildCompleteStyle"
```

---

### Task 3: Add `tech` brand fallback to cli.js

**Files:**
- Modify: `skills/remotion-canvas/cli.js`

In `generateDefaultStyle`, add `tech` to the `brands` lookup object:

```js
const brands = {
  claude: { label: "Claude", primary: "#cc785c", canvas: dark ? "#1a1816" : "#faf9f5" },
  vercel: { label: "Vercel", primary: "#0070f3", canvas: dark ? "#000000" : "#ffffff" },
  linear: { label: "Linear", primary: "#5e6ad2", canvas: dark ? "#0a0a0f" : "#f8f8fc" },
  stripe: { label: "Stripe", primary: "#635bff", canvas: dark ? "#0a2540" : "#f6f9fc" },
  apple: { label: "Apple", primary: "#0071e3", canvas: dark ? "#000000" : "#f5f5f7" },
  tech: { label: "Tech", primary: "#0ea5e9", canvas: dark ? "#0a0e1a" : "#f0f4f8" }, // NEW
};
```

- [ ] **Step 1:** Insert the `tech` line into the `brands` object.
- [ ] **Step 2:** Commit

```bash
git add skills/remotion-canvas/cli.js
git commit -m "feat(remotion-canvas): add tech brand fallback to generateDefaultStyle"
```

---

### Task 4: Add `tech` profile to brand-profiles.ts

**Files:**
- Modify: `skills/remotion-canvas/src/design/brand-profiles.ts`

Insert a new profile before the closing `];`:

```ts
{
  id: "tech",
  label: "Tech",
  darkMode: true,
  recommendedBackgrounds: ["geometric", "grid", "nebula"],
  keywords: ["ai", "coding", "engineer", "technology", "developer", "software", "tech", "programming", "算法", "编程", "技术", "工程师"],
  categories: ["ai", "developer-tools", "tech"],
},
```

- [ ] **Step 1:** Insert the profile above.
- [ ] **Step 2:** Commit

```bash
git add skills/remotion-canvas/src/design/brand-profiles.ts
git commit -m "feat(remotion-canvas): add tech brand profile"
```

---

### Task 5: Extend CLI findFile for content-pipeline production/ directories

**Files:**
- Modify: `skills/remotion-canvas/cli.js`

There are **four** `findFile` calls to extend. In each call, add the content-pipeline `production/` path as the last entry in the array.

**Call 1 — `cmdMatchStyle` (content-structure.md):**

Find:
```js
const contentPath = findFile(args.project, [
    "visual-narrative-out/content-structure.md",
    "content-structure.md",
  ]);
```

Replace with:
```js
const contentPath = findFile(args.project, [
    "visual-narrative-out/content-structure.md",
    "content-structure.md",
    "production/content/00-structure.md",
  ]);
```

**Call 2 — `cmdBeatAssign` (SRT):**

Find:
```js
const srtPath = findFile(args.project, [
    "visual-narrative-out/script.srt",
    "script.srt",
    "timing/script.srt",
  ]);
```

Replace with:
```js
const srtPath = findFile(args.project, [
    "visual-narrative-out/script.srt",
    "script.srt",
    "timing/script.srt",
    "production/subtitles/sub.srt",
  ]);
```

**Call 3 — `cmdBeatAssign` (structure):**

Find:
```js
const structurePath = findFile(args.project, [
    "visual-narrative-out/content-structure.md",
    "content-structure.md",
  ]);
```

Replace with:
```js
const structurePath = findFile(args.project, [
    "visual-narrative-out/content-structure.md",
    "content-structure.md",
    "production/content/00-structure.md",
  ]);
```

**Call 4 — `cmdRender` and `cmdPreview` (audio):**

Find:
```js
const audioFile = findFile(args.project, [
    "timing/voiceover.wav",
    "visual-narrative-out/voiceover.wav",
    "voiceover.wav",
  ]);
```

Replace with:
```js
const audioFile = findFile(args.project, [
    "timing/voiceover.wav",
    "visual-narrative-out/voiceover.wav",
    "voiceover.wav",
    "production/media/voiceover.wav",
  ]);
```

Also handle the case where `structurePath` points to a `.md` file but `beat-assign` expects JSON. The safest fix is in `cmdBeatAssign`: if `structurePath` ends with `.md`, ignore it and generate the fallback `structure.json`.

Find this block in `cmdBeatAssign`:

```js
const structureInput = structurePath || structureJsonPath;
```

Replace with:
```js
const structureInput = (structurePath && !structurePath.endsWith(".md")) ? structurePath : structureJsonPath;
```

- [ ] **Step 1:** Apply all five replacements above.
- [ ] **Step 2:** Commit

```bash
git add skills/remotion-canvas/cli.js
git commit -m "feat(remotion-canvas): extend CLI file discovery for content-pipeline production/ dirs"
```

---

### Task 6: Update choreograph.ts to pick geometric background for tech brand

**Files:**
- Modify: `skills/remotion-canvas/src/pipeline/choreograph.ts`

In `createDefaultBackground`, add a `tech`-brand branch before the generic dark fallback.

Find:
```ts
if (style.brand === "netflix" || isDark) {
```

Replace with:
```ts
if (style.brand === "tech") {
    return {
      type: "geometric",
      params: {
        kind: "geometric",
        patternType: "circuit",
        lineColor: `${style.colors.primary}40`,
        lineOpacity: 0.08,
        nodeColor: style.colors.primary,
        nodeOpacity: 0.3,
        spacing: 80,
        motionType: "pulse",
        motionSpeed: 0.001,
      },
    };
  }

  if (style.brand === "netflix" || isDark) {
```

- [ ] **Step 1:** Insert the `tech` branch above the `netflix` check.
- [ ] **Step 2:** Commit

```bash
git add skills/remotion-canvas/src/pipeline/choreograph.ts
git commit -m "feat(remotion-canvas): default to geometric background for tech brand"
```

---

### Task 7: Generate feature structure.json

**Files:**
- Create: `features/content-pipeline/ai-companies-build-ai-mid-video/visual-narrative-out/structure.json`

The existing `beat-assign.ts` stub cycles SRT beats across all slots with `i % allSlots.length`. To get a video where each subtitle block appears with an entrance animation, create a structure with **one section and one body slot**. All beats map to that single slot, which means it enters once on the first beat and then stays. The actual per-beat text display is handled by the subtitle overlay.

Create `structure.json`:

```json
{
  "sections": [
    {
      "id": "sec-main",
      "chunks": [
        {
          "id": "sec-main-chunk-0",
          "slots": [
            {
              "id": "sec-main-chunk-0-slot-body",
              "content": "AI is building AI"
            }
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 1:** Write the file above to the exact path.
- [ ] **Step 2:** Commit

```bash
git add features/content-pipeline/ai-companies-build-ai-mid-video/visual-narrative-out/structure.json
git commit -m "chore(features): add minimal structure.json for remotion-canvas pipeline"
```

---

### Task 8: Run match-style pipeline

**Run:**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-canvas
node cli.js match-style \
  --project ../../features/content-pipeline/ai-companies-build-ai-mid-video \
  --style tech --dark
```

**Expected:** `visual-narrative-out/style.json` is generated with `brand: "tech"` and `darkMode: true`.

- [ ] **Step 1:** Run command.
- [ ] **Step 2:** Verify output:

```bash
cat ../../features/content-pipeline/ai-companies-build-ai-mid-video/visual-narrative-out/style.json | grep -E '"brand"|"darkMode"|"primary"'
```

Expected output contains:
```
"brand": "tech"
"darkMode": true
"primary": "#0ea5e9"
```

---

### Task 9: Run beat-assign pipeline

**Run:**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-canvas
node cli.js beat-assign \
  --project ../../features/content-pipeline/ai-companies-build-ai-mid-video
```

**Expected:** `visual-narrative-out/assignments.json` is generated with beat entries mapped from `sub.srt`.

- [ ] **Step 1:** Run command.
- [ ] **Step 2:** Verify output count matches SRT blocks:

```bash
node -e "const a = require('../../features/content-pipeline/ai-companies-build-ai-mid-video/visual-narrative-out/assignments.json'); console.log('beats:', a.totalBeats, 'duration:', a.totalDurationSec + 's');"
```

---

### Task 10: Run build pipeline

**Run:**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-canvas
node cli.js build \
  --project ../../features/content-pipeline/ai-companies-build-ai-mid-video
```

**Expected:** `visual-narrative-out/beat-manifest.json` and `visual-narrative-out/presentation.html` are generated.

- [ ] **Step 1:** Run command.
- [ ] **Step 2:** Verify manifest exists and has expected fields:

```bash
node -e "const m = require('../../features/content-pipeline/ai-companies-build-ai-mid-video/visual-narrative-out/beat-manifest.json'); console.log('beats:', m.meta.totalBeats, 'brand:', m.style.brand, 'bg:', m.background.type, 'sections:', m.sections.length);"
```

---

### Task 11: Validate manifest with Zod

**Run:**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-canvas
node cli.js validate \
  ../../features/content-pipeline/ai-companies-build-ai-mid-video/visual-narrative-out/beat-manifest.json
```

**Expected:** Output ends with `✅ BeatManifest is valid.`

- [ ] **Step 1:** Run command.
- [ ] **Step 2:** If validation fails, fix the reported field errors before proceeding.

---

### Task 12: Render silent MP4

**Run:**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-canvas
node cli.js render \
  --project ../../features/content-pipeline/ai-companies-build-ai-mid-video \
  --audio-mode silent
```

**Expected:** `features/content-pipeline/ai-companies-build-ai-mid-video/videos/final.mp4` is created.

- [ ] **Step 1:** Run command. Rendering may take several minutes for a long video.
- [ ] **Step 2:** Verify output file exists:

```bash
ls -lh ../../features/content-pipeline/ai-companies-build-ai-mid-video/videos/final.mp4
```

---

### Task 13: Review output and decide on refinements

- [ ] **Step 1:** Open the generated `presentation.html` in a browser to review structure.
- [ ] **Step 2:** Play `final.mp4` and evaluate:
  - Is the dark tech color scheme visible?
  - Is the geometric background rendering?
  - Do subtitles appear at the correct timestamps?
  - Is the visual effect sufficient, or does it need per-beat slot exit animation (currently slots never exit because `chunk-renderer.tsx` passes `exitFrame: null`)?

If the result is acceptable, the feature spec’s success criteria are met. If additional animation polish is needed (e.g., each beat should replace the previous text slot), open a follow-up task to:

1. Modify `chunk-renderer.tsx` to compute an `exitFrame` based on the next beat that references the same slot.
2. Or, generate more slots so beats map 1:1 to slots and old slots fade out naturally.

---

## Spec coverage checklist

| Spec requirement | Task that implements it |
|------------------|------------------------|
| 逐句精细同步 (Beat-level) | Task 9–10 (SRT → beats → manifest) |
| 科技暗色视觉风格 | Task 1, 3, 4 (brand config), Task 8 (pipeline) |
| geometric 背景 | Task 6 (choreograph default), Task 10 (manifest) |
| 全自动生成 (一键出片) | Task 8–12 (CLI pipeline execution) |
| content-pipeline production/ 目录识别 | Task 5 (file discovery) |
| 无音频 MP4 输出 | Task 12 (silent render) |

## Placeholder scan

- No TBD or TODO.
- All file paths are exact.
- All commands are copy-paste ready.
- All code blocks are complete snippets.

## Execution choice

Plan saved to `docs/superpowers/plans/2026-05-24-ai-companies-remotion-canvas-plan.md`.

Choose:

1. **Subagent-Driven (recommended)** — dispatch fresh subagents per task
2. **Inline Execution** — execute tasks in this session

Defaulting to **Subagent-Driven** as requested ("用subagent先尝试方案A").
