# d:\harnessworld\one-context\skills\gitsync\sync_repos.ps1

function Run-WithTimeout {
    param(
        [string]$Command,
        [string]$Arguments,
        [int]$TimeoutSeconds = 30
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Command
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = (Get-Location).Path
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    
    $p.Start() | Out-Null
    
    $completed = $p.WaitForExit($TimeoutSeconds * 1000)
    if (-not $completed) {
        $p.Kill()
        return @{ Timeout = $true }
    }
    
    return @{
        Timeout = $false
        ExitCode = $p.ExitCode
        Output = $p.StandardOutput.ReadToEnd()
        Error = $p.StandardError.ReadToEnd()
    }
}

$gitDirs = @(
    "repos\develop\FunctionCanvas",
    "repos\develop\hangprofile",
    "repos\develop\VideoFactory",
    "repos\integrations\trend-radar",
    "repos\reference\anime",
    "repos\reference\architecture-diagram-generator",
    "repos\reference\awesome-design-md",
    "repos\reference\claude-code-best-practice",
    "repos\reference\GSAP",
    "repos\reference\html-anything",
    "repos\reference\html-ppt-skill",
    "repos\reference\hyperframes",
    "repos\reference\open-design",
    "repos\reference\openhuman",
    "repos\reference\remotion-video-skill",
    "repos\research\awesome-design-md",
    "repos\research\paperwork"
)

$baseDir = "D:\harnessworld\one-context"

foreach ($relDir in $gitDirs) {
    $dir = Join-Path $baseDir $relDir
    if (Test-Path $dir) {
        Write-Host "========================================"
        Write-Host "Syncing: $relDir"
        Write-Host "========================================"
        Push-Location $dir
        try {
            $branch = (git branch --show-current 2>$null)
            if ([string]::IsNullOrEmpty($branch)) {
                Write-Host "  No active branch (detached HEAD or empty repo)"
                continue
            }
            $upstream = (git rev-parse --abbrev-ref '@{upstream}' 2>$null)
            if ([string]::IsNullOrEmpty($upstream)) {
                Write-Host "  No upstream configured for branch '$branch'"
                continue
            }
            
            $localHead = (git rev-parse HEAD 2>$null)
            $remoteHeadBefore = (git rev-parse $upstream 2>$null)
            
            Write-Host "  Branch: $branch"
            Write-Host "  Upstream: $upstream"
            Write-Host "  Local HEAD:  $($localHead.Substring(0,8))"
            Write-Host "  Remote HEAD: $($remoteHeadBefore.Substring(0,8))"
            
            # Fetch
            Write-Host "  Fetching from remote (with 30s timeout)..."
            $remoteParts = $upstream -split '/'
            $remoteName = $remoteParts[0]
            $remoteBranch = $remoteParts[1..($remoteParts.Count-1)] -join '/'
            
            $fetchRes = Run-WithTimeout "git" "fetch $remoteName $remoteBranch" 30
            if ($fetchRes.Timeout) {
                Write-Host "  WARNING: Fetch timed out after 30 seconds!"
                continue
            }
            if ($fetchRes.ExitCode -ne 0) {
                Write-Host "  ERROR: Fetch failed with exit code $($fetchRes.ExitCode)"
                Write-Host "  Error output: $($fetchRes.Error)"
                continue
            }
            
            $remoteHeadAfter = (git rev-parse $upstream 2>$null)
            Write-Host "  Fetched to:  $($remoteHeadAfter.Substring(0,8))"
            
            if ($localHead -eq $remoteHeadAfter) {
                Write-Host "  Result: Already up to date (no changes)"
                continue
            }
            
            # Check fast-forward
            git merge-base --is-ancestor $localHead $remoteHeadAfter 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  WARNING: Cannot fast-forward. Local branch has diverged."
                continue
            }
            
            # Pull
            Write-Host "  Fast-forwarding..."
            $status = (git status --porcelain 2>$null)
            $hasChanges = ![string]::IsNullOrEmpty($status)
            
            if ($hasChanges) {
                Write-Host "  Stashing local changes..."
                git stash push -m "gitsync-auto"
                git pull --ff-only
                Write-Host "  Restoring stashed changes..."
                git stash pop
            } else {
                git pull --ff-only
            }
            
            $localHeadAfter = (git rev-parse HEAD 2>$null)
            Write-Host "  After sync: $($localHeadAfter.Substring(0,8))"
            if ($localHeadAfter -eq $remoteHeadAfter) {
                Write-Host "  Status: Synced"
            } else {
                Write-Host "  Status: MISMATCH"
            }
        } catch {
            Write-Host "  ERROR: $_"
        } finally {
            Pop-Location
        }
        Write-Host ""
    } else {
        Write-Host "Directory not found: $relDir"
    }
}
