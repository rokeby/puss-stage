import os
import runpy
import unreal

here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexBeeSwarm")
runpy.run_path(os.path.join(here, "bee_swarm_sandbox.py"),
               init_globals={"BEE_SWARM_SANDBOX_MODE": "APPLY"}, run_name="__main__")
