# P01: make the wing score play + a smooth walk-in from the Opening curtain fall (Gary, 2 Oct evening, his own words in
# the Conductor 4 session: "P1 is ok as it is [no resize], but make sure it plays including with a smooth movement into
# passage from curtain fall").
## A. Wing score shift (tool Saved/CodexConductor/p01_score_shift.py, DRY/APPLY/REVERT)
Fact (measured 30 Sep, Soft goods probe_passage_key_alignment.json; memory puss-passage-keys-absolute): P01's 3-key wing
score sits at 0.0-14.52 s, before P01's start at 15.0 s, so it never plays; it was displaced by the Opening's 15.0 s insertion.
Patch K (MoveSection) is BUILT (cc1331e), so future rebuilds carry keys; this one-off offset is not repaired by K.
DRY: read P01's passage section channels in the Master from asset data (no Sequencer UI/eval), list every channel's keys
(frame + value), confirm the 3-key wing-modulation score and its offset relative to P01's section start, and compute the
shift that puts the score's first key at P01's start + the same relative offset it had before the Opening insertion
(expected +15.0 s; report the derivation, refuse if it isn't a clean constant). APPLY: backup the Master to
Backups/PreP01ScoreShift-<stamp>; shift ONLY those keys; save the Master only; read back; SavedMasterMatchesShow alone.
REVERT from the record. Harness offline with a (-) control (a non-constant offset refuses).
## B. Opening -> P01 walk-in (plan only this pass)
Read Docs/Conductor/STREAM_STATE_LOOK_AND_CAMERA_2026-10-01.md §1, Saved/CodexCameraPilot/{key_walkin_i1_p02.py,
walkin_plan.py,walkin_transitions.json,test_walkin_plan.py}, and Saved/CodexConductor/specs/WALKIN_GENERALISE.md (which
put Opening->P01 out of scope as unprobed). Determine, declaration-proven or MEASURED from files: the Opening sequence path,
its camera(s), the curtain drop bake's landed time (bake chain: memory puss-bake-facts-from-artifact-chain: cache ->
<cache>_<bake_id>.abc -> DropBake/<bake_id>.json; release_frame may be None), the pile edge, and the P01 start/camera.
Write an `OPENING` entry into walkin_transitions.json with what is proven, null + a note for what isn't, and a READ-ONLY
editor probe script (Saved/CodexConductor/opening_walkin_probe.py: no save path, census asserted unchanged) that would
measure the nulls. Do not key anything.
Offline only this pass: no Unreal, no build, commit nothing. Final message: per item proven/measured/inferred/null, the
harness output, and what the editor probe will read.
