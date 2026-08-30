# Security

不要在公开 Issue 中披露未修复的漏洞、凭证或私人研究数据。

## 报告方式

优先使用 [CarmanMS/yafei-one-context 的 GitHub Security Advisories](https://github.com/CarmanMS/yafei-one-context/security/advisories/new)。若问题只存在于上游 `harnessworld/one-context`，同时按上游仓库的安全渠道报告。

报告中请包含受影响版本、复现步骤、影响范围和可行的缓解方式；请勿附真实 API key、私人 vault 内容或其他敏感样本。

## 敏感边界

以下内容不得提交：

- `skills/obsidian-knowledge/api-key.txt`
- `.env`、服务凭证和访问令牌
- `knowledge/**` 的导出副本或被内联的私人笔记
- 本地 Agent 会话、浏览器凭据和个人生成产物
- 子仓中的未公开研究或教学材料

`knowledge/**` 只能经 Obsidian Local REST API 访问。任何绕过 API 的读取、索引、同步或上传均视为安全边界违规。

依赖或部署示例不得包含默认生产密码、静态密钥或匿名公网数据服务。
