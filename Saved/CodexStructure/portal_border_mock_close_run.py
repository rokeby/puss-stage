"""Run portal_border_mock_bench.py in mode 'close'."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "portal_border_mock_bench.py"), init_globals={"BENCH_MODE": "close"})
