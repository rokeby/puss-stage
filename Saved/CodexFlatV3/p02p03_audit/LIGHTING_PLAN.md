# P02/P03 P01-style lighting audit and plan

Date: 2026-10-08. Offline/read-only. This file proposes values and conductor gates; it does not authorize or perform an Unreal write.

## Current-state verdict

- **Measured:** P02 currently has 270 light attachments and 47 non-lights across 23 wing rows. Its 6 Oct P01-rig-pattern APPLY added/read back 121 managed roles (`E:/PussStage/Saved/CodexConductor/p02_rig_pattern_report_APPLY_20261006-223825.json:1`; current labels in `E:/PussStage/Saved/CodexFlatV3/rzswap/rzswap_dry_P02_LATEST.json:1`).
- **Measured:** P03 is already P01-structured and saved/read-back verified: 377 P01-structure lights were added, 286 replaced lights removed, and special/non-light rows preserved. Current reconstructed total is 443 lights plus 67 non-lights. The APPLY saved only Show+level with an empty final dirty census (`E:/PussStage/Saved/CodexConductor/p03_lighting_as_p01_report_APPLY_20261008-051137.json:1`).
- **Measured:** P03 copied P01 source ordinals 1?21 without wrapping, retained P03 role colours (95 dominant-colour fallbacks), matched four BeamLook actors at bays 4/8/13/18, and suppressed three unmatched P03 Smoke Test actors (`p03_lighting_as_p01_report_APPLY_20261008-051137.json:1`).
- **Inferred / not accepted:** saved readback proves authored state, not the intended rendered look. It remains UNCLEAR whether the all-row CROSS roles conflict visually with Gary?s ?20% of L/R side lighting? direction, and whether P02 rakes avoid shooting across the corridor (`E:/PussStage/Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:220-222`; `GARY_PIE_NOTES_2026-10-05.md:230-232`).

## What ?P01 style? contains

The ranges below are **measured** from the saved P01 rig record; positions are passage-relative centimetres and intensities are the saved candela values. P03 copied these structural values, then remapped colour from P03 roles (`E:/PussStage/Saved/CodexConductor/p01_rig_pattern_record.json:1`; `E:/PussStage/Saved/CodexConductor/p03_lighting_as_p01.py:267-324`).

| Family / roles | Type and placement | Intensity min/median/max | Colour / motion |
|---|---|---:|---|
| CROSS +Y/-Y | Spots; abs Y 10.5?15.2 m, Z 7.2?13.8 m | +Y 1.8/2.1/2.6; -Y 9.6/12.1/14.4 | P01 mint/coral; steady flicker function |
| LOW +Y/-Y | Rects; abs Y 6.3?9.2 m, Z 2.1?2.7 m | +Y 3.1/4.0/4.7; -Y 0.6/0.6/0.8 | P01 warm/black; slow or breath |
| ENTRY top/fwd/high | Spots at centre/top and both sides, Z 9.5?21.7 m | 3.4?70 (one high outlier 2000) | warm amber/peach/dark; steady/slow/breath/buzz; selected shadows |
| TOP_DOWN | Centre spot, Z 12.0?12.4 m | 2.4/2.9/3.4 | cool blue; fault function; shadows |
| FLOAT L/R | Ground spots, abs Y 3.6?7.1 m, Z 0.25 m | 5.1/6.1/6.9 | white, steady |
| TOP L/R | High side spots, Z 12.5?14.4 m | L 0/60.5/99; R 0/38.5/63 | warm/cool fairy-tale tops |
| LOW_SIDE key/fill | Side spots, abs Y 11.0?13.7 m, Z 2.0?9.0 m | key 256/448/576; fill 39/88/144 | orange/pink or cool fill; shadows |
| BEAM_R | Ground-side spots, Z 1.3?3.8 m | 2000/3250/4500 | mostly orange; gobo/flicker direction |
| Practical clamp/bulb | Points near floor, Z 1.0?2.2 m | clamp 520/845/1170; bulb 0 | warm/pink bodies; hum/steady |

