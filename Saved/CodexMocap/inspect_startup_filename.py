"""Read only the pending file-query argument without suspending Unreal."""
import pathlib
import subprocess
import json
from launch_empty_assembly import command_line

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
pid = json.loads((folder / 'assembly_launch.json').read_text(encoding='utf-8'))['editor_pid']
line = command_line(pid)
assert 'PussStage.uproject' in line and '/Engine/Maps/Entry' in line, line
commands = folder / 'startup_filename_commands.txt'
commands.write_text('~0s\nkb 20\nr rcx\ndq @rcx L6\ndu poi(poi(@rcx+0x10)+8) L100\nqd\n', encoding='ascii')
log = folder / ('startup_filename_' + str(pid) + '.txt')
with log.open('w', encoding='utf-8') as output:
    run = subprocess.run(['C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/cdb.exe',
        '-pvr', '-p', str(pid), '-sins', '-netsyms:no', '-cf', str(commands)],
        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=45)
print('exit', run.returncode)
print(log.read_text(encoding='utf-8')[-8500:])
