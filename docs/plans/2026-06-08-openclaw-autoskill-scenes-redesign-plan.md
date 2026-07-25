# OpenClaw 双轨自进化 — 全场景重设计实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重写 10 个 Remotion 场景的 SVG 图形和动画，修正事实错误，交付 3 个可在 `npx remotion studio` 中对比的 Composition（VersionA / VersionB / VersionC）。

**Architecture:** 共享内容层（`scenes/svg/Diagrams.tsx`）+ 3 版动画 wrapper（`scenes/variants/{A,B,C}/`）。Root.tsx 注册 3 个 Composition，共用 audioConfig.ts 时长。Video 组件接收 variant prop 决定用哪版 SceneTopic。

**Tech Stack:** Remotion 4.0.473, Anime.js 4.4.1 (`useAnimeTimeline`), React 18, TypeScript

---

## Task 1: 重写 Diagrams.tsx — 修正后的 10 个 SVG 组件

**Files:**
- Rewrite: `remotion/src/scenes/svg/Diagrams.tsx`

**Step 1: 重写 DualTrackRings（s00 封面）**

保留双轨同心环概念，内容不变（事实正确）。为动画版本预留 `className` 标记。

```tsx
export const DualTrackRings: React.FC<{ opacity?: number }> = ({ opacity = 1 }) => (
  <svg viewBox="0 0 900 700" width="100%" style={{ maxHeight: 620, opacity }}>
    <defs>
      <linearGradient id="ringA" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor={COLORS.debateFast} />
        <stop offset="100%" stopColor={COLORS.accent} />
      </linearGradient>
      <linearGradient id="ringB" x1="100%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor={COLORS.debateSlow} />
        <stop offset="100%" stopColor={COLORS.accent} />
      </linearGradient>
    </defs>
    <circle className="ring ring-outer" cx="450" cy="350" r="280" fill="none" stroke="url(#ringA)" strokeWidth="4" opacity="0.35" />
    <circle className="ring ring-mid" cx="450" cy="350" r="220" fill="none" stroke="url(#ringB)" strokeWidth="5" opacity="0.5" />
    <circle className="ring ring-inner" cx="450" cy="350" r="150" fill={COLORS.accentDim} stroke={COLORS.accent} strokeWidth="3" />
    <text className="label" x="450" y="330" textAnchor="middle" fill={COLORS.debateFast} fontSize="32" fontWeight="700">
      Self-Improving
    </text>
    <text className="label" x="450" y="375" textAnchor="middle" fill={COLORS.muted} fontSize="28">
      错题本 · 轻量
    </text>
    <text className="label" x="450" y="430" textAnchor="middle" fill={COLORS.debateSlow} fontSize="32" fontWeight="700">
      AutoSkill
    </text>
    <text className="label" x="450" y="470" textAnchor="middle" fill={COLORS.muted} fontSize="28">
      技能封装 · 可复用
    </text>
    <text className="label" x="450" y="560" textAnchor="middle" fill={COLORS.text} fontSize="36" fontWeight="700">
      OpenClaw 双轨进化
    </text>
  </svg>
);
```

**Step 2: 重写 BrokenChain（s01 痛点）— 断裂链条替代遗忘循环**

```tsx
export const BrokenChain: React.FC = () => (
  <svg viewBox="0 0 1000 420" width="100%" style={{ maxHeight: 400 }}>
    <defs>
      <marker id="arr" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
        <polygon points="0 0, 10 3.5, 0 7" fill={COLORS.accent} />
      </marker>
    </defs>
    {[
      { x: 100, label: "执行任务" },
      { x: 340, label: "出错踩坑" },
      { x: 580, label: "会话结束" },
      { x: 820, label: "再次犯错" },
    ].map((n, i) => (
      <g key={n.label} className="chain-node">
        <rect x={n.x - 90} y="150" width="180" height="100" rx="14" fill={COLORS.accentDim} stroke={COLORS.accent} strokeWidth="2" />
        <text x={n.x} y="210" textAnchor="middle" fill={COLORS.text} fontSize="32" fontWeight="700">{n.label}</text>
        {i < 3 && (
          <line
            className={i === 1 ? "link broken" : "link"}
            x1={n.x + 95} y1="200" x2={n.x + 155} y2="200"
            stroke={i === 1 ? "#ef4444" : COLORS.accent}
            strokeWidth="3"
            strokeDasharray={i === 1 ? "8 6" : "none"}
          />
        )}
      </g>
    ))}
    <text x="460" y="320" textAnchor="middle" fill="#ef4444" fontSize="30" className="break-label">
      ✕ 记忆断裂：程序性经验丢失
    </text>
    <text x="500" y="375" textAnchor="middle" fill={COLORS.muted} fontSize="28">
      手写 SKILL 慢 · RAG 只检索不写回
    </text>
  </svg>
);
```

**Step 3: 重写 DualTrackRails（s02 双轨）— 铁轨双层隐喻**

