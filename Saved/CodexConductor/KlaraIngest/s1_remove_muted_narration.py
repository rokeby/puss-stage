"""Remove the one MUTED narration audio section from LS_DevScene_01 (Gary, 7 Oct: "Remove the muted narration").

Targets only an inactive (muted) MovieSceneAudioSection whose range is exactly [5216, 6091) display frames.
Refuses unless exactly one matches. Copies the .uasset to Backups/ first; saves only that sequence; reads back.
Markers: S1NARR_REMOVED_OK | S1NARR_STOP.
"""
import os
import shutil
import time

import unreal

SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
WANT = (5216, 6091)
RUN = "S1NARR-" + time.strftime("%Y%m%d-%H%M%S")


def _stop(why):
    unreal.log_error("S1NARR_STOP|run=%s|%s" % (RUN, why))
    raise RuntimeError(why)


def _audio_sections(seq):
    out = []
    for track in seq.find_tracks_by_type(unreal.MovieSceneAudioTrack):
        for sec in track.get_sections():
            out.append((track, sec))
    for b in seq.get_bindings():
        for track in b.find_tracks_by_type(unreal.MovieSceneAudioTrack):
            for sec in track.get_sections():
                out.append((track, sec))
    return out


def _range(sec):
    return (sec.get_start_frame(), sec.get_end_frame())


seq = unreal.load_asset(SEQ)
if seq is None:
    _stop("NO_SEQUENCE")
rows = []
for track, sec in _audio_sections(seq):
    snd = sec.get_sound()
    rows.append({"track": track.get_display_name(), "range": _range(sec), "active": sec.is_active(),
                 "sound": snd.get_path_name() if snd else None})
    unreal.log("S1NARR_SECTION|run=%s|%s" % (RUN, rows[-1]))
hits = [(t, s) for t, s in _audio_sections(seq) if (not s.is_active()) and _range(s) == WANT]
if len(hits) != 1:
    _stop("MATCHES=%d (want exactly 1 muted section at %s)" % (len(hits), WANT))
track, sec = hits[0]

pkg = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()) + "InfinityStage/Dev/Sequences/LS_DevScene_01.uasset"
bdir = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", "PreS1NarrRemove-" + RUN)
os.makedirs(bdir)
shutil.copy2(pkg, bdir)
unreal.log("S1NARR_BACKUP_OK|run=%s|backup=%s" % (RUN, bdir))

seq.modify()
track.modify()
before = len(track.get_sections())
track.remove_section(sec)
if len(track.get_sections()) != before - 1:
    _stop("REMOVE_READBACK")
if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
    _stop("SAVE_FAILED")
left = [s for t, s in _audio_sections(seq) if (not s.is_active()) and _range(s) == WANT]
if left:
    _stop("STILL_PRESENT_AFTER_SAVE")
unreal.log("S1NARR_REMOVED_OK|run=%s|removed_range=%s|sections_left=%d|backup=%s" % (RUN, WANT, len(_audio_sections(seq)), bdir))
