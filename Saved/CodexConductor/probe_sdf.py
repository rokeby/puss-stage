import json
def main():
    import unreal
    out = {}
    for p in ("/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/SM_PearlClam_Bottom", "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/SM_PearlClam_Lid",
              "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/SM_PearlClam_Mantle", "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/SM_PearlClam_Pearl_v2"):
        m = unreal.load_asset(p)
        if m is None:
            out[p] = None; continue
        bs = unreal.EditorStaticMeshLibrary.get_lod_build_settings(m, 0) if hasattr(unreal.EditorStaticMeshLibrary, "get_lod_build_settings") else None
        out[p.split("/")[-1]] = {"gen_df": bool(bs.get_editor_property("generate_distance_field_as_if_two_sided")) if bs else None,
                                 "df_res": bs.get_editor_property("distance_field_resolution_scale") if bs else None,
                                 "nanite": bool(m.get_editor_property("nanite_settings").get_editor_property("enabled"))}
    unreal.log("PROBE_SDF_OK|" + json.dumps(out))
main()
