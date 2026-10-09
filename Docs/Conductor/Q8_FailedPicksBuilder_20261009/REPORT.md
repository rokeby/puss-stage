# Q8 failed-picks builder — offline handoff

Run: `Q8PROOF-20261009-01`. No Blender or Unreal was opened or invoked.

## P01 pick 9 diagnosis

- **Measured:** the existing pilot and `_o2` SkinColor images differ at only 12 pixels outside the validator's 130 cm cluster-union mask; every observed channel delta is one byte. A same-profile pilot replay from the recorded seed differs from the approved pilot at 33 pixels, also by at most one byte (`evidence.json:7-13`).
- **Declaration-proven:** the validator requires byte equality outside the fixed cluster unions (`Tools/FlatV3/rebuild_pilot_organic_skins.py:268-310`), while the `_o2` build deliberately uses the same seed and restores the RNG state after its side-stream noise (`Tools/FlatV3/build_skin.py:458-500`).
- **Inferred:** the failure is sparse SkinColor replay drift across separate image builds, not an input, seed, alpha, peel-percentage, or cluster-centre mismatch. The failure report independently records all five of those checks as passing (`DerivedAssets/FlatV3/Realism_20261007/P01_classical_garden/RZ_BUILD_REPORT_v2_P01.json`).
- **Proposed minimal fix (not applied):** after generating `_o2`, copy the approved pilot SkinColor bytes outside the existing 130 cm union into `_o2`, then run the unchanged validator. This preserves the exact intended contract and does not loosen a gate. The harness's positive control proves that composite is exact outside while retaining changed `_o2` pixels inside (`DerivedAssets/FlatV3/Realism_20261007/_tools_v2/test_q8_failed_picks_offline.py`).

## P03 pick 64

- **Declaration-proven:** the production seed derives deterministically from the owner (`DerivedAssets/FlatV3/Realism_20261007/_tools_v2/rz2_build_one.py:82-83`); the seam gate remains `<= 40 cm` (`Tools/FlatV3/build_skin.py:969-973`).
- **Measured:** seed `20301663` produces 40.527344 cm and fails. The documented rule tests `base+n` in ascending order from `n=1`; the first candidate, `20301664`, produces 35.644531 cm and passes (`evidence.json:17-24`).
- **Declaration-proven:** the selected seed and rule are recorded as an owner-only override (`DerivedAssets/FlatV3/Realism_20261007/_tools_v2/rz2_common.py`).

## Valances 2, 10 and 61

- **Declaration-proven:** all three are opt-in owner overrides; other cards retain the portrait default (`DerivedAssets/FlatV3/Realism_20261007/_tools_v2/rz2_common.py`).
- **Measured:** a 4096×2048 landscape SkinColor gives texel aspects 1.473714, 1.627879 and 1.465909 respectively, all inside the unchanged `0.2 < aspect < 5.0` gate (`evidence.json:27-52`; `Tools/FlatV3/tk_build_v3_flat_t5j.py:51-65`). Full pilot plus isotropic skin-stage runs passed 4/4, including exact outside-union validation (`evidence.json:54-59`).

## Tool contract and post-curtain-bake order

`q8_skin_stage.py` has guarded `DRY`, `APPLY`, and `REVERT` modes. APPLY records the offline dirty-package census as not applicable, writes the record before mutation, moves any prior Q8 outputs into `Backups/PreQ8FailedPicks-<run>`, writes only `skin_q8`/`skin_v3_q8`, reads back its record, and emits `Q8_FAILED_PICKS_SKIN_STAGE_SUCCESS`. REVERT requires its own distinct confirm string and never permanently deletes the replaced outputs.

After the curtain bake, from `E:\PussStage`, run in this order:

```powershell
& 'D:\PussStageTools\FlatV3\venv\Scripts\python.exe' 'DerivedAssets\FlatV3\Realism_20261007\_tools_v2\q8_skin_stage.py' APPLY --root 'E:\PussStage' --run-id 'Q8APPLY-YYYYMMDD-HHMM' --confirm APPLY_Q8_FAILED_PICKS_SKINS
& 'D:\PussStageTools\FlatV3\venv\Scripts\python.exe' 'DerivedAssets\FlatV3\Realism_20261007\_tools_v2\rz2_build_one.py' P03_stones_coast_sheds P03_real_64_weathered_wooden_pallet_L
& 'D:\PussStageTools\FlatV3\venv\Scripts\python.exe' 'DerivedAssets\FlatV3\Realism_20261007\_tools_v2\rz2_build_one.py' valances_upper_wings VAL_real_2_black_velvet_curtain_C
& 'D:\PussStageTools\FlatV3\venv\Scripts\python.exe' 'DerivedAssets\FlatV3\Realism_20261007\_tools_v2\rz2_build_one.py' valances_upper_wings VAL_real_10_ornate_curtain_valance_C
& 'D:\PussStageTools\FlatV3\venv\Scripts\python.exe' 'DerivedAssets\FlatV3\Realism_20261007\_tools_v2\rz2_build_one.py' valances_upper_wings VAL_real_61_purple_velvet_curtain_C
```

## Verification

- **Measured:** offline harness 13/13, with explicit negative and positive controls (`evidence.json:61-65`).
- **Measured:** full pure-Python skin stage 4/4; no Blender/Unreal (`evidence.json:2-5`, `evidence.json:54-59`).
- **Unclear/open:** P01's baseline-composite fix is intentionally a proposal only. Decide whether to apply it narrowly to pick 9 or make it the general isotropic SkinColor preservation rule before rerunning P01.
