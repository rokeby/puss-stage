# P11: Passage timing = music, plus musical analysis (final jobs 4.1, Gary 8 Oct)
Gary: "Each passage should just rely on its music for its timings ... tie everything to the music so we have a fixed and clear timing, as well as running the musical analysis so we can start playing with lights."
Measured Master music (Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md row 2.2), track vs section length:
- P01 73.5 s vs 96.3 s
- P02 45.5 s vs 47.5 s
- P03 40.2 s vs 42.2 s
- P04 48.4 s vs 50.4 s
- P05 42.0 s vs 186.4 s
- P06 110.6 s vs 126.0 s
The Opening has music too: find it (Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md).
Part A (offline, the main deliverable tonight): **musical analysis** of the Opening and of every Passage's music.
- Find the source audio (WAV/SoundWave sources under Content/ or the import tools' args).
- Produce Tools/MusicAnalysis/ with a script and DerivedAssets/MusicAnalysis/<segment>.json holding: duration, tempo/beat grid, onsets, RMS envelope at 25 fps, and SECTION boundaries. Gary calls the energetic bursts "flurries" or "waves": detect them (energy rises), number them, and give start/peak/end times.
- Also produce one PNG per segment: waveform + envelope + numbered flurries.
- The Opening matters most: Gary's cue list is "(1) second flurry/wave: curtain falls; (2) second flurry/wave: lights come on; (3) third flurry, end of opening: perspective adjustment".
- numpy/scipy only. If librosa is installed use it, otherwise implement onset strength yourself.
Part B: a **DRY-only planning tool** that reports, per Passage, how to make its Master section length = its music length. Rules:
- Passage keys are ABSOLUTE and pins travel but keys don't (read Docs/ and the memory notes in Docs/InfinityStageSessionHandover.md on rebuilds).
- List every keyed track that falls past the new end and every downstream section that moves.
- Write the APPLY path only as a design in the report. Never apply.
Deliver Docs/Conductor/P11_MUSIC_TIMING_2026-10-08.md.
