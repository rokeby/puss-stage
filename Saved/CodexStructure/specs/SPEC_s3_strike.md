# Spec: `Saved/CodexStructure/s3_strike_apply.py`: Scene 3's bright strike after the cast appear

Gary (1 Oct): when the lights strike it is "very bright", because "the shore figures exist on a bright shore …
surrounding their ritual clam". Sequence of events: the cast appear in the landed, dim hangar
(`s3_cast_reveal_apply.py`, REVEAL_S = W1 + 0.5), "then … the lights strike up".

## Timing
- `STRIKE_S` = S3's FIRST uplight strike time after step 1's re-time: the earliest key where an `S3 Uplight k`
  intensity leaves 0. Expect W1 + 2.0 = 6.1261 s. Read it from the sequence.
- So the new lights strike WITH the hangar's existing three-strike rhythm. The dark beat after the reveal is ~1.5 s.
- Refuse unless REVEAL_S < STRIKE_S.
- Each new light's Intensity: `[(0,0), (STRIKE_S,0), (STRIKE_S+0.2, I)]`, LINEAR.

## New level actors
- All Movable, all ATTACHED to `S3 Hangar Root`, placed in ROOT-RELATIVE coordinates: x from the box mouth, y across,
  z up from the hinge.
- The level's saved root pose is HANGING (pitch −90). Never place by world position at rest, and never rotate the root.
- Each light points at its target via a look-at rotation computed in root space. Prove the aim in the read-back with
  each light's forward vector at the LANDED pose.

| Label | Type | Root-rel location (cm) | Aim at (root-rel) | Shadows | Start values (tuned at review) |
|---|---|---|---|---|---|
| `S3 Strike Key` | RectLight 400×200 | (700, 500, 1000) | cast centre (2000, −150, 120) | ON | 4000 cd, 5600 K |
| `S3 Strike Fill L` | RectLight 600×300 | (900, −900, 400) | cast centre | off | 1000 cd, 6500 K |
| `S3 Strike Fill R` | RectLight 600×300 | (900, 900, 400) | cast centre | off | 1000 cd, 6500 K |
| `S3 Strike Cyc 1..3` | RectLight 400×100 | (5000, −700/0/700, 1100) | far wall (6000, same y, 900) | off | 1500 cd, 7000 K |

- Intensity units: set them explicitly (candelas) and read them back.
- Exactly ONE shadowed light: VSM page overflow shows as colour rectangles here.

**Exposure:** S3 has no exposure volume. Add `S3 Hangar Pinned Exposure` exactly as `hangar_build.py` makes one
(~442–455): same span, unbound False, SAVED blend weight 0, and auto-exposure min = max = `pinned_ev100` from
`hangar_s3_plan.json`.
- Key its BlendWeight `[(W0,0),(W1,1)]`, AUTO, to match the other hangars after step 1.
- Append a pre-scene drive for it to the `S3 Arrival`'s `pre_scene_float_drives`, as step 1 does. Keep the existing
  entries and assert their count is unchanged.
- The strike stays at that pinned exposure, so it READS as a blast. Don't key exposure at the strike.

## Prerequisites (guard)
- Step 1 applied to S3: the root keys are `[(W0,−90),(W1,0)]`.
- `s3_cast_reveal_record.json` exists.
- No actor already carries a `S3 Strike` label or `S3 Hangar Pinned Exposure`.

## Traps
1. Never open Sequencer: asset API only.
2. Guards:
   - world `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
   - no PIE;
   - BOTH dirty lists empty;
   - no ZZ_/TEMP_ actors;
   - record absent.
3. Back up first to `Backups/PreS3Strike-<stamp>/`: the level, LS_S3_HangarRise, the record.
4. Save ONLY the level and LS_S3_HangarRise. Never Save All.
5. Read-back before saving:
   - every actor's relative transform (±0.1 cm, ±0.1°);
   - the landed-pose aim (dot with the target direction > 0.999);
   - intensity, units, temperature, shadows;
   - every key (1 frame, 1e-3);
   - the drives count and entries;
   - the exposure settings.
   - Any mismatch: stop, no save.
6. The done line `S3_STRIKE_DONE|run=<HHMMSS>|...` carries a post-run census of BOTH packages.
7. The revert destroys the recorded actors and removes their bindings and the added drive, gated on a read-back.
8. Every number in the table is a module-level constant, so a tuning re-run is a one-line edit plus revert/apply.

## References
- `hangar_build.py`: light helpers, the PPV, keying.
- `s4_predrive_author_apply.py`: drives, guards, record/revert, runners, `.name`, `conv_guid_to_string`.

## Harness `Saved/CodexStructure/test_s3_strike_plan.py` (plain Python)
Keep these pure: the root-relative → landed-world transform, the look-at rotation, and the key planning.
- **POSITIVE:**
  - every light's landed forward vector hits its target within 0.1°;
  - the strike keys start at STRIKE_S;
  - exactly one shadowed light.
- **NEGATIVE, each must FAIL:**
  - a) aiming computed with the root at −90 (the rest pose) misses by about 90°;
  - b) STRIKE_S ≤ REVEAL_S raises;
  - c) two shadowed lights raises.

Deliver: the script, apply/revert/dry-run runners with request JSONs, and the harness. Run the harness and report its
lines verbatim. Don't run Unreal.

Final message:
- files;
- harness output;
- what you couldn't verify.
