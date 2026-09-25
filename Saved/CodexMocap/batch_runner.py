"""Resumable, sequential body solve queue for this approved capture session."""
import builtins
import ctypes
import datetime
import json
import pathlib
import time
import traceback
import unreal

FOLDER = pathlib.Path('E:/PussStage/Saved/CodexMocap')
STATUS = FOLDER / 'batch_status.json'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def summarize_body(performance, frame_count):
    valid = []
    raw = 0
    joint_counts = []
    for start in range(0, frame_count, 128):
        frames = performance.get_animation_data(start, min(frame_count, start + 128))
        for offset, frame in enumerate(frames):
            bones = frame.get_editor_property('body_animation_data')
            if len(bones):
                valid.append(start + offset)
                joint_counts.append(len(bones))
            if len(frame.get_editor_property('raw_body_animation_smplx_data')):
                raw += 1
    missing = []
    valid_set = set(valid)
    gap_start = None
    for index in range(frame_count + 1):
        if index < frame_count and index not in valid_set:
            if gap_start is None:
                gap_start = index
        elif gap_start is not None:
            missing.append([gap_start, index])
            gap_start = None
    return {'body_frames': len(valid), 'raw_body_frames': raw, 'total_frames': frame_count,
            'first_body_frame': valid[0] if valid else None, 'last_body_frame': valid[-1] if valid else None,
            'min_joints': min(joint_counts) if joint_counts else 0,
            'max_joints': max(joint_counts) if joint_counts else 0, 'unsolved_ranges': missing}


