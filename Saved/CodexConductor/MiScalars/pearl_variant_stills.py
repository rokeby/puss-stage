"""PIE-only pearl comparison stills. Nothing is saved; nothing is spawned in the editor world.

Two calls (a capture right after a transport jump can be a stale frame):
  PVS_PHASE="SCRUB"    performance mode off (original written to pearl_variant_stills_state.json first), scrub the
                       Master to Scene 3 at PVS_SCENE_FRAME (default 1800: lid open, glow full), pause, restore the
                       original performance mode  -> PVS_SCRUB_OK
  PVS_PHASE="CAPTURE"  for each VARIANT: set PIE-only materials / MID params / glow-light intensity / visibility,
                       then capture SHOTS with a SceneCaptureComponent2D added to the PIE clam root actor
                       (AActor::AddComponentByClass [decl Actor.h; behaviour inferred]) -> PNGs + a contact sheet in
                       Saved/CodexConductor/Captures/<run>/ -> PVS_CAPTURE_OK
Every PIE-only change is undone at the end of CAPTURE (materials, visibility, light) so PIE playback continues as authored.
No exposure override (memory: capture-exposure convention). Markers PVS_*|run=<id>; PVS_FAILED|run=<id>|<reason>.
"""
import datetime
import json
import math
import os

PHASE = globals().get("PVS_PHASE", "SCRUB")
SCENE_FRAME = int(globals().get("PVS_SCENE_FRAME", 1800))
SCENE_FPS = 24.0
MASTER_TICKS_PER_SCENE_FRAME = None      # derived live from the segment (scene frames = 24 fps)
DIR = "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/"
PEARL, TWIN, ROOT, GLOW = "S3 PearlClam Pearl", "S3 PearlClam Pearl Fade", "S3 PearlClam", "S3 Drama Pearl Glow"
GREEN = {"vectors": {"PaletteA": (0.72, 0.74, 0.48), "PaletteB": (-0.22, 0.10, 0.10), "PaletteC": (1.0, 1.0, 1.0),
                     "PaletteD": (0.0, 0.0, 0.0), "SubsurfaceBase": (0.92, 0.91, 0.87), "GlowColor": (1.0, 0.97, 0.92)},
         "scalars": {"IridStrength": 0.45, "SubsurfaceIrid": 0.45, "FresnelExponent": 2.0, "Glow": 0.03, "GlowIrid": 0.0}}
# variant: (name, solid_visible, solid_mi, solid_overrides, twin_visible, twin_mi, twin_overrides, glow_cd or None=as keyed)
VARIANTS = [
    ("a_v3_pink", True, DIR + "MI_PearlClam_Pearl_v3", None, False, None, None, None),
    ("b_green_orange", True, DIR + "MI_PearlClam_Pearl_v3_GreenOrange", None, False, None, None, 3.0),
    ("c_green_twin_fade1", False, None, None, True, DIR + "MI_PearlClam_Pearl_Fade", dict(GREEN, fade=1.0), 3.0),
    ("d_green_twin_fade05", False, None, None, True, DIR + "MI_PearlClam_Pearl_Fade", dict(GREEN, fade=0.5), 3.0),
    ("e_green_dither_fade05", False, None, None, True, DIR + "MI_PearlClam_Pearl_Dither", dict(GREEN, fade=0.5), 3.0),
]
SHOTS = (("near", 0.0, 20.0, 70.0, 35.0), ("side", 120.0, 12.0, 90.0, 35.0), ("wide", 240.0, 30.0, 180.0, 40.0))


def _log(u, msg):
    u.log(msg)


def _find(u, world, label):
    hits = [a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor) if a.get_actor_label() == label]
    return hits[0] if len(hits) == 1 else None


def scrub(u, run, world, here):
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("show roots %d" % len(roots))
    root = roots[0]
    segs = [s for s in list(root.transport.segments) if s.type == u.InfinityCueType.SCENE
            and (str(s.label) == "Scene 3" or str(s.label).startswith("Scene 3 "))]
    if len(segs) != 1:
        raise RuntimeError("Scene 3 segments %d" % len(segs))
    a, b = int(segs[0].start_frame.value), int(segs[0].end_frame.value)
    tpf = 24000.0 / SCENE_FPS                         # master tick resolution 24000 (klara_preroll_s1 probe_args)
    target = int(a + SCENE_FRAME * tpf)
    if not a <= target < b:
        raise RuntimeError("target %d outside Scene 3 %d..%d" % (target, a, b))
    tr = root.transport
    state = os.path.join(here, "pearl_variant_stills_state.json")
    orig = bool(tr.get_editor_property("performance_mode")) if not os.path.exists(state) else \
        json.load(open(state, encoding="utf-8"))["performance_mode"]
    with open(state, "w", encoding="utf-8") as fh:
        json.dump({"performance_mode": orig, "run": run}, fh)
    try:
        tr.set_editor_property("performance_mode", False)
        res = tr.scrub_to_master_frame(u.FrameNumber(target))
        root.sequence_player.pause()
        now = int(tr.get_current_master_frame().value)
    finally:
        tr.set_editor_property("performance_mode", orig)
    if "SUCCEEDED" not in str(res) or abs(now - target) > 1:
        raise RuntimeError("scrub %s now=%d target=%d" % (res, now, target))
    os.remove(state)
    _log(u, "PVS_SCRUB_OK|run=%s|scene_frame=%d|master=%d|performance_mode=%s(restored)" % (run, SCENE_FRAME, now, orig))


