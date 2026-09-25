"""User approved closing only stalled PussStage PID 58276 on 12 September."""
import ctypes
from ctypes import wintypes
import datetime
import json
from launch_empty_assembly import ROOT, kernel, editors, command_line, run

pid = 58276
running = editors()
print('CURRENT_EDITORS', json.dumps(running), flush=True)
target = next((p for p in running if p['pid'] == pid), None)
cache = json.loads((ROOT / 'Saved/SourceControl/UncontrolledChangelists.json').read_text(encoding='utf-8-sig'))
assert not any(f.startswith('G:/') for c in cache['changelists'] for f in c['files']), 'Stale paths remain'
if target:
    line = command_line(pid)
    assert 'E:\\PussStage\\PussStage.uproject' in line and '/Engine/Maps/Entry' in line, line
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    handle = kernel.OpenProcess(0x1000 | 0x100000 | 0x1, False, pid)
    assert handle, ctypes.WinError(ctypes.get_last_error())
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        assert kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times))
        ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        created = datetime.datetime.fromtimestamp((ticks - 116444736000000000) / 10000000, datetime.timezone.utc)
        assert abs((created - datetime.datetime(2026, 9, 12, 22, 20, 45, tzinfo=datetime.timezone.utc)).total_seconds()) < 2, created
        assert kernel.TerminateProcess(handle, 1), ctypes.WinError(ctypes.get_last_error())
        assert kernel.WaitForSingleObject(handle, 30000) == 0, 'Exit not confirmed; refusing restart'
        print('APPROVED_STALLED_STARTUP_CLOSED', pid, created.isoformat(), flush=True)
    finally:
        kernel.CloseHandle(handle)
else:
    print('Approved PID is already closed; no process terminated', flush=True)
run()