class MocapBatch:
    def __init__(self):
        self.manifest = json.loads((FOLDER / 'batch_manifest.json').read_text(encoding='utf-8'))
        self.jobs = self.manifest['jobs']
        self.active = None
        self.job = None
        self.delegate = None
        self.callback = None
        self.completion_signaled = False
        self.last_write = 0
        self.next_action = time.monotonic() + 2
        self.started = utc()
        self.running = False
        self.in_tick = False
        self.original_throttle = None
        self.background_settings = None
        self.sleep_prevention = False
        if STATUS.exists():
            previous = json.loads(STATUS.read_text(encoding='utf-8'))
            if previous.get('root') != self.manifest['root']:
                raise RuntimeError('Status belongs to a different batch')
            prior = {j['stem']: j for j in previous['jobs']}
            for job in self.jobs:
                old = prior.get(job['stem'])
                if old and old.get('state') in ('solved_exported', 'verified'):
                    job.update(old)
        assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
        assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
            assert package.get_path_name().startswith(self.manifest['root'] + '/')
        for job in self.jobs:
            p = unreal.load_asset(job['performance'])
            assert p and not p.is_processing()
            assert p.get_editor_property('body_tracking') and not p.get_editor_property('face_tracking')
        self.running = True
        # A running capture job may keep the computer awake; the display can still sleep.
        self.sleep_prevention = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
        try:
            prefs = unreal.find_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
            if prefs is not None:
                self.original_throttle = prefs.get_editor_property('bThrottleCPUWhenNotForeground')
                self.background_settings = prefs
                prefs.set_editor_property('bThrottleCPUWhenNotForeground', False)
        except Exception as exc:
            unreal.log_warning('MOCAP_BATCH_BACKGROUND_PREF|' + str(exc))
        self.callback = unreal.register_slate_post_tick_callback(self.tick)
        self.write_status(force=True)
        unreal.log('MOCAP_BATCH_STARTED|takes=' + str(len(self.jobs)) + '|root=' + self.manifest['root'])

    def write_status(self, force=False):
        now = time.monotonic()
        if not force and now - self.last_write < 10:
            return
        self.last_write = now
        report = {'root': self.manifest['root'], 'started_utc': self.started, 'updated_utc': utc(),
                  'running': self.running, 'current': self.job['stem'] if self.job else None,
                  'completed': sum(j['state'] in ('solved_exported', 'verified') for j in self.jobs),
                  'failed': sum(j['state'] == 'failed' for j in self.jobs),
                  'sleep_prevention': self.sleep_prevention, 'jobs': self.jobs}
        STATUS.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def finished(self, *args):
        self.completion_signaled = True
        unreal.log('MOCAP_TAKE_COMPLETION_EVENT|' + (self.job['stem'] if self.job else 'none'))

    def start_job(self, job):
        self.job = job
        self.active = unreal.load_asset(job['performance'])
        assert self.active and not self.active.is_processing()
        assert self.active.get_editor_property('start_frame_to_process') == 0
        assert self.active.get_editor_property('end_frame_to_process') == job['image_count']
        assert self.active.can_process(), 'Cannot process ' + job['performance']
        self.completion_signaled = False
        self.delegate = self.active.get_editor_property('on_processing_finished_dynamic')
        self.delegate.add_callable(self.finished)
        self.active.set_blocking_processing(False)
        job['state'] = 'processing'
        job['started_utc'] = utc()
        self.write_status(force=True)
        unreal.log('MOCAP_TAKE_START|' + job['stem'] + '|frames=' + str(job['image_count']))
        result = self.active.start_pipeline()
        job['start_pipeline_result'] = str(result)
        if result != unreal.StartPipelineErrorType.NONE:
            raise RuntimeError('StartPipeline refused: ' + str(result))

    def complete_job(self):
        p, job = self.active, self.job
        assert not p.is_processing()
        assert self.completion_signaled
        coverage = summarize_body(p, job['image_count'])
        job['coverage'] = coverage
        assert coverage['body_frames'] > 0, 'Pipeline completed without body motion'
        assert p.contains_animation_data_type(unreal.FrameAnimationDataType.BODY)
        assert unreal.EditorAssetLibrary.save_loaded_asset(p, only_if_is_dirty=False)
        job['performance_saved_utc'] = utc()
        # Preserve a reusable source animation without selecting the final cast's body.
        settings = unreal.MetaHumanPerformanceExportUtils.get_export_animation_sequence_settings(p)
        settings.set_editor_property('show_export_dialog', False)
        settings.set_editor_property('package_path', self.manifest['root'] + '/RawAnimations')
        settings.set_editor_property('asset_name', 'AS_' + job['stem'] + '_Body_Full')
        settings.set_editor_property('export_body', True)
        settings.set_editor_property('export_face', False)
        settings.set_editor_property('export_skeleton', unreal.PerformanceExportSkeleton.PERFORMER_SKELETON)
        settings.set_editor_property('export_range', unreal.PerformanceExportRange.WHOLE_SEQUENCE)
        settings.set_editor_property('enable_head_movement', False)
        settings.set_editor_property('auto_save_anim_sequence', True)
        destination = self.manifest['root'] + '/RawAnimations/AS_' + job['stem'] + '_Body_Full'
        assert not unreal.EditorAssetLibrary.does_asset_exist(destination), 'Refusing to overwrite ' + destination
        animation = unreal.MetaHumanPerformanceExportUtils.export_animation_sequence(p, settings)
        assert animation, 'Animation export returned no asset'
        assert unreal.EditorAssetLibrary.save_loaded_asset(animation, only_if_is_dirty=False)
        # Export can also create a performer-proportioned mesh and skeleton. Save only this run's packages.
        for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
            package_path = package.get_path_name()
            if package_path.startswith(self.manifest['root'] + '/'):
                assert unreal.EditorAssetLibrary.save_asset(package_path, only_if_is_dirty=False)
        job['animation'] = animation.get_path_name()
        try:
            job['animation_seconds'] = animation.get_editor_property('sequence_length')
            job['animation_skeleton'] = animation.get_editor_property('skeleton').get_path_name()
        except Exception as exc:
            job['animation_metadata_note'] = str(exc)
        job['state'] = 'solved_exported'
        job['finished_utc'] = utc()
        unreal.log('MOCAP_TAKE_SAVED|' + job['stem'] + '|body_frames=' + str(coverage['body_frames']) +
                   '|total_frames=' + str(job['image_count']) + '|animation=' + job['animation'])
        self.release_current()
        self.next_action = time.monotonic() + 3
        self.write_status(force=True)

    def release_current(self):
        if self.delegate:
            try:
                self.delegate.remove_callable(self.finished)
            except Exception as exc:
                unreal.log_warning('MOCAP_BATCH_UNBIND|' + str(exc))
        self.active = None
        self.delegate = None
        self.job = None
        self.completion_signaled = False

    def stop(self):
        self.running = False
        if self.callback is not None:
            unreal.unregister_slate_post_tick_callback(self.callback)
            self.callback = None
        try:
            if self.original_throttle is not None and self.background_settings is not None:
                self.background_settings.set_editor_property('bThrottleCPUWhenNotForeground', self.original_throttle)
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        self.sleep_prevention = False
        self.write_status(force=True)
        unreal.log('MOCAP_BATCH_QUEUE_FINISHED|completed=' + str(sum(j['state'] in ('solved_exported', 'verified') for j in self.jobs)) +
                   '|failed=' + str(sum(j['state'] == 'failed' for j in self.jobs)))

    def tick(self, delta_seconds):
        if self.in_tick or not self.running:
            return
        self.in_tick = True
        try:
            if self.active:
                if self.completion_signaled and not self.active.is_processing():
                    self.complete_job()
                else:
                    self.write_status()
            elif time.monotonic() >= self.next_action:
                pending = next((j for j in self.jobs if j['state'] == 'queued'), None)
                if pending:
                    self.start_job(pending)
                else:
                    self.stop()
        except Exception:
            error = traceback.format_exc()
            unreal.log_error('MOCAP_BATCH_JOB_ERROR|' + error)
            if self.job:
                self.job['state'] = 'failed'
                self.job['error'] = error
                self.job['finished_utc'] = utc()
            # Never start a second solve if the first is still active after an error.
            if self.active and self.active.is_processing():
                self.running = False
                self.write_status(force=True)
            else:
                self.release_current()
                self.next_action = time.monotonic() + 3
                self.write_status(force=True)
        finally:
            self.in_tick = False


def start():
    previous = getattr(builtins, 'PUSS_MOCAP_BATCH', None)
    if previous is not None and previous.running:
        raise RuntimeError('An approved mocap queue is already running')
    batch = MocapBatch()
    builtins.PUSS_MOCAP_BATCH = batch
    return batch