```tsx
export const DualTrackRails: React.FC = () => (
  <svg viewBox="0 0 1000 520" width="100%" style={{ maxHeight: 480 }}>
    {/* 上层轨道 — Self-Improving */}
    <rect className="track track-upper" x="60" y="60" width="880" height="180" rx="16" fill="rgba(110,200,122,0.08)" stroke={COLORS.debateFast} strokeWidth="3" />
    <text x="120" y="115" fill={COLORS.debateFast} fontSize="36" fontWeight="800">▲ Self-Improving（轻轨）</text>
    {["失败/纠正 → LEARNINGS.md", "可编辑 Markdown · 人可审", "高频 → promote 升级"].map((t, i) => (
      <text key={t} x="140" y={155 + i * 38} fill={COLORS.text} fontSize="28" className="track-item">{t}</text>
    ))}
    {/* 下层轨道 — AutoSkill */}
    <rect className="track track-lower" x="60" y="280" width="880" height="180" rx="16" fill="rgba(124,140,248,0.08)" stroke={COLORS.debateSlow} strokeWidth="3" />
    <text x="120" y="335" fill={COLORS.debateSlow} fontSize="36" fontWeight="800">▼ AutoSkill（重载线）</text>
    {["重复成功模式 → 新 SKILL.md", "提取 · 维护 · 检索 · 执行", "可触发工作流 · 版本化"].map((t, i) => (
      <text key={t} x="140" y={375 + i * 38} fill={COLORS.text} fontSize="28" className="track-item">{t}</text>
    ))}
    {/* 中间连接 */}
    <line x1="500" y1="240" x2="500" y2="280" stroke={COLORS.accent} strokeWidth="2" strokeDasharray="4 4" />
    <text x="500" y="502" textAnchor="middle" fill={COLORS.muted} fontSize="28">两轨可并行：错题本指导改法 · AutoSkill 封装成熟套路</text>
  </svg>
);
```

**Step 4: 重写 NotebookFlow（s03 Self-Improving）— 笔记本翻页**

```tsx
export const NotebookFlow: React.FC = () => (
  <svg viewBox="0 0 1000 420" width="100%" style={{ maxHeight: 400 }}>
    {[
      { x: 130, icon: "✗", label: "失败/纠正", sub: "捕捉错误" },
      { x: 370, icon: "📝", label: "写入 LEARNINGS", sub: "可编辑 Markdown" },
      { x: 610, icon: "→", label: "注入上下文", sub: "下次会话读取" },
      { x: 850, icon: "⬆", label: "promote", sub: "升级为 Skill" },
    ].map((s, i) => (
      <g key={s.label} className="notebook-page">
        <rect x={s.x - 100} y="100" width="200" height="220" rx="12"
          fill={COLORS.accentDim} stroke={COLORS.debateFast} strokeWidth="2" />
        <text x={s.x} y="160" textAnchor="middle" fontSize="42">{s.icon}</text>
        <text x={s.x} y="220" textAnchor="middle" fill={COLORS.text} fontSize="28" fontWeight="700">{s.label}</text>
        <text x={s.x} y="260" textAnchor="middle" fill={COLORS.muted} fontSize="24">{s.sub}</text>
        {i < 3 && (
          <path className="page-arrow" d={`M ${s.x + 105} 200 L ${s.x + 155} 200`}
            stroke={COLORS.accent} strokeWidth="3" markerEnd="url(#arr)" />
        )}
      </g>
    ))}
    <text x="500" y="390" textAnchor="middle" fill={COLORS.muted} fontSize="28">
      适合探索期 · 经常改口径的任务
    </text>
    <defs>
      <marker id="arr" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
        <polygon points="0 0, 10 3.5, 0 7" fill={COLORS.accent} />
      </marker>
    </defs>
  </svg>
);
```

**Step 5: 重写 AutoSkillCycle（s04 AutoSkill）— 环形流水线**

