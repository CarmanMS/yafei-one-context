# Run from repo root or double-click; working dir is this script's folder.
# After build, opens the PDF externally (Cursor's built-in PDF tab often caches old bytes).
#   -NoOpen   Skip opening any viewer (CI / batch)
param([switch]$NoOpen)

Set-Location $PSScriptRoot
pdflatex -interaction=nonstopmode p_ALLP.tex
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
pdflatex -interaction=nonstopmode p_ALLP.tex
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$pdf = Join-Path $PSScriptRoot 'p_ALLP.pdf'
if (-not (Test-Path -LiteralPath $pdf)) { exit 0 }

$t = (Get-Item -LiteralPath $pdf).LastWriteTime
$full = (Resolve-Path -LiteralPath $pdf).Path
$hash = (Get-FileHash -LiteralPath $pdf -Algorithm SHA256).Hash
Write-Host "p_ALLP.pdf updated: $t"
Write-Host "Full path: $full"
Write-Host "SHA256: $hash   (if this string changes after an edit, the PDF on disk is new—ignore stale Cursor tab)"

if ($NoOpen) {
    Write-Host "Skipped external PDF open (-NoOpen)."
    exit 0
}

& (Join-Path $PSScriptRoot 'open-p_ALLP-external.ps1')
Write-Host "Use Sumatra/external window for truth; Cursor embedded PDF preview is unreliable."