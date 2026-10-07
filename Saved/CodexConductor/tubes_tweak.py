"""Tubes tweak (Gary 7 Oct, P01): "90% of the fluorescents on the fence can go off, with a few of those blinking. The
fluorescents wash whiteness more than I'd prefer - I mostly want them bright when looking at them with a halo but not
much light pollution - dim?"  -> per structure: TubeDeadFraction, TubeBlinkFraction, TubeGlowLevel (emissive, the halo),
TubeLightIntensity (lumens, the spill). Same guarded DRY/APPLY/REVERT path as rig_tubes_everywhere.py (live-proven 6 Oct):
record (fsync) + umap backup before the first write, read back, MaterializeStructure, IsStructureCurrent, census = the
level only, save the level, census clean. Dead selection is monotonic (Spot.bAlive = Random >= DeadFraction,
InfinityStageStructureActor.cpp:2148 + the per-spot stream), so raising it only switches tubes OFF, never re-rolls
which ones live [declaration-proven]. Blinkers are drawn among the alive tubes (BlinkPick < BlinkFraction).
Args: tubes_tweak_args.json {"mode", "confirm": "<MODE> tubes tweak", "structures": [...], "set": {field: value},
"glow_scale": x (multiplies the live glow), "light_scale": y (multiplies the live intensity)}.
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS = HERE + "tubes_tweak_args.json"
RECORD = HERE + "tubes_tweak_record.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
TUBE_MESH = "/Engine/BasicShapes/Cylinder"
TUBE_MI = "/Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Tube_Office"
LIGHT_FN = "/Game/InfinityStage/Lighting/MI_LF_Flicker_Hum"
CONFIRM_TAIL = "tubes tweak"
DEFAULTS = {"mode": "DRY", "structures": ["Infinity Stage - Structure 01"], "set": {}, "glow_scale": None, "light_scale": None}
# Every Underpass field this tool may write (snake_case UPROPERTY names). "enabled" only with enable_underpass_where_off.
FIELDS = ("tube_dead_fraction", "tube_blink_fraction", "tube_glow_level", "tube_light_intensity", "enabled", "tubes")
TU_FIELDS = ("tube_glow_level", "tube_blink_fraction")
RUN = datetime.datetime.now().strftime("TT-%Y%m%d-%H%M%S")


def stop(msg):
    unreal.log_error("TUBES_TWEAK_FAILED|run=%s|%s" % (RUN, msg))
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
        unreal.log("TUBES_TWEAK_NO_ARGS|run=%s|running DRY with the defaults" % RUN)
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
    """The four fields APPLY writes: explicit "set" values, then the scales on the LIVE glow / intensity."""
    if not under.get_editor_property("enabled") or not under.get_editor_property("tubes"):
        return None
    t = {}
    merged = dict(a.get("set") or {})
    merged.update((a.get("per_structure") or {}).get(label, {}))
    for k, v in merged.items():
        if k not in FIELDS[:4]:
            stop("FIELD_NOT_ALLOWED|%s" % k)
        t[k] = float(v)
    if a.get("glow_scale") is not None:
        t["tube_glow_level"] = float(under.get_editor_property("tube_glow_level")) * float(a["glow_scale"])
    if a.get("light_scale") is not None:
        t["tube_light_intensity"] = float(under.get_editor_property("tube_light_intensity")) * float(a["light_scale"])
    if not 0.0 <= t.get("tube_dead_fraction", 0.0) <= 1.0 or not 0.0 <= t.get("tube_blink_fraction", 0.0) <= 1.0:
        stop("FRACTION_RANGE|%s" % t)
    if not 0.0 <= t.get("tube_glow_level", 0.0) <= 8.0:
        stop("GLOW_RANGE|%s" % t)
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
                     "counts": {"tubes": actor.get_editor_property("underpass_tube_count"),
                                "lights": actor.get_editor_property("underpass_tube_light_count"),
                                "blinkers": len(actor.get_editor_property("underpass_tube_blinkers"))},
                     "refused": None if t is not None else ("ASSETS_MISSING" if missing else "UNDERPASS_OR_TUBES_OFF")})
    unreal.log("TUBES_TWEAK_PLAN|run=%s|mode=%s|missing_assets=%s|rows=%s"
               % (RUN, mode, missing, json.dumps(rows, default=str)))
    if mode == "DRY":
        unreal.log("TUBES_TWEAK_DRY_OK|run=%s|structures=%d|refused=%d"
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
        backup = "E:/PussStage/Backups/PreTubesTweak-%s" % RUN
        os.makedirs(backup)
        with open(RECORD, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "args": a, "backup": backup,
                       "before": {r["structure"]: {k: r["before"][k] for k in FIELDS[:4]} for r in rows},
                       "counts_before": {r["structure"]: r["counts"] for r in rows}}, h, indent=1, default=str)
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
            targets[label] = {k: v for k, v in b.items() if k in FIELDS[:4]}

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
        unreal.log("TUBES_TWEAK_BUILT|run=%s|structure=%s|%s" % (RUN, label, json.dumps(after[label])))

    dirty = census()
    if dirty["maps"] != [WORLD] or dirty["content"]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_MAP_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    if mode == "REVERT":
        os.replace(RECORD, RECORD + ".reverted-" + RUN)
    unreal.log("TUBES_TWEAK_%s_OK|run=%s|structures=%d|after=%s|saved=level|dirty_after=0+0"
               % (mode, RUN, len(after), json.dumps(after)))


main()
