"""Enable Creator and request normal shutdown only after all completion gates pass."""
import builtins
import datetime
import hashlib
import os
import pathlib
import shutil
import time
import unreal
import restart_common as common


def inspect():
    plan = common.read(common.PLAN)
    status = common.read(common.FOLDER / 'batch_status.json')
    audit_path = common.FOLDER / 'batch_final_audit.json'
    audit = common.read(audit_path) if audit_path.exists() else None
    issues = common.batch_issues(status, audit)
    project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if project != common.PROJECT.parent.resolve() or os.getpid() != plan['old_editor_pid']:
        issues.append('MCP is attached to a different project or Editor process')
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        issues.append('PIE/SIE is active')
    world = editor.get_editor_world().get_path_name().split('.', 1)[0]
    if world != plan['world']:
        issues.append('The open map changed since the restart was armed')
    batch = getattr(builtins, 'PUSS_MOCAP_BATCH', None)
    if batch is None or batch.running or batch.active is not None:
        issues.append('The live batch has not stopped cleanly')
    dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    dirty += [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if dirty:
        issues.append('Unsaved packages: ' + ', '.join(dirty))
    return plan, issues, {'pid': os.getpid(), 'world': world, 'dirty_packages': dirty}


def execute():
    plan, issues, snapshot = inspect()
    assert not issues, '\n'.join(issues)
    helper = common.read(common.STATUS)
    assert helper['token'] == plan['token'] and helper['state'] == 'requesting_restart'
    age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(helper['updated_utc'])
    assert age.total_seconds() < 60, 'Restart helper is not freshly ready'
    assert not getattr(builtins, 'PUSS_CREATOR_QUIT_ARMED', False), 'Quit has already been scheduled'
    original = common.PROJECT.read_bytes()
    descriptor = common.read(common.PROJECT)
    plugins = descriptor.setdefault('Plugins', [])
    matches = [p for p in plugins if p.get('Name') == 'MetaHumanCharacter']
    assert len(matches) <= 1
    backup = common.PROJECT.parent / 'Backups' / ('PreEnableMetaHumanCreator-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(exist_ok=False)
    shutil.copy2(common.PROJECT, backup / common.PROJECT.name)
    common.write(backup / 'restart_plan.json', plan)
    if matches:
        matches[0]['Enabled'] = True
    else:
        plugins.append({'Name': 'MetaHumanCharacter', 'Enabled': True})
    common.write(common.PROJECT, descriptor)
    assert common.read(common.PROJECT) == descriptor
    assert (backup / common.PROJECT.name).read_bytes() == original
    gate = {'state': 'quit_scheduled', 'token': plan['token'], 'pid': os.getpid(),
            'updated_utc': common.utc(), 'backup': str(backup), 'snapshot': snapshot,
            'project_sha256_before': hashlib.sha256(original).hexdigest(),
            'project_sha256_after': hashlib.sha256(common.PROJECT.read_bytes()).hexdigest()}
    common.write(common.GATE, gate)
    builtins.PUSS_CREATOR_QUIT_ARMED = True
    due = time.monotonic() + 5

    def quit_on_tick(delta):
        if time.monotonic() < due:
            return
        unreal.unregister_slate_post_tick_callback(builtins.PUSS_CREATOR_QUIT_CALLBACK)
        # Recheck immediately before closing, in case the user edited something.
        _, new_issues, _ = inspect()
        if new_issues:
            gate.update(state='shutdown_cancelled', issues=new_issues, updated_utc=common.utc())
            common.write(common.GATE, gate)
            unreal.log_warning('MOCAP_CREATOR_SHUTDOWN_CANCELLED|' + str(new_issues))
            return
        gate.update(state='quit_called', updated_utc=common.utc())
        common.write(common.GATE, gate)
        unreal.log('MOCAP_CREATOR_QUIT_REQUESTED|pid=' + str(os.getpid()))
        unreal.SystemLibrary.quit_editor()

    builtins.PUSS_CREATOR_QUIT_CALLBACK = unreal.register_slate_post_tick_callback(quit_on_tick)
    unreal.log('MOCAP_CREATOR_RESTART_GATE_SUCCESS|backup=' + str(backup))
