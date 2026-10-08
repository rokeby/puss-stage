# P19: recover the production curtain bake from its stream (no re-sim)
The production unfurl bake `unfurl_sleight_b1hop10_p02` (launcher Saved/CodexSoftGoods/run_prod_unfurl.ps1; script
E:\PussStage\.claude\worktrees\agent-a40d86303acede5de\Scripts\bake_curtain_drop.py) ran 03:24-08:09 EDT 8 Oct.
Blender then CRASHED (EXCEPTION_ACCESS_VIOLATION at 0x0, "No OpenGL vendor detected"; C:\Users\Administrator\AppData\Local\Temp\blender.crash.txt).
The machine's GPU was lost at ~05:12 EDT (nvidia-smi "GPU is lost"); a reboot is pending.
Measured by the conductor:
- Saved/CodexSoftGoods/DropBake/unfurl_sleight_b1hop10_p02_stream.f32 holds ALL 390 frames: frame-major xyz float32, world space (bake_curtain_drop.py:930-955), 45430 vertices; every frame is non-zero and changing.
- `_stream.json` holds the vertex count + faces.
- The final `<id>.json` report and `<id>.abc` were NOT written: the crash was at/after the Alembic export, bake_curtain_drop.py:1088-1093.
- The log reaches CURTAIN_DROP_FRAME|360/390.
Job:
1. Read bake_curtain_drop.py to reproduce EXACTLY what its Alembic export would have written:
   - object name, transform, UVs (if the cloth mesh has UVs, the stream doesn't: find where they come from and how to rebuild them deterministically from the same source mesh/pleat generator);
   - frame range ABC_START (launcher CLIP_START=210, but line ~977 may move it: reconstruct the logic from the log and the args) to FRAMES;
   - fps and scale.
2. Write Tools/CurtainBake/stream_to_abc.py: a headless Blender (`blender -b --factory-startup`) script that builds the mesh from the stream (+ UVs), keys the per-frame vertex positions (mesh cache / shape keys, whichever matches the original export settings) and exports `<id>.abc`. It also writes a reconstructed `<id>.json` report marked "reconstructed_from_stream" with the fields the import chain needs. Read memory doc Docs/ and Saved/CodexSoftGoods/DropBake/*.json of a previous COMPLETED bake (e.g. unfurl_sleight_b1hop10_p01 or the s18-s20 ones) to match the schema; the artifact chain is cache → <cache>_<bake_id>.abc → DropBake/<bake_id>.json.
3. Offline harness: a small synthetic stream round-trip (vertices in == vertices read back from the exported ABC via Blender, or via a pure-python check of the frame data you key before export). DO NOT run Blender now (the GPU is lost and the PC needs a reboot): make the script runnable later and give the exact command.
Deliver Docs/Conductor/P19_CURTAIN_STREAM_TO_ABC_2026-10-08.md.
