"""Rig tubes everywhere (Gary, 6 Oct ~00:30): "please add them everywhere so they can be switched on or used to blink or
atmosphere when they're needed. In fact give them a low glow setting and make 20% of them blink everywhere, so they can
be seen in the background. But other than P02 only give light to the fence-top ones, not the central rail ones".

NEEDS THE TU BUILD (held patch Scripts/patches/2026-10-06_TU_tubes_everywhere.patch): the fields tube_fence_top_rows,
tube_*_emit_light, tube_glow_level and tube_blink_* exist only after it. Without them the tool stops BUILD_MISSING_TU
before touching anything.

Args (Saved/CodexConductor/rig_tubes_everywhere_args.json; if the file is missing the tool runs DRY with DEFAULTS):
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> rig tubes everywhere",
   "structures": ["Infinity Stage - Structure 01", ...]   (default: all six),
   "all_rows_light": ["Infinity Stage - Structure 02"]     (P02: centre, corner and fence-top rows all give light),
   "glow": 0.15, "blink_fraction": 0.2, "light_every": 4, "light_max": 48, "corner_inset_cm": 45.0,
   "fence_top_raise_cm": 15.0, "enable_underpass_where_off": false}
Every other structure gives light from its fence-top rows only (centre and corner rows glow and light nothing).
The tube stretch becomes the whole Passage (station 0 to -1) everywhere, P02 included.

DRY:    read-only. Per structure: underpass on/off, current tube fields, what APPLY would set, refusals.
APPLY:  guards (no PIE, census clean, TU fields present, MI_UP_Tube_Office + MI_LF_Flicker_Hum exist, no record) ->
        record (fsync; every touched field's BEFORE value) + umap backup Backups/PreRigTubesEverywhere-<run> ->
        set fields -> read back -> MaterializeStructure -> IsStructureCurrent -> census (the level only) -> save level ->
        census clean -> RIG_TUBES_EVERYWHERE_APPLY_OK|run=..
        A structure whose underpass is OFF is refused (UNDERPASS_OFF) unless enable_underpass_where_off is true:
        enabling it with no iron meshes builds the tubes alone (fence-top rows at fence height; deck rows hang under a
        deck line DeckHeightCm up with no deck) - a look call for Gary, hence off by default.
REVERT: restore every recorded field, re-materialize, census, save -> RIG_TUBES_EVERYWHERE_REVERT_OK|run=..
Any failure after a write says "NOTHING SAVED; Don't-Save restart" (the record and the umap backup stand).
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS = HERE + "rig_tubes_everywhere_args.json"
RECORD = HERE + "rig_tubes_everywhere_record.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
TUBE_MESH = "/Engine/BasicShapes/Cylinder"
TUBE_MI = "/Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Tube_Office"
LIGHT_FN = "/Game/InfinityStage/Lighting/MI_LF_Flicker_Hum"
CONFIRM_TAIL = "rig tubes everywhere"
DEFAULTS = {
    "mode": "DRY",
    "structures": ["Infinity Stage - Structure 0%d" % n for n in range(1, 7)],
    "all_rows_light": ["Infinity Stage - Structure 02"],
    "glow": 0.15,
    "blink_fraction": 0.2,
    "light_every": 4,
    "light_max": 48,
    "corner_inset_cm": 45.0,
    "fence_top_raise_cm": 15.0,
    "enable_underpass_where_off": False,
}
# Every Underpass field this tool may write (snake_case UPROPERTY names). "enabled" only with enable_underpass_where_off.
FIELDS = ("enabled", "tubes", "tube_mesh", "tube_material", "tube_from_station", "tube_to_station",
          "tube_corner_inset_cm", "tube_lights", "tube_light_every", "tube_light_max", "tube_light_function_material",
          "tube_centre_rows_emit_light", "tube_corner_rows_emit_light", "tube_fence_top_rows",
          "tube_fence_top_raise_cm", "tube_fence_top_rows_emit_light", "tube_glow_level", "tube_blink_fraction")
TU_FIELDS = ("tube_centre_rows_emit_light", "tube_corner_rows_emit_light", "tube_fence_top_rows",
             "tube_fence_top_raise_cm", "tube_fence_top_rows_emit_light", "tube_glow_level", "tube_blink_fraction")
RUN = datetime.datetime.now().strftime("RTE-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("RIG_TUBES_EVERYWHERE_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def plain_value(v):
    if isinstance(v, (bool, int, float)) or v is None:
        return v
    return v.get_path_name() if hasattr(v, "get_path_name") else str(v)


def plain(under):
    return {k: plain_value(under.get_editor_property(k)) for k in FIELDS}


def load_args():
    if not os.path.exists(ARGS):
        unreal.log("RIG_TUBES_EVERYWHERE_NO_ARGS|run=%s|running DRY with the defaults" % RUN)
        return dict(DEFAULTS)
    a = dict(DEFAULTS)
    a.update(json.load(open(ARGS, encoding="utf-8")))
    return a


def find_structures(labels):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    out = {}
    for label in labels:
        hits = [x for x in actors if str(x.get_actor_label()) == label
                and x.get_class().get_name() == "InfinityStageStructureActor"]
        if len(hits) != 1:
            stop("STRUCTURE_COUNT|%s|%d" % (label, len(hits)))
        out[label] = hits[0]
    return out


def target_for(label, under, a, assets):
    """The fields APPLY writes for one structure, or None if it is refused (underpass off)."""
    all_rows = label in a["all_rows_light"]
    t = {
        "tubes": True,
        "tube_mesh": assets["mesh"],
        "tube_material": assets["mi"],
        "tube_from_station": 0,
        "tube_to_station": -1,
        "tube_corner_inset_cm": float(a["corner_inset_cm"]),
        "tube_lights": True,
        "tube_light_every": int(a["light_every"]),
        "tube_light_max": int(a["light_max"]),
        "tube_light_function_material": assets["lf"],
        "tube_centre_rows_emit_light": bool(all_rows),
        "tube_corner_rows_emit_light": bool(all_rows),
        "tube_fence_top_rows": True,
        "tube_fence_top_raise_cm": float(a["fence_top_raise_cm"]),
        "tube_fence_top_rows_emit_light": True,
        "tube_glow_level": float(a["glow"]),
        "tube_blink_fraction": float(a["blink_fraction"]),
    }
    if not under.get_editor_property("enabled"):
        if not a.get("enable_underpass_where_off"):
            return None
        t["enabled"] = True
    return t


def same(got, want):
    if isinstance(want, float) and isinstance(got, (int, float)):
        return abs(float(got) - want) < 1e-4
    return got == want


def main():
    a = load_args()
    mode = str(a.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        stop("MODE|%s" % mode)
    if mode != "DRY" and a.get("confirm") != "%s %s" % (mode, CONFIRM_TAIL):
        stop("CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM_TAIL))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    structures = find_structures(list(a["structures"]))

    # The TU build must be in: probe its fields on the first structure, read-only.
    probe = list(structures.values())[0].get_editor_property("underpass")
    for k in TU_FIELDS:
        try:
            probe.get_editor_property(k)
        except Exception:
            stop("BUILD_MISSING_TU|field=%s: build 2026-10-06_TU_tubes_everywhere.patch first" % k)

    assets = {"mesh": unreal.load_asset(TUBE_MESH), "mi": unreal.load_asset(TUBE_MI), "lf": unreal.load_asset(LIGHT_FN)}
    missing = [k for k, v in assets.items() if v is None]

    rows = []
    for label, actor in structures.items():
        under = actor.get_editor_property("underpass")
        before = plain(under)
        t = None if missing else target_for(label, under, a, assets)
        rows.append({"structure": label, "underpass_enabled": before["enabled"], "before": before,
                     "target": None if t is None else {k: plain_value(v) for k, v in t.items()},
                     "lights_from": "all rows" if label in a["all_rows_light"] else "fence-top rows only",
                     "refused": None if t is not None else ("ASSETS_MISSING" if missing else "UNDERPASS_OFF")})
    unreal.log("RIG_TUBES_EVERYWHERE_PLAN|run=%s|mode=%s|missing_assets=%s|rows=%s"
               % (RUN, mode, missing, json.dumps(rows, default=str)))
    if mode == "DRY":
        unreal.log("RIG_TUBES_EVERYWHERE_DRY_OK|run=%s|structures=%d|refused=%d"
                   % (RUN, len(rows), sum(1 for r in rows if r["refused"])))
        return

    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))

    if mode == "APPLY":
        if missing:
            stop("ASSETS_MISSING|%s" % missing)
        refused = [r["structure"] for r in rows if r["refused"]]
        if refused:
            stop("UNDERPASS_OFF|%s|set enable_underpass_where_off (a look call) or drop them from structures" % refused)
        if os.path.exists(RECORD):
            stop("RECORD_EXISTS|" + RECORD)
        backup = "E:/PussStage/Backups/PreRigTubesEverywhere-%s" % RUN
        os.makedirs(backup)
        with open(RECORD, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "args": a, "backup": backup,
                       "before": {r["structure"]: r["before"] for r in rows}}, h, indent=1, default=str)
            h.flush()
            os.fsync(h.fileno())
        shutil.copy2(UMAP, backup)
        targets = {label: target_for(label, actor.get_editor_property("underpass"), a, assets)
                   for label, actor in structures.items()}
    else:
        if not os.path.exists(RECORD):
            stop("NO_RECORD|" + RECORD)
        rec = json.load(open(RECORD, encoding="utf-8"))
        targets = {}
        for label, b in rec["before"].items():
            if label not in structures:
                stop("REVERT_STRUCTURE_NOT_IN_ARGS|%s" % label)
            targets[label] = {k: (unreal.load_asset(v) if isinstance(v, str) else v) for k, v in b.items()}

    after = {}
    for label, t in targets.items():
        actor = structures[label]
        under = actor.get_editor_property("underpass")
        for k, v in t.items():
            under.set_editor_property(k, v)
        actor.modify()
        actor.set_editor_property("underpass", under)
        back = plain(actor.get_editor_property("underpass"))
        want = {k: plain_value(v) for k, v in t.items()}
        bad = {k: (back[k], want[k]) for k in want if not same(back[k], want[k])}
        if bad:
            stop("READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, json.dumps(bad, default=str)))
        if not actor.materialize_structure():
            stop("MATERIALIZE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % label)
        if not actor.is_structure_current():
            stop("NOT_CURRENT|%s|NOTHING SAVED; Don't-Save restart" % label)
        after[label] = {"tubes": actor.get_editor_property("underpass_tube_count"),
                        "lights": actor.get_editor_property("underpass_tube_light_count"),
                        "light_every_used": actor.get_editor_property("underpass_tube_light_every_used"),
                        "blinkers": len(actor.get_editor_property("underpass_tube_blinkers"))}
        unreal.log("RIG_TUBES_EVERYWHERE_BUILT|run=%s|structure=%s|%s" % (RUN, label, json.dumps(after[label])))

    dirty = census()
    if dirty["maps"] != [WORLD] or dirty["content"]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_MAP_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(RECORD, RECORD + ".reverted-" + RUN)
    unreal.log("RIG_TUBES_EVERYWHERE_%s_OK|run=%s|structures=%d|after=%s|saved=level|dirty_after=0+0"
               % (mode, RUN, len(after), json.dumps(after)))


main()
