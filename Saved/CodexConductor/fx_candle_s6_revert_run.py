import os
import runpy
import unreal

here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor")
runpy.run_path(os.path.join(here, "fx_candle_s6.py"),
               init_globals={"FX_CANDLE_S6_MODE": "REVERT"}, run_name="__main__")
