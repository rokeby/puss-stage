#!/usr/bin/env bash
# Screen-record the desktop for PIE run-throughs (Gary 10 Oct).
#   Scripts/screenrec.sh start [label]   # starts ffmpeg detached (desktop, 30 fps, NVENC H.264)
#   Scripts/screenrec.sh stop            # stops it, remuxes to MP4, copies to the shared drive
# Records locally first (the Google Drive mount is too slow to write live), as MPEG-TS so a hard stop still leaves a
# playable file. Started via PowerShell Start-Process: a bash '&' child dies with the tool call. System audio via Scripts/loopback_rec.py (WASAPI loopback, silence-padded).
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
    rm -f "$LOCAL/.stopaudio"
    PY="$(cygpath -w "$(command -v python)")"
    SCR="$(cygpath -w /e/PussStage/Scripts/loopback_rec.py)"
    AARGS="\"$SCR\" \"$W\\$name.wav\" \"$W\\.stopaudio\""
    powershell -NoProfile -Command "Start-Process -FilePath '$PY' -WindowStyle Hidden -RedirectStandardError '$W\\$name.audio.log' -ArgumentList '$AARGS'"
    sleep 2
    echo "recording -> $LOCAL/$name.ts" ;;
  stop)
    [ -f "$STATE" ] || { echo "not recording"; exit 1; }
    name="$(cat "$STATE")"
    rm -f "$LOCAL/.stopaudio.done"; touch "$LOCAL/.stopaudio"
    taskkill //IM ffmpeg.exe //F > /dev/null 2>&1 || true
    for i in $(seq 1 30); do [ -f "$LOCAL/.stopaudio.done" ] && break; sleep 0.5; done
    if [ -f "$LOCAL/.stopaudio.done" ] && [ -s "$LOCAL/$name.wav" ]; then
      ffmpeg -hide_banner -loglevel error -y -i "$LOCAL/$name.ts" -i "$LOCAL/$name.wav" -map 0:v -map 1:a -c:v copy \
        -c:a aac -b:a 192k -shortest -movflags +faststart "$LOCAL/$name.mp4" && rm -f "$LOCAL/$name.ts" "$LOCAL/$name.wav"
    else
      echo "WARNING: no audio (loopback recorder did not finish); saving video only" >&2
      ffmpeg -hide_banner -loglevel error -y -i "$LOCAL/$name.ts" -c copy -movflags +faststart "$LOCAL/$name.mp4" \
        && rm -f "$LOCAL/$name.ts"
    fi
    rm -f "$LOCAL/.stopaudio" "$LOCAL/.stopaudio.done"
    cp "$LOCAL/$name.mp4" "$DEST/" && echo "saved: $DEST/$name.mp4 ($(du -h "$LOCAL/$name.mp4" | cut -f1))"
    rm -f "$STATE" ;;
  *) echo "usage: $0 start [label] | stop" >&2; exit 2 ;;
esac
