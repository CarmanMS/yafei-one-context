# `p_ALLP` LaTeX

## One-shot PDF

```powershell
.\compile-pdf.ps1
```

**Why the PDF in Cursor “never changes”:** the file on disk is updated; Cursor’s **built-in PDF tab often keeps an old buffer**. This is an editor limitation, not LaTeX.

**Default fix (no extra questions):** `compile-pdf.ps1` now **opens the PDF outside Cursor** after a successful build. If **SumatraPDF** is installed (or `SUMATRA_PDF_PATH` points to `SumatraPDF.exe`), it uses **`-reuse-instance`**: one window, **reloads when the same file is rebuilt**. Treat that window as the source of truth, not the Cursor tab.

Each successful compile also prints **SHA256** of `p_ALLP.pdf` in the terminal—if you change `.tex` and recompile, that hex string **must** change when the new PDF is written; if it changes but the Cursor PDF tab does not, the tab is stale (editor bug).

**LaTeX Workshop (Save):** saving `p_ALLP.tex` runs **pdflatex ×2** and should refresh the **LaTeX Workshop PDF tab** (right side). Path contains Chinese characters → workspace sets `latex-workshop.latex.watch.usePolling: true` so the viewer notices the new `p_ALLP.pdf`.

**Ctrl+Shift+B:** default task **compile PDF (Cursor 内预览)** = compile only (`-NoOpen`). External Sumatra: run task **compile PDF (外部 Sumatra/WPS)** or recipe **+ open external PDF**.

- Skip auto-open (e.g. CI): `.\compile-pdf.ps1 -NoOpen`
- Custom Sumatra path: `$env:SUMATRA_PDF_PATH = 'D:\Tools\SumatraPDF.exe'` then run the script

## Auto-rebuild while editing (no Cursor extension)

Leave this running in a terminal; it watches `p_ALLP.tex` and dependencies:

```powershell
.\watch-pdf.ps1
```

Requires **latexmk** on `PATH` (MiKTeX: install the `latexmk` package). Stop with Ctrl+C.

## Cursor / VS Code: PDF on save (LaTeX Workshop)

1. Install extension **LaTeX Workshop** (`James-Yu.latex-workshop`).
2. Open the **one-context repo root** as the workspace (so repo `.vscode/settings.json` applies).
3. Edit `p_ALLP.tex` and **save** — the extension runs `pdflatex` twice.

Workspace viewer is **`tab`** (in-editor). `*.pdf` opens with **LaTeX Workshop’s viewer**, not the plain text editor.

### If the embedded PDF looks stale

1. **Ctrl+Shift+P** → **`LaTeX Workshop: Refresh PDF viewer`** (`latex-workshop.refresh-viewer`).
2. Still wrong → close the PDF tab → **`LaTeX Workshop: View LaTeX PDF`**.
3. Do **not** open `p_ALLP.pdf` from the explorer as a normal file (shows “Binary file…” or an old buffer).
4. Terminal: after compile, check **SHA256** printed by `compile-pdf.ps1`; if the hash changed but the tab did not, the tab is stale—use step 1–2 or external Sumatra.

Optional keybinding (user `keybindings.json`): bind **`latex-workshop.refresh-viewer`** while editing `.tex`.

**Canonical vs `repos/`:** The maintained `p_ALLP.tex` / `p_ALLP.pdf` for this feature live only in this directory (`features/research/approximating-local-lifting-property/paper/`). `repos/.../p_ALLP.tex` is a different draft (different title); do not confuse it with this manuscript unless you intentionally compile that file.
