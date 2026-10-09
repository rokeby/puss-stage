<#
One unattended entry point for the Saturday Scene fallback render.

DRY:     live read-only Master survey and transient MRQ config probe.
APPLY:   backup/record, live DRY, create-only config BUILD, then S1-S6 P/C
         render -> encode -> QC -> merge-promote. Failures stop that delivery
         and the run continues with the next Scene. Raw renders are never deleted.
REVERT:  restore pre-run current.json and jobs manifest. Config assets and render
         evidence are retained; the report identifies them for a later reviewed cleanup.
#>
[CmdletBinding()]
param(
    [ValidateSet("DRY", "APPLY", "REVERT")][string]$Mode = "DRY",
    [string]$Confirm = "",
    [string]$RunId = ("SATFILM-" + (Get-Date -Format "yyyyMMdd-HHmmss")),
    [ValidatePattern('^v\d{2}$')][string]$Version = "v01",
    [ValidateSet("P", "C")][string[]]$Tiers = @("P", "C"),
    [string]$ProjectRoot = "E:\PussStage",
    [string]$ApprovedBy = "Saturday unattended hard QC"
)
$ErrorActionPreference = "Stop"

function Stop-Film([string]$Reason) {
    Write-Output ("SATFILM_STOPPED|run={0}|mode={1}|reason={2}" -f $RunId, $Mode, $Reason)
    exit 2
}

function Assert-MachineIdle {
    $busy = Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -match '^(UnrealEditor|UnrealEditor-Cmd|blender)$'
    }
    if ($busy) {
        Stop-Film ("PROCESSES_RUNNING|" + (($busy | ForEach-Object { "{0}:{1}" -f $_.ProcessName, $_.Id }) -join ","))
    }
}

function Invoke-MrqAuthoring([string]$AuthorMode, [string]$Suffix) {
    $argsObject = [ordered]@{
        mode = $AuthorMode
        run_id = "$RunId-$Suffix"
        version = $Version
        scenes = @(1, 2, 3, 4, 5, 6)
        tiers = @($Tiers)
        render_root = (($ProjectRoot -replace '\\', '/') + "/Renders/Fallbacks")
    }
    if ($AuthorMode -eq "BUILD") {
        $argsObject.confirm = "BUILD MRQFB"
        $argsObject.decided_by = $ApprovedBy
    }
    $env:MRQFB_ARGS_JSON = ($argsObject | ConvertTo-Json -Compress -Depth 6)
    $logPath = Join-Path $RunRoot ("mrq_{0}.log" -f $AuthorMode.ToLowerInvariant())
    $argv = @(
        $ProjectFile,
        "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
        ("-ExecutePythonScript={0}" -f $CmdRunner),
        "-Unattended", "-NoSplash", "-NullRHI", "-stdout", "-FullStdOutLogOutput",
        ("-AbsLog={0}" -f $logPath)
    )
    try {
        & $EditorCmd @argv
        $exitCode = $LASTEXITCODE
    } finally {
        Remove-Item Env:MRQFB_ARGS_JSON -ErrorAction SilentlyContinue
    }
    $marker = "MRQFB_{0}_OK|run={1}-{2}" -f $AuthorMode, $RunId, $Suffix
    $found = (Test-Path -LiteralPath $logPath) -and (Select-String -LiteralPath $logPath -SimpleMatch $marker -Quiet)
    if ($exitCode -ne 0 -or -not $found) {
        Stop-Film ("{0}_FAILED|exit={1}|marker={2}|log={3}" -f $AuthorMode, $exitCode, $found, $logPath)
    }
    Write-Output ("SATFILM_{0}_OK|run={1}|log={2}" -f $AuthorMode, $RunId, $logPath)
}

