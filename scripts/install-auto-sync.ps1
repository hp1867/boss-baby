[CmdletBinding()]
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "BossBaby GitHub Auto Sync"
$RepoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$WatcherPath = Join-Path $PSScriptRoot "auto-sync.ps1"

if ($Uninstall) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "Removed scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path -LiteralPath $WatcherPath)) {
    throw "Watcher not found: $WatcherPath"
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$powerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$watcherArgument = '"' + $WatcherPath + '"'
$arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File $watcherArgument"

$action = New-ScheduledTaskAction `
    -Execute $powerShellExe `
    -Argument $arguments `
    -WorkingDirectory $RepoPath
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal `
    -UserId $identity `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Automatically commits BossBaby edits and pushes them to GitHub." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Output "Installed and started scheduled task: $TaskName"
Write-Output "Repository: $RepoPath"
Write-Output "Log: $(Join-Path $RepoPath '.git\auto-sync.log')"
