# PG6 — animated_gobo: keyed Approach "focus pull" in/out (offline code + harness)

Read `_house_rules.md` (rules 3-6, 9). Offline only: no Unreal, no MCP. The editor steps are run later by the gobo session.

## Gary, 9 Oct
"The approach is a nice idea, and perhaps that's something that can flash on before and after, so as if the shadow
puppetry pulls into focus from a very blurry state." So: at the start the shadow arrives large and very blurry and pulls
into focus; at the end it goes back out.

## Current code (read it; cite file:line)
`Saved/CodexConductor/animated_gobo.py`: MPC `MPC_ShadowGobo` has scalars Frame, Clock, Approach (MPC_SCALARS);
`_add_frame_track` keys Frame (plan `frame_interp` CONSTANT/LINEAR) and Clock (linear over playback) on ONE MPC track
section spanning playback; `apply_model` / `_track_snapshot` / `comparable` / VERIFY compare snapshots; Approach drives
`grow = 1 + ApproachGrow*Approach` and defocus `ApproachBlur*Approach` in CODE_UV / CODE_EDGE (no material change
needed). Harness: `Saved/CodexConductor/test_animated_gobo_offline.py` (162/0 now).

## Build
1. New optional arg `approach_keys`: `[[seconds_from_frame_start, value], ...]` (value 0..1, strictly increasing
   seconds), keyed LINEAR on the MPC `Approach` channel of the same section, converted to display frames with the
   existing tick logic. Also a convenience arg `approach_pull`: `{"in_s": 1.5, "out_end_s": <seconds from frame_start>,
   "out_s": 1.5, "from": 1.0}` that expands to [[0,from],[in_s,0],[out_end_s-out_s,0],[out_end_s,from]]; refuse both
   together. Defaults: none (Approach stays 0, as today).
2. Plan/record/snapshot: `approach_keys` in the plan digest; `_track_snapshot` reads the Approach channel (channel_param
   handles suffixes) into `approach_keys`; apply_model expects it; channel_count counts it; `comparable()` keeps old
   records (005: no approach_keys field) revertible — add a test like J01-J03.
3. DRY reports the focus-pull timing in seconds and the max grow/defocus it implies (with the run's ApproachGrow /
   ApproachBlur); refuse values outside 0..1, non-increasing times, keys outside playback.
4. Do not change the material, the shared master/MPC validation, or anything else.

## Traps (rule 9 applies)
- Channel values are float32: compare read-back numerically (1e-4), never by hashing rounded values.
- Approach keys must not alter Frame or Clock keys (assert both unchanged in the harness).
- add_scalar_parameter_key takes TICKS (raw FFrameNumber): reuse the display->tick conversion; a -control must show
  that passing display frames would misplace the keys.

## Harness additions (+/-)
pull expansion exact; validation refusals (-) for each bad input; snapshot round-trip with approach keys (+); a v2
record without approach_keys stays revertible (+) and a real Approach key drift is detected (-); Frame/Clock unchanged
(+); digest changes when approach keys change (+).

## Deliver (rule 8)
Diff summary with file:line, commit (or file list), harness counts (old 162 must still pass), and the exact args block
for run 006 with `approach_pull` in=1.5 s / out over the last 1.5 s before frame 400 (I2), from=1.0.
