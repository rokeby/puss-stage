# P11 music timing and musical analysis — 8 Oct 2026

## Outcome

- **[measured]** Seven offline analyses were generated: Opening plus P01–P06. Each JSON contains source provenance, duration, tempo candidates, beat grid, onsets, a 25 fps RMS envelope, suggested sections, and three strongest separated energy rises (“flurries”); each PNG overlays waveform, envelope, and numbered flurries. The bundle records `runId=P11-20261008-R2`, zero Unreal packages saved, and `cueScoreMutated=false` (`DerivedAssets/MusicAnalysis/manifest.json:3`, `:55-58`).
- **[declaration-proven]** The tool refuses writes under `E:/PussStage`; analysis APPLY is limited to derived files, while Passage timing is DRY-only (`Tools/MusicAnalysis/p11_music_timing.py:310`, `:346-397`, `:452-458`).
- **[measured]** The offline harness passed **21/21**, including positive signal/PNG/APPLY-REVERT/planning controls and negative manifest, path, gap, and missing-music controls (`Tools/MusicAnalysis/test_p11_music_timing.py:51-98`).
- **[inferred]** The musical labels and flurry selection are proposals for Gary, not ground truth. The tunable defaults select at most the three strongest rises separated by six seconds; no lighting cue has been authored or applied (`Tools/MusicAnalysis/p11_music_timing.py:83-119`, `:471-475`).

## Analysis results

**[measured]** Times below are start / peak / end seconds from the selected music interval. Tempo is the highest numerical candidate; P06 has no stable candidate.

| Segment | Analysed duration | Top tempo | Suggested flurries |
|---|---:|---:|---|
| **[measured]** Opening | 95.504 s | 129.199 BPM | #1 35.08 / 37.44 / 40.96; #2 54.88 / 57.36 / 60.88; #3 69.84 / 70.44 / 73.96 (`DerivedAssets/MusicAnalysis/Opening.json:4`, `:15`, `:6554-6577`) |
| **[measured]** P01 | 73.516 s | 67.070 BPM | #1 2.68 / 2.96 / 6.48; #2 7.52 / 10.00 / 13.52; #3 43.04 / 45.52 / 46.44 (`DerivedAssets/MusicAnalysis/P01.json:4`, `:13`, `:5006`) |
| **[measured]** P02 | 45.514 s | 99.370 BPM | #1 2.76 / 3.12 / 6.64; #2 13.56 / 13.92 / 16.72; #3 19.52 / 19.96 / 23.48 (`DerivedAssets/MusicAnalysis/P02.json:4`, `:13`, `:3324`) |
| **[measured]** P03 | 40.218 s | 68.034 BPM | #1 9.68 / 12.16 / 13.12; #2 21.20 / 21.72 / 23.84; #3 37.68 / 38.40 / 39.16 (`DerivedAssets/MusicAnalysis/P03.json:4`, `:13`, `:2814`) |
| **[measured]** P04 | 48.398 s | 59.618 BPM | #1 17.04 / 19.52 / 23.04; #2 27.12 / 29.60 / 30.64; #3 34.88 / 37.36 / 38.44 (`DerivedAssets/MusicAnalysis/P04.json:4`, `:13`, `:3148`) |
| **[measured]** P05 | 42.022 s | 67.127 BPM | #1 4.68 / 5.24 / 5.64; #2 21.44 / 22.12 / 23.64; #3 32.16 / 34.64 / 35.36 (`DerivedAssets/MusicAnalysis/P05.json:4`, `:13`, `:2930`) |
| **[measured]** P06 | 110.561 s | none | #1 36.64 / 37.20 / 40.72; #2 43.08 / 43.56 / 47.08; #3 85.16 / 85.80 / 86.36 (`DerivedAssets/MusicAnalysis/P06.json:4`, `:13`, `:6448`) |

### Opening cue reading

- **[measured]** The strongest selected Opening rises peak at 37.44, 57.36, and 70.44 s; the third ends at 73.96 s (`DerivedAssets/MusicAnalysis/Opening.json:6554-6577`).
- **[inferred]** Gary’s duplicated “second flurry” instruction maps both curtain fall and lights-on to the 54.88–60.88 s wave unless one of those ordinal labels is a typo. This needs his choice; the tool does not invent an ordering.
- **[measured]** After flurry #3, the analysis still finds a releasing tail through 95.341 s, so “third flurry, end of opening” means the final major gesture, not literal audio EOF (`DerivedAssets/MusicAnalysis/Opening.json:6545-6549`).