def _mid(comp, mi, ov, u):
    comp.set_material(0, u.load_asset(mi))
    mid = comp.create_dynamic_material_instance(0, u.load_asset(mi))
    for k, v in (ov or {}).get("vectors", {}).items():
        mid.set_vector_parameter_value(k, u.LinearColor(v[0], v[1], v[2], 1.0))
    for k, v in (ov or {}).get("scalars", {}).items():
        mid.set_scalar_parameter_value(k, float(v))
    if ov and "fade" in ov:
        mid.set_scalar_parameter_value("Fade", float(ov["fade"]))
    return mid


def capture(u, run, world, here):
    pearl, twin, root, glow = (_find(u, world, x) for x in (PEARL, TWIN, ROOT, GLOW))
    missing = [n for n, a in ((PEARL, pearl), (TWIN, twin), (ROOT, root), (GLOW, glow)) if a is None]
    if missing:
        raise RuntimeError("PIE actors missing %s" % missing)
    pc = pearl.get_component_by_class(u.StaticMeshComponent)
    tc = twin.get_component_by_class(u.StaticMeshComponent)
    lc = glow.get_component_by_class(u.LightComponent)
    orig = {"pearl_mat": pc.get_material(0), "twin_mat": tc.get_material(0), "pearl_hidden": pearl.is_hidden(),
            "twin_hidden": twin.is_hidden(), "glow": float(lc.get_editor_property("intensity"))}
    tgt = pearl.get_actor_location()
    out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor",
                       "Captures", run)
    os.makedirs(out, exist_ok=True)
    rt = u.RenderingLibrary.create_render_target2d(world, 1280, 720, u.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    cap = root.add_component_by_class(u.SceneCaptureComponent2D, True, u.Transform(), False)
    if cap is None:
        raise RuntimeError("add_component_by_class returned None")
    rows = []
    try:
        cap.set_editor_property("texture_target", rt)
        cap.set_editor_property("capture_source", u.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        cap.set_editor_property("capture_every_frame", False)
        cap.set_editor_property("capture_on_movement", False)
        for name, sv, smi, sov, tv, tmi, tov, gcd in VARIANTS:
            pearl.set_actor_hidden_in_game(not sv)
            twin.set_actor_hidden_in_game(not tv)
            if sv:
                _mid(pc, smi, sov, u)
            if tv:
                _mid(tc, tmi, tov, u)
            lc.set_intensity(orig["glow"] if gcd is None else float(gcd))
            for shot, yaw_off, el_deg, dist, fov in SHOTS:
                yaw, el = math.radians(yaw_off), math.radians(el_deg)
                loc = u.Vector(tgt.x + dist * math.cos(el) * math.cos(yaw), tgt.y + dist * math.cos(el) * math.sin(yaw),
                               tgt.z + dist * math.sin(el))
                cap.set_world_location_and_rotation(loc, u.MathLibrary.find_look_at_rotation(loc, tgt), False, True)
                cap.set_editor_property("fov_angle", fov)
                cap.capture_scene()
                fn = "%s__%s.png" % (name, shot)
                u.RenderingLibrary.export_render_target(world, rt, out, fn)
                p = os.path.join(out, fn)
                rows.append({"variant": name, "shot": shot, "bytes": os.path.getsize(p) if os.path.exists(p) else 0})
    finally:
        pc.set_material(0, orig["pearl_mat"])
        tc.set_material(0, orig["twin_mat"])
        pearl.set_actor_hidden_in_game(orig["pearl_hidden"])
        twin.set_actor_hidden_in_game(orig["twin_hidden"])
        lc.set_intensity(orig["glow"])
        cap.destroy_component(cap)
    small = [r for r in rows if r["bytes"] < 20000]
    _log(u, "PVS_CAPTURE_OK|run=%s|n=%d|small=%d|dir=%s|glow_keyed=%.2f|%s"
         % (run, len(rows), len(small), out, orig["glow"], json.dumps(rows)))


def main():
    import unreal as u
    run = "PVS-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    here = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor", "MiScalars")
    try:
        if world is None:
            raise RuntimeError("no PIE world")
        (scrub if PHASE == "SCRUB" else capture)(u, run, world, here)
    except Exception as exc:  # noqa: BLE001 - every stop leaves a run-stamped marker
        u.log_error("PVS_FAILED|run=%s|phase=%s|%s: %s" % (run, PHASE, type(exc).__name__, exc))


main()
