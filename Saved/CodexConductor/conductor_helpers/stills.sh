# usage: stills.sh <passage> <fractions-json> <label>
cd /e/PussStage
echo "{\"passage\": \"$1\", \"fractions\": $2, \"label\": \"$3\"}" > Saved/CodexConductor/passage_stills_args.json
python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/conductor_pie_begin_request.json >/dev/null 2>&1
for i in $(seq 1 30); do python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/census_print_request.json >/dev/null 2>&1; tail -30 Saved/Logs/PussStage.log | grep -q '"pie": true' && break; sleep 4; done
python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/passage_stills_request.json >/dev/null 2>&1
for i in $(seq 1 90); do grep -qE "PASSAGE_STILLS_(OK|FAILED)\|run=PSTILLS-$1-[0-9-]*-$3" Saved/Logs/PussStage.log && break; sleep 5; done
grep -E "PASSAGE_STILLS_(OK|FAILED)" Saved/Logs/PussStage.log | tail -1 | cut -c1-260
python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/conductor_pie_end_request.json >/dev/null 2>&1
for i in $(seq 1 20); do python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/census_print_request.json >/dev/null 2>&1; tail -30 Saved/Logs/PussStage.log | grep -q '"pie": false' && break; sleep 3; done
tail -30 Saved/Logs/PussStage.log | grep CENSUS_PRINT | tail -1 | cut -c1-200
