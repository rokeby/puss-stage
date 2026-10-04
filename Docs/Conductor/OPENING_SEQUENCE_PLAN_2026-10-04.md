# The long Opening — plan and build (4 Oct 2026, offline)

**Status: planned and built offline. NOTHING has run in Unreal.** Tool, timing table and harness are
in `Saved/CodexConductor/`. The harness passes 55/55 (`test_opening_sequence_output.txt`). Every
live step is listed in §9.

Tiers (AGENTS.md): **[decl]** = declaration-proven (a header, source, config or file we can read);
**[meas]** = measured (an intervention was run and read back; for this doc that is usually a
probe from 2 Oct or earlier, or this harness run offline); **[inf]** = inferred, with the reason.
Each claim carries its own tag.

## 1. The ask

Gary, 4 Oct ~01:00 (verbatim): *"Also plan and build for a longer opening curtain sequence. Actually
the entire length of current p01 track is for opening curtain before p01 even begins. Needs lighting
to flicker and activate to musical intensities, fit to length (with unactivated mode before) and
start mode in unlit curtain, lights flickering on as music begins, lights swivelling into place,
before curtain falls and we move in as track goes into final quarter or so after last swell. Not
sure how kind of thing this is currently build but would be necessary to be able to manually tune
it"*.

Context: `Docs/Conductor/DECISIONS_FOR_GARY_2026-09-30.md:47` says P01 carrying the opening-curtain
music is wrong **[decl]**. Run-through, 3 Oct: *"the opening should move in with the lights dark"*,
with P01's lights then pinging on (`Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:14-15`) **[decl]**.

## 2. What exists today

| Fact | Tier | Where |
| --- | --- | --- |
| The Opening is the Show cue "Opening — Curtain". It is a **Sequence** cue with OpeningReveal, playing `LS_Opening_Curtain_Baked`, [0,375] at 25 fps = 15 s, with one camera cut 0–375 on "Opening — Stalls Camera" | [meas] | `Saved/CodexCameraPilot/probe_interaction_cut_binding.json` (row "Opening — Curtain"); `Saved/CodexConductor/opening_walkin_probe.json` |
| The curtain drop is GeometryCache `GC_CurtainDrop_Opening`, bake `final13_opening_a06_w188`. Three sections: HOLD [0,49) is a one-tick window at offset 23200; FALL [49,299) runs from 23200; PILE [299,375) is a one-tick window at 263999. Release 1.993 s, landed 6.327 s | [meas] | `opening_walkin_probe.json` "curtain"; `Saved/CodexSoftGoods/opening_hold_at_release_final13.json` "after"; rule at `opening_hold_at_release.py:6-12` |
| The walk-in has 376 per-frame keys, starts 8.90 s, ends 15.0 s, uses ease 1.0 s and 250 cm/s, focal 15→25 mm (run WALKIN-OPENING-APPLY-20261002-A) | [meas] | `Saved/CodexCameraPilot/walkin_OPENING_record.json` |
| Walk-in planner: from rest it accelerates over `ease_s`, then holds `v_end`, ending exactly at `end_s` | [decl] | `Saved/CodexCameraPilot/walkin_plan.py:34-90` |
| P01 starts at Master 15.0 s, section [15.0, 111.336]. Its wing score (3 keys) sits at 15.0 / 18.36 / 29.52 s | [meas] | `opening_walkin_probe.json` "p01"; `Saved/CodexConductor/p01_score_shift_report.json` |
| **Patch K is built.** Rebuild calls `MoveSection` before `SetRange`, and `PassageKeysFollowSection` passed on 2 Oct | [decl] source; [meas] test | `Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:299-307`; `Saved/Logs/SS-FullInfinityStage-20261002.log:2776` |
| A Sequence cue can carry music. The Master builder gives every enabled non-Wing cue whose `Scene.Music` is Start/Crossfade its rail over that segment | [decl] | `InfinityStageSequenceBuilderLibrary.cpp:430-477` (mode test 441-442, range 476); struct `InfinityStageTypes.h:816-817` |
| Passages carry music the same way (`PassageSettings.Music`) | [decl] | `InfinityStageSequenceBuilderLibrary.cpp:383-422`; `InfinityStageTypes.h:997` |
| `FitMode` (MusicLocked…) is **not read by any compile code** (searched all `.cpp` outside tests; only Resize, Interchange and the Cue Desk write it). So removing P01's music should not change P01's length | [decl] search; [inf] that length has no other music dependency | grep `FitMode` over `Plugins/InfinityStage/Source` |
| **Existing Opening lights:** two Show "house warmer" spots, `P01 Wing 001 House L/R`, at (−2100, ±650, 1265), aim pitch −19.8 / yaw ±21.9, 33°/20°, 1740 cd, 2800 K, **steady**. Plus 18 floats behind the curtain line. The lip floats were held for the portal build | [decl] plan, [meas] verify on 28 Sep | `Saved/CodexStructure/p01_warmer_plan.json:32,60`; `Docs/OpeningLight_2026-09-27.md:235-250` |
| An editor edit to a Show-generated light **writes back into the Show** (any non-interactive property change on a lamp attached to a PassageActor) | [decl] | `Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageEditorModule.cpp:292-350` |
| Light Drama strike is driven by **camera route distance, never time**. Slow moves follow ShowSeconds | [decl] | `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageLightDrama.h:20-30`; `InfinityStagePassageActor.cpp:1625` |
| `extend_scene_playback.py` supports Sequence cues, but its KEY GATE refuses when any later Passage has a varying channel. P01's wing score varies, so it **would refuse the Opening** | [decl] | `Saved/CodexSoftGoods/extend_scene_playback.py:27-33, 306-312` |
| Marked-frame scripting exists in 5.8 (Get/Add/Set/Delete/Sort, display-rate or tick units) | [decl] | `D:\Unreal Engine\UE_5.8\…\SequencerScripting\Public\ExtensionLibraries\MovieSceneSequenceExtensions.h:531-603` |

