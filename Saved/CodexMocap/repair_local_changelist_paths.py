"""Back up and remap the stale pre-migration editor changelist cache."""
import datetime
import hashlib
import json
import pathlib
import shutil

root = pathlib.Path('E:/PussStage')
target = root / 'Saved/SourceControl/UncontrolledChangelists.json'
old_prefix = 'G:/Shared drives/GZZ Studio Drive/Projects/2026. SHS 3 Evenings/UE5.8/PussStage/'
new_prefix = 'E:/PussStage/'
original = target.read_bytes()
data = json.loads(original)
assert data['version'] == 1
changes = []
for changelist in data['changelists']:
    output = []
    seen = set()
    for filename in changelist['files']:
        updated = filename
        if filename.startswith(old_prefix):
            updated = new_prefix + filename[len(old_prefix):]
            assert pathlib.Path(updated).resolve().is_relative_to(root.resolve())
            changes.append({'old': filename, 'new': updated})
        key = updated.replace('\\', '/').casefold()
        if key not in seen:
            output.append(updated)
            seen.add(key)
    changelist['files'] = output
assert changes, 'No matching stale paths; nothing changed.'
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup = root / 'Backups' / ('PreChangelistPathRepair-' + stamp)
backup.mkdir(parents=True, exist_ok=False)
shutil.copy2(target, backup / target.name)
assert (backup / target.name).read_bytes() == original
assert target.read_bytes() == original, 'Cache changed during inspection; abort.'
target.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
saved = json.loads(target.read_text(encoding='utf-8'))
assert saved == data
assert not any(f.startswith(old_prefix) for c in saved['changelists'] for f in c['files'])
report = {'state': 'cache_repaired_waiting_for_editor_restart', 'backup': str(backup),
    'source_sha256': hashlib.sha256(original).hexdigest(),
    'original_bytes': len(original), 'remapped_count': len(changes),
    'remaining_entries': sum(len(c['files']) for c in data['changelists']),
    'changes': changes}
(root / 'Saved/CodexMocap/changelist_path_repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'changes'}, indent=2))
