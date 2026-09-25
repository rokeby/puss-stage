"""File-backed plan and status for the explicitly authorized post-mocap restart."""
import datetime
import json
import pathlib

FOLDER = pathlib.Path('E:/PussStage/Saved/CodexMocap')
PROJECT = pathlib.Path('E:/PussStage/PussStage.uproject')
ENGINE = pathlib.Path('D:/Unreal Engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe')
PYTHON = pathlib.Path('D:/Unreal Engine/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe')
PLAN = FOLDER / 'creator_restart_plan.json'
STATUS = FOLDER / 'creator_restart_status.json'
GATE = FOLDER / 'creator_restart_gate.json'
VERIFIED = FOLDER / 'creator_restart_verified.json'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    # Each output has a single writer. Readers retry transient incomplete reads.
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def batch_issues(status, audit=None):
    issues = []
    if status.get('root') != '/Game/Metahuman/FullTakes_20260910':
        issues.append('Unexpected batch root')
    if status.get('running'):
        issues.append('Mocap batch is still running')
    jobs = status.get('jobs', [])
    if len(jobs) != 8 or status.get('failed') != 0:
        issues.append('The eight-take queue has not finished without failures')
    if not jobs or any(j.get('state') != 'verified' for j in jobs):
        issues.append('Not every take is saved and verified')
    if any(j.get('coverage', {}).get('body_frames') != j.get('image_count') for j in jobs):
        issues.append('Some video frames have no verified body data')
    if audit is None or not audit.get('success') or not audit.get('all_takes_verified'):
        issues.append('Final batch audit has not passed')
    if audit and audit.get('checked_utc', '') < status.get('started_utc', ''):
        issues.append('Final batch audit is stale')
    return issues


def report(state, plan, **details):
    value = {'state': state, 'updated_utc': utc(), 'token': plan['token'],
             'old_editor_pid': plan['old_editor_pid'], **details}
    write(STATUS, value)
    lines = ['# MetaHuman Creator restart — 10 September 2026', '', '**Status:** ' + state + '.',
             '', 'Updated: ' + value['updated_utc'] + '.',
             '', 'User-authorized action: after all eight mocap takes finish, enable MetaHuman Creator and restart PussStage.',
             '', 'The restart requires all eight takes to be saved and verified, full body-frame coverage, a passing final batch audit, no PIE, and no unsaved content or maps.',
             '', 'Only `MetaHumanCharacter` is enabled in `E:/PussStage/PussStage.uproject`. A timestamped backup is made first. The helper waits for the old Editor to exit normally before opening the same project and map.',
             '', 'After launch, MCP checks the new process, the project, the map, the Creator plugin and its Python subsystem.',
             '', '[Detailed restart status](../Saved/CodexMocap/creator_restart_status.json).',
             '', '[Mocap batch report](MocapBatch-20260910.md).']
    if details.get('error'):
        lines += ['', '**Attention required:** ' + str(details['error'])]
    if details.get('backup'):
        lines += ['', 'Project backup: `' + details['backup'] + '`.']
    pathlib.Path('E:/PussStage/Docs/MetaHumanCreatorRestart-20260910.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return value
