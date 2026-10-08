"""PIE only, no asset writes: move the PIE transport to the Scene 1 segment's start and play.
Markers: S1PLAY_OK|run=.. only after every check below; S1PLAY_FAILED|run=..|<reason> otherwise.

8 Oct fix (first live run 07:23:37: scrub=UNSAFE_EXTERNAL_CLOCK, playback went on in Scene 3, marker still said OK):
  * the refusal is the performance interlock: ScrubToMasterFrame refuses when bPerformanceMode is on and the CURRENT
    segment's ExternalSound is DeclaredUnpausable and the target differs from the current frame
    [decl InfinityStageTransportController.h:28-30,452-453,738-740; project source
    Private/InfinityStageTransportController.cpp:1672-1690, 2580-2590];
  * the proven path: performance_mode False on the PIE transport, original written to a file FIRST, scrub, restore
    [prec pie_s3_goto.py:13-24, KlaraIngest/klara_s4v5_preview.py:373-388,537-541; meas
    Saved/Logs/PussStage-backup-2026.10.08-04.59.47.log:12003 'PIE_S3_GOTO_OK|scrub=SUCCEEDED' with it off];
  * ScrubToMasterFrame pauses the player itself (cpp:1694), so no separate pause: a refused scrub changes nothing;
  * verified: result SUCCEEDED, get_current_master_frame() == the segment start right after the scrub, playing after
    play(), the frame inside [start, end), performance_mode restored and read back.
State file s1_play_from_start_state.json (beside this file): the ORIGINAL performance_mode, written before any change;
an unrestored state from an earlier run is reused, never overwritten (pie_s3_goto.py's orig file was overwritten by a
second run and 'restored' False [meas PussStage-backup-2026.10.08-04.59.47.log:12043]).
Never: save anything, end PIE, unreal objects in module globals (memory: editor crash).
"""
import datetime
import json
import os

try:
    import unreal
except ModuleNotFoundError:  # offline harness without the fake
    unreal = None

MARK = "S1PLAY"
SCENE_LABEL = "Scene 1"
STATE_NAME = "s1_play_from_start_state.json"


class PlayError(RuntimeError):
    pass


def _here():
    if unreal is not None and not getattr(unreal, "_PUSS_FAKE", False):
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraPrerollS1_20261008")
    return os.path.dirname(os.path.abspath(__file__))


def _write(path, data):
    with open(path + ".tmp", "w", encoding="utf-8") as h:
        json.dump(data, h, indent=1, sort_keys=True)
        h.flush()
        os.fsync(h.fileno())
    os.replace(path + ".tmp", path)


def play_s1(run, here=None):
    """Returns the OK detail string; raises PlayError(reason) on any failed check."""
    here = here or _here()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise PlayError("NO_PIE")
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1:
        raise PlayError("SHOW_ROOTS_%d" % len(roots))
    root = roots[0]
    tr = root.transport
    segs = [s for s in list(tr.segments) if s.type == unreal.InfinityCueType.SCENE
            and (str(s.label) == SCENE_LABEL or str(s.label).startswith(SCENE_LABEL + " "))]
    if len(segs) != 1:
        raise PlayError("SCENE1_SEGMENTS_%d" % len(segs))
    start, end = int(segs[0].start_frame.value), int(segs[0].end_frame.value)
    before = int(tr.get_current_master_frame().value)
    sp = os.path.join(here, STATE_NAME)
    prior = None
    if os.path.exists(sp):
        with open(sp, "r", encoding="utf-8") as h:
            prior = json.load(h)
    pm_now = bool(tr.get_editor_property("performance_mode"))     # decl InfinityStageTransportController.h:452-453
    if prior and not prior.get("restored"):
        original = bool(prior["performance_mode_before"])         # an earlier run never restored: keep ITS original
        unreal.log_warning("%s_REUSED_STATE|run=%s|original performance_mode=%s from run %s"
                           % (MARK, run, original, prior.get("run")))
    else:
        original = pm_now
    state = {"run": run, "performance_mode_before": original, "restored": False, "master_before": before,
             "segment": [start, end], "written": datetime.datetime.now().isoformat(timespec="seconds")}
    _write(sp, state)                                                 # the original FIRST, then change
    res = after_scrub = after_play = playing = None
    err = None
    try:
        if pm_now:
            tr.set_editor_property("performance_mode", False)
            if bool(tr.get_editor_property("performance_mode")):
                raise PlayError("PERFORMANCE_MODE_STILL_ON")
        res = tr.scrub_to_master_frame(unreal.FrameNumber(start))    # decl InfinityStageTransportController.h:738-740
        if res != unreal.InfinityTransportResult.SUCCEEDED:
            raise PlayError("SCRUB_%s|target=%d|master=%d|performance_mode_was=%s" % (res, start, before, pm_now))
        after_scrub = int(tr.get_current_master_frame().value)
        if abs(after_scrub - start) > 1:     # the getter rounds back to the authored tick (cpp:1716-1730); 1 t slack
            raise PlayError("FRAME_READBACK|%d want %d" % (after_scrub, start))
        root.sequence_player.play()                                   # prec pie_s3_goto.py:24 (after a SUCCEEDED scrub)
        playing = bool(tr.is_transport_playing())
        after_play = int(tr.get_current_master_frame().value)
        if not playing:
            raise PlayError("NOT_PLAYING|master=%d" % after_play)
        if not start - 1 <= after_play < end:
            raise PlayError("NOT_IN_SCENE1_AFTER_PLAY|master=%d segment=[%d, %d)" % (after_play, start, end))
    except PlayError as exc:
        err = exc
    finally:
        tr.set_editor_property("performance_mode", original)
        restored = bool(tr.get_editor_property("performance_mode")) == original
        state.update(restored=restored, result=str(res), after_scrub=after_scrub, after_play=after_play,
                     playing=playing, error=str(err) if err else None)
        _write(sp, state)
    if not restored:
        raise PlayError("PERFORMANCE_MODE_RESTORE|want %s|%s" % (original, err or "playing from Scene 1"))
    if err is not None:
        raise err
    return ("start=%d|end=%d|scrub=%s|master_before=%d|after_scrub=%d|after_play=%d|playing=%s|performance_mode=%s"
            "(restored)" % (start, end, res, before, after_scrub, after_play, playing, original))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    try:
        detail = play_s1(run)
    except PlayError as exc:
        unreal.log_error("%s_FAILED|run=%s|%s" % (MARK, run, exc))
        return False
    except Exception as exc:  # noqa: BLE001 - every exit leaves a marker
        unreal.log_error("%s_FAILED|run=%s|EXCEPTION|%s: %s" % (MARK, run, type(exc).__name__, exc))
        raise
    unreal.log("%s_OK|run=%s|%s" % (MARK, run, detail))
    return True


if unreal is not None and not getattr(unreal, "_PUSS_FAKE", False):
    main()
