#!/usr/bin/env bash
# ZenMux API Key 验证脚本 — 在阿里云服务器或本地运行
# 用法: bash verify-zenmux.sh sk-ai-v1-你的key
# 作用: 确认 Key 可用、列出可用模型、测试对话，确认无误再填入 Dify

set -e
KEY="${1:?用法: bash verify-zenmux.sh <你的ZenMux-API-Key>}"
BASE="https://zenmux.ai/api/v1"

echo "============================================"
echo "  ZenMux API Key 验证"
echo "============================================"
echo

echo "[1/3] 测试连通性 + 列出可用模型（前 600 字符）..."
echo "--------------------------------------------"
curl -s --max-time 30 "$BASE/models" \
  -H "Authorization: Bearer $KEY" | head -c 600
echo; echo

echo "[2/3] 对话测试 — deepseek-chat ..."
echo "--------------------------------------------"
curl -s --max-time 60 "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"1+1等于几？只回答数字"}],"max_tokens":50}'
echo; echo

echo "[3/3] 对话测试 — anthropic/claude-opus-4.8 ..."
echo "--------------------------------------------"
curl -s --max-time 60 "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"anthropic/claude-opus-4.8","messages":[{"role":"user","content":"你好，简短回复"}],"max_tokens":50}'
echo; echo

echo "============================================"
echo "  验证完成"
echo "  若上方有正常回复 → Key 可用，可填入 Dify"
echo "  若返回 401 → Key 错误或未充值"
echo "  若 deepseek-chat 报 model not found → 看 [1/3] 列表里的准确 slug 再试"
echo "============================================"
