# W&T brief Q17 (Codex job 76, OFFLINE --worktree): plan the ragged held curtain for the Opening plus a feasibility verdict for the P02/P03 end curtains
Read _house_rules.md. OFFLINE ONLY: no Unreal, no Blender, no GPU. The machine belongs to another stream until ~19:30 UTC. Read the main tree; write only inside your worktree.
Gary, 9 Oct ~16:45 UTC: the hold-pose ragged curtain (/Game/Scenes/Curtain/Baked/GC_CurtainDrop_RaggedProscenium_P02Held, imported by job 74, record Saved/CodexSoftGoods/q16/) "can be in the opening curtain, and yes replace the p2 end curtain, p3 end curtain ... Unless placing the image on the end curtains on a new curtain is hard or time consuming, in which case do not bother."

A. OPENING. Find exactly how the Opening curtain plays today:
   - which GC (import_passing_bake.py says GC_CurtainDrop_Opening is played by the Opening and all five transitions; verify);
   - which actor, sequence and tracks reference it, and how the release/timing is keyed (import_passing_bake.json plan.release_in_cache_s, Rig's p04 cross-stream contract in that docstring, and the curtain_sleight / Arrival tools under Saved/CodexConductor/).
   Grep the records and git log; cite file:line.
   Recommend the least-risk swap. Either (a) point ONLY the Opening's reference at the ragged GC, leaving the five transitions alone, or (b) something else, with reasons.
   Account for timing:
   - held cache range 450..1080 @30 fps; release at 480; lands at 665; held from 695;
   - the cache length vs the Opening's section length;
   - material slot: MI_CurtainVelvet_DeepRed_Drop.
   Write a DRY/APPLY/REVERT tool for that swap: field-scoped, backup, census, read-back, run-id markers, offline harness with +/- controls. Do NOT run it.
B. P02/P03 END CURTAINS, feasibility only:
   - Find the current end-curtain image path: Saved/CodexConductor/curtain_image.py + curtain_image_args.json, passage_end_drape.py, and their records, the end-curtain material/MI and how the picture maps (UV channel, projection, or world-aligned).
   - Determine the ragged GC's UVs from the bake source:
     - Saved/CodexSoftGoods/DropBake/ragged_prep/bake_curtain_drop_ragged.py;
     - Scripts/build_curtain_chaos_pattern.py with cut_rags: does the flat pattern carry a 0..1 UV over the full cloth, are rags cut out of that UV, and are there pleats in the UV;
     - the q16 import record (UV channels imported).
   - Verdict, one of:
     - CHEAP: the image maps via the existing MI/UVs with a param or MI swap, ≤ ~30 min editor;
     - MODERATE: a new MI or projection, no re-bake;
     - HARD: UV rework or re-bake.
     Give evidence per claim.
   - If CHEAP or MODERATE, sketch the steps and reuse the existing curtain_image tool if possible. If HARD, say "skip" and why.
Tag every claim (declaration-proven / measured / inferred) per house rules. Write the plan to Docs/WingsTextures/RAGGED_CURTAIN_PLAN_2026-10-09.md plus the tool(s) under Saved/CodexSoftGoods/q17/. Final message: the verdict for B, the recommended swap for A, the tool paths, the harness result. Under 300 words.
