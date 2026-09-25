"""Snapshot the exact existing scene assets before the authorized cast integration."""
import datetime
import hashlib
import json
import pathlib
import shutil

root = pathlib.Path('E:/PussStage').resolve()
names = ['InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap',
         'InfinityStage/Dev/DA_InfinityStage_V1Show.uasset', 'Scenes/LS_Clams.uasset',
         'Scenes/LS_OrtalanSheetSway.uasset', 'Scenes/BP_OrtalanSheet.uasset',
         'Scenes/CA__OrtolanSheets.uasset', 'Scenes/SM_OrtalanSheet.uasset']
destination = root / 'Backups' / ('PreShoreClamIntegration-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
assert destination.resolve().is_relative_to(root / 'Backups')
destination.mkdir(parents=True, exist_ok=False)
records = []
for name in names:
    source = root / 'Content' / name
    target = destination / 'Content' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.copy2(source, target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    records.append({'relative_path': 'Content/' + name, 'bytes': target.stat().st_size, 'sha256': before})
report = {'backup': str(destination), 'files': records, 'total_bytes': sum(r['bytes'] for r in records)}
(destination / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(root / 'Saved/CodexMocap/clam_integration_backup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'backup': str(destination), 'files': len(records), 'bytes': report['total_bytes']}))
