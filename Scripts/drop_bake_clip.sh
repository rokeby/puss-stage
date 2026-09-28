#!/usr/bin/env bash
# Turn a drop-bake clip frame sequence into a real-time MP4 (30 fps / CLIP_STEP) with ffmpeg.
#   bash Scripts/drop_bake_clip.sh <DROP_ID> [step]
set -euo pipefail
ID="$1"; STEP="${2:-1}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/Saved/CodexSoftGoods/DropBake"
FFMPEG="$LOCALAPPDATA/Microsoft/WinGet/Links/ffmpeg.exe"
FPS=$(python -c "print(30/$STEP)")
for view in side 34; do
  "$FFMPEG" -y -loglevel error -framerate "$FPS" -i "$DIR/${ID}_clip_${view}/f%04d.png" \
    -vf "scale=1280:-2,format=yuv420p" -c:v libx264 -crf 20 -movflags +faststart "$DIR/${ID}_${view}.mp4"
  echo "$DIR/${ID}_${view}.mp4"
done
