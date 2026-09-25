"""Install the one-shot restart requested by the user; do not change plugins yet."""
import builtins
import hashlib
import os
import pathlib
import subprocess
import sys
import uuid
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
folder = str(project / 'Saved' / 'CodexMocap')
if folder not in sys.path:
    sys.path.insert(0, folder)
import restart_common as common
assert hasattr(unreal.SystemLibrary, 'quit_editor')
assert common.PYTHON.is_file() and common.ENGINE.is_file()
existing = getattr(builtins, 'PUSS_CREATOR_RESTART_HELPER', None)
assert existing is None or existing.poll() is not None, 'A restart helper is already running'
assert not common.PLAN.exists(), 'An existing restart plan needs inspection before replacement'
batch = getattr(builtins, 'PUSS_MOCAP_BATCH', None)
assert batch is not None and batch.running, 'Expected the approved mocap batch to be running'
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None
plan = {'authorized': True, 'token': str(uuid.uuid4()), 'created_utc': common.utc(),
        'old_editor_pid': os.getpid(), 'world': editor.get_editor_world().get_path_name().split('.', 1)[0],
        'project': str(common.PROJECT), 'engine': str(common.ENGINE),
        'action': 'After all eight mocap takes are saved and verified, enable MetaHuman Creator and restart this project',
        'project_sha256_at_arm': hashlib.sha256(common.PROJECT.read_bytes()).hexdigest()}
common.write(common.PLAN, plan)
import creator_restart_gate
_, issues, snapshot = creator_restart_gate.inspect()
assert 'Mocap batch is still running' in issues, 'The deferred restart guard did not block the active solve'
common.write(common.FOLDER / 'creator_restart_preflight.json', {
    'checked_utc': common.utc(), 'active_solve_blocks_restart': True,
    'project_unchanged': hashlib.sha256(common.PROJECT.read_bytes()).hexdigest() == plan['project_sha256_at_arm'],
    'current_issues': issues, 'snapshot': snapshot})
with (common.FOLDER / 'creator_restart_helper.log').open('a', encoding='utf-8') as log:
    helper = subprocess.Popen([str(common.PYTHON), str(common.FOLDER / 'restart_after_mocap.py')],
        cwd=str(project), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
builtins.PUSS_CREATOR_RESTART_HELPER = helper
unreal.log('MOCAP_CREATOR_RESTART_ARMED|old_editor_pid=' + str(os.getpid()) + '|helper_pid=' + str(helper.pid))
