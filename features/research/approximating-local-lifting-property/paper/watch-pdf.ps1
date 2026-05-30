# Continuous build: saves to p_ALLP.tex (or inputs) trigger pdflatex via latexmk.
# Run in this folder; Ctrl+C to stop. Requires latexmk (MiKTeX: install latexmk package).
Set-Location $PSScriptRoot
$latexmk = Get-Command latexmk -ErrorAction SilentlyContinue
if (-not $latexmk) {
    Write-Error "latexmk not on PATH. MiKTeX: install the latexmk package, or use compile-pdf.ps1 after each edit."
    exit 1
}
latexmk -pvc -pdf -interaction=nonstopmode -synctex=1 p_ALLP.tex
