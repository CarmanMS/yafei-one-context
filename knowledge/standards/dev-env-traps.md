# Dev Env Traps

开发环境中容易被误判为代码 bug 的现象及处置。

## Remotion Studio: bugs.remotion.dev 请求失败

**现象**：`npm run dev` 启动 Remotion Studio 后，浏览器控制台报错：

```
mediabunny.cjs:16047 Uncaught (in promise) AbortError: The user aborted a request.
inspector.js:7 Fetch request failed: TypeError: Failed to fetch
```

Network 面板可见：

```
GET https://bugs.remotion.dev/api/4.0.463 => net::ERR_SOCKS_CONNECTION_FAILED
```

**原因**：Remotion Studio 启动时自动请求 `bugs.remotion.dev` 检查当前版本是否有已知 bug。当系统配置了 SOCKS 代理（如 `127.0.0.1:13659`）且该代理无法转发 HTTPS 请求到该域名时，fetch 被中止，mediabunny 的 AbortController 将其包装为 `AbortError`。

**影响**：**无功能影响**。仅版本 bug 检查提示缺失，不影响预览、渲染、导出。

**处置**：

1. 忽略即可（推荐）
2. 或在浏览器中将 `bugs.remotion.dev` 加入代理例外（bypass）
3. 或临时关闭 SOCKS 代理

**判断依据**：控制台仅有 `bugs.remotion.dev` 的 `ERR_SOCKS_CONNECTION_FAILED`，且 Remotion Studio 界面正常、视频可播放、WAV 的 206 Partial Content 请求正常 → 确认为代理问题而非代码 bug。