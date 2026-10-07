# P01 shorten + retime to Cameron's walk song (plan, 7 Oct)

Offline only. Nothing here has run in Unreal. Each claim is tagged per AGENTS.md:
**[decl]** read in source or a header, **[meas]** read back from an earlier run's record, **[inf]**
inferred (the reason is given), **[prec]** an in-repo tool that already makes the call.

## 1. Recommendation

**Drop the last 6 bays (P01 Wing 043–048). Keep 42. Then retime P01 to song + 2 s = 75.52 s.**

| | today | after drop 6 + retime |
|---|---|---|
| bays | 48 | 42 |
| length | 96.336 s **[meas]** `walking_music_swap_record_P01.json` segments_before 2312640..4624705 | **75.520 s**: 73.516 s song + 2 s, rounded up to a 25 fps frame |
| route (TotalDistanceCm) | 28784.01 cm **[meas]** `probe_routes.json`, `hangar_s1_record.json` dock | **25184.01 cm**: −3600 cm |
| bay walk speed | 300.0 cm/s **[meas]** PSTILLS-P01-20261005-070532: x 2840.1→8620.3 cm over 9.634→28.901 s, and the same through 86.702 s | **≈337 cm/s (+12.4 %)** |
| P01 lead-in, where the Opening walk-in hands over | ≈250 cm/s **[meas]** `opening_walkin_probe.json`, `opening_timing.json` walkin.v_end 251.3 | ≈281 cm/s. Re-ease the walk-in (step 7). |

The right-hand column is **[inf]**. It is computed by `test_p01_shorten_offline.py --table`, which
uses the retime tool's own functions. Its timing split is inferred: every interval is 48000 ticks
and every gap 600 cm (`p456_baseline_plan.json` p01_spacing). The 300 cm/s measured above supports
that split. The DRY reads the real per-bay values.

The full sweep, all ending at 75.52 s:

| bays dropped | 0 | 4 | **5** | **6** | 7 | 8 |
|---|---|---|---|---|---|---|
| bay speed (cm/s) | 385.2 | 353.3 | 345.2 | **337.3** | 329.3 | 321.3 |
| rise over 300 cm/s | +28.4 % | +17.8 % | +15.1 % | **+12.4 %** | +9.8 % | +7.1 % |
| route (m) | 287.8 | 263.8 | 257.8 | **251.8** | 245.8 | 239.8 |

Why 6 and not 5:

- **The look repeats every 6 bays.** That is 3 wing meshes (roccoco, pillar1, Pillar2) × 2
  ceilings. The new last bay, 42, is Pillar2 + CloudCeilingSmall, the same as today's last bay 48.
  With 5 dropped, the passage would end on bay 43 (roccoco + Ceiling) instead. **[meas]**
  `CodexFlatV3/swapkit/show_wing_dump.json`, 4 Oct. The meshes may have changed since; the
  harness asserts this from that dump.
- 6 is the lower edge of the brief's 12–15 % window. 5 sits at the upper edge and keeps bay 43,
  where the unapplied note-lamp plan has a target.
- **The exact N is still Gary's call:** `decided_by` in `p01_shorten_args.json` is empty.

## 2. Mechanism: disable the cues; do not delete them

How the compiler builds a Passage:

- A Passage is each maximal run of **enabled** WingPair cues. A disabled cue ends the run and is
  skipped. **[decl]** `InfinityStageCompiler.cpp:200-205, 240-246`
- Its settings row is found by an **exact** (FirstCueGuid, LastCueGuid) match. **[decl]** `:81-89`
  So P01's LastCueGuid must move to bay 42. If it does not, P01 loses its lead-in/tail, music and
  Choreo.

How the tool moves LastCueGuid:

- `ReconcilePassageSettings` does the same job on its own. It keeps the row whose old First falls
  in the new run and rewrites First/Last. **[decl]** `InfinityStageShowAsset.cpp:126-181`
- `RebuildManagedMaster` calls it. **[decl]** `InfinityStageSequenceBuilderLibrary.cpp:208-209,
  632-633`
- `p01_shorten.py` also writes LastCueGuid explicitly. After the rebuild, it asserts that the
  rebuild left it there.

What disabling leaves alone:

- Disabled cues keep every field and **keep their array index**. Index-holding records therefore
  stay valid, for example `lighting_scores_record_P01.json` scratch.show_index 51.
- They are not materialised: attachments need a compiled wing. **[decl]**
  `InfinityStagePassageActor.cpp:1850-1875`, called from `:902-917`
- REVERT re-enables the cues and restores the old LastCueGuid, which is exact.

Alternatives that were rejected:

- **`ResizePassageToDuration`.** It deletes the trailing cues (`Cues.RemoveAt`
  `InfinityStageWingSequenceInterchange.cpp:709`). It also rewrites every interval and gap to the
  preferred speed and spacing and sets ManualPassage (`InfinityStagePassageResizeLibrary.cpp:247-281`).
  That would lose the attachments and shift later cue indices.
