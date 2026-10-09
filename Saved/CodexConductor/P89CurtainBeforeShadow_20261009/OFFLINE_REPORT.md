# Job 89 offline report — 9 October 2026

No Unreal, MCP, PIE, Blender, Show asset, level, or `.uasset` was opened or
changed in this worktree.

## Timing table

`first lit` means the first display frame whose evaluated spot intensity is
greater than `1e-4`. At 25 fps the default 0.5 s margin rounds up to 13 frames.

| Interaction | Offline before evidence | Conditional repaired result |
| --- | --- | --- |
| I1 | **declaration-proven:** curtain spawn/GC begins 75, reaches hung pose 175; the job-44 pattern starts its fade at 175, so first lit is expected at 176: 1 frame / 0.04 s margin. (`curtain_sleight_record_I1.json`; `interaction_shadow_transition.py:177-224`) | **inferred until conductor DRY:** curtain ready 0, spot unchanged, expected first lit 176: 176 frames / 7.04 s margin. |
| I3 | **UNCLEAR:** common authored defaults are spawn 75 / hung 175 and job 44 uses play-start for the spot, but the claimed applied I3 transaction record is not present in this worktree. (`curtain_sleight.py:107-123,445-455,497-512`; `interaction_shadow_transition.py:177-224`) | **conditional:** only if live DRY finds the same fault, curtain ready becomes 0; spot timing stays unchanged unless it starts before frame 13. Otherwise the sequence is untouched. |
| I4 | **UNCLEAR:** same source-level expectation; applied I4 record absent here. | **conditional:** same selective rule as I3. |
| I5 | **UNCLEAR:** same source-level expectation; applied I5 record absent here. | **conditional:** same selective rule as I3. |

I2 is the **declaration-proven reference**, not a target: its recorded spot fade
is 175–275 and `I2Order` holds the curtain from frame 0
(`interaction_shadow_transition_record_I2.json`; `I2Order_20261008/i2_order.py:1-16,536-580`).

The conductor's `DRY ALL` is the authoritative per-interaction measured table:
it reads the live spawn, transform, Geometry Cache, `bHidden` visibility, and
evaluated intensity channels and writes `p89_curtain_before_shadow_dry_<run>.json`.

## Verification tiers

- **declaration-proven:** the tool permits only DRY/APPLY/REVERT, requires exact
  confirmations, rejects dirty/open/wrong-world state, saves only the selected
  Interaction sequence, and never creates/removes bindings or tracks
  (`p89_curtain_before_shadow.py:459-486,727-847`).
- **measured offline:** 32/32 harness checks pass, including curtain-after-spot
  refusal, curtain-before-spot acceptance, unchanged-interaction identity, I1
  ordering, channel suffixes, enum wrappers, visibility semantics, float
  tolerance, and preservation of later events (`test_p89.py`).
- **inferred:** the live tool calls and UE read-back are based on project
  precedents; this worktree did not run them.
- **not proved:** saved Unreal state and rendered visual acceptance. A green DRY
  or APPLY does not prove that the shadow visually lands on opaque cloth.
