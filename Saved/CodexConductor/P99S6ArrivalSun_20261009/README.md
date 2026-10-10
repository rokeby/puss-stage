# Job 126 correction — P06 arrival parcan and sun disc

The directory keeps its legacy Job 99 name so conductor request paths do not
break. Its implementation, confirms, reports and markers are Job 126 / Passage
06 only. Offline delivery: no Unreal, MCP, PIE, Blender or asset save was run.

## Split DRY and PIE evidence

With PIE stopped, `p99_request.json` records the exact managed-Master range for
`Passage 6`, P06 actor/components, the celestial cycle and every sun/sky setting.
Success is `JOB126_P06_DRY_OK`; the dirty census must be unchanged.

The conductor separately pauses within the first six seconds of **Passage 6**
and runs `p99_pie_probe_request.json`. The probe never starts, stops or scrubs
PIE. It records:

- live camera pose/FOV and a 3 x 3 central frustum trace;
- every on-screen `SM_Lantern_ParCan`, including normalized UV and pixel screen
  position, actor/component/instance identity, and P06 ownership evidence;
- Structure ISM instance-to-Show cue/attachment mapping, plus Job 43, P06 FX,
  scaffold and fixture-record provenance;
- directional-light atmosphere flag/index, source angle and disc colour scale;
- SkyAtmosphere visibility/settings, actual sun UV/elevation, a ray toward the
  sun, and P06 mesh screen bounds crossing the sun's horizontal position.

Success is `JOB126_P06_PIE_PROBE_OK`. APPLY requires SHA-pinned reports from
both phases.

## Parcan route

Set `obstruction_action` to `HIDE_ACTORS_P06` and copy one or more exact actor
labels from hideable P06 probe rows. APPLY adds `bHidden`/`bHidden` visibility
tracks on the Master only across the measured Passage 6 section; VISIBLE
`False` hides them and Restore State restores them afterward. Nothing is
deleted or moved. A Structure actor with multiple ParCan ISM instances is
reported but deliberately refused: `bHidden` cannot hide one ISM instance
without hiding the whole Structure.

## Sun route

The existing P06 celestial cycle retains rotation and intensity authority.
Job 126 does not key either value. With `SHOW_ATMOSPHERE_P06`, APPLY reuses or
creates the named SkyAtmosphere, keeps it hidden in the editor, and adds
P06-range Master tracks that show the actor/component, temporarily suspend the
celestial rig's foreign-sky suppression, and set only `LightSourceAngle` from
args. All use Restore State. The shipped 1.22 degree size is a review default,
not creative approval.

## Ordered runbook

1. Run `python Saved/CodexConductor/P99S6ArrivalSun_20261009/test_p99_offline.py`.
2. With PIE stopped, run `p99_request.json`; require `JOB126_P06_DRY_OK`.
3. Manually pause within P06 0–6 s and run `p99_pie_probe_request.json`; require
   `JOB126_P06_PIE_PROBE_OK`.
4. Stop PIE. Review screen positions and sun diagnosis; copy exact hideable
   actor labels and both report hashes into args. Obtain Gary's approval for
   the actor selection and disc size.
5. Set `APPLY` / `APPLY JOB126 P06 ARRIVAL SUN`; require
   `JOB126_P06_APPLY_OK`, named saves, read-back and `dirty=0+0`.
6. For reversal use `REVERT` / `REVERT JOB126 P06 ARRIVAL SUN`; require
   `JOB126_P06_REVERT_OK`.

## Render controls

- Matched before/after at P06 +0.25 s and the requested middle arrival frame.
- Sun disc plus reflection at P06 +0.25 s and +2.0 s.
- Negative controls at P05, S5, S6, after P06, and in the editor viewport.
- Revert still at the same P06 frame.

Automation/read-back is not rendered acceptance. Gary must judge the obstruction
clearance, sun size/luminance, wing-top clearance and reflection continuity.