- **Keeping the cues and only shortening the range or route.** The range is not authoritative. The
  compiler re-joins any enabled contiguous WingPairs, and a range that is not maximal is refused
  (`passage_retime_to_music.py` `_cue_range`).
- **Keeping the end fixed with a longer TailDistanceCm.** This gives the same 381 cm/s mean as
  retime-only, plus a 36 m empty walk at the end.
- **Moving P01's start forward**, the p02_straighten "DOCK" anchor. The Opening is keyed absolutely
  onto x = 0: walk-in target, curtain pile and stalls camera (`walkin_OPENING_record.json` plan.target).

Two rebuild behaviours make some pins unrecoverable, so the tool refuses them:

- The rebuild **deletes** wing pins on wings that are no longer in the Passage.
- It also deletes relative pins at or beyond the new length. **[decl]**
  `SequenceBuilderLibrary.cpp:280-291`

`p01_shorten.py` refuses both (`WING_PIN_ON_DROPPED_BAY`, `RELATIVE_PIN_PAST_NEW_END`), because
REVERT could not bring them back.

## 3. What follows from the drop

**Timing.**

- P01 shrinks by the dropped bays' intervals: 6 × 2 s = 12 s **[inf]**.
- Every later Master section moves earlier by MoveSection. **[decl]** `:300-309`
- The gates are the retime tool's own, imported unchanged: segments, managed sections, Passage
  keys, artist content, music fit, Master in sync.

**The end view moves back 3600 cm.**

- The P01 route is auto-fit straight. **[meas]** `probe_routes.json` auto_fit_straight true;
  **[decl]** `InfinityStagePassageActor.cpp:772-786`
- The Scene 1 Entry Handoff camera and the S1 hangar dock both sit at the **old** end,
  (28784.01, 0, 150). **[meas]** `CodexStructure/hangar_s1_record.json`, `scene_docks.json`

Consequences:

- **Scene 1 goes stale.** The tool allows exactly that Scene to go stale and fails on any other.
- APPLY needs `followons_ack` to include `S1_REDOCK` and `MATCH_S1_HANDOFF`. This follows the
  precedent at `p02_straighten.py:76-82`.

**Not inventoried yet:** what stands at the S1 end beyond the hangar. The lane inventory covers
lanes 2–6 only (`lane_inventory_130421.json`). The DRY's `region_inventory` lists every level
actor from 10 m before the new end to 150 m past the old end, within ±50 m laterally.

**Records keyed to the dropped bays.** These are re-plan items; the cues themselves still exist.
Offline `scan_orphans` with N = 6 gives these hits:

| record | hits | status |
|---|---|---|
| `lighting_scores_record_P01.json` | B43–B48 scores, 6 GUIDs | applied 5 Oct. Its REVERT still finds the cues; a re-run expects 48 bays. |
| `p01_rig_pattern_record.json` | B43, B45–B48 | applied 6 Oct |
| `rig_lamp_drop_record_P01.json` | B43, B45–B48 | applied 6 Oct |
| `p01_note_lamps_plan.json` | targets on B43 | PLAN only, never applied. Its route model, timing and speed change, so it must be re-planned whatever N is. |
| `light_guid_audit_20261004-121338.json`, `hf_preflight_FV3HF-20261006-P01.json`, `swapkit_apply_FV3D-20261006-01.json` | label mentions | history only |
| `CodexStructure/blink_spots_revert_record.json` | bay 48 GUID | revert record |
| `puss_shadow_spot_args.json`, the song-markers record, `lighting_drift_decisions_P01.json` | none | Song-relative cues at 11.6 s and 38.2 s, and markers ≤ 70.6 s (record SONGMK-20261006-011925), all lie inside 75.52 s. |

**Kept:** Gary's hand-set bays 3 and 4 (`p01_note_lamps_config.json` exclude_cues), plus bays 1–2
(the Opening house lights on bay 1, `lighting_scores_record_P01.json` foreign_owned). They are in
`keep_labels`, and any drop that includes one is refused.

**Show order is not label order.** Positions 10–12 read 011, 012, 010 **[meas]** (4 Oct dump). The
drop is by Show position, which is the compiler's order. Positions 43–48 carry labels 043–048.

## 4. Files

- `p01_shorten.py`: DRY / APPLY / REVERT. The confirm string is `"<MODE> P01SHORTEN"`. It also
  materialises P01 + Structure 01 and checks that the end view moved by the dropped distance (±5 cm).
- `p01_shorten_run.py`, `p01_shorten_request.json`, and `p01_shorten_args.json` (DRY, undecided).
- `test_p01_shorten_offline.py`: 10 tests, 97 checks, 0 failed. Every gate has a failing control.
- The retime tool is extended, backward compatible:
  - `VALID_KEYS` now includes "1" (`passage_retime_to_music.py:127`).
  - A `RETIME_IMPORT_ONLY` load guard (end of file), which the shipped runner never sets.
  - A P01-only `ENTRY_SPEED_STEP` warning.
  - The args gain a P01 row and the prerequisite `p01_shorten_record.json`.
  - Its harness: 21 tests, 283 checks, 0 failed.
  - Two harness checks failed **before** this change. They asserted the args file still held
    P02–P05, but it holds ["3","4"] since RETIME-20261006-014626. They were rewritten to be
    file-independent.

