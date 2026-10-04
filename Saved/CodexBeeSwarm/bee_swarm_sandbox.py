"""Create the swarm SANDBOX map /Game/Scenes/Effects/Swarm/L_SwarmSandbox (new map only).

LEVEL ACTIVITY: this OPENS a new map in the shared editor and, at the end, re-opens
the Show level. Announce it to the conductor first; no other stream may be mid-edit
in the Show level (a dirty map refuses the run). It never touches the Show level's
content and never saves anything but the sandbox map.

Modes: DRY (default; read-only preflight) / APPLY.
Requires: the v3 C++ built (class /Script/InfinityStage.InfinityStageBeeSwarmActor),
bee_swarm_assets APPLIED, and NS_BeeSwarm built by hand (runbook section 3).

Layout (cm; +X is the camera's view direction; floor z = 0; S6-like void):
  swarm actor        (0, 0, 150)   box centre; default bounds 600 x 450 x 140 half
  candle light       (0, 0, 110)   point, 120 lm, 1900 K, attenuation 700 cm, volumetric 1
  GO1 camera height  55 cm         cameras at (-300, 0, 55) looking +X
    SB Camera Focus60   35 mm f/2.0 focus 60 cm   (30 cm bee soft, 200 cm bee soft)
    SB Camera Focus200  35 mm f/2.0 focus 200 cm  (30/60 cm bees blur: the S6 read)
  reference bees     SM_Bee side-on at 30, 60, 200 cm in front of the cameras
                     (x = -270, -240, -100), each with a 2 cm cube below and a label
  floor              20 m plane, MI_Bee_Body (near-black)
  fog                exponential height fog, volumetric on (candle halo, as S6)
  post               unbound PPV: motion blur amount 0.5, max 5 % (engine defaults made
                     explicit); NO exposure override (capture convention)
The swarm component's bDrawDebugTarget is ON in the sandbox: the orange sphere is
the darting target ("moving target"). PIE: player 0's camera drives the swarm; use
the spectator (WASD) to emulate the GO1, or the cameras above for matched stills.

Marker: BEE_SWARM_SANDBOX_SAVED|run=...|map=...|actors=...|returned_to=...
"""
from __future__ import annotations

import importlib.util
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


def _load_common():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bs_common.py")
    spec = importlib.util.spec_from_file_location("_bs_common_sb", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_common()

CAMERA_X, CAMERA_Z = -300.0, 55.0
REFERENCE_BEES = ((30.0, 6.0), (60.0, -8.0), (200.0, 10.0))   # (distance cm, y offset cm)
CAMERAS = (("SB Camera Focus60", 60.0), ("SB Camera Focus200", 200.0))


def _label(actor, text):
    actor.set_actor_label(text)
    return actor


def _spawn(eas, cls, loc, rot=(0.0, 0.0, 0.0), label=None):
    actor = eas.spawn_actor_from_class(cls, unreal.Vector(*loc),
                                       unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]))
    C.require(actor is not None, "SPAWN_FAILED|%s" % cls)
    if label:
        _label(actor, label)
    return actor


def _mesh_actor(eas, mesh_path, loc, rot, scale, label, material=None):
    actor = _spawn(eas, unreal.StaticMeshActor, loc, rot, label)
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    comp.set_static_mesh(unreal.EditorAssetLibrary.load_asset(mesh_path))
    actor.set_actor_scale3d(unreal.Vector(*scale))
    if material is not None:
        comp.set_material(0, material)
    return actor


def preflight():
    world = C.editor_world(unreal)
    census = C.dirty_census(unreal)
    C.require(not census["maps"], "MAP_DIRTY_REFUSING_LEVEL_SWITCH|%s" % census["maps"])
    C.require(not C.exists(unreal, C.SANDBOX_MAP), "SANDBOX_EXISTS|" + C.SANDBOX_MAP)
    for path in (C.MESH, C.MI_BODY, C.NIAGARA_SYSTEM):
        C.require(C.exists(unreal, path), "PREREQUISITE_MISSING|" + path)
    swarm_class = unreal.load_class(None, C.SWARM_ACTOR_CLASS)
    C.require(swarm_class is not None, "SWARM_CLASS_MISSING|build the v3 patch first|" + C.SWARM_ACTOR_CLASS)
    return C.asset_id(world), census, swarm_class