function Assert-DiskFromDry([string]$DryRun) {
    $dryPath = Join-Path $MrqRoot ("mrq_dry_{0}.json" -f $DryRun)
    if (-not (Test-Path -LiteralPath $dryPath)) { Stop-Film ("NO_DRY_RECORD|" + $dryPath) }
    $dry = Get-Content -Raw -Encoding UTF8 -LiteralPath $dryPath | ConvertFrom-Json
    $driveName = (Split-Path -Qualifier $FallbackRoot).TrimEnd(':')
    $freeGb = [math]::Round((Get-PSDrive $driveName).Free / 1GB, 1)
    $needGb = 5.0
    $estimates = @()
    $times = @()
    foreach ($tier in $Tiers) {
        $disk = [double]$dry.plan.totals.est_disk_gb.PSObject.Properties[$tier].Value
        $hours = @($dry.plan.totals.est_hours.PSObject.Properties[$tier].Value)
        $needGb += $disk * 1.3
        $estimates += ("{0}:{1}GB" -f $tier, $disk)
        $times += ("{0}:{1}h" -f $tier, ($hours -join "/"))
    }
    $gate = [math]::Round($needGb, 1)
    Write-Output ("SATFILM_DRY_ESTIMATE|run={0}|disk={1}|time_low_mid_high={2}|free={3}GB|gate={4}GB" -f $RunId, ($estimates -join ","), ($times -join ","), $freeGb, $gate)
    if ($freeGb -lt $gate) { Stop-Film ("FREE_DISK|{0}GB<{1}GB" -f $freeGb, $gate) }
}

