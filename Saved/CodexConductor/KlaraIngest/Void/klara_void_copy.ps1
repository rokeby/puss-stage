# Klara Void copy (Gary 7 Oct: "import void"). Editor CLOSED. NEW files only (census: 0 collisions). Verify SHA-256.
$ErrorActionPreference = "Stop"
$K = "C:\KlaraIngest\KK_Children_copy\Content"; $O = "E:\PussStage\Content"; $H = "E:\PussStage\Saved\CodexConductor\KlaraIngest\Void"
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw "EDITOR_RUNNING" }
$n = 0; $bad = @(); $skipped = @()
foreach ($r in Get-Content "$H\copy_list.txt") { if (-not $r) { continue }
  $src = Join-Path $K $r; $dst = Join-Path $O $r
  if (Test-Path $dst) { $skipped += $r; continue }
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item $src $dst; if ((Get-FileHash $src).Hash -ne (Get-FileHash $dst).Hash) { $bad += $r }; $n++ }
"KLARA_VOID_COPY_DONE|files=$n|bad=$($bad.Count)|skipped_existing=$($skipped.Count)"
