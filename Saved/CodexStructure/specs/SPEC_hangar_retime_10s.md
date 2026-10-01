# Spec: `Saved/CodexStructure/hangar_retime_apply.py`: S1, S2, S3 and S6 take Scene 4's 10 s rise

Gary (1 Oct, answered in the conductor session; confirmed in Rig & atmosphere): "Yes, all adopt the 10 s rise" for
S1, S2, S3 and S6. S5 is out of scope.

These four hangars are the same 60 × 20 × 30 m box with K = 1, built by `hangar_build.py`:
- S1, S3 and S6 at 30 Sep ~02:30–02:37 (commit d64ce61's builder);
- S2 rebuilt at 12:31 (26c12fd's builder).

Their `LS_SN_HangarRise` sequences carry the OLD timing:
- root pitch −90 at −3.567 → 0 at +16.0 (re-keyed by `arrivals_apply.py`, records `arrivals_record.json` and
  `arrivals_s2_record.json`);
- the builder's later beats at 18.0–28.5 s;
- the builder's pre-17:40 light keys.

Scene 4's sequence `/Game/InfinityStage/RigAtmos/LS_S4_HangarRise` is the TARGET. Make each of the four match it, role
for role.

## Target, per role (scene seconds; W0 = −5.8739, W1 = 4.1261, SHIFT = W1 − 16.0 = −11.8739)
Read W0 and W1 from `s4_rekey_window_record.json`. REFUSE if they're absent or differ from these values by more than
1e-3.

| Binding label (N = scene) | Channel | Target keys |
|---|---|---|
| `SN Hangar Root` | transform pitch | `[(W0, −90), (W1, 0)]`, AUTO |
| `SN Hangar Roof Hinge` (absent at S6: skip) | pitch | builder `[(0,−90),(18.5,−90),(24.5,0)]`, later two keys + SHIFT |
| `SN Hangar Lattice Fly` | Z location | builder `[(0,z0),(24.5,z0),(28.5,z0−fly)]`, later two keys + SHIFT |
| `SN Uplight k` | Intensity | builder strike keys + SHIFT (keep each light's own offset and the 0.2 s ramp) |
| parent starts `SN Practical` | Intensity | `[(W0, 0), (W1, full)]`, LINEAR, full = the channel's current max |
| parent starts `SN Lattice Glow` | Intensity | `[(W0, 0), (W1, full)]`, LINEAR |
| `SN Hangar Pinned Exposure` (if the actor exists; S3 has none) | BlendWeight | `[(W0, 0), (W1, 1)]`, AUTO; also set the actor's SAVED `blend_weight` to 0 (record the old value) |

- Check the table against S4's own channels: read LS_S4_HangarRise in the dry run and print S4's keys per role beside
  the plan.
- Any role whose plan differs from S4's pattern by more than 1 frame or 1e-3 → REFUSE.
- Don't change playback ranges, section ranges or any nest section. The rise ends stay at 31.0 s.
  - Trap: a subsequence section that outlives its inner sequence's playback restores the REST pose (pitch −90).
  - Assert, per scene, that no nest section in LS_DevScene_0N is longer than the rise's playback range.

## Expected BEFORE state (guard)
- Root: must equal that scene's `keys_new` in the arrivals record.
- Every other channel must equal what THE BUILDER THAT BUILT IT wrote. Derive that with
  `git show d64ce61:Saved/CodexStructure/hangar_build.py` (S1/S3/S6) and `git show 26c12fd:...` (S2).
- Dry run: print MATCH/MISMATCH per channel. Apply: refuse on ANY mismatch, or on any binding in the sequence that
  matches no role.

## Arrival pre-drives (patch P is built)
Author `pre_scene_float_drives` on each level actor `SN Arrival`, exactly as `s4_predrive_author_apply.py` did for S4:
- one entry per practical and glow light component (`Target` = the light component of the level actor whose label
  equals the parent binding's name; `BindingGuid` = that component binding's GUID; `PropertyName` = "Intensity");
- plus the exposure volume if it exists.
- Match one-to-one; never by index. Record the previous drives.
- S2 and S6 aren't nested. Their Arrivals decline (NoSubSection), but author them anyway.

## Reference implementations (mirror their structure, guards, record/revert and runners)
- `s4_rekey_window_apply.py`: channel finding, `.name` for enums, `conv_guid_to_string`, suffixed channel names.
- `s4_predrive_author_apply.py`: the drives and the seam check.
- `seam_check_readonly.py`: Master time mapping.

## Traps
1. Never open Sequencer: asset API only. Opening or scrubbing a Master-bound sequence dirties the map.
2. Guards before any write:
   - world `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
   - no PIE;
   - BOTH dirty lists empty;
   - no ZZ_/TEMP_ actors;
   - record absent.
3. Back up first to `Backups/PreHangarRetime-<stamp>/`: the level, the four rise assets, the record.
4. Save ONLY the four rise assets and the level.
5. Read-back before saving:
   - every changed key (1 frame, 1e-3);
   - every drives array;
   - SEAM for nested S1 and S3: the Arrival's `resolve_float_drive_at_master_frame` one Master tick before the
     Scene's start equals the channel at scene time 0 (1e-2), for one practical and one glow. It must also be clearly
     below full at W0 + 1 s.
   - The root pitch at scene 0 must equal S4's (≈ −33.42°) within 0.05°.
   - Any failure: stop, no save.
6. The done line `HANGAR_RETIME_DONE|run=<HHMMSS>|...` carries a post-run census of BOTH packages. Never Save All.
7. The revert restores every recorded key, saved blend weight and drives array, gated on a read-back of the applied
   state.

## Harness `Saved/CodexStructure/test_hangar_retime_plan.py` (plain Python, no Unreal)
Keep planning pure: `plan_scene(before_by_role, W0, W1, builder_beats) -> after_by_role`.
- **POSITIVE:** S3's builder-old before-state plans to S4's after-state, role for role, with S4's values taken from
  `s4_rekey_window_record.json` plus `s4_predrive_author_record.json`.
- **NEGATIVE, each must FAIL:**
  - a) a before-state with the root still at `[(0,−90),(1,−90),(16,0)]` (arrivals not applied) refuses;
  - b) an unknown binding refuses;
  - c) a plan that shifts the root as well (double-shift) is detected;
  - d) W0 ≥ 0 raises.

Deliver: the script; apply/revert/dry-run runners with request JSONs (same pattern as the S4 tools); the harness.
Run the harness and report its lines verbatim. Don't run Unreal.

Final message:
- files;
- harness output;
- what the dry run will print;
- what you couldn't verify.
