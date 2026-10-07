# S4 hangar: make it bigger for Klara's set (7 Oct, offline plan; nothing has been run in Unreal)

Gary, 7 Oct, his own words: "Rebuild the S4 hangar bigger". The rule is to resize the hangar and never her set.

How each claim was established:
- **[decl]** read in source, with file:line.
- **[meas]** read from a run record.
- **[off]** computed offline by `Saved/CodexStructure/hangar_resize_s4_plan.py`, which prints `HANGAR_RESIZE_S4_PLAN_OK`.
- **[inf]** inferred, with the reason given.

## 1. Verdict: resize in place, do not revert and rebuild

A `hangar_build.py` rebuild of S4 cannot be run as the tools stand.

- **No revert path.** `hangar_revert.py` refuses Scene 4 (`assert n != 4`) [decl hangar_revert.py:21].
- **APPLY refuses.** It stops while the S4 tag or `LS_S4_HangarRise` exists [decl hangar_build.py:340, 342].
- **Tuned state would be lost.** The live S4 hangar is the five-pass build plus layered tunes, and a fresh build would
  discard them:
  - the root rise runs −5.87 → 4.13 s, the roof 6.63–12.63 s and the lattice 12.63–16.63 s
    [meas s4_rekey_window_record.json `after`];
  - the S4 Arrival's 39 PreSceneFloatDrives are bound to the light components [meas s4_predrive_author_record.json];
  - the far wall is split into the exit-door pieces [meas hangar_exit_doors_record.json];
  - the Klara hookin nests the rise in `LS_DevScene_04`, section [0, 775] [meas klara_reveal_dry_S4.json plan.lattice.facts].

A default rebuild would re-key the rise to K × (1–16, 18.5–24.5, 24.5–28.5) [decl hangar_build.py:463] and give it
new actors and GUIDs.

**Plan:** move and rescale the existing actors in place.
- The labels, bindings, drives and key times all survive.
- One channel changes value: the lattice fly's Z.

## 2. Parameters

| | live | reveal proposal | **this plan** |
|---|---|---|---|
| depth | 6000 | 4000 | **6000** |
| half_w | 1000 | 1500 | **1400** |
| height | 3000 | 3000 | **3000** |
| lattice_z | 1200 | 1700 | **1700** |
| lattice_fly | 1600 | (not set) | **1200** |
| apron | 500 | 500 | **500** |
| ghost_x | 2500 | (not set) | **3500** |
| rail_pitch | 800 | | **1100** |
| uplight_pitch | 600 | | **900** |

The values in bold other than depth, height and apron are proposed here and are not Gary's.

**K.** K = sqrt(max(depth, 2·height)/6000) = sqrt(6000/6000) = **1.000**, as before [decl :178; off]. The rise timing is
unchanged by construction: the live key times are kept, not rescaled.

**Depth stays 6000.** The 4000 proposal would *shrink* the box and move the far wall and exit door 20 m nearer. 6000 also
encloses her set, whose far edge is at dock x 3183 against a limit of 6400 [off].

**half_w 1400 instead of 1500.**
- At 1500 the floor splits into 2 columns, because `round(1.5) = 2` [decl :97]. That relabels the floor tiles.
- With the default pitches it also adds a 4th rail and a 4th uplight. Those are new lights with no keys and no drives.
- At 1400 the piece counts and labels are identical to the live hangar: 115 labels and the same counts [off].
- Clearances for her set at y ±931:
  - inside the reveal's side margin of 100 (limit 1300);
  - inside the comfort margin of 300 (931 + 300 = 1231 ≤ 1400) [off].

**lattice_fly 1200.** With lattice_z 1700 and the old 1600 fly, the flown lattice would rest at 3300. That is above the
roof (3000), which swings over it [inf from plan_for geometry]. With a 1200 fly, the rail tops sit at 2951 [off].

**The ghost light was standing inside her set.** It sat at box (2500, −400) against her set's box x range 0–2683
[off `ghost_was_inside_set: true`]. It moves to box x 3500. It keeps the same parent, Floor 2 Hinge [decl :142].

**Lattice keys:**
- lattice fly Z keys become [[0, 2900], [12.6261, 2900], [16.6261, 1700]];
- the times are unchanged;
- set top 1355 + 300 ≤ 1700, so `under_lattice` passes and the `allow_lattice_overlap` warning goes away.

The full per-actor list of targets (root frame) is in `Saved/CodexStructure/hangar_resize_s4_targets.json`.

## 3. Docking: no re-dock

The dock and the hinge do not move.
- **Dock:** the Scene 4 Entry Handoff Camera at (10668.47, 240000) is the P04 route end [meas scene_docks.json].
- **Hinge:** dock + apron 500 = 11168.47 [meas hangar_exit_doors_record.json landed_root_transform].
- **Apron:** unchanged.

So the P04 end needs no re-dock, and neither does `floor_dark_wet_apply.py`'s S4 hinge check [decl :21-23].

