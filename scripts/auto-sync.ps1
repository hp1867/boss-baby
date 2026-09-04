[CmdletBinding()]
param(
    [switch]$Once,
    [ValidateRange(2, 300)]
    [int]$PollSeconds = 3,
    [ValidateRange(5, 3600)]
    [int]$SettleSeconds = 12,
    [ValidateRange(15, 3600)]
    [int]$RetrySeconds = 60
)

$ErrorActionPreference = "Stop"
$RepoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$GitCommand = Get-Command git.exe -ErrorAction Stop
$GitExe = $GitCommand.Source

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)

    # Windows PowerShell 5.1 wraps a native program's stderr as ErrorRecord
    # objects. Git writes normal progress and warnings to stderr, so judge the
    # command by its process exit code instead of ErrorActionPreference.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = @(& $script:GitExe -C $script:RepoPath @GitArgs 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    $output = ($lines | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    [pscustomobject]@{
        ExitCode = $exitCode
        Output   = $output
    }
}

$gitDirResult = Invoke-Git -GitArgs @("rev-parse", "--absolute-git-dir")
if ($gitDirResult.ExitCode -ne 0) {
    throw "BossBaby is not a Git worktree: $($gitDirResult.Output)"
}

$GitDir = $gitDirResult.Output.Trim()
$LogPath = Join-Path $GitDir "auto-sync.log"
$ProtectedPaths = @(
    "config.json"
)

function Write-SyncLog {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $script:LogPath -Value "$timestamp $Message" -Encoding UTF8
}

function Get-CurrentBranch {
    $result = Invoke-Git -GitArgs @("symbolic-ref", "--quiet", "--short", "HEAD")
    if ($result.ExitCode -ne 0) {
        return $null
    }
    return $result.Output.Trim()
}

function Get-HeadCommit {
    $result = Invoke-Git -GitArgs @("rev-parse", "HEAD")
    if ($result.ExitCode -ne 0) {
        return $null
    }
    return $result.Output.Trim()
}

function Test-PushNeeded {
    $upstream = Invoke-Git -GitArgs @(
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}"
    )
    if ($upstream.ExitCode -ne 0) {
        return $true
    }

    $ahead = Invoke-Git -GitArgs @(
        "rev-list",
        "--count",
        "$($upstream.Output.Trim())..HEAD"
    )
    if ($ahead.ExitCode -ne 0) {
        return $true
    }

    return ([int]$ahead.Output.Trim()) -gt 0
}

function Get-WorkingTreeSnapshot {
    $result = Invoke-Git -GitArgs @("status", "--porcelain=v1", "--untracked-files=all")
    if ($result.ExitCode -ne 0) {
        Write-SyncLog "Could not read Git status: $($result.Output)"
        return $null
    }
    return $result.Output
}

function Test-GitOperationInProgress {
    $markers = @(
        "index.lock",
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-apply",
        "rebase-merge",
        "sequencer"
    )

    foreach ($marker in $markers) {
        if (Test-Path -LiteralPath (Join-Path $script:GitDir $marker)) {
            return $true
        }
    }
    return $false
}

