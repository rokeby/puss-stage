# Codex job 92 — S2 hangar envelope (offline delivery)

## Verdict

- **Measured (saved record):** the 15 S2 V3 overlay wing pivots occupy approximately root-local `x=1041..4595`,
  `y=-1504..1851`, with ceiling pivots at `z=1640` cm. This is calculated offline from the applied overlay record's
  recorded transforms (`Saved/CodexFlatV3/s2klara/overlay/s2v3_overlay_record.json:425`, `:620`, `:659`).
- **Measured (offline arithmetic):** the existing 1000 cm half-width cannot contain those pivots, before adding any
  mesh extent or margin. The harness encodes that positive/negative control
  (`Saved/CodexConductor/Job92S2Envelope_20261009/test_s2_envelope_offline.py:20`).
- **Inferred, deliberately gated:** 2500 cm half-width, 4500 cm height, lattice at 2800 cm landed / 4200 cm rest is a
  conservative starting proposal. Offline records do not contain every Japanese_Alley component bound, so APPLY
  recomputes live renderable bounds and refuses unless 300 cm side/top/lattice clearance and 200 cm rest-rig-to-roof
  clearance fit
  (`Saved/CodexConductor/Job92S2Envelope_20261009/s2_envelope.py:232`).

## Dedupe and authority

- **Declaration-proven:** `hangar_build.py` owns the parametric dimensions and derives every position from them; its
  historical defaults are half-width 1000 / height 3000 cm (`Saved/CodexStructure/hangar_build.py:18-25`, `:61`).
- **Measured (repository):** no Job 92/E10 implementation commit or tool existed before this delivery. Existing S4
  resize code is S4-specific; this job does not run it or rebuild/destroy actors.
- **Declaration-proven:** ARRMOV identifies roof/lattice movers by exact binding names and stores their target/GUID
  drives (`Saved/CodexConductor/arrival_movers.py:1-7`, `:32-47`). Job 92 fingerprints those exact S2 drives; it does
  not re-mint GUIDs or write engine-owned fields.
- **Declaration-proven:** S2WALLHIDE binds `AActor::bHidden` and treats its bool channel as visibility
  (`Saved/CodexConductor/KlaraIngest/s2_exit_wall_hide.py:3-5`, `:44-47`). Job 92 rejects any visibility property other
  than `bHidden` and preserves the sequence.

## Delivered change

- **Declaration-proven:** `s2_bounds_probe.py` is a read-only, no-save census of Klara renderable component bounds,
  the existing hangar, ARRMOV, S2WALLHIDE, V3 overlay, floor/apron and both handoff cameras.
- **Declaration-proven:** `s2_envelope.py` supplies DRY/APPLY/REVERT, confirm strings, a DRY digest, pre-change backup,
  exclusive record, exact dirty-package gates, named saves, pre/post-save read-back and run-id success markers.
- **Declaration-proven:** APPLY changes existing S2 hangar geometry in place: side/far walls, roof hinge/roof, lattice,
  floor/apron, practical/rail lateral positions and pinned exposure. It preserves the 300 cm exit opening.
- **Declaration-proven:** only the lattice fly's suffix-normalised `Location.Z` values change in
  `LS_S2_HangarRise`; key times are unchanged. All other rise/fold data is fingerprinted. `str(FGuid)` is never used;
  GUIDs use `GuidLibrary.conv_guid_to_string`.
- **Declaration-proven:** Klara's level, `LS_NEW_SHRINE_S2Hangar`, `LS_S2_V3WingsOverlay`, `LS_DevScene_02`, ARRMOV,
  S2WALLHIDE and entry/exit cameras are guarded dependents and are never saved. Widening/raising the container does
  not justify moving her authored content or the handoff anchors.

## Verification and remaining acceptance

- **Measured (offline):** `test_s2_envelope_offline.py` passes 13/13, failures 0, errors 0, with explicit negative
  controls for undersized width/height, unchanged walls, naïve door scaling, unmapped keys, enum text and digest drift.
- **Measured (offline):** all four Python files compile and `git diff --check` is clean.
- **Unproven:** live bounds, exact actor count, live DRY digest, package census, APPLY/REVERT and saved read-back. The
  conductor must run them in order from the folder README.
- **Unproven:** PIE and rendered acceptance. Use `STILLS_PLAN.md`; never save Klara's streamed level.
