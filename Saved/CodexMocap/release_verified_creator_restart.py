"""Release the existing restart helper after live verification of the install."""
import pathlib
import time
import restart_common as common
import watch_creator_content as watcher

plan = common.read(common.PLAN)
assert plan['authorized'] is True
assert not common.VERIFIED.exists(), 'Restart already verified'
assert not common.batch_issues(common.read(common.FOLDER / 'batch_status.json'),
                               common.read(common.FOLDER / 'batch_final_audit.json'))
first = watcher.inspect_install()
assert first['ready'], first
time.sleep(30)
second = watcher.inspect_install()
assert second == first and second['ready'], second
common.write(common.FOLDER / 'creator_core_data_ready.json', {
    'token': plan['token'], 'verified': True, 'verified_utc': common.utc(),
    'method': 'Launcher UI reports UE5.8 update completed; completed manifest and installed Creator content stable across 30 seconds',
    'evidence': second,
    'correction': 'InstallTags is empty after successful UE5.8.2 optional-content installation; use committed install state and installed files'
})
print('CREATOR_CONTENT_VERIFIED_RESTART_GATE_RELEASED', flush=True)
