"""EDITOR-ONLY sky toggle (Gary 7 Oct: the sky sphere in the editor prevents lighting work; no scene uses it).
Uses Actor.set_is_temporarily_hidden_in_editor — TRANSIENT: not saved, does not dirty packages, game/PIE unaffected,
resets when the editor/level reloads. Args editor_sky_toggle_args.json {"hide": true|false}.
Targets: every SkyAtmosphere, VolumetricCloud, SkyLight and sky-sphere BP in the editor world, plus DirectionalLights in
Klara's streamed levels (ours are already at intensity 0 and keyed only by the P06 sunset).
Marker EDITOR_SKY_TOGGLE_OK|hide=..|n=..|census_unchanged=.. / EDITOR_SKY_TOGGLE_FAILED."""
import json


def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/editor_sky_toggle_args.json", encoding="utf-8"))
    hide = bool(a.get("hide", True))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    w = ed.get_editor_world()
    lib = unreal.EditorLoadingAndSavingUtils
    before = (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
              sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    persistent = w.get_outermost().get_name()
    hits = []
    for a_ in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        cls = a_.get_class().get_name()
        is_sky = isinstance(a_, (unreal.SkyAtmosphere, unreal.SkyLight)) or "VolumetricCloud" in cls \
            or "SkySphere" in cls or "Sky_Sphere" in cls
        foreign_sun = isinstance(a_, unreal.DirectionalLight) and a_.get_outermost().get_name() != persistent
        if is_sky or foreign_sun:
            a_.set_is_temporarily_hidden_in_editor(hide)
            hits.append("%s(%s)" % (a_.get_actor_label(), a_.get_outermost().get_name().split("/")[-1]))
    after = (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
             sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    unreal.log("EDITOR_SKY_TOGGLE_OK|hide=%s|n=%d|census_unchanged=%s|%s" % (hide, len(hits), before == after, "; ".join(hits)))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("EDITOR_SKY_TOGGLE_FAILED|%r" % (exc,))