**Nothing today does time-driven, music-driven light in a Sequence cue** [decl]. Searched: Light
Drama (distance-driven), the managed Passage section (no light channel, per
`Docs/Conductor/LIGHTING_TALK_PREP_2026-10-03.md` §3), and the Opening's own tracks (drape, cut,
walk-in only). So the rig below is new.

## 3. The phase table (defaults, from the music analysis)

The source is `Saved/InfinityStage/MusicAnalysis/P01_Intro_WalkingMusic_1.analysis.json`: 96.336 s,
major changes at 5.48 / 12.17 / 22.99 / 69.29 / 74.86 / 81.13 / 92.97 s, and sections
"quiet 0–23, building 23–81, quiet 81–96" **[decl]**. Swells are peaks of the smoothed (3 s)
`intensity` curve with prominence ≥ 0.12. That gives 2.8, 10.2, 22.4, 44.0, **56.8 (climax)**,
**67.5**, 73.6 and 84.8 s **[meas, offline]**. Every time snaps to the 25 fps frame grid.

| # | Phase | From → to (s) | Rule (tunable in `opening_timing.json`) |
| --- | --- | --- | --- |
| 0 | **Unactivated**: curtain unlit, every rig lamp at 0 | 0 → **1.52** | `music_start` = first waveform bin ≥ 10% of peak RMS |
| 1 | **Flicker on**: lamps stutter on, staggered 0 / 0.36 / 0.72 s, then sit at an idle 35% | **1.52 → 4.00** | `flicker_start` = music_start; `flicker_end` = +2.5 s |
| 2 | **Swivel**: FOH L/R move from a parked aim (12° high, 18° outward) to the warmer aim | **5.48 → 12.16** | the first two major changes after the flicker |
| 3 | **Music envelope**: intensity follows the music (FOH 1144–1990 cd, wash 592–1030 cd) | **12.16 → 85.76** | env = 50% smoothed `intensity` + 50% smoothed RMS (2.5 s, 2 passes); scale = 0.55 + 0.70·min(1, gain·0.85·env) × nominal |
| — | Last swell | **67.52** | the last swell with level ≥ 0.40 (56.8 is the climax) |
| — | Final quarter starts | 72.25 | 0.75 × track |
| 4a | **Curtain release** | **74.87** | the first major change ≥ max(last swell + 1 s, final quarter); lands within ½ frame of the 74.86 change |
| 4b | Curtain landed | 79.21 | release + 130/30 s (bake frames 480→610, unchanged) |
| 4c | **Walk-in (move in)**, rig fading to dark | **85.76 → 96.36** | `walkin_start` = end − walk duration (ease 10 s, so 10.6 s); starts on the last small swell (84.8) |
| — | **Opening end = new P01 start** | **96.36** (frame 2409) | the track rounded up to a frame |