P05 starts on its own lane at y = 320000 [meas scene_docks.json route_ends], so it is independent of the S4 box. No P05
re-dock is needed [inf: the handoff is a Master cut, not spatial].

`klara_hookin` does not re-place the stream. The klara_reveal APPLY moves her level itself, to
(11435.67, 239650.88, 0) [meas DRY level_transform_after].

## 4. Runbook (each step is gated on the previous one; take a `Backups/` snapshot first)

0. **Offline check.** Run `python hangar_resize_s4_plan.py`.
   - Expect `HANGAR_RESIZE_S4_PLAN_OK|labels=115|moves=113|k=1.000->1.000`.

1. **Hangar sweep DRY.** Run `hangar_build.py` with the new params, without `HANGAR_APPLY`.
   - **Copy** `hangar_s4_plan.json` aside first: the dry run overwrites it [decl :325].
   - DRY must confirm:
     - `problems = []`, `blockers = []` and `unchecked = []` at y ±1550;
     - `HANGAR_DRY_RUN_OK|mutated=0`;
     - the S4 compare lists `off_by_more_than_1cm` only for the labels in targets.json `moves`.

2. **Resize DRY, then APPLY.** Tool: `Saved/CodexStructure/hangar_resize_s4.py` (written 7 Oct and offline-tested; harness `test_hangar_resize_s4_offline.py` 17/0; never run in Unreal). Run it through `hangar_resize_s4_run.py` / `_request.json`. APPLY needs `confirm`, `approved_by` and the DRY's `plan_sha256`.
   - **Gates:**
     - world, no PIE, nothing dirty, no ZZ_ actors, Sequencer closed;
     - drift: every live root-relative pose is within 1 cm of `loc_old`;
     - lattice fly at 2800 (rest) or 1200 (landed) [memory: the level is saved LANDED];
     - root pitch is read and never written.
   - **Then:**
     - write the record and make the backup (level and `LS_S4_HangarRise`);
     - work parents first, setting each world pose as root ∘ `loc_new`;
     - rescale the slabs, the apron and the PPV Y;
     - rewrite only the values of the fly's `Location.Z` keys and default;
     - read everything back;
     - save the level and the rise only.
   - Marker: `HANGAR_RESIZE_S4_APPLY_OK|run=`.
   - Skip the plan_for label "S4 Hangar Far Wall": its actor is now "…Above Exit" [meas exit-door record].

3. **Exit doors.** These are covered by step 2 (the five pieces in targets.json). Never re-run `hangar_exit_doors`
   APPLY or REVERT: its revert covers all six scenes [decl hangar_exit_doors.py:1051].

4. **Arrival and rise keys.** No change, beyond the lattice Z values in step 2. The root is untouched.

5. **Handoff.** Run `MatchNamedSceneHandoffs`, then `rebuild_managed_master`. Both must report no change.

6. **Args (DONE 7 Oct, S4 only; S1 subtrees identical to HEAD; valid only after the resize APPLY).** Update both args files, because the reveal reads `lattice_z` from args [decl klara_reveal.py:1547]:
   - `klara_hookin_args.json` hangars.4: half_w 1400, lattice_z 1700;
   - `klara_reveal_args.json` hookin_hangars.4.lattice_z: 1700.

7. **klara_reveal S4 DRY.** It must show:
   - no `SET_DOES_NOT_FIT_LIVE_BOX`;
   - `under_lattice` passes;
   - `lowers_cm` 1200;
   - live box half_w 1400.

   `LEAD_ABOVE_RANGE` (1459 > 800) is **accepted by the conductor**: `scenes.4.placement.lead_max_cm` is now 1500, a per-Scene override that klara_reveal.py now supports (S4 only). Her set reaches about 959 cm behind her first camera, and resizing the
   hangar cannot fix that [decl :253-255]. The conductor must raise `lead_max` or accept the warning.

8. **extend_scene_playback** to the printed `new_end_s` (195.6 s), then klara_reveal **APPLY**.

9. **Tests and stills.**
   - Tests: SavedMasterMatchesShow and SceneCutBindingsResolve, each run singly.
   - PIE stills: the rise at about 4 s, 14 s (lattice) and 16.7 s; then L, G0, C−1, C, E−1, E and X.
   - Check: the walnut floor stretched to 1.4× in Y [inf]; the treetops under the 1711 glows; nothing crossing the walls.

## 5. Revert, in reverse order

- **klara_reveal:** REVERT, then extend back.
- **Resize:** `hangar_resize_s4.py` REVERT puts back the recorded poses, scales and fly keys, after a drift check.
  Otherwise restore `Backups/PreHangarResizeS4-<run>` with the editor closed (Don't-Save).
- **Args:** put the two args files back.
- **Never use these to undo the resize:**
  - `hangar_exit_doors` REVERT;
  - `hangar_revert.py`;
  - `s4_rekey_window` REVERT while the resize is applied (it would restore lattice 2800/1200) [inf].
