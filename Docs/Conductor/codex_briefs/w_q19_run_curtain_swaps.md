# W&T brief Q19 (--unreal, conductor slot ~19:35 UTC, NO PIE): run the ragged curtain swaps — Opening (q17), then P02 and P03 end curtains (q18), then the verifiers
Read _house_rules.md. Rule 2 RELAXED: you may use the Unreal MCP via `python Saved/CodexMocap/mcp_request.py tools/call --params-file <req> --timeout 900`.
Rule 1 EXCEPTION: you run in the MAIN tree. You may write ONLY the args, records and request files under Saved/CodexSoftGoods/q17/ and q18/. No git.
HARD RULES:
- NO PIE (never start or end it).
- Never quit or restart the editor. Never Save All. No Blender.
- Klara levels must never be saved.
- Census (Saved/CodexFlatV3/curtain/census_probe.json → the last CI_CENSUS line must read content=[] maps=[] pie=False) before each write.
- Parse markers by run id. Stop on the first failure; no repairs. Keep it tight: Gary needs the editor right after.
Tools are already written and harness-green (read their docstrings and args first):
1. Saved/CodexSoftGoods/q17/ragged_opening_swap.py: DRY, check its report (template + 3 GC sections → GC_CurtainDrop_RaggedProscenium_P02Held; five transitions fingerprinted), then APPLY. Require the OK markers and the read-back.
2. Saved/CodexSoftGoods/q18/ragged_endcurtain_swap.py with --passage P02: DRY, then APPLY. Then the same for P03. MI override, offsets and transform must read back unchanged.
3. Verifiers: Saved/CodexFlatV3/q14/q14_verifiers_request.json, then read the two "Test Completed. Result={Success}" lines after its Q14_VERIFIERS_QUEUED marker. Census after.
Restore any args file you switched to APPLY back to DRY afterwards.
Final message: run ids and markers per step, read-backs, census before and after. Under 200 words.
