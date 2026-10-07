#!/bin/bash
# usage: mcprun.sh <request.json under Saved/CodexConductor> <stop-regex> [show-regex]
cd /e/PussStage
free=$(powershell -c "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)")
echo "free_ram_gb=$free"
T=$(date -u +%Y.%m.%d-%H.%M.%S)
python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/purge_saved_module_cache_request.json >/dev/null 2>&1
python Saved/CodexMocap/mcp_request.py tools/call --params-file "Saved/CodexConductor/$1" >/dev/null 2>&1
until grep -a -E "$2|LogPython: Error" Saved/Logs/PussStage.log | awk -F'[][]' -v t="$T" '$2>t' | grep -q .; do sleep 3; done
sleep 2
grep -a -E "${3:-$2}|LogPython: Error" Saved/Logs/PussStage.log | awk -F'[][]' -v t="$T" '$2>t' | cut -c30-500 | tail -${4:-25}
