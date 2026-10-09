# W&T brief Q16 (Codex job 74, --unreal, conductor slot, NO PIE): import ragged_proscenium_p02_held as a GeometryCache (Gary sanctioned the import 9 Oct, without seeing a render)
Read _house_rules.md. Rule 2 RELAXED: you may use the Unreal MCP via `python Saved/CodexMocap/mcp_request.py tools/call --params-file <req> --timeout 900`.
Rule 1 EXCEPTION: you run in the MAIN tree. You may write ONLY:
- Saved/CodexSoftGoods/import_passing_bake* files (mode file, the record),
- Saved/CodexSoftGoods/DropBake/acceptance.json (one added entry, see 1),
- new files under Saved/CodexSoftGoods/q16/.
No git.
HARD RULES:
- NO PIE (never start or end it). No GPU-heavy work.
- Never quit or restart the editor. Never Save All. No Blender.
- Klara levels must never be saved.
- Census (Saved/CodexFlatV3/curtain/census_probe.json → the last CI_CENSUS line must read content=[] maps=[] pie=False) before and after.
- Parse markers by run id. Stop on the first failure; no repairs.
- Mind the bulk-import memory: one cache per call.
SOURCE: Saved/CodexSoftGoods/DropBake/ragged_proscenium_p02_held.abc. Its record is ragged_proscenium_p02_held.json, and its Blender read-back is ragged_prep/Q13_BLENDER_EXPORT.json (error 0 at frames 450/665/695/1080). It was made from ragged_proscenium_p02 (record ragged_proscenium_p02.json: release_frame 480, ABC_START 450, 30 fps). The cloth lands at frame 665 and holds frame 700's pose from 695 on.
TOOL: Saved/CodexSoftGoods/import_passing_bake.py (read its docstring). Do NOT fork it unless you must.
1. Acceptance gate: the tool refuses unless DropBake/acceptance.json marks the bake ALL=true.
   - This bake never ran the overnight acceptance, so add ONE entry for bake_id ragged_proscenium_p02_held, flagged `"sanctioned_by": "Gary 9 Oct (import without a render)", "ALL": true`.
   - Include the Q13 gates (floor and colliders PASS, post-blend speed 0, read-back 0) as evidence fields.
   - Back up acceptance.json first.
   - If the tool needs record fields that the held record lacks (checkpoint extents for the axis check, release frame), derive them from ragged_proscenium_p02_held_stream.f32 + _stream.json (hang frame = release−1 = 479, last frame 1080; Blender m → UE cm: X = 100y, Y = 100x, Z = 100z). Write them into a q16/ sidecar the tool can read, or into the mode file. NEVER edit the p02 record.
2. Mode: {"bake_id": "ragged_proscenium_p02_held", "gc_name": "GC_CurtainDrop_RaggedProscenium_P02Held", "sm_prefix": "SM_CurtainRaggedP02Held", "mi_name": "MI_CurtainVelvet_DeepRed_Drop", "place": null}.
   - These are new assets, so replace nothing.
   - Run DRY first (dry_run true), then the real import.
   - The axis check must pass.
   - Require PUSS_SOFTGOODS_BAKE_IMPORT_SUCCESS by run id.
   - Do NOT place an actor, and do NOT hook it into any sequence or sleight: hook-up is a separate decision.
3. Read back:
   - asset exists;
   - sample count / frame range (631 frames, 30 fps);
   - bounds at the hang and the last frame vs the stream extents (tolerance as the tool's TOL_CM).
4. Census after the run.
Final message: run ids, markers, asset paths, read-back numbers, census before and after. Under 250 words.
