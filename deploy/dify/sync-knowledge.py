#!/usr/bin/env python3
\"\"\"
sync-knowledge.py — 将本地 knowledge/ 目录同步到远程 Dify 知识库

用法:
  # 先设置环境变量或创建 .env 文件:
  export DIFY_URL=https://your-server.com
  export DIFY_API_KEY=your-dataset-api-key

  # 同步所有文档:
  python sync-knowledge.py --dir ../../knowledge

  # 仅同步指定子目录:
  python sync-knowledge.py --dir ../../knowledge/standards

  # 先预览(不真正上传):
  python sync-knowledge.py --dir ../../knowledge --dry-run

依赖: pip install requests
\"\"\"

import os
import sys
import json
import hashlib
import argparse
import mimetypes
from pathlib import Path

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests")
    sys.exit(1)

# ============================================================
# 默认配置 — 可通过环境变量覆盖
# ============================================================
DIFY_URL = os.getenv("DIFY_URL", "").rstrip("/")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")

# 支持的文件类型
SUPPORTED_EXTS = {
    ".md", ".txt", ".pdf", ".docx", ".csv", ".html", ".htm",
    ".xlsx", ".xls", ".json", ".xml", ".yaml", ".yml",
}

# 忽略的文件/目录
IGNORE_DIRS = {"__pycache__", ".git", "node_modules", ".DS_Store", "images"}
IGNORE_FILES = {"README.md", ".DS_Store"}


def get_file_hash(path: Path) -> str:
    \"\"\"计算文件 SHA256 用于去重\"\"\"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_knowledge(base_dir: Path) -> list[dict]:
    \"\"\"扫描目录，返回文件信息列表\"\"\"
    files = []
    if not base_dir.exists():
        print(f"❌ 目录不存在: {base_dir}")
        return files

    for item in sorted(base_dir.rglob("*")):
        if not item.is_file():
            continue
        # 跳过忽略
        if item.name in IGNORE_FILES:
            continue
        # 跳过忽略目录中的文件
        if any(part in IGNORE_DIRS for part in item.parts):
            continue
        ext = item.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            print(f"  ⏭ 跳过(不支持格式): {item.relative_to(base_dir)}")
            continue
        files.append({
            "path": item,
            "relative": str(item.relative_to(base_dir)),
            "ext": ext,
            "size": item.stat().st_size,
            "hash": get_file_hash(item),
        })
    return files


def upload_file(url: str, api_key: str, filepath: Path, dataset_id: str) -> bool:
    \"\"\"上传单个文件到 Dify 知识库\"\"\"
    # 自动判断 MIME
    mime_type, _ = mimetypes.guess_type(str(filepath))
    if mime_type is None:
        mime_type = "application/octet-stream"

    with open(filepath, "rb") as f:
        files = {"file": (filepath.name, f, mime_type)}
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = requests.post(
                f"{url}/v1/datasets/{dataset_id}/document/create-by-file",
                headers=headers,
                files=files,
                timeout=120,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                doc_id = data.get("document", {}).get("id", "unknown")
                print(f"  ✅ 上传成功: {filepath.name} (id={doc_id})")
                return True
            else:
                print(f"  ❌ 上传失败: {filepath.name} — {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"  ❌ 上传异常: {filepath.name} — {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="同步本地 knowledge/ 到 Dify 知识库")
    parser.add_argument("--dir", default="../../knowledge",
                        help="knowledge 目录路径 (默认 ../../knowledge)")
    parser.add_argument("--url", default=DIFY_URL,
                        help="Dify 服务器地址 (或设置 DIFY_URL 环境变量)")
    parser.add_argument("--api-key", default=DIFY_API_KEY,
                        help="Dify 数据集 API Key (或设置 DIFY_API_KEY 环境变量)")
    parser.add_argument("--dataset-id", required=True,
                        help="Dify 知识库(数据集) ID")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览，不上传")
    parser.add_argument("--limit", type=int, default=0,
                        help="限制上传文件数 (0=不限)")

    args = parser.parse_args()

    # 检查配置
    if not args.url:
        print("❌ 请提供 Dify URL (--url 或 DIFY_URL 环境变量)")
        sys.exit(1)
    if not args.api_key:
        print("❌ 请提供 API Key (--api-key 或 DIFY_API_KEY 环境变量)")
        sys.exit(1)
    if not args.dataset_id:
        print("❌ 请提供知识库 ID (--dataset-id)")
        sys.exit(1)

    # 扫描
    base = Path(args.dir).resolve()
    print(f"🔍 扫描知识库目录: {base}")
    files = scan_knowledge(base)
    print(f"   共找到 {len(files)} 个可上传文件\\n")

    if not files:
        print("没有需要上传的文件。")
        return

    # 预览
    print("文件列表:")
    for f in files:
        size_kb = f["size"] / 1024
        print(f"  📄 {f['relative']} ({size_kb:.1f} KB)")
    print()

    if args.dry_run:
        print("🟡 DRY RUN — 未执行上传")
        return

    # 上传
    if args.limit > 0:
        files = files[:args.limit]

    print(f"🚀 开始上传 {len(files)} 个文件到 {args.url} ...")
    success = 0
    fail = 0
    for f in files:
        ok = upload_file(args.url, args.api_key, f["path"], args.dataset_id)
        if ok:
            success += 1
        else:
            fail += 1

    print(f"\\n📊 完成: ✅ {success} 成功 | ❌ {fail} 失败 | 📁 共 {len(files)} 个")


if __name__ == "__main__":
    main()