The Master grows by **81.36 s** **[meas, offline planner]**. All of this is a first proposal to tune
by eye. "or so after last swell" is read as: the release follows the last *big* swell (67.5) and
lands inside the final quarter. If Gary meant the late small swell (84.8), set `last_swell` to 84.8
and move `curtain_release` / `walkin_start` (§5). The walk must then be ≤ 11.2 s and start after
the landing **[decl, validator]**.

## 4. The rig: what swivels, and how it is authored

**Fixtures (defaults in the JSON):**
- **FOH L / FOH R**: "moving heads" at the house warmers' exact positions. They flicker on in a
  parked aim, then swivel to the warmers' approved aim and level (1740 cd = scale 1.0).
- **Wash C**: a soft centre wash on the cloth from (−2600, 0, 900). It is new and its level is a
  first guess **[inf]**.
- **Foot 1/2** (lip footlights): designed, but **disabled**, because the lip floats are held for the
  portal build (`Docs/OpeningLight_2026-09-27.md` "Held for the portal build") **[decl]**.

**Authored as level SpotLight actors** ("Opening Rig - <name>", tag `InfinityStage.OpeningRig`,
level intensity 0, parked aim). They are bound as **possessables** in `LS_Opening_Curtain_Baked`:
the actor binding carries the swivel transform track, and a component child binding carries an
`Intensity` float track. Reasons:
1. They are **not Show attachments**. A Sequencer/editor edit of a Show lamp writes back into the
   Show (`InfinityStageEditorModule.cpp:292-350`) **[decl]**, and P01's materialize destroys and
   respawns attachment actors, which would break bindings (`p01_hallway_pingon.py:27-35`) **[decl]**.
2. Actor + component-child possessable is the write pattern already **measured** by the 2 Oct
   walk-in on this same sequence (CineCameraComponent child binding) **[meas]**. The light
   `Intensity` track is the pattern the hangar rises use (`hangar_light_keys_probe.json`) **[meas]**.
3. Outside the Opening, Sequencer restores their pre-animated state, so they are at 0
   everywhere else **[inf]**: this rests on the default restore-state completion and has not been
   checked in PIE.

**Phase 0 is not dark until the Show warmers are dealt with.** The two House spots burn steadily
through the Opening today **[decl]**. The tool disables them (Show write + P01 materialize + level
save) **only** when `house_warmers.disable` is true and `decided_by` is set. Until then the rig adds
to the warmers. The rig fades to dark during the walk-in (`walkin.end_light_level` 0.0), which
matches "move in with the lights dark" and P01's ping-on **[decl note; creative default]**.

## 5. Manual tuning: both ways, and which wins

- **JSON**: edit `Saved/CodexConductor/opening_timing.json` (moments in seconds or `"auto"`, plus
  rules, envelope gain/floor/peak/headroom/smoothing, flicker seed/idle, fixtures, ease), then run
  DRY, then APPLY.
- **Sequencer**: every moment is a marked frame `OPN <name>` on `LS_Opening_Curtain_Baked`. Drag
  one, save the sequence, re-run.
- **Precedence** (`opening_sequence_plan.py: reconcile_moments`), against the frames recorded at
  the last APPLY:
  - Marker moved, JSON not: **the marker wins** and is written back to the JSON with
    `"source": "sequencer"`.
  - JSON moved, marker not: the JSON wins.
  - Both moved to different frames: **refused**, naming the moment.
  - Marker deleted: recreated from the JSON.
  - Derived markers (`final_quarter`, `curtain_landed`, `swell_NN`) are informational and are put
    back if moved.
- Dragging `curtain_release` moves the GC FALL by exactly the same frames **[meas, harness]**.
  Dragging `walkin_start` re-solves the ease (allowed 5.6–11.2 s for 14 m at 2.5 m/s) and keeps
  the end on P01's start **[meas, harness]**.
- **Hand-edited keys** (rig intensity or the walk-in edited in Sequencer): the tool hashes every
  track it owns at APPLY. If a hash changed, it **refuses** until the binding name is added to
  `hand_tuned_tracks` (keep it, left untouched) or `overwrite_hand_edits` is set. The swivel is two
  AUTO keys (start/end), so a hand nudge is easy.

