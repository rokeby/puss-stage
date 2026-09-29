#!/bin/sh
# Fresh backup of every folder holding a P04 rollout MI (from p04_backup_folders.json). Run right before the apply.
cd /e/PussStage
TS=$(date +%Y%m%d-%H%M%S); B="Backups/PreWingRolloutP04-$TS"
for d in $(python -c "import json; print(' '.join(json.load(open('Saved/CodexWingMateriality/p04_backup_folders.json'))['folders']))"); do
  mkdir -p "$B/$(dirname "$d")" && cp -a "$d" "$B/$(dirname "$d")/"
done
printf 'Pre-rollout snapshot of the P04 wing material folders, Wing materiality.\nLive undo: rollout_rollback_<stamp>.json from rollout_apply.py.\n' > "$B/README.txt"
echo "$B"; find "$B" -name '*.uasset' | wc -l
