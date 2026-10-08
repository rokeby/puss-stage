# Conductor 5 log — 8 Oct 2026 (UTC)

## 00:00–01:50 — S3 timing to sound, lighting pass (Gary in the editor, then on a 15-min break)

All [measured] by success markers unless marked.
- Lattice glow 8→1 cd, uplights 4000→1000 (S3L-20261008-000149 / -000632). BUG found: the S3 float hold in
  LS_DevScene_03 holds lights by channel DEFAULT after 31 s, so rise-only edits reverted after the fold. s3_light_levels.py
  now writes the hold defaults too (fixed in S3L-20261008-003136).
- Opening (Gary): dark, rig folds, figures appear in the dark, ghost, then waves. S3OPEN-20261008-003115; Gary then moved
  the ghost to 7.6–8.1 s by hand; figures at Scene frame 100 (S3FIG-20261008-012750, rise 405→125 [inferred 1:1 nesting:
  the fold section is 32.375 s vs 31 s inner, play rate unreadable]); strike group OFF always (Gary: "don't like them"),
  rig practicals + lattice 0 all scene (S3L-20261008-003136, -012916).
- Editor crash ~00:18 during Gary's manual editing; restore list empty.
- Audio: Gary's "Shore_People_Stereo(1).wav" = sha-identical to DerivedAssets/.../f32/S03_Shore_People_Stereo_f32.wav;
  the 16-bit derivative (sha 46cc34c7…, 246.877 s) imported as SW_S3_Shore_People, track "Scene Score" in LS_DevScene_03
  from frame 0 (SCENEAUDIO-20261007-214457, local-time run id). scene_audio_import.py gained start_option scene_start
  and marker kind "given". Eight audio markers; old 'S3 1–7' deleted (S3MREPL-20261008-014526); VampStart/VampEnd kept
  (transport reads them).
- Closed Gary's open Sequencer tab on LS_DevScene_03 (census clean) so the tools could run (close_sequencer.py).
- Drama lights S3DRAMA-20261008-014904 (after a failed first APPLY, CUBIC enum → Don't-Save restart, record kept as
  .failed-…): Clam Key spot 400 cd 4200 K on the risen clam (ramps with Gary's rise keys 3593→4170), Pearl Glow pink
  point attached to the pearl (faint in the rise, 40 cd from 4290, out at 3:10 = 4560), 4 cool 6500 K wall-graze spots
  3000 cd (choir 3120→, 30 % after 3:10), wave lights ×2.5 / ×1.8 + a deterministic shimmer. Values are first guesses,
  NOT seen rendered.
- Both tests green after the writes (SavedMasterMatchesShow, SceneCutBindingsResolve singly).
- Grease red tint: subagent building an offline v2 master + swap (not run).
