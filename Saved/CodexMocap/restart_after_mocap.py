"""One-shot background helper: wait, request graceful shutdown via MCP, relaunch, verify."""
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import time
import traceback
import urllib.request
import restart_common as common

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel.WaitForSingleObject.restype = wintypes.DWORD
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.SetThreadExecutionState.argtypes = [wintypes.DWORD]
kernel.SetThreadExecutionState.restype = wintypes.DWORD


def send(payload, session=None, timeout=30):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if session:
        headers['Mcp-Session-Id'] = session
    req = urllib.request.Request('http://127.0.0.1:8000/mcp', json.dumps(payload).encode(), headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode('utf-8')
        if not raw.strip():
            value = None
        elif raw.lstrip().startswith('{'):
            value = json.loads(raw)
        else:
            entries = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')]
            value = entries[-1] if entries else None
        if value and 'error' in value:
            raise RuntimeError(str(value['error']))
        return value, response.headers.get('Mcp-Session-Id')


def call_script(name):
    _, session = send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2024-11-05', 'capabilities': {},
        'clientInfo': {'name': 'PussStageAuthorizedCreatorRestart', 'version': '1.0'}}})
    send({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, session)
    response, _ = send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
        'name': 'call_tool', 'arguments': {'toolset_name': 'MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset',
        'tool_name': 'ExecuteProjectPythonFile', 'arguments': {'relativeSavedPath': 'CodexMocap/' + name}}}}, session, timeout=45)
    assert response and not response.get('result', {}).get('isError'), str(response)
    result = response['result']
    for block in result.get('content', []):
        if block.get('type') == 'text':
            try:
                returned = json.loads(block['text']).get('returnValue', {})
            except (ValueError, AttributeError):
                continue
            if 'bSuccess' in returned:
                assert returned['bSuccess'], str(returned)
                return returned
    raise RuntimeError('MCP did not return a project-Python execution result: ' + str(response))


def old_process_handle(plan):
    handle = kernel.OpenProcess(0x00100000 | 0x1000, False, plan['old_editor_pid'])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        name = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(name))
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        assert os.path.normcase(name.value) == os.path.normcase(str(common.ENGINE)), name.value
        return handle
    except Exception:
        kernel.CloseHandle(handle)
        raise


def has_exited(handle):
    result = kernel.WaitForSingleObject(handle, 0)
    if result == 0xFFFFFFFF:
        raise ctypes.WinError(ctypes.get_last_error())
    return result == 0


def run():
    plan = common.read(common.PLAN)
    handle = None
    new_editor = None
    details = {'helper_pid': os.getpid()}
    try:
        assert plan['authorized'] is True
        assert common.ENGINE.is_file() and common.PROJECT.is_file()
        handle = old_process_handle(plan)
        kernel.SetThreadExecutionState(0x80000001)
        common.report('waiting_for_verified_batch', plan, **details)
        deadline = time.monotonic() + 6 * 3600
        finished_since = None
        while time.monotonic() < deadline:
            if has_exited(handle):
                raise RuntimeError('The original Editor exited before the authorized restart gate; no new Editor was launched')
            try:
                status = common.read(common.FOLDER / 'batch_status.json')
                audit_path = common.FOLDER / 'batch_final_audit.json'
                audit = common.read(audit_path) if audit_path.exists() else None
            except (OSError, json.JSONDecodeError):
                time.sleep(2)
                continue
            if not status.get('running'):
                finished_since = finished_since or time.monotonic()
                issues = common.batch_issues(status, audit)
                if not issues:
                    break
                if time.monotonic() - finished_since > 120:
                    raise RuntimeError('; '.join(issues))
            common.report('waiting_for_verified_batch', plan, current=status.get('current'),
                          completed=status.get('completed'), failed=status.get('failed'), **details)
            time.sleep(10)
        else:
            raise RuntimeError('The six-hour wait expired; the Editor was left untouched')

        common.report('requesting_restart', plan, **details)
        try:
            call_script('enable_creator_and_quit.py')
        except Exception:
            # Normal shutdown may close MCP after the script has already succeeded.
            if not common.GATE.exists():
                raise
            gate = common.read(common.GATE)
            if gate.get('token') != plan['token'] or gate.get('state') not in ('quit_scheduled', 'quit_called'):
                raise
        gate = common.read(common.GATE)
        assert gate['token'] == plan['token'] and gate['pid'] == plan['old_editor_pid']
        details['backup'] = gate['backup']
        common.report('waiting_for_normal_editor_exit', plan, **details)
        deadline = time.monotonic() + 5 * 60
        while not has_exited(handle):
            gate = common.read(common.GATE)
            if gate['state'] == 'shutdown_cancelled':
                raise RuntimeError('Restart cancelled: ' + '; '.join(gate['issues']))
            if time.monotonic() >= deadline:
                raise RuntimeError('Unreal did not close normally within five minutes; it was not force-stopped')
            time.sleep(1)

        # Character creation also needs the optional Core Data. Its Launcher
        # installation must take place while Unreal is closed.
        current_plan = common.read(common.PLAN)
        if current_plan.get('require_core_data_installation'):
            common.report('editor_closed_waiting_for_core_data_installation', plan, **details)
            ready_path = common.FOLDER / 'creator_core_data_ready.json'
            install_deadline = time.monotonic() + 8 * 3600
            while time.monotonic() < install_deadline:
                if ready_path.exists():
                    try:
                        ready = common.read(ready_path)
                        if ready.get('token') == plan['token'] and ready.get('verified'):
                            break
                    except (OSError, json.JSONDecodeError):
                        pass
                time.sleep(5)
            else:
                raise RuntimeError('Core Data installation was not confirmed; the project was left closed')

        # No shell and no force-stop; launch only after the original process has exited.
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 1
        new_editor = subprocess.Popen([str(common.ENGINE), str(common.PROJECT), plan['world']],
            cwd=str(common.PROJECT.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, startupinfo=startup,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        details['new_editor_pid'] = new_editor.pid
        common.report('editor_reopened_waiting_for_mcp', plan, **details)
        deadline = time.monotonic() + 20 * 60
        last_error = None
        while time.monotonic() < deadline:
            if new_editor.poll() is not None:
                raise RuntimeError('The restarted Editor exited with code ' + str(new_editor.returncode))
            try:
                call_script('verify_creator_restart.py')
                verification = common.read(common.VERIFIED)
                assert verification['token'] == plan['token']
                assert verification['pid'] == new_editor.pid, 'MCP is serving a different new Editor process'
                common.report('complete_creator_enabled_and_restart_verified', plan, verification=verification, **details)
                return
            except Exception as exc:
                last_error = str(exc)
                common.report('editor_reopened_waiting_for_mcp', plan, last_check=last_error, **details)
            time.sleep(10)
        raise RuntimeError('The Editor reopened but Creator verification did not pass: ' + str(last_error))
    except Exception as exc:
        common.report('attention_required', plan, error=str(exc), traceback=traceback.format_exc(), **details)
        raise
    finally:
        if handle:
            kernel.CloseHandle(handle)
        kernel.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    run()
