# P22 — S2 Shrine rotated hook-in

**measured** — Offline delivery, 8 October 2026. No Unreal, MCP, PIE, Blender, package save, or Content write was performed in this worktree.

## What is built

- **declaration-proven** — S2 is isolated from the applied S1/S4 sequence record: its args name `klara_hookin_seq_record_S2.json`, target `LS_DevScene_02`, Klara source `LS_NEW_SHRINE`, and `rekey_rotation: true` (`Saved/CodexConductor/KlaraIngest/klara_hookin_s2_args.json:137-160`). The existing `/Game/Scenes/LS_Shrine` subsection remains in `LS_DevScene_02` but is set inactive; the copy is added on a separate reversible track (`klara_hookin.py:1544-1565`, `:1723-1726`). The protected `klara_hookin_seq_record.json` is not modified.
- **declaration-proven** — Absolute top-level transform sections now use one rigid transform: XY values and unweighted cubic tangents rotate, XYZ translates, and Rotation.Z gains the level yaw with canonical Euler samples unwrapped first (`Saved/CodexConductor/KlaraIngest/klara_hookin.py:301-390`). Child/attached bindings and additive/relative sections are left unchanged and logged (`klara_hookin.py:399-403`, `:1144-1193`, `:1595-1670`). Curves with mismatched XY time/interpolation/extrapolation or weighted tangents refuse rather than approximate (`klara_hookin.py:335-355`).
- **declaration-proven** — Sequence duplication preserves the camera-cut binding IDs and component focus settings; every absolute camera/focus-target transform binding is visited by the same re-key loop. DRY enumerates every camera cut, reports its transformed position/yaw/lens/frustum and maps it to an S2 scene frame (`klara_hookin.py:1196-1257`). **inferred** — the duplicated live cut/focus bindings will resolve after APPLY; only Unreal read-back and stills can prove that.
- **declaration-proven** — DRY writes a separate `klara_hookin_s2_dry.json` and `klara_hookin_s2_topdown.png`. The PNG plots hangar walls, all four footprint corners, and each resolved cut-camera frustum (`klara_hookin_s2_args.json:8-13`; `klara_hookin.py:1260-1343`, `:1346-1418`). Frustum length 12 m, fallback HFOV 50 degrees, and 1400 px are review-only args; they do not affect APPLY.
- **declaration-proven** — the level-visibility section is VISIBLE only over S2's planned window and uses RESTORE_STATE. APPLY read-back requires the exact level name and frame range (`klara_hookin.py:1738-1766`). Outside S2, including P02, the streaming level remains hidden because APPLY_STREAM authored `initially_visible=False` (`klara_hookin.py:1449`) and no other segment owns this VISIBLE section. **inferred** — segment-wide runtime hiding remains pending PIE verification.
- **declaration-proven** — APPLY_SEQ backs up `LS_DevScene_02`, creates an exclusive record before mutation, admits only the Scene sequence plus the new copy in the dirty census, saves only those packages, reloads state, and emits `KLARAHOOK_APPLY_SEQ_OK` (`klara_hookin.py:1706-1788`). Klara's level and source sequence are never saved.

## Placement and accepted exception

- **measured** — the applied streaming record places Japanese Alley at `(13828.1567, 78182.3453, -790)` cm, yaw `316.427481` degrees; its 3390 x 2556 cm footprint misses the 100 cm wall-clearance target by 378 cm per side (`Saved/CodexConductor/KlaraIngest/klara_hookin_stream_record.json:13-55`, `:148-178`).
- **measured** — offline pure planning reproduces four hangar-local floor corners `(1805,-1278)`, `(5195,-1278)`, `(5195,1278)`, `(1805,1278)` cm against walls `y=-1000/+1000`. Physical wall penetration is therefore **2.78 m right and 2.78 m left**; the accepted 3.78 m figure includes the requested 1 m clearance margin. The explicit budget is 400 cm (`klara_hookin_s2_args.json:7-13`; `klara_hookin.py:404-421`, `:531-555`).
- **measured** — height is 1220 cm above her ground against a 1200 cm lattice: 20 cm taller. It remains below the 3000 cm roof and is a warning, not a refusal (`klara_hookin_stream_record.json:169-178`).
- **binary-proven** — read-only SHA-256 checks found `LS_NEW_SHRINE.uasset` (589447 bytes, `C0AE...AF36`), `Japanese_Alley.umap` (1388276 bytes, `1CEC...B8E`), and `Shrine_Stereo__3_.uasset` (12963328 bytes, `E329...2D49`) under `E:/PussStage/Content`. The sequence bytes contain two CineCameraActor names, CameraCutTrack, transform tracks, and the Shrine audio reference. **inferred** — binary strings do not prove resolved cuts or rendered framing.

## Offline harness

- **measured** — `python Saved/CodexConductor/KlaraIngest/test_klara_hookin_offline.py` returned `KLARAHOOK_HARNESS|run=34|failures=0|errors=0`. Positive controls cover rigid values/tangents, between-key Hermite evaluation, Euler wrap, accepted overhang, retained/deactivated old S2 declarations, and PNG output. Negative controls cover translation-only mismatch, XY time mismatch, weighted tangents, a 377.9 cm rejection, and additive/relative classification (`test_klara_hookin_offline.py:218-311`, `:339-373`; `klara_hookin_s2_harness_results.json:1-25`).

## Conductor runbook

1. **DRY** — keep `mode="DRY"`, set a unique `run_id`, leave `confirm` empty, then execute `CodexConductor/KlaraIngest/klara_hookin_s2_run.py`. Require `KLARAHOOK_DRY_OK`, `apply_ready=1`, zero dirty packages, the 378 cm accepted warning, the 1220/1200 warning, no unresolved camera rows, and inspect `klara_hookin_s2_topdown.png`. **measured pending** — this live DRY was forbidden in the offline brief.
2. **APPLY_SEQ** — change only `mode` to `APPLY_SEQ`, `confirm` to `APPLY_SEQ KLARAHOOK`, and use a fresh run id. Do not run APPLY_STREAM: the stream record already contains Japanese Alley. Require backup `Backups/PreKlaraHookin-Seq-<run>`, isolated record `klara_hookin_seq_record_S2.json`, exact dirty census, post-save read-back, and `KLARAHOOK_APPLY_SEQ_OK`. Never save Klara's level.
3. **Tests/read-back** — rerun the 34-test offline harness. Run the printed `extend_scene_playback` DRY then confirmed APPLY for S2, and independently read back the nested copy, muted stand-in narration, exact Level Visibility range/name, RESTORE_STATE, clean census, and camera-cut bindings. **measured pending** — saved Unreal state is not claimed here.
4. **Stills** — start PIE only after the editor is clean. Feed the unique `camera_preview["2"][].scene_fraction` values from the DRY report to `scene_stills_args.json` with `passage: "S2"`, run `scene_stills_run.py`, and inspect every cut still for wall cuts, framing, lighting, and P02/other-segment leakage. **rendered pending** — Gary's visual acceptance is still required.

## Open questions

- **inferred** — if DRY finds weighted/misaligned XY curves, the safe decision is whether to use a translation-only placement or author a dedicated bake; this tool deliberately refuses approximation.
- **inferred** — the 2.78 m physical side penetration is approved geometrically by the 400 cm budget, but the camera-frustum PNG and rendered cut stills decide whether the box illusion survives.
