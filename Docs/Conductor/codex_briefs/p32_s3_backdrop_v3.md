# P32: S3 backdrop v3 = Gary's new deep-ocean painting (9 Oct)
Source: DerivedAssets/S3Shore/backdrop_v3/backdrop_v3_src.jpg (1696x2528, copied from Gary's Downloads/bwsdst-wbuvuv.jpg).
Precedent pipeline: Tools/FlatV3/build_scene3_backdrop.py (Real-ESRGAN x4 tiled -> 2x intermediate -> non-uniform POT
4096x8192; model D:\PussStageTools\FlatV3\models\RealESRGAN_x4plus.pth; CUDA). The current backdrop actor is "S3 Backdrop"
(Saved/CodexConductor/s3_backwall_marble.py docstring; MI_S3_OpalBeach_Backdrop child per S3_MURAL_LOWER_2026-10-07.md); the
S3 exit-door leaf crops its art from the backdrop image (Tools/FlatV3/build_s3_exit_door_crop.py, rect
[0.42525,0.8485,0.57475,0.99817], built for BACKDROP_BOTTOM_Z_CM -5; the mural was later lowered: read S3_MURAL_LOWER_2026-10-07.md).
Job (offline; DO NOT run CUDA/GPU work: Gary may be in PIE; prove the code on a tiny CPU-sized fixture only):
1. Tools/FlatV3/build_scene3_backdrop_v3.py: crop to exact 2:3 (report the crop box), NO local stroke edits (paint as-is),
   Real-ESRGAN 2x via the same function, POT 4096x8192 output + QA sheet; args --input/--output/--dry.
2. A UE tool s3_backdrop_v3_ue.py DRY/APPLY/REVERT: create-only texture import (settings copied from the live current
   backdrop texture, read live), a NEW child MI of the current backdrop MI with only the texture param swapped, assign to
   "S3 Backdrop" (record old material); re-run the exit-door crop against the NEW image and swap the leaf texture likewise
   (create-only). Census: new assets + map only. House rules incl. rule 9.
3. Harness +/- controls (crop ratio, POT size, param-swap only, leaf crop rect recomputed from the lowered mural offset).
Report the conductor's run order (GPU upscale step first, after Gary leaves).
