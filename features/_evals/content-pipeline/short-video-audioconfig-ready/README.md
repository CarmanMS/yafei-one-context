# short-video-audioconfig-ready

Eval fixture for `skills/remotion-pipelines` — sized for a "short video" project
that's about to call `scripts/generate-audioconfig.mjs` (策略 A，单 WAV)。

## Layout

| File | Size | Purpose |
|------|------|---------|
| `script.srt` | ~8.5 KB | 115 字幕段，重编号 1..115，总时长 `00:04:57,320 → 00:04:59,480`（≈ 5min） |
| `voiceover.wav` | ~2.3 MB | 5 分钟纯静音，mono / 8 kHz / 8-bit PCM —— 策略 A 只 `copyFileSync` 不读内容 |

## Provenance

- `script.srt`：截自 `features/content-pipeline/agent-long-term-memory-alibaba-cloud-mid-video/production/subtitles/sub.srt` 前 5 分钟段。
- `voiceover.wav`：由 `ffmpeg -f lavfi -i anullsrc=mono:8000 -t 300 -c:a pcm_u8` 生成，纯静音，避免引入真实音频版权 / 体积。

## Why this shape

策略 A 评测只关心：
1. 脚本能把 SRT 解析成 N 段 → 写出 `src/audioConfig.ts`
2. `SCENES.length === SRT 段数`
3. `TOTAL_FRAMES > 0` / `FPS === 30`

策略 A 不依赖 ffmpeg/ffprobe（无外部二进制），WAV 内容可以是静音；策略 B 才会去切 WAV，本 fixture 不针对策略 B。
