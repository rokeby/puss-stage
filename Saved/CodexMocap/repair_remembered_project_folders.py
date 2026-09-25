"""Repair only obsolete project-root references in the generated editor config."""
import datetime
import json
import pathlib
import shutil
import sys

root = pathlib.Path('E:/PussStage')
target = root / 'Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini'
old = b'G:/Shared drives/GZZ Studio Drive/Projects/2026. SHS 3 Evenings/UE5.8/PussStage/'
new = b'E:/PussStage/'
original = target.read_bytes()
count = original.count(old)
if not count:
    print('Remembered project folders are already local; no change.')
    sys.exit(0)
assert count <= 11, count
backup = root / 'Backups' / ('PreRememberedFolderRepair-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True, exist_ok=False)
shutil.copy2(target, backup / target.name)
assert (backup / target.name).read_bytes() == original
assert target.read_bytes() == original
updated = original.replace(old, new)
target.write_bytes(updated)
assert target.read_bytes() == updated and old not in updated
report = {'target': str(target), 'backup': str(backup), 'remapped_count': count, 'original_bytes': len(original)}
(root / 'Saved/CodexMocap/remembered_folder_repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
