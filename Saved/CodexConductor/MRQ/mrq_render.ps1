<#
mrq_render.ps1 - command-line Movie Render Queue render of ONE fallback job, editor CLOSED (7 Oct 2026, offline-written,
NOT RUN). Windows PowerShell 5.1.

  powershell -NoProfile -ExecutionPolicy Bypass -File E:\PussStage\Saved\CodexConductor\MRQ\mrq_render.ps1 -Job S5_P_v01_t10
  ... -Job S5_P_v01 -PreflightOnly      (checks + prints the command line, renders nothing)
  ... -Job S3_C_v01_k02 -MoveAside      (an existing non-empty frames folder is RENAMED to <dir>.prev-<ts>, never deleted)

Reads mrq_jobs_built.json (written by mrq_fallbacks.py BUILD). Refuses unless ALL hold:
  - no UnrealEditor.exe / UnrealEditor-Cmd.exe / blender.exe running (memory: the machine hard-crashed 7 Oct with the
    editor ~21 GB + Blender ~17 GB on 64 GB; a render runs ALONE);
  - free physical RAM >= -MinFreeRamGB (default 40) and free space on the output drive >= 1.3 x estimate + 5 GB;
  - the Master .uasset hash equals the one recorded at BUILD (the custom ranges are Master frames; a Master rebuild or
    a Scene relength can move them) unless -AcceptMasterChange;
  - the job's frames folder is empty or absent (or -MoveAside).
Watchdog: every 15 s logs free RAM and frames written to <take>\logs\<job>_watch.csv; if free RAM stays below
-KillBelowFreeGB (default 6) for two samples it kills ONLY the render process tree it started (MRQFB_WATCHDOG_KILL).
Success is ASSERTED from disk, not from the exit code: the frame count and contiguity equal the job's render range,
and the .wav exists when the job has one. Writes <take>\render_result_<job>_<ts>.json and a manifest of dependency
file hashes for the stale check (mrq_post.py stale). Final line: MRQFB_RENDER_OK|... or MRQFB_RENDER_FAILED|...
Never starts or touches the editor, PIE, the Show, the level or any asset.
#>
param(
    [Parameter(Mandatory = $true)][string]$Job,
    [string]$JobsFile = "E:\PussStage\Saved\CodexConductor\MRQ\mrq_jobs_built.json",
    [double]$MinFreeRamGB = 40,
    [double]$KillBelowFreeGB = 6,
    [switch]$MoveAside,
    [switch]$AcceptMasterChange,
    [switch]$PreflightOnly
)
$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"

function Fail([string]$why) {
    Write-Output ("MRQFB_RENDER_FAILED|job={0}|reason={1}" -f $Job, $why)
    exit 2
}
function FreeRamGB() {
    return [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2)
}
function Kill-Tree([int]$ProcId) {
    $kids = Get-CimInstance Win32_Process -Filter ("ParentProcessId={0}" -f $ProcId) -ErrorAction SilentlyContinue
    foreach ($k in $kids) { Kill-Tree ([int]$k.ProcessId) }
    try { Stop-Process -Id $ProcId -Force -ErrorAction Stop } catch {}
}

if (-not (Test-Path $JobsFile)) { Fail ("NO_JOBS_FILE|{0} (run mrq_fallbacks.py BUILD first)" -f $JobsFile) }
$rec = Get-Content -Raw -Encoding UTF8 $JobsFile | ConvertFrom-Json
$j = $rec.built | Where-Object { $_.name -eq $Job }
if ($null -eq $j) { Fail ("UNKNOWN_JOB|built={0}" -f (($rec.built | ForEach-Object { $_.name }) -join ",")) }

