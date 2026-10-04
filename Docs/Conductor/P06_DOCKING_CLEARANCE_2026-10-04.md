# P06 v3 interleave: docking clearance (conductor, 4 Oct night)

**Verdict: NOT CLEARED as planned (+4500 cm route end).** It can be re-submitted in either form below.

## Evidence (tier per claim)
- **Measured:** the current P06 camera stop is 27640.28 cm, which matches the template's old_end. The source is `Saved/CodexStructure/arrivals_probe.json`, Scene 6 entry: last_station 27250, tail 390.28, 250 cm/s. Its arrival_placed is false.
- **Declaration-proven:** the Show carries no Scene transform, so docking is a level operation only. See `Docs/Conductor/SCENE_DOCKING_AUDIT_2026-09-29.md:87`. The S6 hangar root is a level actor (binding ED6FD1DE…) and does not follow a Passage re-fit.
- **Inferred:** a +45 m end therefore either drives the route 45 m into the S6 hangar's landed volume, or (if the hangar sits off-axis) leaves it 45 m behind. The structure invariant is "clean Passage end for hangar docking". The same failure was found for the P04 resize (handover, 2 Oct night: "S4 hangar ~340 m behind").
- **Not measured:** the S6 hangar root's live transform, and an overlap box from 27640 to 32140 cm along the route. The editor is unavailable tonight (restore dialog), so none of the ack's null fields can be filled with evidence offline.

## Re-submit as one of these
- **A (recommended, no level move):** keep the route end at 27640.28 cm and fit the 64 cues by tightening spacing (or trimming). There is no docking change, and the ack reduces to "end unchanged" plus a read-back.
- **B (keep +18 s):** the extension plus relocating the S6 hangar root and its Arrival by the measured end delta. This is a level write: backup, compose against the LIVE root (memory: level-saved-landed frame trap), an inside-box guard, then a read-only overlap probe before and after. It belongs to the conductor's S6 chain, after the light-GUID audit.

The Scene 6 time shift (+432,000 frames) is fine either way under patch K.
