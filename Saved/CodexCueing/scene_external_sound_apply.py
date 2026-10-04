"""Gary, 4 Oct (questionnaire, his words): "only s03 has cellist external sound but other
scenes do need an option to stop the clock and restart if an interjection is needed".

Sets Scene.ExternalSound = None on Scenes 1, 2, 4, 5, 6; Scene 3 stays DeclaredUnpausable.
Request: Saved/CodexCueing/scene_external_sound_request.json {"mode": "DRY"|"APPLY", "run": "<id>"}.
APPLY: refuses in PIE or with dirty packages; backs up the Show; writes by index (array
elements are copies); saves ONLY the Show; reads back. Marker SCENE_EXTSOUND_APPLY_OK|run=...
Never: Save All, level save, reload, end PIE.
"""
import datetime
import json
import os
import shutil

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
UNLOCK = ["Scene 1", "Scene 2", "Scene 4", "Scene 5", "Scene 6"]
KEEP_LOCKED = ["Scene 3"]


def _prefix(label):
    for name in UNLOCK + KEEP_LOCKED:
        if label == name or label.startswith(name + " "):
            return name
    return None


def run():
    import unreal
    project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    with open(os.path.join(project_dir, "Saved", "CodexCueing", "scene_external_sound_request.json"), encoding="utf-8") as handle:
        request = json.load(handle)
    mode, run_id = request["mode"].upper(), request["run"]
    show = unreal.load_asset(SHOW_PATH)
    none = unreal.InfinityExternalSoundAuthority.NONE
    locked = unreal.InfinityExternalSoundAuthority.DECLARED_UNPAUSABLE
    cues = show.get_editor_property("cues")
    plan = []
    for index in range(len(cues)):
        cue = cues[index]
        if cue.get_editor_property("type") != unreal.InfinityCueType.SCENE:
            continue
        name = _prefix(str(cue.get_editor_property("label")))
        if name is None:
            continue
        current = cue.get_editor_property("scene").get_editor_property("external_sound")
        target = none if name in UNLOCK else locked
        plan.append((index, name, current, target))
    found = sorted(p[1] for p in plan)
    if found != sorted(UNLOCK + KEEP_LOCKED):
        raise RuntimeError("expected Scenes 1-6 exactly once each, found %s" % found)
    changes = [p for p in plan if p[2] != p[3]]
    summary = ";".join("%s:%s->%s" % (p[1], p[2], p[3]) for p in changes)
    if mode == "DRY":
        unreal.log("SCENE_EXTSOUND_DRY_OK|run=%s|changes=%d|%s" % (run_id, len(changes), summary))
        return
    if mode != "APPLY":
        raise RuntimeError("bad mode %s" % mode)
    if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError("PIE running")
    dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()] + \
            [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if dirty:
        raise RuntimeError("dirty packages before APPLY: %s" % dirty)
    if not changes:
        raise RuntimeError("NOOP: nothing to change (NOOP is not success)")
    source = os.path.join(project_dir, "Content", "InfinityStage", "Dev", "DA_InfinityStage_V1Show.uasset")
    backup = os.path.join(project_dir, "Backups", "PreSceneExtSound-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup)
    shutil.copy2(source, os.path.join(backup, os.path.basename(source)))
    show.modify()
    for index, name, current, target in changes:
        cue = cues[index]
        scene = cue.get_editor_property("scene")
        scene.set_editor_property("external_sound", target)
        cue.set_editor_property("scene", scene)
        cues[index] = cue
    show.set_editor_property("cues", cues)
    readback = show.get_editor_property("cues")
    for index, name, current, target in plan:
        got = readback[index].get_editor_property("scene").get_editor_property("external_sound")
        if got != target:
            raise RuntimeError("in-memory read-back: %s is %s, expected %s (nothing saved)" % (name, got, target))
    dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if set(dirty) - {SHOW_PATH} or maps:
        raise RuntimeError("out-of-scope dirty before save: %s %s" % (dirty, maps))
    if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
        raise RuntimeError("save failed")
    left = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if left:
        raise RuntimeError("dirty after save: %s" % left)
    unreal.log("SCENE_EXTSOUND_APPLY_OK|run=%s|changes=%d|%s|backup=%s" % (run_id, len(changes), summary, backup))


try:
    run()
except Exception as error:
    import unreal
    unreal.log_error("SCENE_EXTSOUND_STOPPED|reason=%s" % error)
    raise
