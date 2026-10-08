# P21b: re-plan the S3 crowd against Gary's answers and the LIVE shot layout (8 Oct evening)
Base: P21 (Docs/Conductor/P21_S3_CROWD_2026-10-08.md; Tools/Mocap/s3_crowd_structure.py planner;
Saved/CodexConductor/s3_crowd_structure.py editor tool, which the conductor already FIXED for UE 5.8 (commit 75456ea):
- play_rate is a MovieSceneTimeWarpVariant: use to_fixed_play_rate()/set_fixed_play_rate();
- UE 5.8 Python has NO section easing, so crossfades key the section's own "Weight_0" channel (DISPLAY rate);
- the bench reads S3 time from the show transport (Master frame - 'Scene 3' segment start)/1000.
Keep those fixes; read the current files first.
Gary's answers (Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md, sections 4.8 + "4.8 refinements"):
1. **20 figures TOTAL**: the 5 present (Shore01_M56, Shore02_F52, Shore03_M59, Shore04_F55, Shore06_F25; Shore05_M53 no
   longer exists) + **15 copies**.
2. **Two or three clusters**, each swaying together (not a thin scatter).
   - Cluster centres on the shore, clear of the clam, the millstone and the camera paths.
   - Each cluster is 5-8 figures, ~0.8-1.5 m apart, loosely in rows, facing the sea/clam.
   - The phase ripple runs within a cluster; clusters are offset by about a quarter period. Deterministic seed.
3. **Establishing crowd shot ~0:15-0:23** (Scene frames 360-552), cutting into the START of B03. Live LS_Clams cuts
   (DRY S3_CROWD_CUTS, 8 Oct; Scene = LS_Clams - 22 frames):
   - "Scene 3 — External Sound — Entry Handoff Camera" 0-505;
   - B03 420-860, B02 856-1733, B07 1540-2828, B06 2820-4548, B08 4538-4858, next 4856-5951.
   B03 then starts at the end of the establishing shot. The establishing camera frames all clusters (35 mm wide).
4. Frenzy 0:23-0:45; soothing from ~1:30 (frame 2160) into the choir sway (unchanged from P21).
5. **Chorus structure**: when the chorus starts (~2:08, frame 3072), FIRST choir close-ups and/or wides that link the
   singing and the swaying (2-3 shots: 50 mm close-ups of 3-4 figures "singing" + one wide of a cluster), THEN the
   handprint wall B06 for **15 s, ENDING on its current final glint**. Keep B06's tail (the last 15 s of the current
   B06 section, i.e. its content up to its current end frame) and give the time before it to the choir shots. Then B08
   as now.
6. Update the preview PNGs (placement with clusters + cameras; shot plan over the audio beats) and the harness (-/+
   controls: count = 20, clusters 2-3, B06 length 15 s ending at the original end frame, cut coverage with no gaps).
Do NOT run Unreal. Deliver Docs/Conductor/P21B_S3_CROWD_REPLAN_2026-10-08.md with the run order and anything the DRY
must confirm live.
