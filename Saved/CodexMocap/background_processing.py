import builtins, ctypes
import unreal
batch=builtins.PUSS_MOCAP_BATCH
assert batch.running
prefs=unreal.find_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
if prefs is not None:
    try:
        batch.background_property='bThrottleCPUWhenNotForeground'
        batch.original_throttle=prefs.get_editor_property(batch.background_property)
        batch.background_settings=prefs
        prefs.set_editor_property(batch.background_property,False)
        unreal.log('MOCAP_BACKGROUND_PROCESSING_READY|previous_throttle='+str(batch.original_throttle)+'|config_not_saved')
    except Exception as exc:
        unreal.log_warning('MOCAP_BACKGROUND_PROCESSING_NO_OVERRIDE|'+str(exc))
else:
    unreal.log('MOCAP_BACKGROUND_PROCESSING_NO_OVERRIDE|settings_object_not_found')
def finish_queue(self):
    self.running=False
    if self.callback is not None:
        unreal.unregister_slate_post_tick_callback(self.callback)
        self.callback=None
    try:
        settings=getattr(self,'background_settings',None)
        if settings is not None and self.original_throttle is not None:
            settings.set_editor_property(self.background_property,self.original_throttle)
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        self.sleep_prevention=False
        self.write_status(force=True)
    completed=sum(j['state'] in ('solved_exported','verified') for j in self.jobs)
    unreal.log('MOCAP_BATCH_QUEUE_FINISHED|completed='+str(completed)+'|failed='+str(sum(j['state']=='failed' for j in self.jobs)))
type(batch).stop=finish_queue
