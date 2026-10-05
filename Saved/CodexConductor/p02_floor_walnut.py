"""(5 Oct, extended to P03 via args "passage": Gary "[P03] also needs floor raising/replacing with the shiny one".)
Gary 5 Oct: P02's floor "should be the wooden waxed shiny floor not the slats"; he chose P01's walnut herringbone.
P02's four slabs (Near/Left/Right/Far around the bend; floor_dark_wet_apply.py left them untouched) sit under the rig's
boards, so the boards (slats) show. This raises each slab so its top is +0.5 cm above the board top (board top =
route z + FloorHeightCm, read live, as floor_dark_wet_apply.py did) and sets every material slot to the material P01's
slab renders (read live from "Passage 01 - Opening Floor").

Args p02_floor_walnut_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> P02FLOOR"}.
APPLY: guards (no PIE, clean census) -> record (fsync) + umap backup -> move Z only + set overrides -> read back ->
census = level only -> save level -> clean. Marker P02_FLOOR_APPLY_OK|run=.. REVERT restores Z and overrides exactly.
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
SLAB_LABELS = {"P02": ("Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right", "Passage 02 - Floor Far"),
               "P03": ("Passage 03 - Floor",)}
LABELS = ()
P01_SLAB = "Passage 01 - Opening Floor"
REC = ""
RUN = datetime.datetime.now().strftime("P02FL-%Y%m%d-%H%M%S")
MAX_RAISE = 12.0


def stop(msg):
    unreal.log_error("P02_FLOOR_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def mats(comp):
    return [m.get_path_name() if m else None for m in comp.get_materials()]


def top(actor):
    o, e = actor.get_actor_bounds(False)
    return o.z + e.z


def main():
    global LABELS, REC
    a = json.load(open(HERE + "p02_floor_walnut_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    pk = str(a.get("passage", "P02")).upper()
    if pk not in SLAB_LABELS:
        stop("PASSAGE_UNSUPPORTED|" + pk)
    LABELS = SLAB_LABELS[pk]
    REC = HERE + ("p02_floor_walnut_record.json" if pk == "P02" else "floor_walnut_record_%s.json" % pk)
    if mode != "DRY" and a.get("confirm") != "%s %sFLOOR" % (mode, pk):
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by = {}
    for x in acts:
        lab = str(x.get_actor_label())
        if lab in LABELS or lab == P01_SLAB:
            by.setdefault(lab, []).append(x)
    if any(len(by.get(l, [])) != 1 for l in LABELS + (P01_SLAB,)):
        stop("LABEL_COUNTS|%s" % {l: len(by.get(l, [])) for l in LABELS + (P01_SLAB,)})
    st = [x for x in acts if x.get_class().get_name() == "InfinityStageStructureActor"
          and str(x.get_actor_label()) == "Infinity Stage - Structure 0" + pk[-1]]
    if len(st) != 1:
        stop("STRUCTURE_COUNT")
    p02 = [x for x in acts if x.get_class().get_name() == "InfinityStagePassageActor"
           and str(x.get_actor_label()).startswith("Passage 0" + pk[-1])][0]
    route = p02.get_editor_property("route")
    W = unreal.SplineCoordinateSpace.WORLD
    zs = [route.get_location_at_distance_along_spline(route.get_spline_length() * i / 20.0, W).z for i in range(21)]
    if max(zs) - min(zs) > 0.5:
        stop("ROUTE_NOT_LEVEL|%.2f..%.2f" % (min(zs), max(zs)))
    board_top = zs[0] + float(st[0].get_editor_property("floor_height_cm"))
    target_top = board_top + 0.5
    walnut = mats(by[P01_SLAB][0].get_component_by_class(unreal.StaticMeshComponent))
    rows = []
    for lab in LABELS:
        x = by[lab][0]
        c = x.get_component_by_class(unreal.StaticMeshComponent)
        rows.append({"label": lab, "loc": [x.get_actor_location().x, x.get_actor_location().y, x.get_actor_location().z],
                     "top": top(x), "raise_cm": target_top - top(x), "materials": mats(c)})
    for r in rows:
        unreal.log("P02_FLOOR_ROW|run=%s|%s" % (RUN, json.dumps(r)))
    if mode == "DRY":
        unreal.log("P02_FLOOR_DRY_OK|run=%s|board_top=%.2f|target_top=%.2f|walnut=%s"
                   % (RUN, board_top, target_top, walnut))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if mode == "APPLY":
        if os.path.exists(REC):
            stop("RECORD_EXISTS")
        bad = [r for r in rows if not (0.0 <= r["raise_cm"] <= MAX_RAISE)]
        if bad:
            stop("RAISE_OUT_OF_RANGE|%s" % json.dumps(bad))
        backup = "E:/PussStage/Backups/Pre%sFloorWalnut-%s" % (pk, RUN)
        os.makedirs(backup)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "rows": rows, "walnut": walnut, "target_top": target_top, "backup": backup}, h, indent=1)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        plan = {r["label"]: (r["loc"][2] + r["raise_cm"], walnut) for r in rows}
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        rec = json.load(open(REC, encoding="utf-8"))
        plan = {r["label"]: (r["loc"][2], r["materials"]) for r in rec["rows"]}
    for lab, (z, ms) in plan.items():
        x = by[lab][0]
        c = x.get_component_by_class(unreal.StaticMeshComponent)
        x.modify()
        loc = x.get_actor_location()
        x.set_actor_location(unreal.Vector(loc.x, loc.y, z), False, False)
        for i, m in enumerate(ms[:c.get_num_materials()]):
            c.set_material(i, unreal.load_asset(m) if m else None)
        if abs(x.get_actor_location().z - z) > 0.01 or mats(c)[:len(ms)] != list(ms)[:c.get_num_materials()]:
            stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % lab)
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("P02_FLOOR_%s_OK|run=%s|passage=%s|slabs=%d|level_saved=1|dirty_after=0+0" % (mode, RUN, pk, len(LABELS)))


main()
