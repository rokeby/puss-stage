"""Read-only: which Show sequences bind lights, post-process, sky or the celestial rig, and what tracks they carry."""
import json, os
import unreal
def pkg(v): return v.get_path_name().split(".",1)[0] if v is not None and hasattr(v,"get_path_name") else None
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
seqs = set()
for n in ("master_sequence", "managed_master_sequence", "master"):
    try:
        v = show.get_editor_property(n)
        if v: seqs.add(pkg(v))
    except Exception: pass
for cue in show.get_editor_property("cues"):
    for n in ("sequence", "level_sequence", "scene_sequence"):
        try:
            v = cue.get_editor_property(n)
            if v: seqs.add(pkg(v))
        except Exception: pass
reg = unreal.AssetRegistryHelpers.get_asset_registry()
for ad in reg.get_assets_by_path("/Game/InfinityStage", recursive=True):
    if str(ad.asset_class_path.asset_name) == "LevelSequence": seqs.add(str(ad.package_name))
KEY = ("light", "sky", "fog", "post", "celest", "exposure", "atmos", "sun", "moon")
report = {}
for path in sorted(seqs):
    ls = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(ls, unreal.LevelSequence): continue
    rec = {"bindings": [], "tracks": []}
    ms = ls.get_movie_scene()
    for b in ls.get_bindings():
        name = b.get_name(); cls = str(b.get_possessed_object_class()) if b.get_possessed_object_class() else "?"
        tracks = [t.get_display_name().__str__() if hasattr(t, "get_display_name") else t.get_class().get_name() for t in b.get_tracks()]
        hit = any(k in (name + cls + " ".join(tracks)).lower() for k in KEY)
        if hit: rec["bindings"].append({"name": name, "class": cls[:80], "tracks": tracks[:12]})
    for t in ls.get_tracks():
        n = t.get_class().get_name(); rec["tracks"].append(n)
    report[path] = rec
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "sequence_lighting.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(report, fh, indent=1, default=str)
unreal.log(f"PUSS_SEQ_LIGHTING_SUCCESS|sequences={len(report)}|with_light_bindings={sum(1 for r in report.values() if r['bindings'])}")