- **Declaration-proven:** Gary?s P01 direction is dominant orange low-side light, fairy-tale red/green/white-yellow/pink tops after about bay 5, lower lights darkening after about bay 12, pale-pink practicals, and staggered beam pulses near bay 20 (`E:/PussStage/Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:254-259`).
- **Measured:** current P03 recolours key/fill to 1900 K orange and 7500 K cool, TOP L/R to 5600/7000 K, CROSS to red/yellow-green, ENTRY forward/LOW fallback to purple, and practicals to 2500?4000 K. Added rows use steady/slow/breath/fault/buzz/hum and four soft-slat functions; no `flash` or `slow_move` field is present in the 377 added specs (`p03_lighting_as_p01_report_APPLY_20261008-051137.json:1`).
- **Measured:** P01?s separate note-lamp record selected 30 lamps (13 glint, 10 bloom, 7 stay), but the P03 copy record does not prove those flash fields transferred. A generalized tool must explicitly serialize and test them if that behaviour is wanted (`E:/PussStage/Saved/CodexConductor/p01_note_lamps_record.json:1`; `p01_note_lamps.py:1-27`).

## Row census

### P02 current and proposed source density

`P01 add` is the exact source-light count for the corresponding P01 ordinal. Final P02 totals remain **UNCLEAR** until live DRY classifies preserved car/event/effect lights.

| P02 row | Current lights | Non-lights | P01 add |
|---|---:|---:|---:|
| P02 Wing 001 | 13 | 2 | 16 |
| P02 Wing 002 | 13 | 2 | 14 |
| P02 Wing 004 | 13 | 2 | 19 |
| P02 Wing 005 | 13 | 2 | 19 |
| P02 Wing 006 | 13 | 2 | 19 |
| P02 Wing 007 | 8 | 2 | 19 |
| P02 Wing 008 | 13 | 2 | 19 |
| P02 Wing 009 | 13 | 2 | 14 |
| P02 Wing 010 | 13 | 2 | 19 |
| P02 Wing 011 | 13 | 2 | 19 |
| P02 Wing 012 | 13 | 2 | 19 |
| P02 Wing 013 | 13 | 2 | 19 |
| P02 Wing 014 | 13 | 2 | 19 |
| P02 Wing 003 | 12 | 2 | 18 |
| P02 Wing 015 | 11 | 2 | 19 |
| P02 Wing 016 | 10 | 2 | 18 |
| P02 Wing 017 | 10 | 2 | 14 |
| P02 Wing 018 | 9 | 2 | 19 |
| P02 Wing 019 | 10 | 3 | 18 |
| P02 Wing 020 | 12 | 2 | 19 |
| P02 Wing 021 | 12 | 2 | 18 |
| P02 Wing 022 | 8 | 2 | 19 |
| P02 Wing 023 | 12 | 2 | 18 |

### P03 current saved state

| P03 row | Current lights | Non-lights | P01-structure added |
|---|---:|---:|---:|
| P03 Wing 001 | 23 | 3 | 16 |
| P03 Wing 003 | 19 | 3 | 14 |
| P03 Wing 002 | 22 | 3 | 19 |
| P03 Wing 004 | 20 | 3 | 19 |
| P03 Wing 005 | 20 | 3 | 19 |
| P03 Wing 006 | 21 | 3 | 19 |
| P03 Wing 007 | 20 | 3 | 19 |
| P03 Wing 008 | 22 | 4 | 14 |
| P03 Wing 009 | 20 | 3 | 19 |
| P03 Wing 010 | 22 | 3 | 19 |
| P03 Wing 011 | 21 | 3 | 19 |
| P03 Wing 012 | 20 | 3 | 19 |
| P03 Wing 013 | 21 | 4 | 19 |
| P03 Wing 014 | 22 | 3 | 18 |
| P03 Wing 015 | 24 | 3 | 19 |
| P03 Wing 016 | 21 | 3 | 18 |
| P03 Wing 017 | 20 | 4 | 14 |
| P03 Wing 018 | 22 | 4 | 19 |
| P03 Wing 019 | 22 | 3 | 18 |
| P03 Wing 020 | 21 | 3 | 19 |
| P03 Wing 021 | 20 | 3 | 18 |

## Proposed args/defaults

### P03: verify only

