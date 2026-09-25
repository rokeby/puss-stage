"""Record the unattended queue's final saved state without changing assets."""
import builtins
import hashlib
import json
import pathlib
import traceback
import unreal
from batch_runner import utc

FOLDER = pathlib.Path('E:/PussStage/Saved/CodexMocap')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(batch):
    reports = {}
    problems = []
    for job in batch.jobs:
        if job['state'] != 'verified':
            problems.append(job['stem'] + ': ' + job['state'])
            continue
        report = json.loads((FOLDER / 'Verification' / (job['stem'] + '.json')).read_text(encoding='utf-8'))
        reports[job['stem']] = report
        if report['coverage']['body_frames'] != job['image_count']:
            problems.append(job['stem'] + ': some frames have no body data')
    original = pathlib.Path('E:/PussStage/Content/Metahuman/Shore1.uasset')
    backup = pathlib.Path('E:/PussStage/Backups/PreMocapFullBatch-20260910-173855/Shore1.uasset')
    original_unchanged = digest(original) == digest(backup)
    if not original_unchanged:
        problems.append('Original Shore1 differs from the pre-batch backup')
    prefs = unreal.find_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
    throttle = prefs.get_editor_property('bThrottleCPUWhenNotForeground') if prefs else None
    restored = throttle == batch.original_throttle
    if not restored:
        problems.append('Background CPU preference was not restored')
    if batch.sleep_prevention:
        problems.append('Batch sleep prevention is still active')
    dirty_content = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    dirty_maps = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    for path in dirty_content:
        if path.startswith(batch.manifest['root'] + '/'):
            problems.append('Unsaved batch package: ' + path)
    result = {
        'checked_utc': utc(), 'all_takes_verified': len(reports) == len(batch.jobs),
        'verified_takes': len(reports), 'total_takes': len(batch.jobs),
        'expected_video_frames': sum(j['image_count'] for j in batch.jobs),
        'saved_body_frames': sum(r['coverage']['body_frames'] for r in reports.values()),
        'original_test_unchanged': original_unchanged,
        'background_throttle_restored': restored, 'background_throttle': throttle,
        'sleep_prevention': batch.sleep_prevention,
        'pie_running': unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None,
        'dirty_content_packages': dirty_content, 'dirty_map_packages': dirty_maps,
        'issues': problems, 'success': not problems,
    }
    (FOLDER / 'batch_final_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log(('MOCAP_BATCH_FINAL_READBACK_SUCCESS|' if result['success'] else 'MOCAP_BATCH_FINAL_REVIEW_REQUIRED|') + json.dumps(result))
    return result


def install():
    batch = builtins.PUSS_MOCAP_BATCH
    cls = type(batch)
    if not hasattr(cls, '_stop_before_final_audit'):
        cls._stop_before_final_audit = cls.stop

        def stop_and_audit(self):
            self._stop_before_final_audit()
            try:
                audit(self)
            except Exception:
                error = traceback.format_exc()
                (FOLDER / 'batch_final_audit.json').write_text(json.dumps({'checked_utc': utc(), 'success': False, 'error': error}, indent=2), encoding='utf-8')
                unreal.log_error('MOCAP_BATCH_FINAL_AUDIT_ERROR|' + error)
            self.write_status(force=True)

        cls.stop = stop_and_audit
    unreal.log('MOCAP_BATCH_FINAL_AUDIT_ATTACHED')
