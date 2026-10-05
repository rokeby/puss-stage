"""Underpass fence (Gary 5 Oct: "in the spaces between girder rig should still be lined with fencing"; "Ground to ~3 m:
mostly open chain-link, some half or torn tarp, rare door gaps"). Layer built in 82035bd (UF, suite 179/0); short
336 cm x ~3 m FenceBays imported by W&T (FV3FBS-20261005-01).

Args underpass_fence_args.json {"mode": "DRY"|"APPLY"|"REVERT", "structure": "...", "confirm": "<MODE> <structure>"}.
APPLY: guards (no PIE, clean census, fence off, underpass on) -> record (fsync) + umap backup -> set the fence fields
(Native height, 4 variants) -> MaterializeStructure -> IsStructureCurrent -> census = level only -> save level -> clean.
Marker UNDERPASS_FENCE_APPLY_OK|run=..; the INFINITY_STAGE_STRUCTURE_OK line after it carries underpass_fence_panels.
REVERT restores the recorded fence fields, re-fits and saves the level.
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
SM = "/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/"
VARIANTS = {  # key: (mesh, overlay, weight)
    "fence_variant_a": (SM + "SM_FenceBay_short_open", None, 0.60),
    "fence_variant_b": (SM + "SM_FenceBay_short_open", SM + "SM_FenceTarp_short_half", 0.20),
    "fence_variant_c": (SM + "SM_FenceBay_short_open", SM + "SM_FenceTarp_short_torn", 0.15),
    "fence_variant_d": (SM + "SM_FenceBay_short_door_gap", None, 0.05),
}
SCALARS = {"fence": True, "fence_height_cm": 300.0, "fence_both_sides": True, "fence_cast_shadow": True}
RUN = datetime.datetime.now().strftime("UPF-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("UNDERPASS_FENCE_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def path(o):
    return o.get_path_name() if o else None


def snap(u):
    out = {k: u.get_editor_property(k) for k in SCALARS}
    out["fence_height_mode"] = str(u.get_editor_property("fence_height_mode"))
    for k in VARIANTS:
        v = u.get_editor_property(k)
        out[k] = {"mesh": path(v.get_editor_property("mesh")), "material": path(v.get_editor_property("material")),
                  "weight": float(v.get_editor_property("weight")),
                  "overlay_mesh": path(v.get_editor_property("overlay_mesh")),
                  "overlay_material": path(v.get_editor_property("overlay_material"))}
    return out


def load(p):
    if p is None:
        return None
    a = unreal.load_asset(p)
    if a is None:
        stop("ASSET_MISSING|" + p)
    return a


def main():
    a = json.load(open(HERE + "underpass_fence_args.json", encoding="utf-8"))
    mode, label = str(a.get("mode", "DRY")).upper(), str(a["structure"])
    if mode != "DRY" and a.get("confirm") != "%s %s" % (mode, label):
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    actors = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if str(x.get_actor_label()) == label]
    if len(actors) != 1:
        stop("STRUCTURE_COUNT|%d" % len(actors))
    actor = actors[0]
    u = actor.get_editor_property("underpass")
    before = snap(u)
    unreal.log("UNDERPASS_FENCE_START|run=%s|mode=%s|structure=%s|underpass_on=%s|before=%s"
               % (RUN, mode, label, u.get_editor_property("enabled"), json.dumps(before, default=str)))
    for m, o, _ in VARIANTS.values():
        load(m)
        load(o)
    if mode == "DRY":
        b = unreal.load_asset(VARIANTS["fence_variant_a"][0]).get_bounding_box()
        unreal.log("UNDERPASS_FENCE_DRY_OK|run=%s|short_open_bounds_x=%.1f..%.1f|z=%.1f..%.1f"
                   % (RUN, b.min.x, b.max.x, b.min.z, b.max.z))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    rec = HERE + "underpass_fence_record_%s.json" % label.split()[-1]
    if mode == "APPLY":
        if not u.get_editor_property("enabled"):
            stop("UNDERPASS_OFF")
        if before["fence"]:
            stop("ALREADY_ON")
        if os.path.exists(rec):
            stop("RECORD_EXISTS")
        backup = "E:/PussStage/Backups/PreUnderpassFence-%s-%s" % (label.split()[-1], RUN)
        os.makedirs(backup)
        with open(rec, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "structure": label, "before": before, "backup": backup}, h, indent=1, default=str)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        for k, v in SCALARS.items():
            u.set_editor_property(k, v)
        u.set_editor_property("fence_height_mode", unreal.InfinityFenceHeightMode.NATIVE)
        for k, (m, o, w) in VARIANTS.items():
            var = u.get_editor_property(k)
            var.set_editor_property("mesh", load(m))
            var.set_editor_property("overlay_mesh", load(o))
            var.set_editor_property("weight", w)
            u.set_editor_property(k, var)
    else:
        if not os.path.exists(rec):
            stop("NO_RECORD")
        b = json.load(open(rec, encoding="utf-8"))["before"]
        for k in SCALARS:
            u.set_editor_property(k, b[k])
        for k in VARIANTS:
            var = u.get_editor_property(k)
            for f in ("mesh", "material", "overlay_mesh", "overlay_material"):
                var.set_editor_property(f, load(b[k][f]))
            var.set_editor_property("weight", b[k]["weight"])
            u.set_editor_property(k, var)
    actor.modify()
    actor.set_editor_property("underpass", u)
    after = snap(actor.get_editor_property("underpass"))
    if mode == "APPLY":
        bad = [k for k, (m, o, w) in VARIANTS.items()
               if after[k]["mesh"] != load(m).get_path_name() or after[k]["overlay_mesh"] != path(load(o))
               or abs(after[k]["weight"] - w) > 1e-4]
        bad += [k for k, v in SCALARS.items() if after[k] != v]
        if bad:
            stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % bad)
    if not actor.materialize_structure():
        stop("MATERIALIZE_FAILED|NOTHING SAVED; Don't-Save restart")
    if not actor.is_structure_current():
        stop("NOT_CURRENT|NOTHING SAVED; Don't-Save restart")
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(rec, rec + ".reverted-" + RUN)
    unreal.log("UNDERPASS_FENCE_%s_OK|run=%s|structure=%s|level_saved=1|dirty_after=0+0" % (mode, RUN, label))


main()
