"""Cancel one verified pending read-only folder check; never terminate a thread or process."""
import ctypes
from ctypes import wintypes
import json
import pathlib
import re
import subprocess
import sys
from launch_empty_assembly import command_line, kernel

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
pid = 16800
assert json.loads((folder / 'assembly_launch.json').read_text())['editor_pid'] == pid
assert 'E:\\PussStage\\PussStage.uproject' in command_line(pid)
subprocess.run([sys.executable, str(folder / 'inspect_startup_filename.py')], check=True, stdout=subprocess.DEVNULL, timeout=50)
snapshot = (folder / ('startup_filename_' + str(pid) + '.txt')).read_text(encoding='utf-8')
assert 'ntdll!ZwQueryAttributesFile+0x14:' in snapshot
assert 'FEditorDirectories::LoadLastDirectories' in snapshot
assert '\\??\\G:\\Shared drives\\GZZ Studio ' in snapshot
assert 'ngs\\UE5.8\\PussStage\\Content' in snapshot
match = re.search(r'\(([0-9a-f]+)\.([0-9a-f]+)\): Wake debugger', snapshot)
assert match and int(match[1], 16) == pid
tid = int(match[2], 16)
kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenThread.restype = wintypes.HANDLE
kernel.GetProcessIdOfThread.argtypes = [wintypes.HANDLE]
kernel.GetProcessIdOfThread.restype = wintypes.DWORD
kernel.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
kernel.CancelSynchronousIo.restype = wintypes.BOOL
# Windows requires THREAD_TERMINATE access for cancellation; this code never calls TerminateThread.
handle = kernel.OpenThread(0x0800 | 0x0001, False, tid)
assert handle, ctypes.WinError(ctypes.get_last_error())
try:
    assert kernel.GetProcessIdOfThread(handle) == pid
    success = bool(kernel.CancelSynchronousIo(handle))
    error = 0 if success else ctypes.get_last_error()
    result = {'pid': pid, 'thread_id': tid, 'cancel_pending_read_requested': success, 'error': error}
    print(json.dumps(result), flush=True)
finally:
    kernel.CloseHandle(handle)
(folder / 'obsolete_folder_read_cancel.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
