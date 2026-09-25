"""Bounded cancellation of only repeatedly verified stale-folder startup reads."""
import pathlib
import subprocess
import sys
import time

script = pathlib.Path(__file__).with_name('release_obsolete_folder_query.py')
for index in range(10):
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=55)
    print(index + 1, result.stdout.strip(), result.stderr[-800:], flush=True)
    if result.returncode:
        print('Stopped: startup is no longer at the exact verified stale-folder read.', flush=True)
        break
    time.sleep(1)
