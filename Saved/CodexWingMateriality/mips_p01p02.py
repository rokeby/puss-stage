"""Mipmaps ON (option a: MipGen FromTextureGroup at native size) for the live P01 and P02 wing
textures. Gary's choice via the conductor, 30 Sep: "Yes, P01+P02 first". No compression change,
no other passages.

Phase via mips_request.json {"phase": "plan" | "apply" | "revert", "include_shared": bool}:
  plan    read-only: every texture the P01/P02 wing components' materials use
          (MaterialEditingLibrary.get_used_textures), under /Game/Scenes/Wings and
          currently TMGS_NoMipmaps. Textures ALSO used by wings in other passages are
          listed separately as collateral. Writes mips_plan.json.
  apply   set FromTextureGroup on the planned textures (shared ones only if
          include_shared), save only those assets, write the prior state to
          mips_rollback.json.
  revert  set every texture in mips_rollback.json back to its prior MipGen and save.
Mip 0 is untouched: no resize, no format change.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL
NO_MIPS = unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS
FROM_GROUP = unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP


def wing_textures_by_passage():
    by_tex = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_name() != "InfinityStagePassageActor":
            continue
        passage = actor.get_actor_label()[:10].replace("Passage ", "P")
        for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
            if "InfinityStage.Managed" not in [str(t) for t in comp.get_editor_property("component_tags")]:
                continue
            for mat in comp.get_materials():
                if mat is None:
                    continue
                getter = getattr(MEL, "get_material_used_textures", None) or MEL.get_used_textures
                for tex in getter(mat):
                    p = wm.pkg(tex)
                    if p and p.startswith("/Game/Scenes/Wings/"):
                        by_tex.setdefault(p, set()).add(passage)
    return by_tex


wm.editor_ready()
before = wm.dirty()
req = wm.read_json("mips_request.json")
phase = req["phase"]
if phase == "plan":
    by_tex = wing_textures_by_passage()
    plan = {"only_p01_p02": [], "shared_with_other_passages": {}, "already_have_mips": 0}
    for p, passages in sorted(by_tex.items()):
        if not ({"P01", "P02"} & passages):
            continue
        tex = unreal.EditorAssetLibrary.load_asset(p)
        if tex.get_editor_property("mip_gen_settings") != NO_MIPS:
            plan["already_have_mips"] += 1
            continue
        others = sorted(passages - {"P01", "P02"})
        if others:
            plan["shared_with_other_passages"][p] = others
        else:
            plan["only_p01_p02"].append(p)
    wm.require(wm.dirty() == before, "plan changed the dirty set")
    wm.write_json("mips_plan.json", plan)
    unreal.log(f"PUSS_WING_MIPS_PLAN_SUCCESS|only_p01_p02={len(plan['only_p01_p02'])}"
               f"|shared={len(plan['shared_with_other_passages'])}|already={plan['already_have_mips']}")
elif phase == "apply":
    wm.require(before == [], f"Refusing to write with dirty packages present: {before}")
    plan = wm.read_json("mips_plan.json")
    targets = list(plan["only_p01_p02"]) + (list(plan["shared_with_other_passages"]) if req.get("include_shared") else [])
    rollback = {}
    for p in targets:
        tex = unreal.EditorAssetLibrary.load_asset(p)
        rollback[p] = str(tex.get_editor_property("mip_gen_settings"))
    wm.write_json("mips_rollback.json", rollback)
    for p in targets:
        tex = unreal.EditorAssetLibrary.load_asset(p)
        tex.set_editor_property("mip_gen_settings", FROM_GROUP)
        wm.require(tex.get_editor_property("mip_gen_settings") == FROM_GROUP, f"{p} did not take")
        wm.require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), f"save {p}")
    after = wm.dirty()
    wm.require(after == [], f"dirty after apply: {after}")
    unreal.log(f"PUSS_WING_MIPS_APPLY_SUCCESS|textures={len(targets)}|dirty=0")
elif phase == "revert":
    wm.require(before == [], f"Refusing to write with dirty packages present: {before}")
    rollback = wm.read_json("mips_rollback.json")
    for p in rollback:
        tex = unreal.EditorAssetLibrary.load_asset(p)
        tex.set_editor_property("mip_gen_settings", NO_MIPS)
        wm.require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), f"save {p}")
    wm.require(wm.dirty() == [], "dirty after revert")
    unreal.log(f"PUSS_WING_MIPS_REVERT_SUCCESS|textures={len(rollback)}")
