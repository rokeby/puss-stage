# AT fix (next build window): the strike rule is wrong (measured 2 Oct ~20:00, Conductor 4)
MEASURED (hangar_light_keys_probe, before restore): ApplyHangarTiming took the EARLIEST zero->positive ramp across ALL lights
as "the strike" (InfinityStageArrival.cpp:737-763). Practicals and Lattice Glow ramp DURING THE RISE from W0 = -5.867 s
(the glow-in-the-dark rise, by design), so the whole rig shifted +15.867 s: uplights to +22.0 s instead of +10.0 s.
S5 (lands +25.3) got glow at +10 and uplights at +32. Restored from Backups/PreHangarTimingApply-20261002-195101 (all six);
re-probed: uplights back at 6.133/6.267/6.433 (S5: 28.47/28.70/28.93).
FIX:
1. The STRIKE is the lights whose zero->positive ramp starts AT OR AFTER LandSeconds (in the standard hangars: the
   uplights at +6.133; S3 also its six Strike lights). Ramps that start before landing (glow/practicals during the rise)
   are NOT moved. Shift = StrikeTarget - earliest post-landing ramp. Report each light as moved/kept.
2. S3: standard families AND the six S3 Strike lights (the v2 replaced the families instead of adding).
3. LightStrikeSeconds is stored RELATIVE to landing (StrikeAfterLandSeconds, default 5.8667 = 10.0 - 4.1333) so S5
   (lands +25.3) strikes at +31.17 automatically; show the absolute time read-only next to it.
4. Tests: a transient rise with a during-rise glow ramp from W0 + a post-landing uplight strike: Apply moves ONLY the
   uplight to the target and leaves the glow unchanged (the old code must FAIL this); S3 moves 6 Strike + standard post-landing
   lights; S5-like landing at 25.3 gets strike 31.17.
5. Keep: S6 dim mode; S5 standardised roof/lattice TIMES (its values kept); root keys untouched.
Re-apply after the build: roof from landing (+4.5 s), lattice after (+4.0 s), strike 5.8667 s after landing; then re-time
the S3 wave slides (their gate now derives the expected frame from the measured strike).
