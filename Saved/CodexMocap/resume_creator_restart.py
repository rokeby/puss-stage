"""Continue the authorized restart using Python outside the UE installation.

Epic Launcher regards every executable below the engine directory as a running
engine app. This helper deliberately uses the machine's independent Python.
"""
import os
import pathlib
import subprocess
import sys
import time
import traceback
import restart_common as common
from restart_after_mocap import call_script, kernel


def run():
    plan = common.read(common.PLAN)
    details = {'helper_pid': os.getpid(), 'helper_python': sys.executable,
               'backup': common.read(common.GATE)['backup']}
    try:
        assert plan['authorized'] is True
        assert not pathlib.Path(sys.executable).resolve().is_relative_to(common.ENGINE.parents[3]), sys.executable
        assert not common.batch_issues(common.read(common.FOLDER / 'batch_status.json'),
                                       common.read(common.FOLDER / 'batch_final_audit.json'))
        assert common.read(common.GATE)['state'] == 'quit_called'
        assert not common.VERIFIED.exists(), 'A restart has already completed'
        kernel.SetThreadExecutionState(0x80000001)
        ready_path = common.FOLDER / 'creator_core_data_ready.json'
        deadline = time.monotonic() + 24 * 3600
        while time.monotonic() < deadline:
            if ready_path.exists():
                ready = common.read(ready_path)
                if ready.get('token') == plan['token'] and ready.get('verified'):
                    break
            common.report('editor_closed_waiting_for_core_data_installation', plan, **details)
            time.sleep(15)
        else:
            raise RuntimeError('Core Data was not confirmed within 24 hours; the project remains closed')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 1
        editor = subprocess.Popen([str(common.ENGINE), str(common.PROJECT), plan['world']],
            cwd=str(common.PROJECT.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, startupinfo=startup,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        details['new_editor_pid'] = editor.pid
        deadline = time.monotonic() + 20 * 60
        last_error = None
        while time.monotonic() < deadline:
            if editor.poll() is not None:
                raise RuntimeError('Restarted Editor exited with code ' + str(editor.returncode))
            try:
                call_script('verify_creator_restart.py')
                verification = common.read(common.VERIFIED)
                assert verification['token'] == plan['token'] and verification['pid'] == editor.pid
                common.report('complete_creator_enabled_and_restart_verified', plan,
                              verification=verification, **details)
                return
            except Exception as exc:
                last_error = str(exc)
                common.report('editor_reopened_waiting_for_mcp', plan, last_check=last_error, **details)
            time.sleep(10)
        raise RuntimeError('Creator verification did not pass: ' + str(last_error))
    except Exception as exc:
        common.report('attention_required', plan, error=str(exc), traceback=traceback.format_exc(), **details)
        raise
    finally:
        kernel.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    run()
