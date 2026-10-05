"""Gary 5 Oct: S3 "Back door needs removal - it doesn't work" -> "Close the wall". Hides "S3 Hangar Exit Door Leaf" and
"S3 Hangar Exit Black" (editor + game) and fills the opening between the far-wall pieces (Left of Exit / Right of Exit /
Below Exit) with ONE new cube wall piece, the same mesh, material, thickness and x as the Left piece, attached to
"S3 Hangar Root", tagged S3.BackDoorFill. Opening box = Left's inner y-edge .. Right's inner y-edge, z = Below's top ..
min(Left, Right) top. Args s3_close_back_door_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S3DOOR"}.
Backup + record first; level-only save; REVERT unhides and destroys the tagged fill. Marker S3_DOOR_CLOSE_<MODE>_OK.
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
REC = HERE + "s3_close_back_door_record.json"
TAG = "S3.BackDoorFill"
P = "S3 Hangar Far Wall "
LABELS = {"left": P + "Left of Exit", "right": P + "Right of Exit", "below": P + "Below Exit",
          "leaf": "S3 Hangar Exit Door Leaf", "black": "S3 Hangar Exit Black", "root": "S3 Hangar Root"}
RUN = datetime.datetime.now().strftime("S3DOOR-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("S3_DOOR_CLOSE_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def box(a):
    o, e = a.get_actor_bounds(False)
    return {"x": [o.x - e.x, o.x + e.x], "y": [o.y - e.y, o.y + e.y], "z": [o.z - e.z, o.z + e.z]}


def main():
    a = json.load(open(HERE + "s3_close_back_door_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "%s S3DOOR" % mode:
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    acts = sub.get_all_level_actors()
    found = {k: [x for x in acts if str(x.get_actor_label()) == v] for k, v in LABELS.items()}
    if any(len(v) != 1 for v in found.values()):
        stop("COUNTS|%s" % {k: len(v) for k, v in found.items()})
    f = {k: v[0] for k, v in found.items()}
    fills = [x for x in acts if x.actor_has_tag(TAG)]
    L, R, B = box(f["left"]), box(f["right"]), box(f["below"])
    y0, y1 = L["y"][1], R["y"][0]
    z0, z1 = B["z"][1], min(L["z"][1], R["z"][1])
    x0, x1 = L["x"]
    plan = {"y": [y0, y1], "z": [z0, z1], "x": [x0, x1], "left": L, "right": R, "below": B}
    unreal.log("S3_DOOR_CLOSE_PLAN|run=%s|%s|existing_fills=%d" % (RUN, json.dumps(plan), len(fills)))
    if not (y1 > y0 + 10 and z1 > z0 + 10):
        stop("OPENING_NOT_FOUND|%s" % json.dumps(plan))
    if mode == "DRY":
        unreal.log("S3_DOOR_CLOSE_DRY_OK|run=%s|opening_w=%.1f|opening_h=%.1f" % (RUN, y1 - y0, z1 - z0))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if mode == "APPLY":
        if os.path.exists(REC) or fills:
            stop("ALREADY_APPLIED")
        backup = "E:/PussStage/Backups/PreS3CloseBackDoor-" + RUN
        os.makedirs(backup)
        before = {k: {"hidden": bool(f[k].get_editor_property("hidden"))}
                  for k in ("leaf", "black")}
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "plan": plan, "before": before, "backup": backup}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        for k in ("leaf", "black"):
            f[k].modify()
            f[k].set_actor_hidden_in_game(True)
            f[k].set_is_temporarily_hidden_in_editor(False)
            f[k].set_editor_property("hidden", True)
        lc = f["left"].get_component_by_class(unreal.StaticMeshComponent)
        mesh = lc.get_editor_property("static_mesh")
        mb = mesh.get_bounding_box()
        size = unreal.Vector(mb.max.x - mb.min.x, mb.max.y - mb.min.y, mb.max.z - mb.min.z)
        centre = unreal.Vector((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        fill = sub.spawn_actor_from_class(unreal.StaticMeshActor, centre, f["left"].get_actor_rotation())
        fill.set_actor_label(P + "Exit Fill (door closed)")
        fill.tags = list(fill.tags) + [unreal.Name(TAG)]
        fc = fill.get_component_by_class(unreal.StaticMeshComponent)
        fc.set_mobility(unreal.ComponentMobility.MOVABLE)
        fc.set_static_mesh(mesh)
        for i, m in enumerate(lc.get_materials()):
            fc.set_material(i, m)
        fill.set_actor_scale3d(unreal.Vector((x1 - x0) / size.x, (y1 - y0) / size.y, (z1 - z0) / size.z))
        fill.set_actor_location(centre, False, False)
        fill.attach_to_actor(f["root"], "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                             unreal.AttachmentRule.KEEP_WORLD, False)
        got = box(fill)
        if (fill.get_attach_parent_actor() is None or abs(got["y"][0] - y0) > 1 or abs(got["y"][1] - y1) > 1
                or abs(got["z"][0] - z0) > 1 or abs(got["z"][1] - z1) > 1):
            stop("FILL_READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(got))
        if not (f["leaf"].get_editor_property("hidden") and f["black"].get_editor_property("hidden")):
            stop("HIDE_READBACK|NOTHING SAVED; Don't-Save restart")
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        rec = json.load(open(REC, encoding="utf-8"))
        for k in ("leaf", "black"):
            f[k].modify()
            f[k].set_editor_property("hidden", rec["before"][k]["hidden"])
            f[k].set_actor_hidden_in_game(rec["before"][k]["hidden"])
        for x in fills:
            sub.destroy_actor(x)
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("S3_DOOR_CLOSE_%s_OK|run=%s|level_saved=1|dirty_after=0+0" % (mode, RUN))


main()
