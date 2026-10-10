# Job 178B - P06 end-window sun disc

Offline-authored only. Nothing here has run in Unreal.

DRY reads the P06 camera without opening or scrubbing Sequencer. At arrival
(the cited still) and near the passage end it fires bounded Visibility traces
left/right/up/down from the camera. It reports each window's horizontal and
vertical angular opening plus the current production sun's angular diameter.
The target diameter is 80% of the selected window's smaller dimension.

The production sunset remains the lighting authority. A centering correction
may change only P06's celestial entry phase and the rig azimuth, and is refused
if it would shift sunset by more than 10 seconds. APPLY reuses the existing
`Infinity Stage - Dusk Sky Atmosphere`; it adds P06-range Restore-State tracks
that show actor/component, suspend foreign-sky suppression, and set
`LightSourceAngle`. It does not create a second sky or sun.

Run order:

1. `python Saved/CodexConductor/Job178P06SunDisc_20261010/test_job178_p06_sun_disc_offline.py`
2. Keep `DRY` / `DRY JOB178B P06 SUN DISC`; run the guarded request. Require
   `JOB178B_P06_SUN_DISC_DRY_OK` and both `JOB178B_MEASURE` rows.
3. Check that all four window boundaries are named hits, not an unbounded scan;
   review current versus target disc and the proposed sunset shift.
4. Set `APPLY` / `APPLY JOB178B P06 SUN DISC`. Require
   `JOB178B_P06_SUN_DISC_APPLY_OK`, `centered=1|occluded=0`, the sky P06 track,
   named save/readback, and `dirty=0+0`.
5. Capture the identical P06 arrival frame and a near-end frame. A saved track
   readback proves configuration, not rendered visibility. Keep the gold Scene
   6-prep particle cloud untouched.
6. Reversal: `REVERT` / `REVERT JOB178B P06 SUN DISC`.

APPLY backs up the Show, Master and level to
`Backups/PreJob178BP06SunDisc-<run>` and writes `job178b_ACTIVE.json` before
mutation. REVERT makes a second backup and refuses cycle/azimuth drift.
