#!/bin/bash
cd /e/PussStage; ok=1
for r in census_probe run_saved_master_test run_scene_cut_test; do T=$(date -u +%Y.%m.%d-%H.%M.%S); python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/${r}_request.json > /dev/null 2>&1; until grep -a "Test Completed. Result=\|CENSUS_PROBE" Saved/Logs/PussStage.log | awk -F'[][]' -v t="$T" '$2>t' | grep -q .; do sleep 3; done; l=$(grep -a "Test Completed. Result=\|CENSUS_PROBE" Saved/Logs/PussStage.log | awk -F'[][]' -v t="$T" '$2>t' | tail -1); echo "$l" | cut -c60-200; echo "$l" | grep -q "Fail\|\"maps\": \[\"" && ok=0; done
[ $ok = 1 ] && echo TESTS_GREEN || echo TESTS_RED
