"""Read-only non-suspending thread-stack snapshot of the verified PussStage startup."""
import json
import pathlib
import subprocess
import urllib.request
from launch_empty_assembly import command_line

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
pid = 58276
line = command_line(pid)
assert 'PussStage.uproject' in line and '/Engine/Maps/Entry' in line, line
commands = folder / 'startup_stack_commands.txt'
commands.write_text('~* kb 14\nqd\n', encoding='ascii')
log = folder / 'startup_thread_stacks_58276.txt'
with log.open('w', encoding='utf-8') as output:
    try:
        run = subprocess.run(['C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/cdb.exe',
            '-pvr', '-p', str(pid), '-sins', '-netsyms:no', '-cf', str(commands)],
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=45)
        result = {'pid': pid, 'debugger_exit_code': run.returncode, 'stack_file': str(log)}
    except subprocess.TimeoutExpired:
        result = {'pid': pid, 'stack_file': str(log), 'debugger_timeout': True}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for url in ['http://127.0.0.1:8558/health/ready', 'http://[::1]:8558/health/ready']:
    try:
        with opener.open(url, timeout=3) as response:
            result[url] = {'status': response.status, 'body': response.read(200).decode('utf-8', errors='replace')}
    except Exception as exc:
        result[url] = str(exc)
(folder / 'startup_wait_probe.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
