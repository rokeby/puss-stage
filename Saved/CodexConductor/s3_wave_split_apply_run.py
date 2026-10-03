"""Run the reviewed S3 wave-split tool in APPLY mode."""
import runpy

runpy.run_path("E:/PussStage/Saved/CodexConductor/s3_wave_split_apply.py",
               init_globals={"S3_WAVE_SPLIT_APPLY": True})
