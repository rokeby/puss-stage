"""Wait for normal exit, repair generated folder prefs after shutdown, then reopen."""
import pathlib
import subprocess
import sys
import time
from launch_empty_assembly import ROOT, editors, run

deadline = time.monotonic() + 60
while any(p['pid'] == 16800 for p in editors()):
    if time.monotonic() > deadline:
        raise RuntimeError('Normal editor exit not confirmed; no process terminated and no editor launched')
    time.sleep(1)
assert not editors(), 'Another editor is open; do not duplicate the project'
subprocess.run([sys.executable, str(ROOT / 'Saved/CodexMocap/repair_remembered_project_folders.py')], check=True)
run()
