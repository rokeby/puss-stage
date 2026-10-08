# P20: S3 chorus "sway together" crowd section (Gary 8 Oct, own words)
Gary: arrange "some of the calmer sections together ... create a section where they sway together", placed in the
CHORUS: "we don't need the whole chorus time and we can replicate some sections too, I might bring more shore people in,
to create a semblance of swaying crowd for chorus". Sync choice: "Same tempo, to the music".
Inputs (all measured by the conductor 8 Oct, committed):
- DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json (CALM/MEDIUM/FRENZY per figure, source + Scene 3 times;
  play_rate 0.6; scene3_s = source_s/0.6 - 22/24).
- DerivedAssets/S3MocapIntensity/s3_sway_runs.json from Tools/Mocap/shore_sway_together.py: per CALM run, the dominant
  sway period + the signal it came from.
- The music (DerivedAssets/Audio/Scenes_20261006/S03_Shore_People_Stereo.wav): the chorus runs 2:08-3:07. Its strongest
  periodicity is a ~7.2 s phrase swell (envelope autocorrelation 0.64; 6.8-7.6 s across sub-windows); the beat is weak
  (~61 BPM, 0.09-0.24).
- Target sway period: 3.6 s scene time (2 sways per phrase). Arg; a refinement of the phrase phase from the WAV is
  welcome (find the phrase-swell maxima times in the window and report them).
Chosen calm source spans (args; defaults below, scene sway period in brackets):
- M56: 5.7-12.1 then 25.7-32.9, crossfaded (3.06/3.19);
- F52: 4.4-13.2 (2.85), looped;
- M59: 1.2-19.1 (4.03);
- F55: 71.7-89.5 (4.58);
- M53: 18.3-32.4 (3.47);
- F25: 78.2-91.5 (3.26).
Per-figure play rate = source_period / 3.6 (so 0.475-0.77 vs today's 0.6, i.e. 0.79x-1.28x); keep within 0.75x-1.3x of 0.6.
Window: default S3 shot B04, Scene 3 frames 3480-4200 @24 (2:25-2:55); args window_start/end. Loop each span with a 1 s
blend between repeats, and ease the section in/out over 1.5 s against what plays before/after (Sequencer skeletal
animation sections blend by weight when they overlap with ease in/out [verify in UE 5.8 headers:
MovieSceneSkeletalAnimationSection / FMovieSceneSkeletalAnimationParams: StartFrameOffset, PlayRate, bReverse, Weight;
cite]).
Where the figures' animation lives: they are nested via LS_Clams (Scene = LS_Clams - 22 frames; read
Saved/CodexConductor/s3_retime.py and probe_s3_* tools + Docs/Conductor/S3_AUDIO_BEATS_2026-10-08.md; the figures are
also teleported at LS_Clams 1461/1462). Find the exact sequence and binding for each figure's
MovieSceneSkeletalAnimationTrack by offline .uasset reads where possible, else make DRY discover them by label.
Build a DRY/APPLY/REVERT editor tool (house rules: record + Backups/Pre<Thing>-<run>, exact census = only the
sequence(s) touched, save only those, read back every section's range/offset/rate, success marker with run id). It
must:
1. split/trim the figure's existing animation section(s) around the window, never deleting outside it;
2. insert the looped calm sections at the computed rates;
3. **report each figure's sway phase at the window start** (from the curves) and offer an optional per-figure start
   nudge (<= half a period), so they do not all lean in lockstep (Gary chose "same tempo", not "in phase"): default
   spread phases evenly;
4. support N EXTRA crowd figures later (Gary may add shore people): duplicate-figure mode is a design section +
   argument stub only. Duplicating a MetaHuman with cloth costs a lot; estimate the performance cost, and list the
   cheaper options (e.g. distant duplicates without cloth sim).
Also: an offline preview PNG (per figure: sway signal over the window after the retime, with the 3.6 s grid and the
phrase maxima), plus a harness with -/+ controls.
Deliver Docs/Conductor/P20_CHORUS_SWAY_2026-10-08.md. Do NOT run Unreal (the PC's GPU is lost until a reboot).
