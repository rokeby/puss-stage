# Lighting drift: scores records vs live Show (DRIFT-20261006-023111)

Generated read-only by `Saved/CodexConductor/lighting_drift_report.py` (run `DRIFT-20261006-023111`). Drift = the scores REVERT's own comparison (`_require_attachment_rows_equal`, lighting_looks_apply.py:1277); every target cue is checked, not just the first. Classes are attributed from other tools' records; UNKNOWN is *inferred* to be a hand edit.

Census before == after: True. Full JSON: `Saved/CodexConductor/lighting_drift_report.json`.

## P01

- targets 48, drifted cues 42; REVERT would stop at: `REVERT_CURRENT_STATE_DRIFT|cue=P01 Wing 001`
- lights by class: RIG_LAMP_DROP 80, UNKNOWN (likely hand edit) 4
- fields by class: OPENING_SEQUENCE_WARMERS 4, RIG_LAMP_DROP 80, UNKNOWN (likely hand edit) 21

**Hand edits (UNKNOWN, inferred)**

| cue | light | slot | field: old -> new (field class if different) |
|---|---|---|---|
| P01 Wing 001 | P01 Wing 001 House L | RETAINED (pre-score, kept lit) | enabled: True -> False (OPENING_SEQUENCE_WARMERS)<br>lighting.attenuation_radius_cm: 4500 -> 3468<br>lighting.inner_cone_angle_degrees: 20 -> 12.42 (OPENING_SEQUENCE_WARMERS)<br>lighting.intensity: 1740 -> 800<br>lighting.outer_cone_angle_degrees: 33 -> 14.94<br>relative_transform.location[0]: -2350 -> -2350<br>relative_transform.location[1]: -650 -> -664.3<br>relative_transform.location[2]: 1265 -> 1265<br>relative_transform.rotation_xyzw: [0.03269, -0.1688, -0.1873, -0.9671] -> [0.03269, -0.1688, -0.1873, -0.9671] |
| P01 Wing 001 | P01 Wing 001 House R | RETAINED (pre-score, kept lit) | enabled: True -> False (OPENING_SEQUENCE_WARMERS)<br>lighting.attenuation_radius_cm: 4500 -> 3025<br>lighting.inner_cone_angle_degrees: 20 -> 12.78 (OPENING_SEQUENCE_WARMERS)<br>lighting.intensity: 1740 -> 800<br>lighting.outer_cone_angle_degrees: 33 -> 15.94<br>relative_transform.location[0]: -2350 -> -2350<br>relative_transform.location[1]: 650 -> 650<br>relative_transform.location[2]: 1265 -> 1265 |
| P01 Wing 001 | P01 SCORE B01 VOID PRACTICAL_DEAD | PRACTICAL_DEAD | lighting.color: [1, 0.72, 0.4, 1] -> [1, 0.4793, 0.1329, 1]<br>relative_transform.location[0]: -10 -> 14.77<br>relative_transform.location[1]: 700 -> 700<br>relative_transform.location[2]: 115 -> 115 |
| P01 Wing 002 | P01 SCORE B02 GAP PRACTICAL_GLIMMER | PRACTICAL_GLIMMER | lighting.color: [1, 0.7, 0.4, 1] -> [1, 0.4508, 0.1329, 1]<br>relative_transform.scale[0]: 1 -> 1<br>relative_transform.scale[1]: 1 -> 1<br>relative_transform.scale[2]: 1 -> 1 |

## P02

- targets 23, drifted cues 17; REVERT would stop at: `REVERT_CURRENT_STATE_DRIFT|cue=P02 Wing 001`
- lights by class: RIG_LAMP_DROP 33, UNKNOWN (likely hand edit) 12
- fields by class: RIG_LAMP_DROP 33, UNKNOWN (likely hand edit) 58

**Hand edits (UNKNOWN, inferred)**

