import json, os, re, sys, unreal
HERE = unreal.Paths.project_saved_dir() + "CodexConductor/J115S3HessianShirts_20261009"
sys.path.insert(0, HERE)
import importlib, j115_core as core, j115_editor as ed
importlib.reload(core); importlib.reload(ed)
OUT = HERE + "/float_hold_shirt_record.json"
WORLD_PKG = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
lib = unreal.EditorLoadingAndSavingUtils
d0 = [p.get_name() for p in lib.get_dirty_content_packages()] + [p.get_name() for p in lib.get_dirty_map_packages()]
assert not d0, "DIRTY_BEFORE|%s" % d0
assert not os.path.exists(OUT), "RECORD_EXISTS"
rows = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    lab = str(a.get_actor_label())
    m = re.match(r"^S3 Hangar Float Hold: (Shore05_M53) Clam$", lab)
    if not m: continue
    fig = m.group(1)
    comp = ed.outfit_component(a)
    mats = [ed.path_of(comp.get_material(i)) for i in range(comp.get_num_materials())]
    slots = [i for i, p in enumerate(mats) if core.classify_material(p) == "shirt"]
    assert slots, "NO_SHIRT_SLOTS|" + lab
    target = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian/MI_%s_Shirt_Hessian_v1" % fig
    mi = unreal.load_asset(target); assert mi, "MISSING|" + target
    rows.append({"label": lab, "actor": a, "comp": comp, "slots": slots, "before": mats, "target": target, "mi": mi,
                 "overrides_before": [ed.path_of(x) for x in (comp.get_editor_property("override_materials") or [])]})
assert len(rows) == 1, "FLOAT_HOLD_COUNT|%d" % len(rows)
with open(OUT, "w") as fh:
    json.dump([{k: v for k, v in r.items() if k not in ("actor", "comp", "mi")} for r in rows], fh, indent=1)
for r in rows:
    r["actor"].modify(); r["comp"].modify()
    for i in r["slots"]:
        r["comp"].set_material(i, r["mi"])
for r in rows:
    got = [ed.path_of(r["comp"].get_material(i)) for i in r["slots"]]
    assert all(g == r["target"] for g in got), "READBACK|%s|%s" % (r["label"], got)
dirty_c = [p.get_name() for p in lib.get_dirty_content_packages()]
dirty_m = [p.get_name() for p in lib.get_dirty_map_packages()]
assert not dirty_c and dirty_m == [WORLD_PKG], "DIRTY_SCOPE|%s|%s" % (dirty_c, dirty_m)
ok = lib.save_dirty_packages(True, False)
left = [p.get_name() for p in lib.get_dirty_map_packages()]
assert not left, "MAP_STILL_DIRTY|%s" % left
unreal.log("FLOAT_HOLD_SHIRT_APPLY_OK|n=%d|slots=%d|record=%s" % (len(rows), sum(len(r["slots"]) for r in rows), OUT))
