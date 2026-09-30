"""Captures of the blink spots for Gary: P01's original beside the new ones, two
views each.
- "path": from the cat's line 12 m before the pool, at eye height, looking down
  the route at it.
- "pool": an oblique from 9 m up and 6 m back, so the gobo's shadow shape in the
  pool reads.

Mutates nothing in the Show or the level. It spawns SceneCapture2D actors as
TRANSIENT (labelled ZZ_BlinkCapture_*) and destroys them in a finally. A
transient object should not dirty its package; dirty is logged before and
after, so we know rather than assume. If maps read dirty=1 after, that's the
capture artefact the conductor documented: DO NOT save the level to tidy it.
Refuses on dirty content or PIE. Manual exposure (EV bias 1.0), as in the
conductor's walnut captures, so every frame is comparable. The flicker light
function makes each frame one instant of the buzz. Lean: all work in main().
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures")
EV = 1.0


def VIEWS(p, fwd):
    # "low" (29 Sep second pass): 4 m up and 3 m back with a wide lens, under the
    # overhead set dressing that blocked the 9 m "pool" views, to read each
    # gobo's shadow shape in its pool.
    if os.environ.get("BLINK_CAPTURE_VIEWS", "low") == "low":
        return (("low", p - fwd * 300.0 + unreal.Vector(0.0, 0.0, 400.0), 90.0),)
    return (("path", p - fwd * 1200.0 + unreal.Vector(0.0, 0.0, 160.0), 70.0),
            ("pool", p - fwd * 600.0 + unreal.Vector(0.0, 0.0, 900.0), 60.0))


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and "L_InfinityStage_V1VerticalSlice" in world.get_name() and ed.get_game_world() is None, "wrong world or PIE"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert c0 == 0, f"content dirty={c0}, not mine to disturb"
    plan = json.load(open(os.path.join(HERE, "blink_spots_plan.json"), encoding="utf-8"))
    pools = json.load(open(os.path.join(HERE, "blink_pools.json"), encoding="utf-8"))
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = {("P" + p.get_actor_label()[8:10]): p for p in sub.get_all_level_actors()
                if isinstance(p, unreal.InfinityStagePassageActor)}
    cues = {gs(c.get_editor_property("cue_guid")): c for c in show.get_editor_property("cues")}
    by_label = {str(c.get_editor_property("label")): g for g, c in cues.items()}
    jobs = [("P01_Wing041_original", "P01", by_label["P01 Wing 041"], pools[0]["pool_world"])]
    for r, pool in zip(plan["rows"], pools[1:]):
        name = f"{r['passage']}_{r['cue'].split()[-1]}_{r['gobo']['kind']}_{int(r['gobo']['lens_cm'])}cm_{int(r['spot']['kelvin'])}K"
        jobs.append((name, r["passage"], r["cue_guid"], pool["pool_world"]))
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    shots = []
    for name, pn, cg, pool in jobs:
        cue = cues[cg]
        st = next(a for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
                  if a.get_editor_property("anchor") == unreal.InfinityAttachmentAnchor.STATION)
        anchor = passages[pn].get_attachment_anchor_world_transform(cue.get_editor_property("cue_guid"), st.get_editor_property("attachment_guid"))
        fwd = unreal.MathLibrary.transform_direction(anchor, unreal.Vector(1.0, 0.0, 0.0))
        p = unreal.Vector(*pool)
        views = VIEWS(p, fwd)
        for view, cam, fov in views:
            rot = unreal.MathLibrary.find_look_at_rotation(cam, p)
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam, rot, True)
            try:
                cap.set_actor_label(f"ZZ_BlinkCapture_{name}_{view}")
                comp = cap.capture_component2d
                comp.set_editor_property("texture_target", rt)
                comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
                comp.set_editor_property("fov_angle", fov)
                pp = comp.post_process_settings
                pp.set_editor_property("override_auto_exposure_method", True)
                pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
                pp.set_editor_property("override_auto_exposure_bias", True)
                pp.set_editor_property("auto_exposure_bias", EV)
                comp.set_editor_property("post_process_settings", pp)
                comp.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, rt, OUT, f"Blink_{name}_{view}.png")
                shots.append(f"Blink_{name}_{view}.png")
            finally:
                sub.destroy_actor(cap)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"BLINK_CAPTURE_OK|shots={len(shots)}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}|out={OUT}")


main()