| cue | light | slot | field: old -> new (field class if different) |
|---|---|---|---|
| P02 Wing 001 | P02 SCORE B01 THEATRICAL BEAM_R | BEAM_R | lighting.color: [1, 0, 0.35, 1] -> [0.2307, 0.001518, 0.09759, 1]<br>lighting.inner_cone_angle_degrees: 2 -> 6<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: -1250 -> -1250<br>relative_transform.rotation_xyzw: [0.02685, -0.03437, -0.6151, -0.7873] -> [0.0283, -0.0332, -0.6481, -0.7603] |
| P02 Wing 001 | P02 SCORE B01 THEATRICAL PRACTICAL_CLAMP | PRACTICAL_CLAMP | lighting.color: [1, 0.66, 0.38, 1] -> [1, 0.3916, 0.1195, 1]<br>relative_transform.location[0]: -30 -> -30<br>relative_transform.location[1]: -720 -> -720<br>relative_transform.rotation_xyzw: [0, -0, 0, 1] -> [0, 0, 1.388e-16, 1] |
| P02 Wing 001 | P02 SCORE B01 THEATRICAL PRACTICAL_BULB_DEAD | PRACTICAL_BULB_DEAD | lighting.color: [0.55, 0.7, 1, 1] -> [0.2623, 0.4508, 1, 1]<br>relative_transform.location[0]: -20 -> -34.13<br>relative_transform.location[1]: 700 -> 706.4<br>relative_transform.rotation_xyzw: [0, -0, 0, 1] -> [0, 0, 1.388e-16, 1] |
| P02 Wing 002 | P02 SCORE B02 P02_LURID_POP BEAM_R | BEAM_R | lighting.color: [1, 0, 0.6, 1] -> [0.3663, 0.855, 0.2346, 1]<br>lighting.inner_cone_angle_degrees: 4 -> 12<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: -1250 -> -1250<br>relative_transform.rotation_xyzw: [0.066, -0.07035, 0.681, 0.7259] -> [0.066, -0.07035, 0.681, 0.7259] |
| P02 Wing 004 | P02 SCORE B03 THEATRICAL BEAM_R | BEAM_R | lighting.color: [1, 0, 0.35, 1] -> [0.2307, 0.001518, 0.09759, 1]<br>lighting.inner_cone_angle_degrees: 2 -> 6<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: 1250 -> 1250<br>relative_transform.rotation_xyzw: [0.02685, 0.03437, -0.6151, 0.7873] -> [0.02685, 0.03437, -0.6151, 0.7873] |
| P02 Wing 005 | P02 SCORE B04 P02_LURID_POP BEAM_R | BEAM_R | lighting.color: [0.3, 1, 0, 1] -> [0.07421, 1, 0, 1]<br>lighting.inner_cone_angle_degrees: 4 -> 12<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: 1250 -> 1250<br>relative_transform.rotation_xyzw: [0.06751, 0.07208, 0.6803, -0.7263] -> [0.06751, 0.07208, 0.6803, -0.7263] |
| P02 Wing 006 | P02 SCORE B05 THEATRICAL BEAM_R | BEAM_R | lighting.color: [1, 0, 0.35, 1] -> [0.2307, 0.001518, 0.09759, 1]<br>lighting.inner_cone_angle_degrees: 2 -> 6<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: -1250 -> -1250<br>relative_transform.rotation_xyzw: [0.02685, -0.03437, -0.6151, -0.7873] -> [0.02685, -0.03437, -0.6151, -0.7873] |
| P02 Wing 008 | P02 SCORE B07 THEATRICAL BEAM_R | BEAM_R | lighting.color: [1, 0, 0.35, 1] -> [0.2307, 0.001518, 0.09759, 1]<br>lighting.inner_cone_angle_degrees: 2 -> 6<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: -1250 -> -1250<br>relative_transform.rotation_xyzw: [0.02685, -0.03437, -0.6151, -0.7873] -> [0.02685, -0.03437, -0.6151, -0.7873] |
| P02 Wing 009 | P02 SCORE B08 P02_LURID_POP BEAM_R | BEAM_R | lighting.color: [1, 0, 0.6, 1] -> [0.01444, 0.1413, 0.03955, 1]<br>lighting.inner_cone_angle_degrees: 4 -> 12<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: -1250 -> -1250<br>relative_transform.rotation_xyzw: [0.06809, -0.07274, 0.68, 0.7264] -> [0.06809, -0.07274, 0.68, 0.7264] |
| P02 Wing 010 | P02 SCORE B09 THEATRICAL BEAM_R | BEAM_R | lighting.color: [1, 0, 0.35, 1] -> [0.2307, 0.001518, 0.09759, 1]<br>lighting.inner_cone_angle_degrees: 2 -> 6<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: 1250 -> 1250<br>relative_transform.rotation_xyzw: [0.02685, 0.03437, -0.6151, 0.7873] -> [0.02685, 0.03437, -0.6151, 0.7873] |
| P02 Wing 011 | P02 SCORE B10 P02_LURID_POP BEAM_R | BEAM_R | lighting.color: [0.3, 1, 0, 1] -> [0.07421, 1, 0, 1]<br>lighting.inner_cone_angle_degrees: 4 -> 12<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: 1250 -> 1250<br>relative_transform.rotation_xyzw: [0.06801, 0.07264, 0.68, -0.7264] -> [0.06801, 0.07264, 0.68, -0.7264] |
| P02 Wing 012 | P02 SCORE B11 THEATRICAL BEAM_R | BEAM_R | lighting.color: [1, 0, 0.35, 1] -> [0.2307, 0.001518, 0.09759, 1]<br>lighting.inner_cone_angle_degrees: 2 -> 6<br>relative_transform.location[0]: -150 -> -150<br>relative_transform.location[1]: -1250 -> -1250<br>relative_transform.rotation_xyzw: [0.02685, -0.03437, -0.6151, -0.7873] -> [0.02685, -0.03437, -0.6151, -0.7873] |