## 5. Supervised run order

Rules for every step:

- Parse markers **by run id** (memory: log markers need run ids).
- Run the tests one at a time after every step that writes the Show or Master:
  `InfinityStage.Editor.SavedMasterMatchesShow`, then `InfinityStage.Editor.SceneCutBindingsResolve`.
- **On any `*_STOPPED` before a save, nothing is saved. Quit the editor with Don't Save and
  restart.** After a save, use REVERT, or restore the named `Backups/` folder.

1. **Snapshot.** Full D: snapshot, plus `Backups/PreP01Shorten-<ts>` of the Show, Master and level.
   The tool also takes its own backup.
2. **Offline.** `python test_p01_shorten_offline.py --table` and
   `python test_passage_retime_to_music.py` must both report 0 failures.
3. **Shorten DRY.** Run `p01_shorten_request.json` with mode DRY. Wait for
   `P01_SHORTEN_DRY_OK|run=…|apply_ready=1`. Then read `p01_shorten_dry.json`:
   - `refusals`
   - `chain_sweep`: the live speeds, which replace the inferred ones above
   - `orphan_scan`
   - `region_inventory`
   - `end_view_before`
4. **Decide.** Gary's N goes into `decided_by`. Copy `expected_for_apply_args` into `expected`. Set
   `followons_ack` to ["S1_REDOCK","MATCH_S1_HANDOFF"].
5. **Shorten APPLY.** Confirm `"APPLY P01SHORTEN"`. Wait for `P01_SHORTEN_APPLY_OK|run=…`. Then run
   the two tests.
6. **Retime.** In `passage_retime_to_music_args.json`, set passages ["1"], then run DRY (confirm
   `"DRY RETIME"`).
   - Expect `PASSAGE_RETIME_DRY_OK` with apply_ready=1. Expect an `ENTRY_SPEED_STEP` warning.
     Expect no `TIME_KEYED_CHANNEL` or Choreo refusals.
   - Copy in `expected`, then run APPLY. Wait for `PASSAGE_RETIME_APPLY_OK`, then run the tests.
   - The retime does not move the end. Distance is unchanged. **[decl]** retime header
7. **Walk-in re-ease.** `opening_sequence_apply.py` DRY, then APPLY. It re-measures P01's entry
   speed live (`:341-358`). This is the Opening stream's tool, so coordinate with that stream.
8. **Scene 1 handoff.** `CodexCameraPilot/match_scene1_handoff.py`: marker
   `PUSS_MATCH_P1_S1_DONE`, then re-run the tests.
9. **S1 re-dock. No tool exists; it needs a spec before step 5 runs for real.** Two options:
   - **(a)** Translate the S1 set by −removed_cm in X: tags `RigAtmos.Scene1*`, the S1 exit doors
     (`hangar_exit_doors_record.json`, applied 3 Oct), and the rise root's world-Location key.
     "a hangar moved rather than rebuilt costs one re-key" (`Docs/HangarExitCost_2026-09-30.md`).
   - **(b)** `hangar_revert`, then `hangar_build.py` at the new Entry camera, then Arrival, then
     re-apply the exit doors.
   - Do this before the Klara hook-in, which is not applied yet and reads the live S1 apron.
10. **Re-plan the orphans.** Re-plan the note lamps, and run any P01 lighting re-runs against 42
    bays.
11. **Look.** P01 stills, plus the P01→Scene 1 crossing, for Gary's verdict.

**REVERT is LIFO.** Revert the retime first, then the shorten. `p01_shorten` REVERT refuses while a
P01 retime record is applied. S1 re-dock steps must be undone before either revert.

## 6. Risks and what is inferred

- **The bay timing split is inferred.** It only moves the numbers; the DRY reads the real
  intervals and gaps.
- **Disabled cues have never been used in this Show.** All 48 were enabled on 4 Oct **[meas]**.
  Python tools that walk cues by label rather than by the compiled Passage may still touch bays
  43–48 **[inf]**. The lighting tools key on 48 bays.
- **The S1 re-dock is the dominant cost, and its scope is unmeasured.** The DRY inventory measures
  it.
- **The P01 floor slab may still reach the old end.** The slab "Passage 01 - Opening Floor" is on
  the hangar build's allow-list. Whether it reaches into the new pit region is **[inf]**, not
  checked.
- **MaterializePassage may dirty more than the level.** If it does, the census gate stops the run
  with nothing saved.
- **If the walk-in is not re-eased,** there is a +12 % speed step at the Opening→P01 cut **[inf]**.
  It has not been seen rendered.
- **The end-view read uses the end frame**, following the `match_scene1_handoff.py:104-106`
  precedent. Its tolerance is 5 cm.
