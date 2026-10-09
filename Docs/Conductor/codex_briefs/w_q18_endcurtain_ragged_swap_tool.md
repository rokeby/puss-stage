# W&T brief Q18 (Codex job 77, OFFLINE --worktree): P02/P03 end-curtain swap to the ragged held cache — the tool only, do not run it
Read _house_rules.md. OFFLINE ONLY: no Unreal, no Blender. Context: Docs/WingsTextures/RAGGED_CURTAIN_PLAN_2026-10-09.md (job 76, verdict CHEAP), and the sibling tool Saved/CodexSoftGoods/q17/ragged_opening_swap.py (+ test): reuse its patterns.
1. DEDUPE FIRST: can Saved/CodexConductor/passage_end_drape.py or curtain_image.py already retarget an existing end drape to a different GeometryCache, keeping the actor, its MI_CurtainImage_P02/P03 component override and its LS_S2/S3_HangarRise section timing? Cite file:line. If one can, with a config change only, write that config plus a harness check and stop there.
2. Otherwise write Saved/CodexSoftGoods/q18/ragged_endcurtain_swap.py (+ args, + test). For each of P02 (actor "P02 End Drape (stand-in)", LS_S2_HangarRise) and P03 ("P03 End Drape (stand-in)", LS_S3_HangarRise):
   - DRY reports the actor's current cache, its component material override(s), and the one GC section (asset, range, start offset) bound to that actor.
   - APPLY:
     - swaps ONLY the component's geometry_cache and that ONE section's cache asset to /Game/Scenes/Curtain/Baked/GC_CurtainDrop_RaggedProscenium_P02Held;
     - preserves the override MI, the image texture/planar scalars, the transform, the section range and the offset (assert unchanged by read-back);
     - keeps manual_tick/running/looping as recorded;
     - takes a backup and writes a run-id record BEFORE mutating;
     - requires a clean census before; the only dirty packages allowed are the level + that HangarRise sequence;
     - saves only those packages;
     - reads back after the save;
     - ends with an exact clean census.
   - REVERT is confirm-gated and field-scoped from the record.
   - Use --passage P02|P03 so each runs separately.
   - Traps:
     - never open or scrub the Master (it dirties the map);
     - compare GUIDs via conv_guid_to_string;
     - read enums by name (_enum_is pattern);
     - never save Klara levels;
     - NOOP ≠ success.
3. Harness with +/- controls:
   - wrong actor label;
   - two sections bound;
   - MI override lost;
   - offset changed;
   - foreign dirty package;
   - cache frame range mismatch.
   Run it.
Final message per house rules: the dedupe verdict, tool paths, harness result. Under 250 words.
