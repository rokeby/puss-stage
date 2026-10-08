# P21: S3 crowd structure: replicate to ~20, establishing sway, frenzy build, soothed choir sway (Gary 8 Oct)
Read Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md section 4.8 (Gary's words and choices) FIRST. This
supersedes the P20 window, but REUSE P20's planner (Tools/Mocap/chorus_sway_together.py, Saved/CodexConductor/s3_chorus_sway.py)
and the analysis inputs (E:/PussStage/DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json, s3_sway_runs.json;
P20 found only F25 and F55 sway rhythmically after retime, while M56/M53 drift slowly and F52/M59 are irregular: see
Docs/Conductor/P20_CHORUS_SWAY_2026-10-08.md and Docs/Conductor/Previews/P20_CHORUS_SWAY_preview.png). Read from the
main tree by absolute path where git-ignored.
Scene 3 = /Game/InfinityStage/Dev/Sequences/LS_DevScene_03, 24 fps; LS_Clams nested (Scene = LS_Clams - 22 frames);
figure teleports at LS_Clams 1461/1462. Existing shots + times: probe/apply tools s3_retime.py, s3_shots_fix.py,
s3_cuts_vamp.py and Docs/Conductor/S3_AUDIO_BEATS_2026-10-08.md. Gary says "there are 5 figures now" (the analysis has
six takes, Shore01-06): DRY must report which figure actors exist and are visible in S3.
Build (DRY/APPLY/REVERT editor tools per house rules; one record and revert for the whole structure, or one per step
in a fixed order with its own reverts):
1. **Crowd duplication** to N (default 20), all live cloth (Gary: fine if it runs OK).
   - Duplicate the figure actors with their sack/cloth components and bindings, as new possessables (or spawnables;
     justify) in the sequence that animates the figures.
   - Never edit Klara's levels. Name them "S3 Crowd NN (from ShoreXX)" and tag them.
   - Placement on the shore: a loose crowd, deterministic seed (single draw per expression), avoid the clam/millstone
     area and the camera paths; positions are args.
   - Placement preview PNG (top-down with cameras).
2. **Act 1 establishing sway** (~0:15-0:23; frames 360-552 default, args).
   - Each crowd member plays a CALM sway span: prefer the rhythmic spans (F25, F55); others' spans may be reused, and
     the same figure's spans may be cut up and set side by side.
   - Retimed to the shared 3.6 s period, phases rippling across the crowd.
   - Plus an additive actor-transform sway (roll about the feet, default ±2.5°, period 3.6 s, phase-wave across the
     crowd; additive section like s3_handheld.py, blend type ADDITIVE) for coherence.
3. **Frenzy build** 552 → 1080 (0:23-0:45).
   - Crossfade per member from calm through MEDIUM into FRENZY spans (segments JSON), with staggered onsets so it
     spreads through the crowd.
   - Frenzy continues under the clam rise and the early cello.
4. **Soothing to choir sway** from ~1:30 (frame 2160) through the chorus to ~3:07 (4488).
   - Frenzy → medium → calm sway over ~10-15 s, then the shared-period sway plus the transform sway.
   - After 3:07, hand back to the existing crying/whimpering behaviour; report what is there.
5. **Shots**:
   - (a) a new establishing CineCamera (wide, sees most of the crowd) over 360-552, replacing whatever plays there
     (report it);
   - (b) 2-3 new choir close-up cameras (3-4 figures in frame "singing", 35-50 mm) placed in the cello/chorus where
     they don't break the B07 orbit Gary likes; propose times;
   - (c) the handprint wall shot B06 (3000-3480) trimmed to ~8 s (3000-3192), with the freed time given to a choir
     close-up.
   - Camera cut tracks must cover playback; nested shot cuts outrank root (memory notes in Docs).
6. **Performance gate**: a PIE bench script the conductor runs. It reads dt median/p90/max and counts "GPU timeout" log
   lines over the establishing and choir windows, and refuses an APPLY of 20 if the 5-figure baseline isn't measured
   first (record both).
Preview PNGs: the crowd timeline (per member: class over time, sway grid) + the shot plan over the S3 audio beats.
Harness with -/+ controls. Do NOT run Unreal. Deliver Docs/Conductor/P21_S3_CROWD_2026-10-08.md with the run order.