$ProjectFile = Join-Path $ProjectRoot "PussStage.uproject"
$MrqRoot = Join-Path $ProjectRoot "Saved\CodexConductor\MRQ"
$JobsFile = Join-Path $MrqRoot "mrq_jobs_built.json"
$CmdRunner = Join-Path $MrqRoot "mrq_fallbacks_cmd.py"
$Driver = Join-Path $ProjectRoot "Tools\Fallbacks\saturday_film.py"
$EditorCmd = "D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$FallbackRoot = Join-Path $ProjectRoot "Renders\Fallbacks"
$RunRoot = Join-Path $FallbackRoot ("_Saturday\" + $RunId)
$BackupRoot = Join-Path $ProjectRoot ("Backups\PreSaturdayFilm-" + $RunId)
$BackupRecord = Join-Path $BackupRoot "prechange_record.json"
$Current = Join-Path $FallbackRoot "current.json"

if (($Tiers -contains "C") -and -not ($Tiers -contains "P")) {
    Stop-Film "C_REQUIRES_P (C reuses the P render's WAV)"
}

foreach ($path in @($ProjectFile, $CmdRunner, $Driver, $EditorCmd)) {
    if (-not (Test-Path -LiteralPath $path)) { Stop-Film ("MISSING|" + $path) }
}

if ($Mode -eq "REVERT") {
    if ($Confirm -ne "REVERT SATURDAY_FILM") { Stop-Film "CONFIRM (want 'REVERT SATURDAY_FILM')" }
    if (-not (Test-Path -LiteralPath $BackupRecord)) { Stop-Film ("NO_BACKUP_RECORD|" + $BackupRecord) }
    $record = Get-Content -Raw -Encoding UTF8 -LiteralPath $BackupRecord | ConvertFrom-Json
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    foreach ($item in $record.files) {
        $target = [string]$item.target
        if ([bool]$item.existed) {
            Copy-Item -LiteralPath ([string]$item.backup) -Destination $target -Force
        } elseif (Test-Path -LiteralPath $target) {
            Move-Item -LiteralPath $target -Destination ($target + ".reverted-" + $RunId + "-" + $stamp)
        }
    }
    Write-Output ("SATFILM_REVERT_OK|run={0}|record={1}|note=config_assets_and_renders_retained" -f $RunId, $BackupRecord)
    exit 0
}

Assert-MachineIdle
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
Write-Output "SATFILM_SKY_POLICY|saved Show/sequence state only; editor-only sky hiding is not applied to renders"

if ($Mode -eq "DRY") {
    Invoke-MrqAuthoring "DRY" "DRY"
    Assert-DiskFromDry "$RunId-DRY"
    Write-Output ("SATFILM_DRY_OK|run={0}|scenes=6|tiers={1}|live_master_ranges=true|run_root={2}" -f $RunId, ($Tiers -join ","), $RunRoot)
    exit 0
}

if ($Confirm -ne "APPLY SATURDAY_FILM") { Stop-Film "CONFIRM (want 'APPLY SATURDAY_FILM')" }
if (Test-Path -LiteralPath $BackupRoot) {
    if (-not (Test-Path -LiteralPath $BackupRecord)) { Stop-Film ("BACKUP_EXISTS_WITHOUT_RECORD|" + $BackupRoot) }
} else {
    New-Item -ItemType Directory -Path $BackupRoot | Out-Null
    $files = @()
    foreach ($target in @($Current, $JobsFile)) {
        $exists = Test-Path -LiteralPath $target
        $backup = Join-Path $BackupRoot ([IO.Path]::GetFileName($target))
        $sha = $null
        if ($exists) {
            Copy-Item -LiteralPath $target -Destination $backup
            $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        }
        $files += [ordered]@{ target = $target; existed = $exists; backup = $backup; sha256 = $sha }
    }
    [ordered]@{
        run_id = $RunId
        created_utc = (Get-Date).ToUniversalTime().ToString("o")
        mode = "APPLY"
        confirm = $Confirm
        files = $files
        retained_on_revert = @("/Game/ZZ_Render/MRQFallbacks/MRQC_FB_*", "Renders/Fallbacks/S* raw and encoded media")
    } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $BackupRecord
}
Write-Output ("SATFILM_BACKUP_OK|run={0}|record={1}" -f $RunId, $BackupRecord)

$checkpoint = Join-Path $RunRoot "checkpoint.json"
$builtForRun = $false
if ((Test-Path -LiteralPath $checkpoint) -and (Test-Path -LiteralPath $JobsFile)) {
    $built = Get-Content -Raw -Encoding UTF8 -LiteralPath $JobsFile | ConvertFrom-Json
    $builtForRun = ($built.run -eq "$RunId-BUILD")
}
if (-not $builtForRun) {
    Invoke-MrqAuthoring "DRY" "DRY"
    Assert-DiskFromDry "$RunId-DRY"
    Assert-MachineIdle
    Invoke-MrqAuthoring "BUILD" "BUILD"
}

if (-not (Test-Path -LiteralPath $JobsFile)) { Stop-Film ("BUILD_WROTE_NO_JOBS|" + $JobsFile) }
$jobs = Get-Content -Raw -Encoding UTF8 -LiteralPath $JobsFile | ConvertFrom-Json
$driveName = (Split-Path -Qualifier $FallbackRoot).TrimEnd(':')
$freeGb = [math]::Round((Get-PSDrive $driveName).Free / 1GB, 1)
$tierEstimates = @()
$needGb = 5.0
foreach ($tier in $Tiers) {
    $estimate = [math]::Round((($jobs.built | Where-Object { $_.tier -eq $tier -and -not $_.test } |
        Measure-Object -Property est_disk_gb -Sum).Sum), 1)
    $tierEstimates += ("{0}:{1}GB" -f $tier, $estimate)
    $needGb += $estimate * 1.3
}
Write-Output ("SATFILM_DISK_ESTIMATE|run={0}|tiers={1}|free={2}GB|gate={3}GB" -f $RunId, ($tierEstimates -join ","), $freeGb, [math]::Round($needGb, 1))
if ($freeGb -lt $needGb) { Stop-Film ("FREE_DISK|{0}GB<{1}GB" -f $freeGb, [math]::Round($needGb, 1)) }

$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { Stop-Film "PYTHON_NOT_FOUND" }
& $python $Driver --project $ProjectRoot --run-id $RunId --version $Version --tiers $Tiers --approved-by $ApprovedBy
$driverExit = $LASTEXITCODE
if ($driverExit -ne 0) {
    Write-Output ("SATFILM_APPLY_INCOMPLETE|run={0}|exit={1}|checkpoint={2}" -f $RunId, $driverExit, $checkpoint)
    exit $driverExit
}
Write-Output ("SATFILM_APPLY_OK|run={0}|checkpoint={1}" -f $RunId, $checkpoint)
