# 一键安装依赖（在仓库根 PowerShell 执行）
#   .\features\research\pdf-math-exam-to-latex-skill-survey\pilot\install-deps.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent) -Parent
$Venv = Join-Path $env:USERPROFILE ".venv-pdf-exam"
$Py = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $Py) { $Py = "python" }

Write-Host "=== 1/3 Python venv @ $Venv（ASCII 路径，避免中文仓库路径导致 MinerU 失败）==="
if (-not (Test-Path "$Venv\Scripts\python.exe")) {
    & $Py -m venv $Venv
}
& "$Venv\Scripts\python.exe" -m pip install -U pip wheel
& "$Venv\Scripts\python.exe" -m pip install "mineru[core]" scipy jinja2 pyyaml jsonschema
& "$Venv\Scripts\mineru.exe" --help 2>$null
if (-not $?) { & "$Venv\Scripts\python.exe" -m mineru.cli.main --help }

Write-Host "=== 2/3 MiKTeX（免费，用于 xelatex 出 PDF）==="
if (Get-Command xelatex -ErrorAction SilentlyContinue) {
    Write-Host "xelatex 已存在: $(Get-Command xelatex | Select-Object -ExpandProperty Source)"
} else {
    Write-Host "正在 winget 安装 MiKTeX（可能弹出 UAC，需数分钟）..."
    winget install --id MiKTeX.MiKTeX -e --accept-package-agreements --accept-source-agreements
    Write-Host "安装后请新开终端，或把 MiKTeX bin 加入 PATH，再运行: xelatex --version"
}

Write-Host "=== 3/3 验证 YAML -> PDF（样例，不依赖 MinerU）==="
$Pilot = Join-Path $Root "features\research\pdf-math-exam-to-latex-skill-survey\pilot"
Push-Location $Pilot
& "$Venv\Scripts\python.exe" ai_revise_questions.py --in questions/page1.sample.yaml --out questions/page1.revised.yaml
if (Get-Command xelatex -ErrorAction SilentlyContinue) {
    & "$Venv\Scripts\python.exe" build_paper.py --input questions/page1.revised.yaml --out output/paper.pdf
    Write-Host "PDF: $Pilot\output\paper.pdf"
} else {
    & "$Venv\Scripts\python.exe" build_paper.py --input questions/page1.revised.yaml --out output/paper.pdf --no-pdf
    Write-Host "已生成 output/paper.tex；安装 MiKTeX 后去掉 --no-pdf 即可出 PDF"
}
Pop-Location
Write-Host "完成。MinerU 解析 PDF: .\ingest_mineru.ps1 -PdfPath `"你的试卷.pdf`""
