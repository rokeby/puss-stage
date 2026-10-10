import unreal as u
s=u.load_asset('/Game/InfinityStage/Dev/Sequences/LS_DevScene_01')
u.log('JOB177_S1_PLAYBACK_PROBE_OK|start=%d|end=%d|display=%s|tick=%s'%(s.get_playback_start(),s.get_playback_end(),s.get_display_rate(),s.get_tick_resolution()))