def build(swarm_class):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = []
    floor_mat = unreal.EditorAssetLibrary.load_asset(C.MI_BODY)
    labels.append(_mesh_actor(eas, "/Engine/BasicShapes/Plane", (0.0, 0.0, 0.0), (0, 0, 0), (20.0, 20.0, 1.0),
                              "SB Floor", floor_mat).get_actor_label())

    swarm = _spawn(eas, swarm_class, (0.0, 0.0, 150.0), label="SB Bee Swarm")
    comp = swarm.get_swarm_component()
    C.require(comp is not None, "SWARM_COMPONENT_MISSING")
    C.set_prop_any(comp, ("draw_debug_target", "b_draw_debug_target"), True)
    C.require(C.asset_id(swarm.get_niagara_component().get_asset()) == C.NIAGARA_SYSTEM,
              "SWARM_NIAGARA_ASSET|%s" % swarm.get_niagara_component().get_asset())
    labels.append(swarm.get_actor_label())

    light = _spawn(eas, unreal.PointLight, (0.0, 0.0, 110.0), label="SB Candle Light")
    lc = light.get_component_by_class(unreal.PointLightComponent)
    lc.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    lc.set_editor_property("intensity", 120.0)
    C.set_prop_any(lc, ("use_temperature", "b_use_temperature"), True)
    lc.set_editor_property("temperature", 1900.0)
    lc.set_editor_property("attenuation_radius", 700.0)
    lc.set_editor_property("volumetric_scattering_intensity", 1.0)
    labels.append(light.get_actor_label())

    fog = _spawn(eas, unreal.ExponentialHeightFog, (0.0, 0.0, 0.0), label="SB Fog")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", 0.03)
    C.set_prop_any(fc, ("enable_volumetric_fog", "volumetric_fog", "b_enable_volumetric_fog"), True)
    labels.append(fog.get_actor_label())

    ppv = _spawn(eas, unreal.PostProcessVolume, (0.0, 0.0, 0.0), label="SB Post (motion blur explicit)")
    C.set_prop_any(ppv, ("unbound", "b_unbound"), True)
    settings = ppv.get_editor_property("settings")
    settings.set_editor_property("override_motion_blur_amount", True)
    settings.set_editor_property("motion_blur_amount", 0.5)
    settings.set_editor_property("override_motion_blur_max", True)
    settings.set_editor_property("motion_blur_max", 5.0)
    ppv.set_editor_property("settings", settings)
    labels.append(ppv.get_actor_label())

    for name, focus in CAMERAS:
        cam = _spawn(eas, unreal.CineCameraActor, (CAMERA_X, 0.0, CAMERA_Z), (0, 0, 0), name)
        cc = cam.get_cine_camera_component()
        cc.set_editor_property("current_focal_length", 35.0)
        cc.set_editor_property("current_aperture", 2.0)
        fs = cc.get_editor_property("focus_settings")
        fs.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
        fs.set_editor_property("manual_focus_distance", focus)
        cc.set_editor_property("focus_settings", fs)
        got = cc.get_editor_property("focus_settings").get_editor_property("manual_focus_distance")
        C.require(abs(float(got) - focus) < 0.01, "FOCUS_READBACK|%s|%s" % (name, got))
        labels.append(name)

    bee_body = unreal.EditorAssetLibrary.load_asset(C.MI_BODY)
    for distance, y in REFERENCE_BEES:
        x = CAMERA_X + distance
        labels.append(_mesh_actor(eas, C.MESH, (x, y, CAMERA_Z), (0, 0, 90.0), (1.0, 1.0, 1.0),
                                  "SB Ref Bee %d cm" % int(distance)).get_actor_label())
        labels.append(_mesh_actor(eas, "/Engine/BasicShapes/Cube", (x, y, CAMERA_Z - 4.0), (0, 0, 0),
                                  (0.02, 0.02, 0.02), "SB Ref Cube %d cm" % int(distance), bee_body).get_actor_label())
        text = _spawn(eas, unreal.TextRenderActor, (x, y, CAMERA_Z + 3.0), (0, 0, 180.0),
                      "SB Label %d cm" % int(distance))
        tc = text.get_component_by_class(unreal.TextRenderComponent)
        C.require(tc is not None, "TEXT_COMPONENT_MISSING")
        tc.set_editor_property("text", unreal.Text("%d cm" % int(distance)))
        tc.set_editor_property("world_size", 1.2 if distance < 100 else 3.0)
        labels.append(text.get_actor_label())
    return labels


