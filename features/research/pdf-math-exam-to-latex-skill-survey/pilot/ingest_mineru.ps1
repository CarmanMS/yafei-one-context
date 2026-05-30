# PDF → MinerU → output/mineru（免费本机）
param(
    [Parameter(Mandatory = $true)]
    [string]$PdfPath,
    [string]$OutDir = "output/mineru"
)

$ErrorActionPreference = "Stop"
$Pilot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Out = Join-Path $Pilot $OutDir
New-Item -ItemType Directory -Force -Path $Out | Out-Null

if (-not (Test-Path -LiteralPath $PdfPath)) {
    throw "PDF not found: $PdfPath"
}

Write-Host "MinerU ingest (free, local). First run downloads models — may take long."
Write-Host "Output: $Out"

# pilot → feature → research → features → repo root
$RepoRoot = Split-Path (Split-Path (Split-Path (Split-Path $Pilot -Parent) -Parent) -Parent) -Parent
$UserVenvMineru = Join-Path $env:USERPROFILE ".venv-pdf-exam\Scripts\mineru.exe"
$RepoVenvMineru = Join-Path $RepoRoot ".venv-pdf-exam\Scripts\mineru.exe"
# 优先 ASCII 路径 venv（仓库在中文路径下时 MinerU/fasttext 会失败）
$MineruExe = if (Test-Path $UserVenvMineru) { $UserVenvMineru } elseif (Test-Path $RepoVenvMineru) { $RepoVenvMineru } else { $null }

$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"
if (-not $env:HF_ENDPOINT) { $env:HF_ENDPOINT = "https://hf-mirror.com" }

if ($MineruExe) {
    & $MineruExe -p $PdfPath -o $Out -f true -s 0 -e 0 -l ch -b pipeline -m auto
} elseif (Get-Command mineru -ErrorAction SilentlyContinue) {
    & mineru -p $PdfPath -o $Out -f true -s 0 -e 0 -l ch -b pipeline -m auto
} else {
    Write-Host "请先创建 venv（建议 ASCII 路径 %USERPROFILE%\.venv-pdf-exam）："
    Write-Host "  python -m venv $env:USERPROFILE\.venv-pdf-exam"
    Write-Host "  & $env:USERPROFILE\.venv-pdf-exam\Scripts\pip install `"mineru[core]`" scipy jinja2 pyyaml jsonschema"
    exit 1
}

Write-Host "Done. Check $Out for *.md"