## P03

- targets 21, drifted cues 20; REVERT would stop at: `REVERT_CURRENT_STATE_DRIFT|cue=P03 Wing 001`
- lights by class: P03_HOUSING_DROP 14, RIG_LAMP_DROP 34
- fields by class: P03_HOUSING_DROP 14, RIG_LAMP_DROP 34

## P04

- targets 15, drifted cues 10; REVERT would stop at: `REVERT_CURRENT_STATE_DRIFT|cue=P04 Wing 008`
- lights by class: RIG_LAMP_DROP 20, UNKNOWN (likely hand edit) 1
- fields by class: RIG_LAMP_DROP 20, UNKNOWN (likely hand edit) 4

**Hand edits (UNKNOWN, inferred)**

| cue | light | slot | field: old -> new (field class if different) |
|---|---|---|---|
| P04 Wing 017 | P04 Wing 017 Blink Spot | RETAINED (pre-score, kept lit) | lighting.color: [1, 0.1356, 0.02732, 1] -> [0.521, 0.7231, 1, 1]<br>relative_transform.location[0]: -425.3 -> -425.3<br>relative_transform.location[1]: 1006 -> 1006<br>relative_transform.rotation_xyzw: [0.2632, 0.4089, -0.4729, 0.7348] -> [0.2632, 0.4089, -0.4729, 0.7348] |

## P05

- targets 93, drifted cues 76; REVERT would stop at: `REVERT_CURRENT_STATE_DRIFT|cue=P05 Wing 001`
- lights by class: RIG_LAMP_DROP 152
- fields by class: RIG_LAMP_DROP 152

## P06

- targets 55, drifted cues 26; REVERT would stop at: `REVERT_CURRENT_STATE_DRIFT|cue=P06 Wing 001`
- lights by class: RIG_LAMP_DROP 35, UNKNOWN (likely hand edit) 2
- fields by class: RIG_LAMP_DROP 35, UNKNOWN (likely hand edit) 2

**Hand edits (UNKNOWN, inferred)**

| cue | light | slot | field: old -> new (field class if different) |
|---|---|---|---|
| P06 Wing 055 | FX TEST - S6 Candle Light | RETAINED (pre-score, kept lit) | <row removed>: present -> absent |
| P06 Wing 055 | FX TEST - S6 Candle | None | <row removed>: present -> absent |

