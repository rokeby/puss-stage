"""READ-ONLY (8 Oct): census of every MovieSceneVisibilityTrack in the show's sequences, by bound property.
[decl] the engine's visibility track binds AActor::bHidden with VISIBLE channel semantics (MovieScenePropertyTrack.h:53-56);
tracks bound to bHiddenInGame were measured inert on actors in PIE (PIES2VIS-185717).  Writes probe_vis_census.json.
VISCENSUS_OK / VISCENSUS_FAILED.  Saves nothing (load_asset only)."""
import json

OUT = "E:/PussStage/Saved/CodexConductor/probe_vis_census.json"


def main():
    import unreal as u
    ar = u.AssetRegistryHelpers.get_asset_registry()
    flt = u.ARFilter(class_paths=[u.TopLevelAssetPath("/Script/LevelSequence", "LevelSequence")], package_paths=["/Game"], recursive_paths=True)
    res = {}
    for d in ar.get_assets(flt):
        path = str(d.package_name)
        if not (path.startswith("/Game/InfinityStage") or path.startswith("/Game/Scenes")):
            continue
        seq = u.load_asset(path)
        if seq is None: continue
        rows = {}
        for b in seq.get_bindings():
            for t in b.get_tracks():
                if isinstance(t, u.MovieSceneVisibilityTrack):
                    p = str(t.get_property_name())
                    rows.setdefault(p, []).append(str(b.get_display_name()))
        if rows:
            res[path] = {p: {"n": len(v), "bindings": sorted(set(v))[:400]} for p, v in rows.items()}
    json.dump(res, open(OUT, "w"), indent=1)
    summ = {k: {p: v["n"] for p, v in r.items()} for k, r in res.items()}
    u.log("VISCENSUS_OK|seqs=%d|%s" % (len(res), json.dumps(summ)))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("VISCENSUS_FAILED|%r" % (exc,))