```tsx
export const AutoSkillCycle: React.FC = () => {
  const nodes = [
    { label: "提取", desc: "从轨迹挖模式", angle: -90 },
    { label: "维护", desc: "去重/版本化", angle: 0 },
    { label: "检索", desc: "BM25+语义", angle: 90 },
    { label: "执行", desc: "调用 Skill", angle: 180 },
  ];
  const cx = 500, cy = 220, r = 180;

  return (
    <svg viewBox="0 0 1000 480" width="100%" style={{ maxHeight: 440 }}>
      <defs>
        <marker id="cycle-arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill={COLORS.debateSlow} />
        </marker>
      </defs>
      {/* 环形连线 */}
      <circle className="cycle-ring" cx={cx} cy={cy} r={r} fill="none"
        stroke={COLORS.debateSlow} strokeWidth="2" strokeDasharray="12 6" opacity="0.4" />
      {/* 弧线箭头 */}
      {nodes.map((n, i) => {
        const a1 = (n.angle + 25) * Math.PI / 180;
        const a2 = (nodes[(i + 1) % 4].angle - 25) * Math.PI / 180;
        const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
        const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
        return (
          <path key={`arc-${i}`} className="cycle-arc"
            d={`M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`}
            fill="none" stroke={COLORS.debateSlow} strokeWidth="3" markerEnd="url(#cycle-arr)" />
        );
      })}
      {/* 节点 */}
      {nodes.map((n) => {
        const rad = n.angle * Math.PI / 180;
        const nx = cx + r * Math.cos(rad), ny = cy + r * Math.sin(rad);
        return (
          <g key={n.label} className="cycle-node">
            <circle cx={nx} cy={ny} r="56" fill={COLORS.accentDim} stroke={COLORS.debateSlow} strokeWidth="3" />
            <text x={nx} y={ny - 6} textAnchor="middle" fill={COLORS.text} fontSize="30" fontWeight="700">{n.label}</text>
            <text x={nx} y={ny + 24} textAnchor="middle" fill={COLORS.muted} fontSize="22">{n.desc}</text>
          </g>
        );
      })}
      <text x={cx} y={cy + 4} textAnchor="middle" fill={COLORS.accent} fontSize="28" fontWeight="700">闭环</text>
      <text x={cx} y="440" textAnchor="middle" fill={COLORS.muted} fontSize="28">
        失败回 Self-Improving 修正 · 越用越会封装技能
      </text>
    </svg>
  );
};
```

**Step 6: 重写 ThreeColumnCompare（s05 三方对比）— 三列光谱**

```tsx
export const ThreeColumnCompare: React.FC = () => (
  <svg viewBox="0 0 1000 480" width="100%" style={{ maxHeight: 460 }}>
    {[
      { x: 170, name: "SkillClaw", org: "AMAP-ML", desc: "离线会话蒸馏", weight: "中", color: COLORS.debateMiddle },
      { x: 500, name: "SkillOS", org: "Google", desc: "RL 治理器", weight: "重", color: COLORS.debateSlow },
      { x: 830, name: "OpenClaw", org: "社区", desc: "Markdown + hooks", weight: "轻", color: COLORS.debateFast },
    ].map((col) => (
      <g key={col.name} className="compare-col">
        <rect x={col.x - 140} y="60" width="280" height="360" rx="16"
          fill={`${col.color}11`} stroke={col.color} strokeWidth="2" />
        <text x={col.x} y="110" textAnchor="middle" fill={col.color} fontSize="34" fontWeight="800">{col.name}</text>
        <text x={col.x} y="148" textAnchor="middle" fill={COLORS.muted} fontSize="24">{col.org}</text>
        <line x1={col.x - 100} y1="170" x2={col.x + 100} y2="170" stroke={col.color} strokeWidth="1" opacity="0.3" />
        <text x={col.x} y="210" textAnchor="middle" fill={COLORS.text} fontSize="28">{col.desc}</text>
        <text x={col.x} y="260" textAnchor="middle" fill={COLORS.text} fontSize="28">
          {col.name === "SkillClaw" ? "跨端共享" : col.name === "SkillOS" ? "insert/update/delete" : "人可审 · 人可删"}
        </text>
        <text x={col.x} y="310" textAnchor="middle" fill={COLORS.text} fontSize="28">
          {col.name === "SkillClaw" ? "需蒸馏训练" : col.name === "SkillOS" ? "需 RL 训练" : "手动 + hooks 扩展"}
        </text>
        <rect x={col.x - 50} y="350" width="100" height="44" rx="22"
          fill={col.color} opacity="0.2" stroke={col.color} strokeWidth="1" />
        <text x={col.x} y="378" textAnchor="middle" fill={col.color} fontSize="26" fontWeight="600">{col.weight}</text>
      </g>
    ))}
  </svg>
);
```

**Step 7: 重写 IntegrationRadial（s06 集成）— 修正：去掉 SkillBank**

```tsx
export const IntegrationRadial: React.FC = () => (
  <svg viewBox="0 0 1000 440" width="100%" style={{ maxHeight: 420 }}>
    <circle className="hub" cx="500" cy="220" r="90" fill={COLORS.accentDim} stroke={COLORS.accent} strokeWidth="4" />
    <text x="500" y="215" textAnchor="middle" fill={COLORS.text} fontSize="32" fontWeight="800">OpenClaw</text>
    <text x="500" y="252" textAnchor="middle" fill={COLORS.muted} fontSize="26">核心</text>
    {[
      { x: 180, y: 120, label: "ClawHub", desc: "技能安装" },
      { x: 180, y: 320, label: "AGENTS.md", desc: "规则注入" },
      { x: 820, y: 120, label: "hooks", desc: "事件触发" },
      { x: 820, y: 320, label: "MCP", desc: "外部能力" },
    ].map((n) => (
      <g key={n.label} className="spoke-node">
        <rect x={n.x - 100} y={n.y - 40} width="200" height="80" rx="14"
          fill="rgba(124,140,248,0.12)" stroke={COLORS.debateSlow} strokeWidth="2" />
        <text x={n.x} y={n.y - 4} textAnchor="middle" fill={COLORS.text} fontSize="30" fontWeight="600">{n.label}</text>
        <text x={n.x} y={n.y + 26} textAnchor="middle" fill={COLORS.muted} fontSize="22">{n.desc}</text>
        <line className="spoke-line"
          x1={n.x < 500 ? n.x + 100 : n.x - 100} y1={n.y}
          x2={n.x < 500 ? 410 : 590} y2={220}
          stroke={COLORS.accent} strokeWidth="2" strokeDasharray="6 4" />
      </g>
    ))}
  </svg>
);
```

