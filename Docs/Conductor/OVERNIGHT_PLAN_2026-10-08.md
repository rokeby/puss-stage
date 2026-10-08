# Overnight plan, 8→9 Oct 2026 (Conductor 5)

Deadline: scene video fallbacks (S1–S6, 1080p25, separate WAV) by **Sun 11 Oct lunchtime**. Standing rules: the editor
sky stays hidden (editor_sky_toggle after any restart); one editor writer at a time; no Save All; tests after writes.

## Phase A: editor on (about 1.5 h, in this order)

| # | Step | Who | Gate |
|---|---|---|---|
| A1 | Pearl fade twin: BUILD_MAT Pearl_Fade / Pearl_Dither → MAT_CHECK → CLAM_PEARL_TWIN → still pair (v3 vs twin) | Finishing touches | look-jump stills to Gary in the morning |
| A2 | Pearl fade keys (s3_pearl_fade.py, fade 3:26–3:30) | Conductor | after A1 |
| A3 | Clam lid 80° → 55° (CLAMOPEN REVERT → APPLY) | Finishing touches | — |
| A4 | S1 animals pre-roll (C2): PROBE → DRY → APPLY → stills 560–640 | Finishing touches | — |
| A5 | S1 entry snap probe (C1), hands-off play across P01→S1 | Conductor | report only |
| A6 | Clam missing from Lumen reflections: mesh distance-field / material check (probe_sdf.py) | Conductor | report only |
| A7 | Both save tests | Conductor | must be green before Phase B |

## Phase B: editor closed, renders (the rest of the night)

| # | Step | Gate |
|---|---|---|
| B1 | MRQ: DRY + BUILD of the render queue (MRQ/mrq_fallbacks.py, plan MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md), now with Lumen HW RT and r.StaticMeshLODDistanceScale=0.25 | DRY clean |
| B2 | S5 10 s test, both tiers (PIE-match, cinematic 8 temporal samples) → timing per frame, file names, codec | Gary looks in the morning |
| B3 | If B2 is clean: PIE-match tier for all six Scenes, S3 straight through (vamp removed) | QC stills + WAV length check; PNGs deleted after QC (Gary) |
| B4 | Cinematic tier where time allows (S3 first) | — |

Blender must be closed during renders (memory: windowed Blender reached 29 GB). Renders run one at a time.

## Offline, in parallel all night (no editor)

| Package | How | Output for the morning |
|---|---|---|
| Figure fabric + MetaHuman look (S3-7 TONIGHT): ~1.8 m shroud pinned to the back of the head and the top of the back, looser but heavy, stained filthy-rag pattern; MetaHumans near-naked in loincloth-coloured underwear | Agent (Claude subagent, or Codex if Gary says so), worktree + offline harness | a plan with tiers, cloth parameter set, texture swatches, nothing applied |
| Vamp end → S3 end bug (C3) | Read InfinityStageTransportController vamp/release/go-hold paths, write a failing test | held C++ patch for the build window |
| Dunes ×2 (+ harvest Gary's painted wet patches) | Agent, headless Blender | set D field + gate + overview stills |
| Fixtures (parcans 3×, bulbs 2×, placement proposals; glimmer bulbs on cords) | Agent | per-passage proposal stills |

## Morning hand-back to Gary
Render test results and times; pearl twin look pair; S1 snap and animals reports; clam-reflection finding; fabric and
MetaHuman look proposals; vamp bug diagnosis.
- Morning note for P3 (dunes x2): Gary: '2x dune height probably means adjusting my wall-following camera' (B06 runs ~10 cm off the right wall at z 171-220). Report camera clearance for B06 and every S3 shot path against set D.
