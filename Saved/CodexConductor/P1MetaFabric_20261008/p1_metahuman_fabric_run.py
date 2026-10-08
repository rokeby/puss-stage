"""Run s3_sack_livecloth.py against the versioned P1 args without overwriting its historical args."""
import os
import runpy

os.environ["S3LIVESACK_ARGS"] = "E:/PussStage/Saved/CodexConductor/P1MetaFabric_20261008/p1_metahuman_fabric_args.json"
runpy.run_path("E:/PussStage/Saved/CodexConductor/s3_sack_livecloth.py", run_name="__main__")
