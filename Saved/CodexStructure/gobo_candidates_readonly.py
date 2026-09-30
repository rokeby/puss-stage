"""Read-only: sizes and default materials of candidate gobo meshes, and P01's
blink spot source radii (these set how soft its shadow can go). Mutates nothing."""
import json
import os

import unreal

MESHES = ["/Game/EnvironmentPacks/Forest_Environment_Set/Environment/Small_Architecture/Meshes/SM_wood_beam_01",
          "/Game/EnvironmentPacks/Forest_Environment_Set/Environment/Small_Architecture/Meshes/SM_wood_beam_02",
          "/Game/EnvironmentPacks/Forest_Environment_Set/Environment/Small_Architecture/Meshes/SM_barrier_board_01",
          "/Game/Scenes/Wings/MiscOriginal/StaticMeshes/SM_vertical_metal_downpipe",
          "/Engine/BasicShapes/Cylinder", "/Engine/BasicShapes/Cube"]


def main():
    out = {"meshes": {}}
    for path in MESHES:
        m = unreal.EditorAssetLibrary.load_asset(path)
        if not m:
            out["meshes"][path] = None
            continue
        b = m.get_bounding_box()
        mats = [s.get_editor_property("material_interface") for s in m.get_editor_property("static_materials")]
        out["meshes"][path] = {"min": [round(b.min.x, 1), round(b.min.y, 1), round(b.min.z, 1)],
                               "max": [round(b.max.x, 1), round(b.max.y, 1), round(b.max.z, 1)],
                               "materials": [x.get_path_name() if x else None for x in mats],
                               "tris": m.get_num_triangles(0)}
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    for cue in show.get_editor_property("cues"):
        if str(cue.get_editor_property("label")) != "P01 Wing 041":
            continue
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if str(a.get_editor_property("label")) == "P01 Wing 041 Entry High -Y":
                L = a.get_editor_property("lighting")
                out["p01_spot"] = {k: L.get_editor_property(k) for k in
                                   ("source_radius_cm", "soft_source_radius_cm", "source_length_cm",
                                    "shadow_bias", "shadow_slope_bias", "attenuation_radius_cm")}
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexStructure", "gobo_candidates.json")
    json.dump(out, open(path, "w"), indent=1)
    unreal.log(f"GOBO_CANDIDATES_OK|meshes={len(out['meshes'])}|mutated=0")


main()
