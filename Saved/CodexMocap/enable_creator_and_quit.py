import pathlib
import sys
import unreal
project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
folder = str(project / 'Saved' / 'CodexMocap')
if folder not in sys.path:
    sys.path.insert(0, folder)
import creator_restart_gate
creator_restart_gate.execute()