## 6. Curtain and camera re-timed (bake unchanged)

- GC sections follow the `opening_hold_at_release.py` rule exactly, moved so the release lands at
  `curtain_release`:
  - HOLD [0, F) is a one-tick window at offset 23200.
  - FALL [F, F+250) starts at offset 23200.
  - PILE [F+250, end) is a one-tick window at 263999.
  - F = round((release − 1/30) × 25) = **1871**.
  - Control: the same function with today's release and end reproduces the live 30 Sep sections
    exactly **[meas, harness vs `opening_hold_at_release_final13.json`]**.
- The drape's spawn section and any other section ending at the old end are extended, and listed
  in the report **[inf]**: which sections exist is read live.
- The walk-in uses Look & camera's planner unchanged, ends at frame 2409 on P01's measured start
  pose, and passes `check_plan` (arrival speed, no pile crossing before landing).
  - Control: the planner with today's inputs reproduces the 376 live keys **[meas, harness]**.
  - Keys are compressed to frame 0 plus the moving block: 267 instead of 2410. Evaluation is
    identical under LINEAR **[inf, standard linear interpolation]**.

## 7. Music: P01 loses its track

The tool moves P01's rail onto the Opening cue's `Scene.Music` (mode Start, same offset). P01's
binding becomes **Silence**, keeping its rail guid so a revert is exact. It does this once only: P01
music Gary assigns later is never moved. **P01 will be 96.3 s of silence until Gary picks its
music.** P01's length should not change (FitMode is not read by the compiler [decl search]; [inf]
otherwise). Before the music moves, the DRY run reports both bindings live **[inf until DRY]**.

A pre-roll of silence before the music would put the music section later than the segment start.
The builder always starts the rail at the segment start (`SequenceBuilderLibrary.cpp:475-476`)
**[decl]**, so a pre-roll needs a builder change or a sequence-local audio track. Today the
unactivated hold is 0–1.52 s, plus whatever the operator holds at frame 0 **[inf]**.

## 8. Downstream: the Master grows by 81.36 s

| System | Effect | Tier |
| --- | --- | --- |
| Segments after the Opening | shift +81.36 s. The tool asserts every later segment moved by exactly Δ, using the extend tool's own `segment_deltas`, before any save | [decl] |
| Passage keys (P01 wing score, P02–P06 constants) | carried by patch K. The tool **measures** carry for this Show: every Passage section's keys, section-relative, must be identical before/after the rebuild, or nothing is saved. P01's score lands at 96.36 / 99.72 / 110.88 s | K built: [meas] test; carry on the real Show: [inf] until APPLY |
| P01 wing score timing vs music | P01 no longer has the music its score was shaped to | [inf] |
| Scene handoff cameras / cut coverage | Passages do not move in space, so the handoffs are unchanged. The Opening's single cut is extended and coverage is gated | [inf] / [decl gate] |
| S1–S6 hangar timing | keys live in each `LS_S<n>_HangarRise` (`atf_hangar_timing_apply.py:29-31`), relative to the Scene: unaffected | [decl] path; [inf] relative evaluation |
| P01 hallway ping-on draft (`p01_hallway_pingon.py`, unapplied) | it keys artist Intensity tracks on the Master at absolute frames from the compiled P01 at run time. **Run it AFTER this change**: if it were applied before, the rebuild would not move artist tracks and it would sit 81 s early. Its "bay one during the Opening walk-in" (`:27`) now means 85.8–96.4 s | [decl] |
| Light Drama slow moves | phase follows ShowSeconds, so every slow sweep shifts phase by 81.36 s (cosmetic) | [decl] `InfinityStagePassageActor.cpp:1625` |
| `walkin_transitions.json` OPENING row (Look & camera's file) | `minimum_end_frame` 375 / `landed_s` 6.33 become stale. **Not edited here** (another stream's file). Re-running their keyer would rebuild a 15 s-style walk at the new end: use this tool's REVERT/APPLY instead | [decl] |
| Benches, captures and stills with hard-coded Master seconds | every time after 15 s moves by +81.36 s | [inf]: not enumerated |
| Run time | +81.36 s | [decl] |

## 9. Tool, order of live steps, saves

