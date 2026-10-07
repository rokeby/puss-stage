# Klara ingest copy (Gary 7 Oct: take hers for the 25 collisions; import S1, S2 (to see), S4; audio as she set it).
# RUN ONLY WITH THE EDITOR CLOSED. 1) snapshot ours  2) copy NEW + COLLIDES  3) verify SHA-256 of every copied file.
$ErrorActionPreference = "Stop"
$K = "C:\KlaraIngest\KK_Children_copy\Content"; $O = "E:\PussStage\Content"; $H = "E:\PussStage\Saved\CodexConductor\KlaraIngest"
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw "EDITOR_RUNNING" }
$stamp = Get-Date -Format "yyyyMMdd-HHmm"; $snap = "D:\PussStageBackups\PreKlaraIngest-$stamp"
foreach ($d in "KK_S1_Animals","KK_S2_Shrine") { robocopy "$O\$d" "$snap\Content\$d" /E /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null; if ($LASTEXITCODE -ge 8) { throw "SNAPSHOT_FAIL $d" } }
foreach ($r in Get-Content "$H\collides_list.txt") { $src = Join-Path $O $r; $dst = Join-Path "$snap\Collides" $r; New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null; Copy-Item $src $dst }
"snapshot=$snap"
$n = 0; $bad = @()
foreach ($r in Get-Content "$H\copy_list.txt") { if (-not $r) { continue }
  $src = Join-Path $K $r; $dst = Join-Path $O $r; New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item $src $dst -Force; if ((Get-FileHash $src).Hash -ne (Get-FileHash $dst).Hash) { $bad += $r }; $n++ }
"KLARA_COPY_DONE|files=$n|bad=$($bad.Count)|snapshot=$snap"; if ($bad) { $bad }
