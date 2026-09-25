"""Observe the Launcher install, then release the authorized restart gate.

Runs with the independent system Python. Does not stop any process, change the
engine installation, or launch an Editor itself. The existing restart helper
owns launch and post-restart verification.
"""
import json
import os
import pathlib
import sys
import time
import traceback
import restart_common as common

MANIFESTS = pathlib.Path('C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests')
ENGINE_ROOT = pathlib.Path('D:/Unreal Engine/UE_5.8')
OPTIONAL = ENGINE_ROOT / 'Engine/Plugins/MetaHuman/MetaHumanCharacter/Content/Optional'
STATUS = common.FOLDER / 'creator_content_watch_status.json'


def inspect_install():
    items = []
    for path in MANIFESTS.glob('*.item'):
        item = common.read(path)
        if item.get('AppName') == 'UE_5.8':
            items.append((path, item))
    if len(items) != 1:
        return {'ready': False, 'reason': 'Launcher has not committed the UE 5.8 installed manifest'}
    path, item = items[0]
    assert pathlib.Path(item['InstallLocation']).resolve() == ENGINE_ROOT.resolve()
    assert item['AppVersionString'].startswith('5.8.2-56702186')
    if item.get('bIsIncompleteInstall', True):
        return {'ready': False, 'reason': 'Launcher installation is incomplete'}
    # UE 5.8.2 Launcher commits InstallTags=[] even after this optional-content
    # installation succeeds. Validate the completed manifest and actual files;
    # do not make the unpopulated tag field an installation gate.
    pending = MANIFESTS / 'Pending' / path.name
    if pending.exists():
        return {'ready': False, 'reason': 'Launcher still has a pending engine install'}
    presets = list((OPTIONAL / 'Presets').rglob('*.uasset'))
    hair = list((OPTIONAL / 'Grooms/Bindings/Hair').glob('WI_*.uasset'))
    garment = OPTIONAL / 'Clothing/WI_DefaultGarment.uasset'
    if len(presets) < 6 or not hair or not garment.is_file():
        return {'ready': False, 'reason': 'Required Creator preset or wardrobe content is missing',
                'preset_asset_count': len(presets), 'hair_item_count': len(hair)}
    required = presets + hair + [garment]
    texture_models = list((OPTIONAL / 'TextureSynthesis').rglob('*'))
    texture_models = [p for p in texture_models if p.is_file()]
    if not texture_models:
        return {'ready': False, 'reason': 'Creator texture synthesis model files are missing'}
    required += texture_models
    if any(p.stat().st_size <= 0 for p in required):
        return {'ready': False, 'reason': 'A required content file is empty'}
    return {'ready': True, 'installed_manifest': str(path),
            'manifest_modified_ns': path.stat().st_mtime_ns,
            'version': item['AppVersionString'], 'install_tags': item['InstallTags'],
            'preset_asset_count': len(presets), 'hair_item_count': len(hair),
            'texture_model_file_count': len(texture_models),
            'default_garment': str(garment), 'installation_complete': True}


def report(state, **details):
    common.write(STATUS, {'state': state, 'updated_utc': common.utc(),
                         'watcher_pid': os.getpid(), **details})


def run():
    plan = common.read(common.PLAN)
    assert plan['authorized'] is True
    assert not pathlib.Path(sys.executable).resolve().is_relative_to(ENGINE_ROOT.resolve())
    assert not common.batch_issues(common.read(common.FOLDER / 'batch_status.json'),
                                   common.read(common.FOLDER / 'batch_final_audit.json'))
    previous = None
    deadline = time.monotonic() + 12 * 3600
    while time.monotonic() < deadline:
        evidence = inspect_install()
        if evidence['ready'] and evidence == previous:
            ready_path = common.FOLDER / 'creator_core_data_ready.json'
            if not ready_path.exists():
                common.write(ready_path, {'token': plan['token'], 'verified': True,
                    'verified_utc': common.utc(), 'evidence': evidence,
                    'method': 'Committed Launcher manifest plus installed Creator assets; stable across 30 seconds'})
            report('content_verified_waiting_for_existing_restart_helper', evidence=evidence)
            break
        previous = evidence
        report('waiting_for_launcher_installation', evidence=evidence)
        time.sleep(30)
    else:
        raise RuntimeError('Creator content did not finish installing within 12 hours')
    deadline = time.monotonic() + 25 * 60
    while time.monotonic() < deadline:
        status = common.read(common.STATUS)
        if status['state'] == 'attention_required':
            raise RuntimeError('Restart helper needs attention: ' + str(status.get('error')))
        if common.VERIFIED.exists():
            verification = common.read(common.VERIFIED)
            assert verification['token'] == plan['token']
            from restart_after_mocap import call_script
            call_script('inspect_shore_cast_api.py')
            inventory = common.read(common.FOLDER / 'shore_cast_api_inventory.json')
            assert inventory['pid'] == verification['pid']
            assert inventory['presets'], 'No Creator presets registered after restart'
            report('restart_verified_and_creator_inventory_ready',
                   editor_pid=verification['pid'], preset_count=len(inventory['presets']),
                   wardrobe_count=len(inventory['wardrobe']))
            return
        time.sleep(15)
    raise RuntimeError('The authorized restart has not verified within 25 minutes')


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        report('attention_required', error=str(exc), traceback=traceback.format_exc())
        raise