**Step 8: 重写 EvolutionLoopFixed（s07 one-context）— 修正：「人审」门**

```tsx
export const EvolutionLoopFixed: React.FC = () => {
  const steps = [
    { label: "执行 Skill", icon: "▶" },
    { label: "记录 LEARNINGS", icon: "📝" },
    { label: "SessionEnd 评估", icon: "🔍" },
    { label: "输出改进建议", icon: "📋" },
  ];
  return (
    <svg viewBox="0 0 1000 440" width="100%" style={{ maxHeight: 420 }}>
      {steps.map((s, i) => {
        const angle = (i / 4) * Math.PI * 2 - Math.PI / 2;
        const nx = 500 + Math.cos(angle) * 200;
        const ny = 220 + Math.sin(angle) * 140;
        const isGate = i === 3;
        return (
          <g key={s.label} className="loop-node">
            <rect x={nx - 110} y={ny - 36} width="220" height="72" rx="12"
              fill={COLORS.accentDim}
              stroke={isGate ? "#f59e0b" : COLORS.debateFast}
              strokeWidth={isGate ? 3 : 2}
              strokeDasharray={isGate ? "8 4" : "none"} />
            <text x={nx - 80} y={ny + 8} fill={COLORS.text} fontSize="28">{s.icon} {s.label}</text>
          </g>
        );
      })}
      {/* 人审标注 */}
      <text x="500" y="400" textAnchor="middle" fill="#f59e0b" fontSize="26" fontWeight="600">
        ⚠ 人工审阅后合入（不自动写回）
      </text>
      <text x="500" y="220" textAnchor="middle" fill={COLORS.accent} fontSize="30" fontWeight="800">
        skill-self-evolution-loop
      </text>
    </svg>
  );
};
```

**Step 9: 重写 DashboardGrid（s08 适用场景）— 仪表盘**

```tsx
export const DashboardGrid: React.FC = () => (
  <svg viewBox="0 0 1000 460" width="100%" style={{ maxHeight: 440 }}>
    {/* 绿灯区 */}
    <rect className="zone zone-green" x="40" y="40" width="440" height="180" rx="16"
      fill="rgba(110,200,122,0.08)" stroke={COLORS.debateFast} strokeWidth="2" />
    <text x="260" y="80" textAnchor="middle" fill={COLORS.debateFast} fontSize="32" fontWeight="700">● 适合</text>
    {["长期个人助手", "重复运维/内容流水线", "可 Markdown 化的 SOP"].map((t, i) => (
      <text key={t} x="260" y={115 + i * 36} textAnchor="middle" fill={COLORS.text} fontSize="28" className="dash-item">{t}</text>
    ))}
    {/* 红灯区 */}
    <rect className="zone zone-red" x="520" y="40" width="440" height="180" rx="16"
      fill="rgba(239,68,68,0.06)" stroke="#ef4444" strokeWidth="2" />
    <text x="740" y="80" textAnchor="middle" fill="#fca5a5" fontSize="32" fontWeight="700">● 不适合</text>
    {["一次性批处理", "无反馈闭环", "强合规 · 禁止自动写库"].map((t, i) => (
      <text key={t} x="740" y={115 + i * 36} textAnchor="middle" fill={COLORS.text} fontSize="28" className="dash-item">{t}</text>
    ))}
    {/* 起步路径 */}
    <rect className="zone zone-start" x="120" y="260" width="760" height="160" rx="16"
      fill={COLORS.accentDim} stroke={COLORS.accent} strokeWidth="2" />
    <text x="500" y="310" textAnchor="middle" fill={COLORS.accent} fontSize="32" fontWeight="700">
      起步：先开 Self-Improving 1–2 周
    </text>
    <text x="500" y="360" textAnchor="middle" fill={COLORS.text} fontSize="28">
      积累错题本 → 挑高频模式 → AutoSkill 封装
    </text>
  </svg>
);
```

**Step 10: 提交**

```bash
git add remotion/src/scenes/svg/Diagrams.tsx
git commit -m "refactor(scenes): rewrite all 10 SVG diagrams with corrected content"
```

---

## Task 2: 实现 Version B — 全场 Spring Stagger

**Files:**
- Create: `remotion/src/scenes/variants/B/SceneTopicB.tsx`
- Create: `remotion/src/scenes/variants/B/VideoB.tsx`

