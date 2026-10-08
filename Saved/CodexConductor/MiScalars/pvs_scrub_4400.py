import os, runpy, unreal
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor", "MiScalars")
runpy.run_path(os.path.join(HERE, "pearl_variant_stills.py"), init_globals={"PVS_PHASE": "SCRUB", "PVS_SCENE_FRAME": 4400})
