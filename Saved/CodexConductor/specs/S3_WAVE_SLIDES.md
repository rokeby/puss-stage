# Scene 3 wave slides (Gary, 2 Oct, his own answers in the Conductor 4 session)
"Waves in S03 need to undulate alternately." Rulings: ±100 cm lateral (dock ±Y), period 15.000 s (360 frames at
24 fps), eased sine; rows alternate direction (Row2 opposite Row1 and Row3); each row delayed 1.000 s (24 frames)
after the row in front (Row1 first); the two halves (A, B) of a row move TOGETHER; motion starts at the light strike
and runs to the Scene's end; before the strike the rows sit at their placed pose. Plan background:
Docs/FlatV3Spec_2026-09-30.md, "Other flats" > Scene 3 > "Wave rows".

Offset for row r (r = 1,2,3) at Scene frame f >= S (S = strike frame, read from the strike tool's record/spec,
Saved/CodexConductor/s3_strike*.py / its record; report where you read it, refuse if not found):
  y_r(f) = dir_r * 100 * sin(2*pi * max(0, f - S - 24*(r-1)) / 360),  dir = (+1, -1, +1).
The vamp loop 3480..4200 (720 frames = 2 periods) must be seamless: assert y_r(4200) == y_r(3480) for each row
(<= 0.01 cm) and report it.

## Tool `Saved/CodexConductor/s3_wave_slides_apply.py` (dry / apply / revert), the house pattern of
s3_vamp_apply.py / s3_shotlist_apply.py: backup LS_DevScene_03 to Backups/PreS3WaveSlides-<stamp>; record; actors
`S3 Wave Row{1,2,3} {A,B}` by exact label (refuse unless exactly six resolve); add or reuse a possessable binding
per actor in LS_DevScene_03 ROOT; a transform track keyed in the space the track uses: the actors are ATTACHED to
`S3 Hangar Root`, which rises, so key their RELATIVE location = placed relative location + offset along the dock Y
axis expressed in the parent's space; prove it by composing back at the LANDED root pose (as s3_flats_place.py
does) and assert that only dock-Y changes (<= 0.01 cm on X/Z, rotation untouched). Refuse if any of these actors
already has a transform track in this sequence. Keys: one per 3 frames from S to the Scene end, LINEAR; assert the
max deviation from the analytic sine between keys <= 0.1 cm; plus one key at S-1 holding the placed pose. Never key
the rise; never touch the Hangar Root.
Clearance: at ±100 cm, assert each row's halves stay within the hangar side walls (landed interior y ±1000) or
report the overhang behind the walls as data. The halves' overlap is unchanged because they move together.
Census = exactly LS_DevScene_03 (plus the level if a possessable binding must dirty it; report it). save_asset that
sequence only; after the apply, SavedMasterMatchesShow and SceneCutBindingsResolve run singly, exact names.
Harness `test_s3_wave_slides_plan.py`: + case (period 360, phase delays 0/24/48, directions, vamp seam equal,
pre-strike hold); − cases: wrong period (288 -> seam unequal must FAIL), same direction on all rows, missing actor,
existing transform track.

THIS PASS: write the tool and the harness, run the harness only. DO NOT contact Unreal (Wings and Textures hold the
editor). Commit nothing. Final message: the plan table (per row: dir, delay, first/last key, seam), the strike frame
and its source, each claim tagged measured/declaration-proven/inferred.
STANDING RULES: NEVER stop PIE/SIE, NEVER quit or restart the editor; no Sequencer UI/eval/scrub, no SequencerTools,
no open-range get_bound_objects, no unreal objects in module globals, no reload, never Save All, no deletes of
pre-existing things.

## Revision 2 (Conductor 4, after pass 1): DRY-RUN GATE ON THE STRIKE FRAME
Pass 1 took S = 147 from s3_strike_record.json STRIKE_S = 6.1333 s (cut-relative; W1 + 2.0 s, s3_strike_apply.py:639)
at 24 fps. That assumes LS_DevScene_03 frame 0 == the cut. The DRY run must read the LS_S3_HangarRise subsection in
LS_DevScene_03 (its start frame and its sequence-to-parent offset, from asset data only) and the S3 Uplight 1 strike key,
compute the strike in LS_DevScene_03 display frames, and STOP unless it equals 147 +/- 1. Report the numbers.