**Step 1: 创建 SceneTopicB.tsx**

与现有 SceneTopic 类似，但 SVG 内子元素按 `.className` 分组做 stagger 入场。

```tsx
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_SIZE, SceneBackground } from "../../shared";
import { VARIANT_CONFIG, type TopicVariant } from "../shared-config";

export const SceneTopicB: React.FC<{ variant: TopicVariant }> = ({ variant }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { title, subtitle, Diagram } = VARIANT_CONFIG[variant];

  const titleSpring = spring({ frame: frame - 6, fps, config: { damping: 22, stiffness: 180 } });
  const diagramDelay = 20;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <SceneBackground intensity={0.5} hexGrid={false} />
      <div style={{
        position: "absolute", top: 48, left: 0, right: 0, textAlign: "center", zIndex: 2,
        opacity: interpolate(titleSpring, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(titleSpring, [0, 1], [-24, 0])}px)`,
      }}>
        <div style={{ fontSize: FONT_SIZE.title, fontFamily: FONT.chinese, color: COLORS.text, fontWeight: 800 }}>{title}</div>
        <div style={{ marginTop: 12, fontSize: FONT_SIZE.body, fontFamily: FONT.chinese, color: COLORS.muted }}>{subtitle}</div>
      </div>
      <div style={{
        position: "absolute", top: 200, left: 60, right: 60, bottom: 48,
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2,
      }}>
        <StaggerWrapper delay={diagramDelay}>
          <Diagram />
        </StaggerWrapper>
      </div>
    </AbsoluteFill>
  );
};

const StaggerWrapper: React.FC<{ delay: number; children: React.ReactNode }> = ({ delay, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const childCount = 8; // approximate max SVG groups
  return (
    <div style={{ width: "100%", height: "100%" }}>
      <style>{`
        .chain-node, .track, .track-item, .notebook-page, .cycle-node, .cycle-arc,
        .compare-col, .spoke-node, .loop-node, .zone, .dash-item, .ring, .label {
          opacity: var(--stagger-opacity, 1);
          transform: translateY(var(--stagger-ty, 0px));
        }
      `}</style>
      {React.Children.map(children, (child) => {
        const progress = interpolate(frame, [delay, delay + childCount * 10], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
        });
        return <div style={{ opacity: progress, transform: `translateY(${(1 - progress) * 16}px)` }}>{child}</div>;
      })}
    </div>
  );
};
```

**Step 2: 创建 VideoB.tsx — 与 Video 同构但用 SceneTopicB**

```tsx
import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { SCENES, getSceneStart } from "../../audioConfig";
import { useCurrentSceneIndex } from "../../hooks/useCurrentSceneIndex";
import { SceneCover } from "../SceneCover";
import { SceneOutro } from "../SceneOutro";
import { SceneTopicB } from "./SceneTopicB";

function SceneRouterB({ id }: { id: string }) {
  const MAP: Record<string, string> = {
    "01": "pain", "02": "dual", "03": "selfimproving", "04": "autoskill",
    "05": "compare", "06": "integrate", "07": "onecxt", "08": "whenuse",
  };
  if (id === "00") return <SceneCover />;
  if (id === "09") return <SceneOutro />;
  return <SceneTopicB variant={MAP[id] as any} />;
}

export const VideoB: React.FC = () => {
  useCurrentSceneIndex();
  const isSingleAudio = new Set(SCENES.map((s) => s.audioFile)).size === 1;
  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0b" }}>
      {SCENES.map((scene, idx) => (
        <Sequence key={scene.id} from={getSceneStart(idx)} durationInFrames={scene.durationInFrames}>
          <SceneRouterB id={scene.id} />
        </Sequence>
      ))}
      {isSingleAudio && <Audio src={staticFile(SCENES[0].audioFile)} />}
    </AbsoluteFill>
  );
};
```

**Step 3: 提交**

```bash
git add remotion/src/scenes/variants/B/
git commit -m "feat(scenes): version B — spring stagger all 10 scenes"
```

---

## Task 3: 实现 Version A — 重点 Anime × 3 + Spring × 7

**Files:**
- Create: `remotion/src/scenes/variants/A/SceneTopicA.tsx`
- Create: `remotion/src/scenes/variants/A/anime-timelines.ts`
- Create: `remotion/src/scenes/variants/A/VideoA.tsx`

**Step 1: 创建 anime-timelines.ts — 3 个场景的 timeline build 函数**

```tsx
import { stagger, type Timeline } from "animejs";

export function buildDualTrackTimeline(tl: Timeline, root: HTMLElement) {
  const tracks = root.querySelectorAll(".track");
  const items = root.querySelectorAll(".track-item");

  tl.add(tracks, {
    opacity: [0, 1],
    translateY: [40, 0],
    duration: 600,
    delay: stagger(200),
  }).add(items, {
    opacity: [0, 1],
    translateX: [-20, 0],
    duration: 400,
    delay: stagger(80),
  }, "-=400");
}

