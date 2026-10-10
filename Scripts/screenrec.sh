#!/usr/bin/env bash
# Screen-record the desktop for PIE run-throughs (Gary 10 Oct).
#   Scripts/screenrec.sh start [label]   # starts ffmpeg detached (desktop, 30 fps, NVENC H.264)
#   Scripts/screenrec.sh stop            # stops it, remuxes to MP4, copies to the shared drive
# Records locally first (the Google Drive mount is too slow to write live), as MPEG-TS so a hard stop still leaves a
# playable file. Started via PowerShell Start-Process: a bash '&' child dies with the tool call. No audio yet.
set -euo pipefail
LOCAL="/e/PussStage/Saved/Recordings"
DEST="/g/Shared drives/GZZ Studio Drive/Projects/2026. SHS 3 Evenings/ScreenRecordings"
STATE="$LOCAL/.current"
mkdir -p "$LOCAL"
case "${1:-}" in
  start)
    [ -f "$STATE" ] && { echo "already recording: $(cat "$STATE")"; exit 1; }
    name="PIE_$(date +%Y%m%d-%H%M%S)${2:+_$2}"
    echo "$name" > "$STATE"
    W="$(cygpath -w "$LOCAL")"
    ARGS="-hide_banner -loglevel error -f gdigrab -framerate 30 -draw_mouse 0 -i desktop -c:v h264_nvenc -preset p4 -cq 21 -pix_fmt yuv420p -f mpegts \"$W\\$name.ts\""
    powershell -NoProfile -Command "Start-Process -FilePath ffmpeg -WindowStyle Hidden -RedirectStandardError '$W\\$name.log' -ArgumentList '$ARGS'"
    sleep 2
    echo "recording -> $LOCAL/$name.ts" ;;
  stop)
    [ -f "$STATE" ] || { echo "not recording"; exit 1; }
    name="$(cat "$STATE")"
    taskkill //IM ffmpeg.exe //F > /dev/null 2>&1 || true
    sleep 2
    ffmpeg -hide_banner -loglevel error -y -i "$LOCAL/$name.ts" -c copy -movflags +faststart "$LOCAL/$name.mp4" \
      && rm -f "$LOCAL/$name.ts"
    cp "$LOCAL/$name.mp4" "$DEST/" && echo "saved: $DEST/$name.mp4 ($(du -h "$LOCAL/$name.mp4" | cut -f1))"
    rm -f "$STATE" ;;
  *) echo "usage: $0 start [label] | stop" >&2; exit 2 ;;
esac
