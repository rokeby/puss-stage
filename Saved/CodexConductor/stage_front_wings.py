"""STAGE FRONT WINGS (temporary): copies of P01 Wing 001 (rococo L/R Flat V3) fixed to the front of the stage.
Gary 8 Oct ~08:30 UTC, own words: "take the wings that we use for the first bay in passage one and affix them to the
front of the stage for now so we have something to look at there."
Geometry [declaration: Docs/StageFrontSpec_2026-09-28.md]: curtain line + posts at x 0 (posts |y| 950-990, to z 1095),
lip x -150.  [measured: probe_front.py 8 Oct] L mesh spans local y +1.7..+725.5, R -727.9..-1.7, z -100..1020, x -16..+4;
in the passage both stand at z 0, yaw 0, scale 1 (pair local transforms).  Placement: x = args.x (default -45, just
downstage of the posts), inner edges at |y| = args.inner_edge (default 850, so they mask the plain posts).
Two StaticMeshActors, labels STAGE FRONT TEMP Wing L/R, tag PussStage.StageFrontTemp, attached to Structure 01
(keep world).  Map-only save.  Args stage_front_wings_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> FRONTWINGS",
"x":-45, "inner_edge":850, "z":0}.  Markers FRONTWINGS_<MODE>_OK|run=.. / FRONTWINGS_FAILED|.."""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "stage_front_wings_record.json"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TAG = "PussStage.StageFrontTemp"
BASE = "/Game/Scenes/Wings/FlatV3/Passage01/StaticMeshes/T5P/"
SIDES = {"L": (BASE + "SM_FlatV3_P01_L_1_roccoco_L_t5p", -1), "R": (BASE + "SM_FlatV3_P01_R__1_roccoco_R_t5p", 1)}


def main():
    a = json.load(open(HERE + "stage_front_wings_args.json"))
    mode = a["mode"]
    run = datetime.datetime.now().strftime("FRONTWINGS-%Y%m%d-%H%M%S")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    acts = sub.get_all_level_actors()
    ours = [x for x in acts if TAG in [str(t) for t in x.tags]]
    struct = [x for x in acts if str(x.get_actor_label()) == "Infinity Stage - Structure 01"]
    if len(struct) != 1:
        raise RuntimeError("STRUCTURE01|%d" % len(struct))
    plan = {}
    for side, (mp, sign) in SIDES.items():
        mesh = unreal.load_asset(mp)
        if mesh is None:
            raise RuntimeError("MESH|" + mp)
        b = mesh.get_bounds()
        lo, hi = b.origin.y - b.box_extent.y, b.origin.y + b.box_extent.y
        # inner edge = the mesh end nearest the centre line once placed
        y = (-float(a["inner_edge"]) - hi) if sign < 0 else (float(a["inner_edge"]) - lo)
        plan[side] = {"mesh": mp, "loc": [float(a["x"]), round(y, 2), float(a["z"])], "span_y": [round(y + lo, 1), round(y + hi, 1)]}
    if mode == "DRY":
        unreal.log("FRONTWINGS_DRY_OK|run=%s|existing=%d|plan=%s" % (run, len(ours), json.dumps(plan)))
        return
    if a.get("confirm") != "%s FRONTWINGS" % mode:
        raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreFrontWings-%s" % run
    os.makedirs(bd)
    shutil.copy2(UMAP, bd)
    if mode == "REVERT":
        if not ours:
            raise RuntimeError("NOTHING_TO_REVERT")
        for x in ours:
            sub.destroy_actor(x)
    elif mode == "APPLY":
        if ours:
            raise RuntimeError("ALREADY_PLACED|%d" % len(ours))
        if os.path.exists(REC):
            raise RuntimeError("RECORD_EXISTS")
        json.dump({"run": run, "args": a, "plan": plan, "backup": bd}, open(REC, "w"), indent=1)
        for side, p in plan.items():
            act = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*p["loc"]), unreal.Rotator(0, 0, 0))
            act.static_mesh_component.set_static_mesh(unreal.load_asset(p["mesh"]))
            act.set_actor_label("STAGE FRONT Wing %s (P01 Wing 001 rococo, provisional)" % side)
            act.tags = [unreal.Name(TAG)]
            act.attach_to_actor(struct[0], unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    else:
        raise RuntimeError("MODE")
    if dirty() != ([], [MAP]):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level() or dirty() != ([], []):
        raise RuntimeError("SAVE|%s" % (dirty(),))
    got = [x for x in sub.get_all_level_actors() if TAG in [str(t) for t in x.tags]]
    rb = {str(x.get_actor_label()): [round(v, 1) for v in (x.get_actor_location().x, x.get_actor_location().y, x.get_actor_location().z)] for x in got}
    want = 0 if mode == "REVERT" else 2
    if len(got) != want:
        raise RuntimeError("READBACK|%s" % rb)
    if mode == "REVERT":
        os.rename(REC, REC + ".reverted-" + run)
    unreal.log("FRONTWINGS_%s_OK|run=%s|actors=%s|backup=%s" % (mode, run, json.dumps(rb), bd))


try:
    main()
except Exception as exc:
    unreal.log_error("FRONTWINGS_FAILED|%r" % (exc,))
