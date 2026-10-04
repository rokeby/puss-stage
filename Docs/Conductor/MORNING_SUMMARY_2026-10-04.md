# Morning summary, 4 Oct (Conductor 4); built up overnight

## Done offline
- **P06 docking:** NOT cleared at +45 m (4c4264e). Docs/Conductor/P06_DOCKING_CLEARANCE_2026-10-04.md has the two options; option A (keep the end, tighter spacing) is recommended and was sent to W&T.
- **GL held patch (e1626f4, unbuilt):** adds a Scene-cue flag `bGo1DrivesCamera`. In a flagged Scene the dog's look carries across that Scene's cuts and the vamp re-cut. There are 2 tests; `git apply --check` passes on HEAD (measured).

## For Gary
- **FOUND [measured in a 3 Oct log; Scene attribution inferred]:** all six Scenes are still Dog Free Look in the data (camera_owner_plan.json, 30 Sep 17:42). Your 2 Oct "GO1 not engaged in Scenes" ruling never reached the Show. Should S1–S5 be set to Timeline?
- **S6:** should the dog's look carry across S6's cuts (apply GL), or keep "reset at every cut" (no patch needed, because S6 is already dog-owned)?
- **S6 "running forward":** the receiver only writes pitch and yaw (declaration-proven), so the forward run must be a keyed camera move.
- **P06:** W&T report you chose option A (end held at 27,640.28 cm, kit FV3P6-20261004-01, 20 offline controls). The pass beat is set per wing (IntervalToNext), not by distance (source-proven, InfinityStageCompiler.cpp:255-315; my earlier "+18 s is stale" and "880 cm" were wrong). W&T are asking you: (a) keep the 2 s beat, +18 s, camera walks ~214 cm/s; or (b) keep 250 cm/s and today's duration, a pair every ~1.7 s. Their runtime mechanism swing at the closer spacing is unchecked.
