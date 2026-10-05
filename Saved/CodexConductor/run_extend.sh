#!/bin/bash
# usage: run_extend.sh <scene_n> <new_end_frame> <dry:true|false>
cd /e/PussStage
python - "$1" "$2" "$3" <<'PY'
import json,sys
n,end,dry=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]=="true"
json.dump({"scene_label":"Scene %d — External Sound"%n,"new_end_frame":end,"dry_run":dry,"run_id":"EXITBLOCK-S%d-%s"%(n,"DRY" if dry else "APPLY")},
          open("Saved/CodexSoftGoods/extend_scene_playback_mode.json","w",encoding="utf-8"),ensure_ascii=True)
PY
timeout 120 python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/purge_saved_module_cache_request.json >/dev/null 2>&1
timeout 1200 python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexSoftGoods/extend_scene_playback_request.json >/dev/null 2>&1
sleep 2
python -c "
import json;r=json.load(open('Saved/CodexSoftGoods/extend_scene_playback.json',encoding='utf-8'))
print('ok',r.get('ok'),'|',str(r.get('message') or r.get('result') or '')[:300]);print('carry',r.get('key_carry_failures'),'gate_info_n',len(r.get('key_gate_info') or []))"
