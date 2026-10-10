import os
import runpy
import unreal

here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(here, "passage_resize_dry_run.py"),
               init_globals={"PASSAGE_RESIZE_LABEL": "Passage 2"}, run_name="__main__")