function Unstage-ProtectedFiles {
    $result = Invoke-Git -GitArgs @("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if ($result.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($result.Output)) {
        return
    }

    foreach ($path in ($result.Output -split "`r?`n")) {
        $normalized = $path.Trim().Replace("\", "/")
        if ($script:ProtectedPaths -contains $normalized) {
            $reset = Invoke-Git -GitArgs @("reset", "-q", "HEAD", "--", $path)
            if ($reset.ExitCode -eq 0) {
                Write-SyncLog "Safety check: kept $normalized out of the automatic commit."
            } else {
                throw "Could not unstage protected file ${normalized}: $($reset.Output)"
            }
        }
    }
}

function Save-WorkingTree {
    if (Test-GitOperationInProgress) {
        Write-SyncLog "Git is busy with another operation; automatic commit postponed."
        return $false
    }

    $add = Invoke-Git -GitArgs @("add", "--all", "--", ".")
    if ($add.ExitCode -ne 0) {
        Write-SyncLog "git add failed: $($add.Output)"
        return $false
    }

    try {
        Unstage-ProtectedFiles
    } catch {
        Write-SyncLog $_.Exception.Message
        return $false
    }

    $diff = Invoke-Git -GitArgs @("diff", "--cached", "--quiet", "--exit-code")
    if ($diff.ExitCode -eq 0) {
        return $false
    }
    if ($diff.ExitCode -ne 1) {
        Write-SyncLog "Could not inspect staged changes: $($diff.Output)"
        return $false
    }

    $message = "Auto-commit: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $commit = Invoke-Git -GitArgs @("commit", "--no-gpg-sign", "-m", $message)
    if ($commit.ExitCode -ne 0) {
        Write-SyncLog "git commit failed: $($commit.Output)"
        return $false
    }

    $head = Get-HeadCommit
    Write-SyncLog "Created automatic commit $($head.Substring(0, 8))."
    return $true
}

function Publish-CurrentBranch {
    $branch = Get-CurrentBranch
    if ([string]::IsNullOrWhiteSpace($branch)) {
        Write-SyncLog "HEAD is detached; automatic push postponed."
        return $false
    }

    $push = Invoke-Git -GitArgs @("push", "origin", $branch)
    if ($push.ExitCode -eq 0) {
        Write-SyncLog "GitHub is up to date on origin/$branch."
        return $true
    }

    Write-SyncLog "Initial push failed; checking whether origin/$branch changed."
    if (-not [string]::IsNullOrWhiteSpace((Get-WorkingTreeSnapshot))) {
        Write-SyncLog "New local edits are present; remote reconciliation postponed."
        return $false
    }

    $pull = Invoke-Git -GitArgs @("pull", "--rebase", "origin", $branch)
    if ($pull.ExitCode -ne 0) {
        $rebaseApply = Join-Path $script:GitDir "rebase-apply"
        $rebaseMerge = Join-Path $script:GitDir "rebase-merge"
        if ((Test-Path -LiteralPath $rebaseApply) -or (Test-Path -LiteralPath $rebaseMerge)) {
            [void](Invoke-Git -GitArgs @("rebase", "--abort"))
        }
        Write-SyncLog "Could not rebase onto origin/$branch; no force-push was attempted."
        return $false
    }

    $retry = Invoke-Git -GitArgs @("push", "origin", $branch)
    if ($retry.ExitCode -eq 0) {
        Write-SyncLog "Rebased and updated origin/$branch."
        return $true
    }

    Write-SyncLog "Push is still pending (network, authentication, or remote policy issue)."
    return $false
}

$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\BossBabyGitHubAutoSync", [ref]$createdNew)
if (-not $createdNew) {
    exit 0
}

try {
    if ($Once) {
        $savedCommit = $false
        $firstSnapshot = Get-WorkingTreeSnapshot
        if (-not [string]::IsNullOrWhiteSpace($firstSnapshot)) {
            Start-Sleep -Seconds $SettleSeconds
            $secondSnapshot = Get-WorkingTreeSnapshot
            if ($secondSnapshot -eq $firstSnapshot) {
                $savedCommit = Save-WorkingTree
            } else {
                Write-SyncLog "Files are still changing; automatic commit postponed."
            }
        }

        if ($savedCommit -or (Test-PushNeeded)) {
            if (Publish-CurrentBranch) {
                exit 0
            }
            exit 1
        }
        exit 0
    }

    Write-SyncLog "Continuous auto-sync started for $RepoPath."
    $lastSnapshot = $null
    $stableSince = $null
    $lastHead = Get-HeadCommit
    $pushPending = Test-PushNeeded
    $lastPushAttempt = [datetime]::MinValue

    while ($true) {
        $now = Get-Date
        $head = Get-HeadCommit
        if ($head -and $lastHead -and $head -ne $lastHead) {
            $pushPending = $true
        }
        if ($head) {
            $lastHead = $head
        }

        $snapshot = Get-WorkingTreeSnapshot
        if (-not [string]::IsNullOrWhiteSpace($snapshot)) {
            if ($snapshot -ne $lastSnapshot) {
                $lastSnapshot = $snapshot
                $stableSince = $now
            } elseif ($stableSince -and ($now - $stableSince).TotalSeconds -ge $SettleSeconds) {
                if (Save-WorkingTree) {
                    $pushPending = $true
                    $lastHead = Get-HeadCommit
                }
                $lastSnapshot = $null
                $stableSince = $null
            }
        } else {
            $lastSnapshot = $null
            $stableSince = $null
        }

        if ($pushPending -and ($now - $lastPushAttempt).TotalSeconds -ge $RetrySeconds) {
            $lastPushAttempt = $now
            if (Publish-CurrentBranch) {
                $pushPending = $false
                $lastHead = Get-HeadCommit
            }
        }

        Start-Sleep -Seconds $PollSeconds
    }
} catch {
    Write-SyncLog "Auto-sync stopped unexpectedly: $($_.Exception.Message)"
    throw
} finally {
    if ($createdNew) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
