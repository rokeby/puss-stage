"""Apply Gary's material choice B (30 Sep: "B ...") to the drape's MI ONLY: VelvetColor and SheenColor, the values benched
as variant B (material_bench_variants.json). Backs up the MI's .uasset first, saves ONLY that asset, reads it back, and
reads Rig's border MI (a child) to show its own overrides are untouched. Mode: apply_drape_material_b_mode.json
{"dry_run": true|false}. Logs PUSS_SOFTGOODS_MATERIAL_B|... Crash rules: everything inside main()."""
import datetime
import json
import os
import shutil

import unreal

MI = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
B = {"VelvetColor": (0.07, 0.004, 0.012, 1.0), "SheenColor": (0.32, 0.03, 0.07, 1.0)}
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    with open(os.path.join(HERE, "apply_drape_material_b_mode.json"), encoding="utf-8") as h:
        dry = bool(json.load(h).get("dry_run", True))
    lib = unreal.MaterialEditingLibrary
    mi = unreal.load_asset(MI)
    before = {k: str(lib.get_material_instance_vector_parameter_value(mi, k)) for k in B}
    borders = [a for a in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True) if "PortalBorder" in a]
    border = unreal.load_asset(borders[0]) if borders else None
    border_before = ({k: str(lib.get_material_instance_vector_parameter_value(border, k)) for k in B}
                     if border else None)
    dirty0 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if dry or dirty0:
        return unreal.log(f"PUSS_SOFTGOODS_MATERIAL_B|{'DRY RUN' if dry else 'refused: dirty ' + str(dirty0)}"
                          f"|before={before}|border={borders[:1]}:{border_before}")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreDrapeMaterialB-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *MI[len("/Game/"):].split("/")) + ".uasset", backup)
    for k, v in B.items():
        lib.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*v))
    lib.update_material_instance(mi)
    dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    unexpected = [p for p in dirty if p != MI]
    if unexpected:
        return unreal.log(f"PUSS_SOFTGOODS_MATERIAL_B|STOPPED: unexpected dirty {unexpected}; nothing saved|backup={backup}")
    saved = unreal.EditorAssetLibrary.save_asset(MI, only_if_is_dirty=False)
    mi = unreal.load_asset(MI)
    after = {k: str(lib.get_material_instance_vector_parameter_value(mi, k)) for k in B}
    border_after = ({k: str(lib.get_material_instance_vector_parameter_value(border, k)) for k in B} if border else None)
    unreal.log(f"PUSS_SOFTGOODS_MATERIAL_B|applied|saved={saved}|before={before}|after={after}"
               f"|border_after={border_after}|backup={backup}")


main()
