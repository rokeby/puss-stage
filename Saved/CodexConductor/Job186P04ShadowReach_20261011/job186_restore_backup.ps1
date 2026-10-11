param(
    [Parameter(Mandatory = $true)][string]$BackupRoot,
    [Parameter(Mandatory = $true)][string]$Confirm
)

$ErrorActionPreference = 'Stop'
if ($Confirm -cne 'RESTORE JOB186 P04 MAP BACKUP') {
    throw 'CONFIRM_MISSING|need=RESTORE JOB186 P04 MAP BACKUP'
}
if (Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue) {
    throw 'UNREAL_EDITOR_RUNNING|close every Unreal editor before package restore'
}

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$backupResolved = [System.IO.Path]::GetFullPath($BackupRoot)
$allowedBackupRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot 'Backups'))
if (-not $backupResolved.StartsWith($allowedBackupRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "BACKUP_OUTSIDE_PROJECT|$backupResolved"
}

$relativeMap = 'InfinityStage\Dev\Maps\L_InfinityStage_V1VerticalSlice.umap'
$source = [System.IO.Path]::GetFullPath((Join-Path $backupResolved $relativeMap))
$target = [System.IO.Path]::GetFullPath((Join-Path (Join-Path $projectRoot 'Content') $relativeMap))
$contentRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot 'Content'))
if (-not $target.StartsWith($contentRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "TARGET_OUTSIDE_CONTENT|$target"
}
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "BACKUP_MAP_MISSING|$source"
}
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "TARGET_MAP_MISSING|$target"
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$safetyRoot = Join-Path $projectRoot ("Backups\PreJob186P04TagRestore-$stamp")
$safetyTarget = Join-Path $safetyRoot $relativeMap
New-Item -ItemType Directory -Path (Split-Path -Parent $safetyTarget) | Out-Null
Copy-Item -LiteralPath $target -Destination $safetyTarget
$beforeHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
$safetyHash = (Get-FileHash -LiteralPath $safetyTarget -Algorithm SHA256).Hash
if ($beforeHash -cne $safetyHash) {
    throw 'PRE_RESTORE_BACKUP_HASH_MISMATCH'
}
Copy-Item -LiteralPath $source -Destination $target -Force
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
if ($sourceHash -cne $targetHash) {
    throw 'RESTORE_HASH_MISMATCH'
}
Write-Output "JOB186_P04_TAG_RESTORE_OK|source=$source|target=$target|sha256=$targetHash|pre_restore_backup=$safetyRoot"