export function buildAutoSkillTimeline(tl: Timeline, root: HTMLElement) {
  const ring = root.querySelector(".cycle-ring");
  const arcs = root.querySelectorAll(".cycle-arc");
  const nodes = root.querySelectorAll(".cycle-node");

  tl.add(ring!, {
    strokeDashoffset: [1200, 0],
    duration: 1000,
  }).add(arcs, {
    strokeDashoffset: [200, 0],
    opacity: [0, 1],
    duration: 500,
    delay: stagger(150),
  }, "-=300").add(nodes, {
    opacity: [0, 1],
    scale: [0.6, 1],
    duration: 400,
    delay: stagger(120, { from: "first" }),
  }, "-=400");
}

export function buildIntegrationTimeline(tl: Timeline, root: HTMLElement) {
  const hub = root.querySelector(".hub");
  const spokes = root.querySelectorAll(".spoke-node");
  const lines = root.querySelectorAll(".spoke-line");

  tl.add(hub!, {
    opacity: [0, 1],
    scale: [0.5, 1],
    duration: 600,
  }).add(lines, {
    strokeDashoffset: [200, 0],
    opacity: [0, 1],
    duration: 400,
    delay: stagger(100),
  }, "-=200").add(spokes, {
    opacity: [0, 1],
    translateX: (_, i) => [(i < 2 ? -60 : 60), 0],
    duration: 500,
    delay: stagger(100),
  }, "-=300");
}
```

**Step 2: 创建 SceneTopicA.tsx — 动态 dispatch**

```tsx
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_SIZE, SceneBackground } from "../../shared";
import { useAnimeTimeline } from "../../shared/animations/anime";
import { VARIANT_CONFIG, type TopicVariant } from "../shared-config";
import { buildDualTrackTimeline, buildAutoSkillTimeline, buildIntegrationTimeline } from "./anime-timelines";

const ANIME_SCENES: Partial<Record<TopicVariant, (tl: any, root: HTMLElement) => void>> = {
  dual: buildDualTrackTimeline,
  autoskill: buildAutoSkillTimeline,
  integrate: buildIntegrationTimeline,
};

