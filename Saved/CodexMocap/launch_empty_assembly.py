"""Launch the approved PussStage retry through a normal command-line process."""
import ctypes
from ctypes import wintypes
import datetime
import json
import pathlib
import subprocess

ROOT = pathlib.Path('E:/PussStage')
ENGINE = pathlib.Path('D:/Unreal Engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe')
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll = ctypes.WinDLL('ntdll')

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD),
        ('szExeFile', wintypes.WCHAR * 260)]

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [('Length', wintypes.USHORT), ('MaximumLength', wintypes.USHORT), ('Buffer', ctypes.c_void_p)]

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD)] + [
        (n, ctypes.c_ulonglong) for n in ['ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile', 'ullAvailPageFile',
        'ullTotalVirtual', 'ullAvailVirtual', 'ullAvailExtendedVirtual']]

kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
ntdll.NtQueryInformationProcess.restype = wintypes.LONG

def command_line(pid):
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.ULONG()
        ntdll.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))
        assert 0 < size.value < 131072, (pid, size.value)
        buffer = ctypes.create_string_buffer(size.value)
        status = ntdll.NtQueryInformationProcess(handle, 60, buffer, len(buffer), ctypes.byref(size))
        assert status == 0, (pid, status)
        value = UNICODE_STRING.from_buffer(buffer)
        return ctypes.wstring_at(value.Buffer, value.Length // 2)
    finally:
        kernel.CloseHandle(handle)

def editors():
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    assert snapshot != wintypes.HANDLE(-1).value
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    result = []
    try:
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.lower() == 'unrealeditor.exe':
                result.append({'pid': entry.th32ProcessID, 'command_line': command_line(entry.th32ProcessID)})
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return result

def run():
    running = editors()
    # A project chooser opened without a project argument is not an editing session.
    # Never start another editor against an already-open project.
    for p in running:
        assert p['command_line'].strip().strip('"').lower() == str(ENGINE).replace('/', '\\').lower(), p
    memory = MEMORYSTATUSEX()
    memory.dwLength = ctypes.sizeof(memory)
    assert kernel.GlobalMemoryStatusEx(ctypes.byref(memory))
    report = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'existing_project_choosers': running,
        'available_physical_gib': memory.ullAvailPhys / 2**30,
        'available_commit_gib': memory.ullAvailPageFile / 2**30,
        'commit_limit_gib': memory.ullTotalPageFile / 2**30,
        'world': '/Engine/Maps/Entry', 'graphics_settings': 'unchanged', 'assembly_settings': 'OPTIMIZED/MEDIUM'}
    process = subprocess.Popen([str(ENGINE), str(ROOT / 'PussStage.uproject'), '/Engine/Maps/Entry'],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
    report['editor_pid'] = process.pid
    (ROOT / 'Saved/CodexMocap/assembly_launch.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)

if __name__ == '__main__':
    run()
