# Job 99 — S6 arrival parcan and sun disc (offline delivery)

> **SUPERSEDED 10 Oct 2026 by Gary's scope correction.** The obstruction and
> missing disc are in Passage 06, not Scene 6. Do not run the S6 plan below;
> use `Docs/Conductor/JOB126_REPORT_2026-10-10.md` and the re-scoped tool in the
> same legacy-named Saved directory.

## Outcome and boundary

- **measured (this run):** dedupe found no prior Job 99 package. The delivered
  offline harness passes `27/0`; Python compilation passes. No Unreal, MCP, PIE,
  Blender, asset save, rendered still, APPLY, or REVERT was run.
  (`Saved/CodexConductor/P99S6ArrivalSun_20261009/test_p99_offline.py:1-47`)
- **inferred:** the package is ready for a conductor-owned live DRY. Current live
  actor identity, saved read-back, runtime effect, and rendered acceptance remain
  unproved until that run.

## (a) Parcan: what records prove, and what DRY must name

- **measured (historical record):** the saved P06 Meshy fixture swap reports the
  P06 Structure body mesh as `SM_Lantern_ParCan`, with 120 fixture bodies / 120
  ISM instances. This makes the P06 Structure fixture generator the leading
  source class, not proof of which one is in Gary's frame.
  (`Saved/CodexConductor/MeshyFixtures_20261007/meshy_swap_record_P06.json:147531-147540`)
- **declaration-proven:** Structure fixture order is deterministic: station order,
  then each enabled Station-anchored LIGHT attachment in Show order; the body ISM
  is emitted in that order. Therefore a live component + instance index maps to
  one exact authoritative Show row.
  (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageStructureActor.cpp:142-179,1927-1955,1984-1987`)
- **declaration-proven:** Job 99 projects every live ParCan ISM origin through the
  actual S6 arrival camera, independently of collision, ranks by frame-centre
  distance, and records actor/component/instance plus cue and attachment GUIDs.
  It also runs central frustum traces and record-token provenance checks.
  (`Saved/CodexConductor/P99S6ArrivalSun_20261009/p99_s6_arrival_sun.py:122-151,232-324`)
- **inferred:** the obstruction is likely one of those 120 P06 Structure cans.
  Gary's alternative—Puss light—remains open until DRY. The Puss shadow tool
  altered the Camera Rig FollowLight component, which has no fixture mesh of its
  own; a Structure can generated for another light may visually coincide with it.
- **declaration-proven:** APPLY never blindly deletes. A standalone actor gets an
  S6-only `bHidden/bHidden` track (VISIBLE `False`); a Structure ISM target is
  moved by exact cue + attachment GUID, with its original transform in the active
  record. Whole multi-instance actor hiding is refused.
  (`Saved/CodexConductor/P99S6ArrivalSun_20261009/p99_s6_arrival_sun.py:351-392,407-456`)

## (b) Sun disc diagnosis and scoped route

- **measured (historical saved read-back):** the P06 sunset reaches effective
  darkness at 52.15 s and ends at solar elevation -16.84 degrees / 0 lux.
  (`Saved/CodexConductor/p06_sunset_record.json:38-41,86-95`)
- **declaration-proven:** the original sunset plan explicitly records that no
  SkyAtmosphere is bound and the built-in dome's `Sun brightness` is held at 0;
  only light, reflection/shadow, and fog scatter were expected.
  (`Saved/CodexConductor/P06_SUNSET_PLAN.md:50`)
- **declaration-proven:** the celestial rig rotates the directional sun from phase,
  forces it to Atmosphere Sun Light index 0, and drives its intensity; its dome
  writes `Sun brightness = 0`.
  (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCelestialRig.cpp:449-495,541-576`)
- **inferred, strongest diagnosis:** a disc cannot appear at S6 arrival if the
  inherited P06 sun is below the horizon/0 lux, and it also cannot render through
  the built-in dome path because that path disables the disc. Hidden foreign sky
  actors or S6 visibility tracks may be an additional cause; the live DRY lists
  them rather than assuming.
- **declaration-proven:** APPLY confines the visible sky/disc intervention to
  `LS_DevScene_06`: S6 `bHidden` tracks show a hidden-by-default SkyAtmosphere and
  the existing dusk sun; Restore State hides/restores them afterward. S6-only
  transform, Intensity, and SourceAngle tracks put the disc inside frame. P18's
  editor-only hidden-sky rule is not removed. Creative defaults are args and need
  Gary's approval.
  (`Saved/CodexConductor/P99S6ArrivalSun_20261009/p99_s6_arrival_sun.py:351-392,407-463`)

## Records, census, read-back, stills

- **declaration-proven:** APPLY and REVERT require exact confirms, a SHA-pinned
  live DRY, a clean correct world, `Backups/PreP99S6ArrivalSun*` before mutation,
  an exclusive active record, exact dirty-package scope, named saves only, clean
  read-back, and run-id success markers. REVERT refuses a drifted moved row.
  (`Saved/CodexConductor/P99S6ArrivalSun_20261009/p99_s6_arrival_sun.py:70-80,398-404,407-498`)
- **declaration-proven:** the stills gate is: matched S6 +0.25 s before/after;
  S6 +0.25/+2.0 s disc plus reflection; P05/S5 and editor-sky negative controls;
  post-S6 Restore State; and a reverted S6 still.
  (`Saved/CodexConductor/P99S6ArrivalSun_20261009/README.md:63-70`)
- **inferred:** no tool result constitutes look approval. Gary must judge the
  obstruction clearance, disc position/size/luminance, reflection continuity,
  and absence of sky in every non-S6 control.

## Open choices before APPLY

1. Copy the DRY's exact actor label or cue/attachment GUIDs; do not type a target
   from appearance.
2. If it is a Structure instance, approve a move delta knowing it also changes
   that fixture during P06. If it is standalone, prefer the S6-only hide.
3. Approve or change 4 degree elevation, dead-ahead azimuth, 2 lux and 1.22 degree
   source angle after the DRY reports the live camera and current sun state.