export const SceneTopicA: React.FC<{ variant: TopicVariant }> = ({ variant }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { title, subtitle, Diagram } = VARIANT_CONFIG[variant];
  const buildFn = ANIME_SCENES[variant];

  const titleSpring = spring({ frame: frame - 6, fps, config: { damping: 22, stiffness: 180 } });
  const containerRef = buildFn ? useAnimeTimeline(buildFn) : undefined;

  const diagramFade = buildFn ? 1 : interpolate(frame, [20, 50], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <SceneBackground intensity={0.5} hexGrid={false} />
      <div style={{
        position: "absolute", top: 48, left: 0, right: 0, textAlign: "center", zIndex: 2,
        opacity: interpolate(titleSpring, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(titleSpring, [0, 1], [-24, 0])}px)`,
      }}>
        <div style={{ fontSize: FONT_SIZE.title, fontFamily: FONT.chinese, color: COLORS.text, fontWeight: 800 }}>{title}</div>
        <div style={{ marginTop: 12, fontSize: FONT_SIZE.body, fontFamily: FONT.chinese, color: COLORS.muted }}>{subtitle}</div>
      </div>
      <div
        ref={containerRef}
        style={{
          position: "absolute", top: 200, left: 60, right: 60, bottom: 48,
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2,
          opacity: diagramFade,
        }}
      >
        <Diagram />
      </div>
    </AbsoluteFill>
  );
};
```

**Step 3: 创建 VideoA.tsx**

同 VideoB 模式，用 `SceneTopicA` 替代。

**Step 4: 提交**

```bash
git add remotion/src/scenes/variants/A/
git commit -m "feat(scenes): version A — 3 anime timelines + 7 spring fallback"
```

---

## Task 4: 实现 Version C — 全场 Anime.js Timeline

**Files:**
- Create: `remotion/src/scenes/variants/C/SceneTopicC.tsx`
- Create: `remotion/src/scenes/variants/C/anime-timelines.ts`
- Create: `remotion/src/scenes/variants/C/VideoC.tsx`

**Step 1: 创建 anime-timelines.ts — 全 10 场 build 函数**

在 Version A 的 3 个基础上，补充剩余 7 个：

```tsx
import { stagger, type Timeline } from "animejs";

// s00 封面：双环从点扩张
export function buildCoverTimeline(tl: Timeline, root: HTMLElement) {
  const rings = root.querySelectorAll(".ring");
  const labels = root.querySelectorAll(".label");
  tl.add(rings, {
    scale: [0, 1],
    opacity: [0, 1],
    duration: 800,
    delay: stagger(200),
  }).add(labels, {
    opacity: [0, 1],
    translateY: [20, 0],
    duration: 500,
    delay: stagger(100),
  }, "-=400");
}

// s01 痛点：链条断裂
export function buildBrokenChainTimeline(tl: Timeline, root: HTMLElement) {
  const nodes = root.querySelectorAll(".chain-node");
  const broken = root.querySelector(".broken");
  const breakLabel = root.querySelector(".break-label");
  tl.add(nodes, {
    opacity: [0, 1],
    translateX: [-30, 0],
    duration: 400,
    delay: stagger(150),
  }).add(broken!, {
    opacity: [0, 1],
    strokeDashoffset: [50, 0],
    duration: 300,
  }).add(broken!, {
    translateX: [-4, 4, -4, 0],
    duration: 300,
  }).add(breakLabel!, {
    opacity: [0, 1],
    scale: [0.8, 1],
    duration: 400,
  });
}

// s02 双轨分裂
export { buildDualTrackTimeline } from "../A/anime-timelines";

// s03 笔记本翻页
export function buildNotebookTimeline(tl: Timeline, root: HTMLElement) {
  const pages = root.querySelectorAll(".notebook-page");
  const arrows = root.querySelectorAll(".page-arrow");
  tl.add(pages, {
    opacity: [0, 1],
    rotateY: [90, 0],
    duration: 500,
    delay: stagger(200),
  }).add(arrows, {
    strokeDashoffset: [60, 0],
    opacity: [0, 1],
    duration: 300,
    delay: stagger(150),
  }, "-=400");
}

// s04 环形
export { buildAutoSkillTimeline } from "../A/anime-timelines";

// s05 三列升起
export function buildCompareTimeline(tl: Timeline, root: HTMLElement) {
  const cols = root.querySelectorAll(".compare-col");
  tl.add(cols, {
    opacity: [0, 1],
    translateY: [80, 0],
    duration: 600,
    delay: stagger(200, { from: "center" }),
  });
}

// s06 集成
export { buildIntegrationTimeline } from "../A/anime-timelines";

// s07 闭环亮起
export function buildEvolutionTimeline(tl: Timeline, root: HTMLElement) {
  const nodes = root.querySelectorAll(".loop-node");
  tl.add(nodes, {
    opacity: [0, 1],
    scale: [0.7, 1],
    duration: 400,
    delay: stagger(180),
  });
}

// s08 仪表盘
export function buildDashboardTimeline(tl: Timeline, root: HTMLElement) {
  const zones = root.querySelectorAll(".zone");
  const items = root.querySelectorAll(".dash-item");
  tl.add(zones, {
    opacity: [0, 1],
    scale: [0.95, 1],
    duration: 500,
    delay: stagger(200),
  }).add(items, {
    opacity: [0, 1],
    translateY: [12, 0],
    duration: 300,
    delay: stagger(60),
  }, "-=300");
}

// s09 收尾：文字聚合（在 SceneOutro 内实现）
export function buildOutroTimeline(tl: Timeline, root: HTMLElement) {
  const words = root.querySelectorAll(".outro-word");
  tl.add(words, {
    opacity: [0, 1],
    translateY: [30, 0],
    duration: 500,
    delay: stagger(100, { from: "center" }),
  });
}
```

**Step 2: 创建 SceneTopicC.tsx — 全场景 Anime**

```tsx
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_SIZE, SceneBackground } from "../../shared";
import { useAnimeTimeline } from "../../shared/animations/anime";
import { VARIANT_CONFIG, type TopicVariant } from "../shared-config";
import * as timelines from "./anime-timelines";

const TIMELINE_MAP: Record<TopicVariant, (tl: any, root: HTMLElement) => void> = {
  pain: timelines.buildBrokenChainTimeline,
  dual: timelines.buildDualTrackTimeline,
  selfimproving: timelines.buildNotebookTimeline,
  autoskill: timelines.buildAutoSkillTimeline,
  compare: timelines.buildCompareTimeline,
  integrate: timelines.buildIntegrationTimeline,
  onecxt: timelines.buildEvolutionTimeline,
  whenuse: timelines.buildDashboardTimeline,
};

export const SceneTopicC: React.FC<{ variant: TopicVariant }> = ({ variant }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { title, subtitle, Diagram } = VARIANT_CONFIG[variant];

  const titleSpring = spring({ frame: frame - 6, fps, config: { damping: 22, stiffness: 180 } });
  const containerRef = useAnimeTimeline(TIMELINE_MAP[variant]);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <SceneBackground intensity={0.5} hexGrid={false} />
      <div style={{
        position: "absolute", top: 48, left: 0, right: 0, textAlign: "center", zIndex: 2,
        opacity: interpolate(titleSpring, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(titleSpring, [0, 1], [-24, 0])}px)`,
      }}>
        <div style={{ fontSize: FONT_SIZE.title, fontFamily: FONT.chinese, color: COLORS.text, fontWeight: 800 }}>{title}</div>
        <div style={{ marginTop: 12, fontSize: FONT_SIZE.body, fontFamily: FONT.chinese, color: COLORS.muted }}>{subtitle}</div>
      </div>
      <div ref={containerRef} style={{
        position: "absolute", top: 200, left: 60, right: 60, bottom: 48,
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2,
      }}>
        <Diagram />
      </div>
    </AbsoluteFill>
  );
};
```

**Step 3: 创建 VideoC.tsx + 更新 SceneCover/SceneOutro 支持 Anime**

SceneCover 加 `useAnimeTimeline(buildCoverTimeline)`，SceneOutro 加 `className="outro-word"` + `useAnimeTimeline(buildOutroTimeline)`。

**Step 4: 提交**

```bash
git add remotion/src/scenes/variants/C/
git commit -m "feat(scenes): version C — full anime.js timeline all 10 scenes"
```

---

## Task 5: 共享配置 + Root.tsx 注册 3 个 Composition

**Files:**
- Create: `remotion/src/scenes/variants/shared-config.ts`
- Modify: `remotion/src/Root.tsx`

**Step 1: 创建 shared-config.ts — 场景 variant → title/subtitle/Diagram 映射**

```tsx
import {
  BrokenChain, DualTrackRails, NotebookFlow, AutoSkillCycle,
  ThreeColumnCompare, IntegrationRadial, EvolutionLoopFixed, DashboardGrid,
} from "../svg/Diagrams";

