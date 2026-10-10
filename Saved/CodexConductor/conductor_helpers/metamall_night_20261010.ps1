# Metamall night run, 10 Oct 2026 (Gary approved): wait for Codex job 184 -> close the Puss editor (Don't-Save)
# -> UBT build of the Metamall proving project -> 3 h standalone soak (-game, janitor on, as on 10 Oct 03:56)
# -> soak report -> backup to the portable SSD (F:), excluding Saved and reconstructable folders.
# No AI involved. The status goes to $Log; each step is stamped.
$ErrorActionPreference = 'Continue'
$Proj    = 'E:\Metamall_UE58_Proving\Metamall260627LJH_UE58_Proving_20260923'
$UProj   = "$Proj\Metamall260627LJH.uproject"
$Engine  = 'D:\Unreal Engine\UE_5.8\Engine'
$Stamp   = Get-Date -Format 'yyyyMMdd_HHmm'
$Out     = "D:\Metamall_Backups\slot_logs\night_$Stamp"
$Log     = "$Out\night_status.log"
New-Item -ItemType Directory -Force $Out | Out-Null
function Say($m) { "$(Get-Date -Format 'HH:mm:ss') $m" | Tee-Object -FilePath $Log -Append }

Say "START night run; project=$Proj"

# 1. Wait for Codex job 184 to finish (max 4 h).
$deadline = (Get-Date).AddHours(4)
while ((Get-Date) -lt $deadline) {
    $j = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'codex.exe' -and $_.CommandLine -match 'Codex job 184' }
    if (-not $j) { break }
    Start-Sleep -Seconds 60
}
Say "STEP1 job 184 no longer running"
Start-Sleep -Seconds 30

# 2. Close the Puss editor without saving (the project's Don't-Save procedure).
Get-Process UnrealEditor -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 10
$prd = 'E:\PussStage\Saved\Autosaves\PackageRestoreData.json'
if (Test-Path $prd) { Rename-Item $prd "PackageRestoreData.json.old-$Stamp" }
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { Say "STOP an editor is still running; nothing else done"; exit 1 }
Say "STEP2 Puss editor closed (Don't-Save)"

# 3. UBT build of the Metamall editor modules.
$bl = "$Out\build.log"
& cmd /c "`"$Engine\Build\BatchFiles\Build.bat`" UnrealEditor Win64 Development -Project=`"$UProj`" -waitmutex -NoUBA > `"$bl`" 2>&1"
$buildCode = $LASTEXITCODE
Say "STEP3 build exit=$buildCode log=$bl"

# 4. Soak, 3 h, standalone game from the editor binaries (no package).
$gl = "$Out\game.log"
$gameArgs = "`"$UProj`" /Game/MAP/L_MainSim -game -windowed -ResX=1920 -ResY=1080 -log -abslog=`"$gl`" -ExecCmds=`"metamall.MemoryJanitor.Enabled 1`""
if ($buildCode -eq 0) {
    $p = Start-Process "$Engine\Binaries\Win64\UnrealEditor.exe" -ArgumentList $gameArgs -PassThru
    Say "STEP4 soak started pid=$($p.Id)"
    $end = (Get-Date).AddHours(3)
    while ((Get-Date) -lt $end -and -not $p.HasExited) { Start-Sleep -Seconds 60 }
    if ($p.HasExited) { Say "STEP4 soak EXITED EARLY code=$($p.ExitCode) (crash?)" } else { Stop-Process -Id $p.Id -Force; Say "STEP4 soak stopped after 3 h" }
    Start-Sleep -Seconds 10
    & python "$Proj\Plugins\MetamallNetworkBridge\Tools\soak\metamall_soak_report.py" $gl -o "$Out\report" *>> $Log
    Say "STEP5 soak report exit=$LASTEXITCODE (2 = a series is GROWING) dir=$Out\report"
} else {
    Say "STEP4 SKIPPED soak: build failed (see build.log)"
}

# 6. Backup to the SSD, excluding Saved and reconstructable folders at any depth.
$dst = "F:\Metamall_UE58_Proving_backup_$Stamp"
robocopy $Proj $dst /E /R:1 /W:1 /NP /XD Saved Intermediate DerivedDataCache Binaries node_modules .vs /LOG:"$Out\backup_robocopy.log" | Out-Null
$rc = $LASTEXITCODE
Say "STEP6 backup robocopy exit=$rc (0-7 = success) dst=$dst"
Say "DONE"
