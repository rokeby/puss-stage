# Hangar timing on the Arrival's Details panel (Gary, 2 Oct, his own answers in the Conductor 4 session)
Gary: "Lights can strike at 10 s, later may be better to give sense of rig setting up new world — would be great if that
sequence's timing was exposed and editable." Chosen: properties on each `S<N> Arrival` (AInfinityStageArrival) in the
Details panel, plus an Apply button. Defaults, relative to the cut (W1 = landing = +4.1261 s):
  roof close  +4.1261 -> +8.6261   (Gary earlier: start at landing, faster)
  lattice     +8.6261 -> +12.6261
  light strike first light at +10.0, keeping each hangar's existing per-light stagger and ramp shapes.

## Read first (do not guess)
- Saved/CodexStructure/hangar_retime_apply.py: the roles (root_pitch, roof_pitch, lattice_fly_z, ppv_weight), discovery by
  labels `S<N> Hangar Roof Hinge` / `S<N> Hangar Lattice Fly` / uplights / practicals / Lattice Glow, the 30 fps rise assets
  `/Game/InfinityStage/RigAtmos/LS_S<N>_HangarRise`, key shapes (roof [0,-90],[start,-90],[end,0]; lattice [0,2800],
  [start,2800],[end,1200]).
- Saved/CodexStructure/hangar_roof_early_apply.py: today's measured state. S1-S4 standard (roof 6.6333->12.6333, lattice
  12.6333->16.6333); S5 NON-standard (roof 0/29.27/38.73; lattice 38.73->45.07); S6 roofless. Light-intensity keys sit
  at +6.6333 in S1, S2, S4, S6 and S3 strikes at +6.1333 (Saved/CodexStructure/s3_strike_record.json uplight_keys).
- The AInfinityStageArrival header and .cpp, and the HL patch (BeginPlay first-key pose in game worlds).

## C++ (editor-only parts under WITH_EDITOR / an editor module if the Arrival lives in a runtime module)
- `USTRUCT FInfinityHangarTiming` on AInfinityStageArrival, Category "Hangar Timing": RoofCloseStartSeconds,
  RoofCloseEndSeconds, LatticeStartSeconds, LatticeEndSeconds, LightStrikeSeconds (all cut-relative seconds), plus a
  VisibleAnywhere LandSeconds read from the root's last key. Defaults as above. EditCondition hides roof fields when the
  hangar has no roof hinge.
- `UFUNCTION(CallInEditor) ApplyHangarTiming()`: inside one FScopedTransaction (undoable), Modify() the rise sequence,
  re-key ONLY: roof_pitch (keep values, interp), lattice_fly_z (keep values, interp), and every light-intensity channel's
  STRIKE (shift each light's zero->on ramp so the earliest strike lands on LightStrikeSeconds, preserving the per-light
  offsets and ramp durations; values unchanged). Never touch root keys, exposure/PPV, playback range, or other
  tracks. Marks the asset dirty; DOES NOT SAVE (Gary saves).
- Validation, refuse with a clear message (log + editor notification) and change nothing: roof start < LandSeconds,
  roof end <= start, lattice start < roof end, light strike < 0 or beyond the sequence's playback range, or key
  shapes not matching the standard (S5 today: refuse and say so; S6: no roof, apply lattice + lights only).
- Log one line: INFINITY_HANGAR_TIMING_APPLIED|actor=..|roof=a..b|lattice=c..d|strike=e|lights=n  (or _REFUSED|reason=..).
- A `ReadHangarTiming()` CallInEditor that fills the struct FROM the asset (so the panel shows the truth first).

## Tests (new file InfinityStageHangarTimingTests.cpp; names UTF-8)
`InfinityStage.Hangar.TimingAppliesToTransientRise`: build a transient level sequence with the standard shape, apply
the defaults, assert roof/lattice/strike keys and that root keys are byte-identical. `...TimingRefusesBadOrder`: roof
before landing, lattice overlapping roof -> refused, keys unchanged. `...TimingPreservesLightStagger`. Each must fail
with the Apply stubbed (state how).

## Deliverable: a HELD patch, nothing built
Write `Scripts/patches/2026-10-02_AT_hangar_timing_details.patch` (git diff of only your files), check
`git apply --check` on HEAD AND that it applies together with `Scripts/patches/2026-10-02_SS_scene_shot_step.patch`
(apply SS then AT in a scratch worktree or with --check sequencing; report). Then RESTORE the working tree (git
checkout your files, delete new files). NO Unreal, NO build, NO UBT, NO editor. Commit nothing. Final message: files,
patch path, apply checks, each claim tagged declaration-proven/inferred, and open questions.