`Saved/CodexConductor/opening_sequence_apply.py` is driven by `opening_sequence_{dry,apply,revert}_run.py`
and `…_request.json` (ExecuteProjectPythonFile). It loads the extend tool's helpers by exec,
without editing that file. In DRY it reports the plan, the live facts, which marker API resolved
and the music bindings, and writes nothing. APPLY/REVERT:
- Guards: no PIE (never ends it), the right world, 0 dirty, no ZZ_ actors.
- Backups first: Show, Master, the sequence and the umap go to `Backups/PreOpeningSequence-<ts>`,
  with an fsync'd intent record.
- Live re-derivation: the bake chain, P01's start pose and speed. It refuses on > 1 unit drift
  from the table.
- Mutate, then rebuild the Master (library call).
- Pre-save asserts: the compiled Opening ends at the new end, the segment deltas, the key carry,
  cut coverage, and only the expected packages dirty.
- Save the named packages only.
- Asserted read-back, then `PUSS_OPENING_APPLIED_OK|run=…`. The record
  `opening_sequence_record.json` keeps the first-apply snapshot for an exact REVERT.

**Live order (needs the editor):**
1. DRY. Read `opening_sequence_report_dry.json`. Check the marker API, the drift, the tail
   sections and the music bindings.
2. APPLY.
3. `run_saved_master_test_request.json`, **alone**: read SavedMasterMatchesShow in the log.
4. `run_scene_cut_test_request.json`, **alone**: read SceneCutBindingsResolve.
5. PIE play-through from the Opening with the dog prone, measuring:
   - the rig dark before 1.5 s;
   - the flicker;
   - the swivel landing on the curtain;
   - the release at 74.9 s;
   - the walk-in arriving at P01;
   - no lighting pop at the crossing.
6. Capture/tune levels by eye.

If APPLY stops after a mutation, nothing was saved: **Don't-Save restart**. Never reload the level.

## 10. Offline harness (55/55)

`python -X utf8 Saved/CodexConductor/test_opening_sequence.py` (output saved next to it). Each rule
has a negative control that must be caught:
- **The envelope follows the analysis.** r ≥ 0.98 against the smoothed curves; the lamp keys follow
  it at r ≥ 0.999. Caught: a 30 s-shifted analysis (r < 0.5), gain 0. Headroom and clipping are held.
- **Unlit before the music.** Caught: music_start 0.
- **Flicker before swivel.** Caught: a swivel inside the flicker. The flicker is deterministic
  (hash, not draw order); a different seed changes it.
- **Release after the last swell and inside the final quarter.** Caught: a release at 60 s, and an
  explicit later last swell.
- **The bake is unchanged.** The **measured** 30 Sep sections are reproduced.
- **The walk-in ends exactly at the new P01 start** on P01's start pose. Caught: one frame early,
  too short, too long. It follows a moved `opening_end`. The **measured** 2 Oct keys are reproduced.
- **Manual marker moves are respected:** marker wins, JSON wins, conflict refused, deleted marker
  recreated, re-solved walk. Caught: a marker dragged out of the final quarter.
- **REVERT is exact:** REVERT(APPLY(original)) == original, re-apply then revert also returns the
  original, foreign markers are kept, and a wrong snapshot is detected.
  - This tests the state algebra the live tool mirrors, **not** the Unreal I/O layer [inf].

## 11. Gary's decisions

1. **P01's music**: it is silent after the move. Pick a track, or keep silence.
2. **The house warmers**: disable them so phase 0 is truly dark (`house_warmers.disable` +
   `decided_by`)?
3. **"Last swell"**: is it the big 67.5 s swell (default, release 74.9) or the late small 84.8 one?
4. **The move-in**: dark move-in (default) or keep the rig lit into P01?
5. **Look**:
   - Wash C level.
   - The park aim and swivel span (5.5→12.2 s).
   - Envelope floor/peak.
   - Footlights on/off (held with the portal build).
6. **Pre-roll** of silence before the music (needs a builder change or a sequence-local audio track).

## 12. Still unproven (needs the live editor)

All tagged [inf]:
- The marker API names (resolved at run time, DRY reports which).
- `parse_string_to_guid`'s return shape.
- That the rig's component child binding resolves in PIE.
- That light Intensity keys drive a level SpotLight in play.
- Restore-state at the Opening's end.
- Patch K carry on the real Show.
- `use_sequence_length` on the Opening cue (read and reported; the post-rebuild segment check
  gates it).
- The look itself.