export type TopicVariant =
  | "pain" | "dual" | "selfimproving" | "autoskill"
  | "compare" | "integrate" | "onecxt" | "whenuse";

export const VARIANT_CONFIG: Record<TopicVariant, { title: string; subtitle: string; Diagram: React.FC }> = {
  pain: { title: "Agent 痛点：程序性记忆断裂", subtitle: "每次会话从零，重复踩坑", Diagram: BrokenChain },
  dual: { title: "OpenClaw 双轨进化", subtitle: "轻轨 Self-Improving + 重载 AutoSkill", Diagram: DualTrackRails },
  selfimproving: { title: "Self-Improving · 错题本", subtitle: "LEARNINGS → 注入上下文 → promote", Diagram: NotebookFlow },
  autoskill: { title: "AutoSkill 生命周期", subtitle: "提取 → 维护 → 检索 → 执行（闭环）", Diagram: AutoSkillCycle },
  compare: { title: "三方方案对比", subtitle: "SkillClaw (AMAP-ML) · Google SkillOS · OpenClaw", Diagram: ThreeColumnCompare },
  integrate: { title: "生态集成", subtitle: "ClawHub · hooks · AGENTS.md · MCP", Diagram: IntegrationRadial },
  onecxt: { title: "one-context 衔接", subtitle: "skill-self-evolution-loop（设计中）", Diagram: EvolutionLoopFixed },
  whenuse: { title: "适用场景与起步", subtitle: "先错题本，再技能封装", Diagram: DashboardGrid },
};
```

**Step 2: 更新 Root.tsx — 注册 3 个 Composition**

```tsx
import React from "react";
import { Composition } from "remotion";
import { TOTAL_FRAMES, FPS } from "./audioConfig";
import { VideoA } from "./scenes/variants/A/VideoA";
import { VideoB } from "./scenes/variants/B/VideoB";
import { VideoC } from "./scenes/variants/C/VideoC";

const CANVAS_W = 1920;
const CANVAS_H = 1080;

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="VersionA" component={VideoA} durationInFrames={TOTAL_FRAMES} fps={FPS} width={CANVAS_W} height={CANVAS_H} />
    <Composition id="VersionB" component={VideoB} durationInFrames={TOTAL_FRAMES} fps={FPS} width={CANVAS_W} height={CANVAS_H} />
    <Composition id="VersionC" component={VideoC} durationInFrames={TOTAL_FRAMES} fps={FPS} width={CANVAS_W} height={CANVAS_H} />
  </>
);
```

**Step 3: 提交**

```bash
git add remotion/src/scenes/variants/shared-config.ts remotion/src/Root.tsx
git commit -m "feat(root): register 3 compositions VersionA/B/C for comparison"
```

---

## Task 6: 验证 — Remotion Studio 启动预览

**Step 1: 安装依赖（如需）**

```bash
cd features/content-pipeline/openclaw-self-improving-autoskill-mid-video/remotion
npm install
```

**Step 2: 启动 Studio**

```bash
npm run dev
```

**Step 3: 验证清单**

- [ ] Studio 启动无报错
- [ ] 左侧列表显示 VersionA / VersionB / VersionC
- [ ] 切换 VersionA：s02/s04/s06 有 Anime 动画，其余 spring 渐入
- [ ] 切换 VersionB：所有场景 stagger 渐入
- [ ] 切换 VersionC：所有场景 Anime timeline 逐步构建
- [ ] 音频正常播放，时长与场景对齐
- [ ] s06 集成图无 SkillBank 节点
- [ ] s07 闭环图标注「人审」「设计中」

**Step 4: 提交最终状态**

```bash
git add -A
git commit -m "chore: fix any remaining issues from studio verification"
```

---

Plan complete and saved to `docs/plans/2026-06-08-openclaw-autoskill-scenes-redesign-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?