def main(mode=None):
    C.require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    selected = str(mode or globals().get("BEE_SWARM_SANDBOX_MODE", "DRY")).upper()
    C.require(selected in ("DRY", "APPLY"), "MODE_INVALID|" + selected)
    run = C.stamp_now()
    report_path = os.path.join(C.saved_dir(unreal), "bee_swarm_sandbox_report.json")
    report = {"ok": False, "mode": selected, "run": run}
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    previous = None
    switched = False
    try:
        previous, census, swarm_class = preflight()
        report.update({"previous_world": previous, "census_before": census})
        if selected == "DRY":
            report["ok"] = True
            C.write_json(report_path, report)
            unreal.log("BEE_SWARM_SANDBOX_DRY_OK|run=%s|previous=%s|census=%s" % (run, previous, census))
            return
        C.require(les.new_level(C.SANDBOX_MAP), "NEW_LEVEL_FAILED|" + C.SANDBOX_MAP)
        switched = True
        world = C.editor_world(unreal)
        C.require(C.asset_id(world) == C.SANDBOX_MAP, "NEW_LEVEL_NOT_OPEN|%s" % C.asset_id(world))
        labels = build(swarm_class)
        C.require(les.save_current_level(), "SANDBOX_SAVE_FAILED")
        after = C.dirty_census(unreal)
        C.require(C.SANDBOX_MAP not in after["maps"], "SANDBOX_STILL_DIRTY|%s" % after)
        C.require(C.exists(unreal, C.SANDBOX_MAP), "SANDBOX_READBACK_MISSING")
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        present = sorted(a.get_actor_label() for a in eas.get_all_level_actors())
        missing = [lab for lab in labels if lab not in present]
        C.require(not missing, "SANDBOX_ACTORS_MISSING|%s" % missing)
        returned = None
        if previous and previous != C.SANDBOX_MAP:
            C.require(les.load_level(previous), "RETURN_LOAD_FAILED|" + previous)
            returned = C.asset_id(C.editor_world(unreal))
        report.update({"ok": True, "labels": labels, "census_after": after, "returned_to": returned})
        C.write_json(report_path, report)
        unreal.log("BEE_SWARM_SANDBOX_SAVED|run=%s|map=%s|actors=%d|returned_to=%s|report=%s"
                   % (run, C.SANDBOX_MAP, len(labels), returned, report_path))
    except Exception as error:  # noqa: BLE001
        report["error"] = str(error)
        report["switched_level"] = switched
        try:
            report["census_at_stop"] = C.dirty_census(unreal)
        except Exception:  # noqa: BLE001
            pass
        C.write_json(report_path, report)
        unreal.log_error("BEE_SWARM_SANDBOX_STOPPED|run=%s|mode=%s|switched=%s|%s|"
                         "if switched: do NOT save; reopen %s from the Content Browser and "
                         "choose Don't Save for the sandbox" % (run, selected, switched, error, previous))
        raise


if __name__ == "__main__":
    main()