# --- preflight -------------------------------------------------------------------------------------------------------
$busy = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(UnrealEditor|UnrealEditor-Cmd|blender)$' }
if ($busy) { Fail ("PROCESSES_RUNNING|{0} (close them; a render runs alone)" -f (($busy | ForEach-Object { "{0}:{1}" -f $_.ProcessName, $_.Id }) -join ",")) }
$free = FreeRamGB
if ($free -lt $MinFreeRamGB) { Fail ("FREE_RAM|{0} GB < {1} GB" -f $free, $MinFreeRamGB) }
$outDir = $j.output_dir -replace '/', '\'
$take = Split-Path $outDir -Parent
$drive = (Split-Path $outDir -Qualifier).TrimEnd(':')
$freeDisk = [math]::Round((Get-PSDrive $drive).Free / 1GB, 1)
$needDisk = [math]::Round([double]$j.est_disk_gb * 1.3 + 5, 1)
if ($freeDisk -lt $needDisk) { Fail ("FREE_DISK|{0}: {1} GB < {2} GB" -f $drive, $freeDisk, $needDisk) }
$masterNow = (Get-FileHash -Algorithm SHA256 ($rec.master_uasset -replace '/', '\')).Hash.ToLower()
if ($masterNow -ne $rec.master_sha256 -and -not $AcceptMasterChange) {
    Fail ("MASTER_CHANGED_SINCE_BUILD|built={0}|now={1} (re-run DRY; BUILD a new version if the Scene ranges moved)" -f $rec.master_sha256.Substring(0, 12), $masterNow.Substring(0, 12))
}
if ((Test-Path $outDir) -and (Get-ChildItem $outDir -File -ErrorAction SilentlyContinue | Select-Object -First 1)) {
    if (-not $MoveAside) { Fail ("OUTPUT_NOT_EMPTY|{0} (use -MoveAside to rename it; nothing is deleted)" -f $outDir) }
    Rename-Item -Path $outDir -NewName ((Split-Path $outDir -Leaf) + ".prev-" + $ts)
}
$logDir = Join-Path $take "logs"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$argv = @($j.argv)
$exe = $argv[0]
$rest = ($argv[1..($argv.Count - 1)] | ForEach-Object { if ($_ -match ' ' -and $_ -notmatch '^-') { '"' + $_ + '"' } else { $_ } }) -join ' '
Write-Output ("MRQFB_PREFLIGHT_OK|job={0}|free_ram_gb={1}|free_disk_gb={2}|need_disk_gb={3}|render_frames={4}|est_hours={5}" -f $Job, $free, $freeDisk, $needDisk, $j.render_frames, (($j.est_hours) -join "/"))
Write-Output ("COMMAND: `"{0}`" {1}" -f $exe, $rest)

# dependency manifest (stale check input), hashed BEFORE the render starts
$depFiles = @($rec.deps_files.all) + @($rec.deps_files.($j.scene.ToString()))
$manifest = @()
foreach ($f in ($depFiles | Where-Object { $_ } | Sort-Object -Unique)) {
    $p = $f -replace '/', '\'
    if (Test-Path $p) {
        $it = Get-Item $p
        $manifest += [pscustomobject]@{ file = $f; size = $it.Length; mtime = $it.LastWriteTimeUtc.ToString("o"); sha256 = (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() }
    }
}
$manifestPath = Join-Path $take ("deps_manifest_{0}_{1}.json" -f $Job, $ts)
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $manifestPath
if ($PreflightOnly) { Write-Output ("MRQFB_PREFLIGHT_ONLY|job={0}|manifest={1}" -f $Job, $manifestPath); exit 0 }

# --- render ----------------------------------------------------------------------------------------------------------
$t0 = Get-Date
$proc = Start-Process -FilePath $exe -ArgumentList $rest -PassThru -WindowStyle Minimized
$watch = Join-Path $logDir ("{0}_watch_{1}.csv" -f $Job, $ts)
"utc,free_ram_gb,frames" | Set-Content -Encoding UTF8 $watch
$low = 0
$killed = $false
$maxHours = [double]$j.est_hours[2] * 2 + 1
while (-not $proc.HasExited) {
    Start-Sleep -Seconds 15
    $fr = FreeRamGB
    $n = (Get-ChildItem $outDir -Filter *.png -File -ErrorAction SilentlyContinue | Measure-Object).Count
    ("{0},{1},{2}" -f (Get-Date).ToUniversalTime().ToString("o"), $fr, $n) | Add-Content -Encoding UTF8 $watch
    if ($fr -lt $KillBelowFreeGB) { $low++ } else { $low = 0 }
    if ($low -ge 2) {
        Write-Output ("MRQFB_WATCHDOG_KILL|job={0}|free_ram_gb={1}|frames={2}" -f $Job, $fr, $n)
        Kill-Tree $proc.Id; $killed = $true; break
    }
    if (((Get-Date) - $t0).TotalHours -gt $maxHours) {
        Write-Output ("MRQFB_WATCHDOG_TIMEOUT|job={0}|hours={1}" -f $Job, $maxHours)
        Kill-Tree $proc.Id; $killed = $true; break
    }
}
$elapsed = ((Get-Date) - $t0).TotalSeconds

# --- assert from disk ------------------------------------------------------------------------------------------------
$a = [int]$j.render_range[0]; $b = [int]$j.render_range[1]
$want = $b - $a
$pngs = Get-ChildItem $outDir -Filter *.png -File -ErrorAction SilentlyContinue
$nums = @()
foreach ($p in $pngs) { if ($p.BaseName -match '\.(\d+)$') { $nums += [int]$Matches[1] } }
$nums = @($nums | Sort-Object -Unique)
$have = New-Object 'System.Collections.Generic.HashSet[int]'
foreach ($x in $nums) { [void]$have.Add($x) }
$missing = @()
for ($f = $a; $f -lt $b; $f++) { if (-not $have.Contains($f)) { $missing += $f; if ($missing.Count -ge 20) { break } } }
$extra = @($nums | Where-Object { $_ -lt $a -or $_ -ge $b })
$wav = @(Get-ChildItem $outDir -Filter *.wav -File -ErrorAction SilentlyContinue)
$okFrames = ($nums.Count -eq $want) -and ($missing.Count -eq 0) -and ($extra.Count -eq 0)
$okWav = (-not $j.wav) -or ($wav.Count -ge 1)
$result = [pscustomobject]@{
    job = $Job; started = $t0.ToString("o"); seconds = [math]::Round($elapsed, 1); exit_code = $(if ($killed) { $null } else { $proc.ExitCode });
    killed = $killed; frames_written = $nums.Count; frames_wanted = $want; first_missing = $missing; out_of_range = $extra.Count;
    wav = @($wav | ForEach-Object { $_.FullName }); s_per_frame = $(if ($nums.Count -gt 0) { [math]::Round($elapsed / $nums.Count, 3) } else { $null });
    manifest = $manifestPath; render_range = @($a, $b); keep_range = $j.keep_range; ok = ($okFrames -and $okWav -and -not $killed)
}
$resPath = Join-Path $take ("render_result_{0}_{1}.json" -f $Job, $ts)
$result | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $resPath
if ($result.ok) {
    Write-Output ("MRQFB_RENDER_OK|job={0}|frames={1}|seconds={2}|s_per_frame={3}|result={4}" -f $Job, $nums.Count, $result.seconds, $result.s_per_frame, $resPath)
    exit 0
}
Fail ("ASSERT|frames={0}/{1}|missing_first={2}|out_of_range={3}|wav={4}|killed={5}|result={6}" -f $nums.Count, $want, (($missing | Select-Object -First 5) -join ","), $extra.Count, $wav.Count, $killed, $resPath)