## DRY Passage relength plan

**[declaration-proven]** Targets are the selected music duration rounded up to the next 25 fps display frame. Passage keys are absolute; managed downstream sections move on rebuild, but keys do not scale within the resized Passage (`Saved/CodexConductor/passage_retime_to_music.py:26-45`).

| Passage | Saved length | Music-locked target | Delta |
|---|---:|---:|---:|
| **[measured]** P01 | 96.336 s | 73.520 s | −22.816 s |
| **[measured]** P02 | 47.520 s | 45.520 s | −2.000 s |
| **[measured]** P03 | 42.240 s | 40.240 s | −2.000 s |
| **[measured]** P04 | 50.400 s | 48.400 s | −2.000 s |
| **[measured]** P05 | 186.364 s | 42.040 s | −144.324 s |
| **[measured]** P06 | 126.001 s | 110.600 s | −15.401 s |

- **[measured]** Total Master shrink: **188.541 s**; new predicted end: tick 42,530,880 (29:32.120 at 24,000 ticks/s). This is offline arithmetic over the latest saved read-back snapshot, not a fresh Unreal read-back (`Tools/MusicAnalysis/p11_timing_snapshot.json:4-10`, `Tools/MusicAnalysis/p11_music_timing.py:414-450`).
- **[measured]** Every moved section, in order: P01 end −22.816; S1 −22.816; I1 −22.816; P02 start/end −22.816/−24.816; S2 −24.816; I2 −24.816; P03 −24.816/−26.816; S3 −26.816; I3 −26.816; P04 −26.816/−28.816; S4 −28.816; I4 −28.816; P05 −28.816/−173.140; S5 −173.140; I5 −173.140; P06 −173.140/−188.541; S6 −188.541; Closing −188.541.
- **[measured]** One proved keyed-track hazard falls past its new end: P05 `Camera.HeightOffsetCm`, keys at ticks 35,426,872 and 35,462,872; the proposed old-coordinate end is 31,999,105 (`Tools/MusicAnalysis/p11_timing_snapshot.json:51`).
- **[inferred]** Nested Choreo coverage is **UNCLEAR** offline: the saved snapshot proves Master Passage-channel keys, not every nested key/section. A future live DRY must enumerate Choreo keys, sections and GO markers before any APPLY (`Tools/MusicAnalysis/p11_timing_snapshot.json:7-10`).

## APPLY path — design only, never run tonight

1. **[declaration-proven]** Run a fresh live DRY from a clean editor and resolve P05’s late height keys plus any newly found Choreo/artist content. Do not use the existing retime tool unchanged: it enforces a one-second fade tail, conflicting with exact `Passage length = music` (`Saved/CodexConductor/passage_retime_to_music.py:64-81`).
2. **[inferred]** After Gary chooses the fade/crossing policy, scale LeadIn, all intervals, and Tail to the exact display-frame target; never scale absolute keys silently.
3. **[declaration-proven]** Back up Show and Master, require exact clean/dirty censuses, rebuild once, prove downstream movement and relative key carry, save only Show and Master, reload/read back, then emit a run-id success marker. Never Save All.

## Commands

```powershell
python -X utf8 Tools/MusicAnalysis/test_p11_music_timing.py
python -X utf8 Tools/MusicAnalysis/p11_music_timing.py analysis --mode DRY --confirm "DRY MUSIC ANALYSIS" --run-id REVIEW
python -X utf8 Tools/MusicAnalysis/p11_music_timing.py plan --mode DRY --confirm "DRY TIMING PLAN"
```

## Open questions for Gary

1. **[inferred]** Which “second flurry” action comes first: curtain fall or lights-on?
2. **[inferred]** Does P06 intentionally stop at the measured 110.561 s interval, leaving the WAV’s 14.439 s source tail unused (`Tools/MusicAnalysis/p11_sources.json:49-54`)?
3. **[inferred]** Should P05’s height-offset return keys be deleted, moved to the new ending, or proportionally retimed?
4. **[inferred]** Does exact music authority remove the old fade/crossing tail, or should the fade live inside the music interval?
