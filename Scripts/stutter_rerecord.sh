#!/usr/bin/env bash
# Like-for-like stutter re-record (29 Sep): power plan read-back, 450 wall-clock frames (PIE off), a 12 s CSV capture,
# then the thread split. Usage: bash Scripts/stutter_rerecord.sh <tag>. Editor-only; nothing is saved; only ONE MCP
# call is active per phase and the waits are local file checks, so MCP stays idle while frames are collected.
set -u
cd "$(dirname "$0")/.."
TAG="${1:-rerecord}"
R=Saved/CodexSoftGoods
echo "power plan: $(powershell -NoProfile -Command 'powercfg /getactivescheme' | tr -d '\r')"
echo "{\"tag\": \"$TAG\", \"frames\": 451}" > $R/editor_frames_mode.json
rm -f "$R/cloth_gate_frames_$TAG.json"
python Saved/CodexMocap/mcp_request.py --timeout 45 tools/call --params-file $R/editor_frames_request.json >/dev/null 2>&1
end=$((SECONDS+180)); until [ -f "$R/cloth_gate_frames_$TAG.json" ] || [ $SECONDS -ge $end ]; do sleep 1; done
python -c "import json;d=json.load(open('$R/cloth_gate_frames_$TAG.json'));print('frames:',{k:d[k] for k in ('frames','seconds','mean_ms','median_ms','p95_ms','max_ms','over_40ms','slate_allow_throttling')});print('gaps:',d['spike_gaps_s'][:20])"
echo '{"mode": "csv_start"}' > $R/editor_trace_mode.json
python Saved/CodexMocap/mcp_request.py --timeout 45 tools/call --params-file $R/editor_trace_request.json >/dev/null 2>&1
sleep 12
echo '{"mode": "csv_stop"}' > $R/editor_trace_mode.json
python Saved/CodexMocap/mcp_request.py --timeout 45 tools/call --params-file $R/editor_trace_request.json >/dev/null 2>&1
sleep 4
python Scripts/analyse_csv_profile.py