**Measured recommendation:** do not APPLY again. Leave the existing args in DRY, run only when the conductor wants a fresh saved-state comparison, and require zero unacknowledged drift before any decision. Existing tool defaults and safety contract are documented at `E:/PussStage/Saved/CodexConductor/p03_lighting_as_p01.py:79-95` and `E:/PussStage/Docs/Conductor/P16_P03_LIGHTING_2026-10-08.md:20-26`.

```json
{"mode":"DRY","match_p01_atmosphere":true,"expected_plan_sha256":"","confirm":""}
```

### P02: new generalized mode required

**Inferred proposal:** generalize `p03_lighting_as_p01.py` instead of stacking another rig-pattern APPLY. Defaults:

```json
{
  "mode": "DRY",
  "source_passage": "P01",
  "target_passage": "P02",
  "source_ordinal_policy": "same_ordinal_no_wrap",
  "colour_policy": "target_role_then_dominant",
  "aim_policy": "own_side_wing",
  "match_p01_atmosphere": true,
  "preserve_nonlights": true,
  "preserve_special_tokens": ["car","moving","move","event","fx","smoke","haze","fire","rain","spark","mote","pyro","polaroid","flash"],
  "expected_target_bays": 23,
  "expected_added_lights": 414,
  "max_added_lights": 414,
  "expected_plan_sha256": "",
  "confirm": ""
}
```

- **Declaration-proven constraint:** `own_side_wing` must turn CROSS/side roles into local rakes/uplights aimed at their own L or R wing; no beam may traverse L-to-R. Preserve the top wash, practicals, and uplights Gary requested (`GARY_PIE_NOTES_2026-10-05.md:220-222`).
- **Declaration-proven constraint:** reuse the existing P03 tool?s drift gate, special preservation, exact Show+level backup, narrow save, materialization, readback, and DRY/APPLY/REVERT markers (`E:/PussStage/Docs/Conductor/P16_P03_LIGHTING_2026-10-08.md:12-18`).
- **Measured requirement:** before APPLY, DRY must report every retained special and dominant-colour fallback, exact per-row totals, shadow totals, atmosphere changes, and a current preview. APPLY remains a conductor decision after rendered review.

## Counts versus known budgets

| Case | Managed/add lights | Total current lights | Relative to P06 rig 204 | Verdict |
|---|---:|---:|---:|---|
| P02 current rig-pattern | 121 | 270 | 0.59x managed | measured |
| P02 proposed P01 structure | 414 | UNCLEAR until DRY | 2.03x added | inferred plan; performance gate required |
| P03 current P01 structure | 377 | 443 | 1.85x added / 2.17x total | measured saved state |
| P06 rig-pattern precedent | 204 | not a hard cap | 1.00x | measured precedent |

- **Measured:** P06?s 204 is an expected managed-row count for 64 bays, not a declared passage budget (`E:/PussStage/Saved/CodexConductor/p06_rig_pattern_args.json:1`; `p06_rig_pattern_report_APPLY_20261006-223913.json:1`).
- **Declaration-proven:** the only explicit code cap found is the show-light event poller?s rotating slice above 1024 tracked lights; it is not a render/shadow acceptance budget (`E:/PussStage/Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageLightEvents.cpp:46-49`; `InfinityStageLightEvents.cpp:541-550`).
- **Measured risk:** P03?s copied set has 100 shadow-casting added lights and 141 shadow-casting current lights. A prior P03 log had a VSM one-pass max-lights overflow, but the note does not prove recurrence (`E:/PussStage/Docs/WingMateriality.md:294-298`).

## Required acceptance

1. **Measured requirement:** current DRY and exact state hash; no mutation.
2. **Measured requirement:** rendered stills/motion at early, middle, late rows; verify wing depth, no corridor-crossing beams, P03 20% side-light intent, fog, car/special motion, and practical bodies.
3. **Measured requirement:** GPU/VSM overlap and shadow-cost capture; compare P02/P03 with P06?s 204-row precedent, not as a cap.
4. **Open:** Gary/conductor decides whether current P03 is accepted or needs a sparse-side-light correction; P02 remains proposal-only until a generalized guarded tool exists.
