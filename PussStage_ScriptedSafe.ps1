<#
.SYNOPSIS
Starts PussStage's opt-in lightweight editor profile for scripted work.

.DESCRIPTION
The profile loads /Engine/Maps/Entry and installs transient editor-only
rendering limits. It does not edit DefaultEngine.ini or saved user settings.
Use -DryRun to inspect the exact executable and arguments without launching.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$AllowParallelEditor,
    [string[]]$AdditionalArguments = @()
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$projectFile = Join-Path $projectRoot 'PussStage.uproject'
$editorExe = 'D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$profileArgument = '-CustomConfig=ScriptedSafe'
$launchArguments = @('"' + $projectFile + '"', $profileArgument, '-NoSplash') + $AdditionalArguments

if (-not (Test-Path -LiteralPath $projectFile -PathType Leaf)) {
    throw "PussStage project file not found: $projectFile"
}
if (-not (Test-Path -LiteralPath $editorExe -PathType Leaf)) {
    throw "UE 5.8 editor not found: $editorExe"
}

Write-Output 'PUSS_SCRIPTED_SAFE_LAUNCH'
Write-Output "Executable=$editorExe"
Write-Output ('Arguments=' + ($launchArguments -join ' '))
Write-Output 'StartupMap=/Engine/Maps/Entry.Entry'
Write-Output 'Normal project launch remains unchanged.'

if ($DryRun) {
    Write-Output 'DRY_RUN_OK|no_process_started=true'
    return
}

$runningEditors = @(Get-Process -Name 'UnrealEditor' -ErrorAction SilentlyContinue)
if ($runningEditors.Count -gt 0 -and -not $AllowParallelEditor) {
    $runningPids = (($runningEditors.Id | Sort-Object) -join ',')
    throw "UnrealEditor is already running (PID(s): $runningPids). Close it, or explicitly use -AllowParallelEditor if a second editor is intentional."
}

Start-Process -FilePath $editorExe -ArgumentList $launchArguments -WorkingDirectory $projectRoot
Write-Output 'LAUNCH_REQUESTED|profile=ScriptedSafe'
