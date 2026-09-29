"""Read-only: does "Passage 01 - Opening Floor" (a 1 m walnut slab, top at z +49.5)
render in game? It contradicts the 26 Sep captures, which showed void. Checks the
four things that could hide it: data layers, sequence bindings (a visibility
track), the level it lives in (a Level Instance?), and spatial loading / World
Partition. Plus the editor-only hide flags. Mutates nothing, spawns nothing.
"""
import json
import os

import unreal

LABEL = "Passage 01 - Opening Floor"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "opening_floor_provenance.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next(a for a in sub.get_all_level_actors() if a.get_actor_label() == LABEL)
rec = {"label": LABEL, "name": actor.get_name(), "path": actor.get_path_name()}


def attempt(key, fn):
    try:
        rec[key] = fn()
    except Exception as exc:
        rec[key] = f"unavailable: {type(exc).__name__}: {exc}"


# 1. Data layers.
def data_layers():
    out = {}
    try:
        out["assets"] = [a.get_path_name() for a in actor.get_editor_property("data_layer_assets") if a]
    except Exception as exc:
        out["assets"] = f"unavailable: {exc}"
    dls = unreal.get_editor_subsystem(unreal.DataLayerEditorSubsystem)
    for getter in ("get_actor_data_layer_instances", "get_actor_data_layers"):
        if hasattr(dls, getter):
            try:
                insts = getattr(dls, getter)(actor)
                out[getter] = [{"name": str(i.get_name()),
                                "loaded_in_editor": _safe(lambda: bool(i.is_loaded_in_editor())),
                                "initial_runtime_state": _safe(lambda: str(i.get_initial_runtime_state())),
                                "visible": _safe(lambda: bool(i.is_visible()))} for i in insts]
            except Exception as exc:
                out[getter] = f"unavailable: {exc}"
    return out


def _safe(fn):
    try:
        return fn()
    except Exception as exc:
        return f"unavailable: {exc}"


attempt("data_layers", data_layers)

# 2. Level / Level Instance / World Partition / spatial loading.
attempt("level", lambda: actor.get_level().get_path_name())
attempt("persistent_level", lambda: world.get_editor_property("persistent_level").get_path_name()
        if hasattr(world, "get_editor_property") else None)
attempt("is_spatially_loaded", lambda: bool(actor.get_editor_property("is_spatially_loaded")))
attempt("world_partition", lambda: bool(unreal.WorldPartitionBlueprintLibrary.get_actor_descs() is not None))
attempt("hidden_in_game", lambda: bool(actor.get_editor_property("hidden")))
attempt("hidden_in_editor_now", lambda: bool(actor.is_hidden_ed()))
attempt("temporarily_hidden_in_editor", lambda: bool(actor.is_temporarily_hidden_in_editor()))
attempt("net_load_on_client", lambda: bool(actor.get_editor_property("net_load_on_client")))
attempt("is_editor_only_actor", lambda: bool(actor.get_editor_property("is_editor_only_actor")))

# 3. Sequence bindings: every LevelSequence under /Game, possessables that resolve
# to this actor (or carry its label), and the tracks on them.
registry = unreal.AssetRegistryHelpers.get_asset_registry()
flt = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath("/Script/LevelSequence", "LevelSequence")],
                      package_paths=["/Game"], recursive_paths=True)
seqs = registry.get_assets(flt)
bindings = []
checked = 0
for data in seqs:
    seq = data.get_asset()
    if not seq:
        continue
    checked += 1
    for binding in seq.get_bindings():
        name = str(binding.get_display_name())
        hit = name == LABEL or "Opening Floor" in name
        if not hit:
            try:
                bound = unreal.MovieSceneSequenceExtensions.locate_bound_objects(seq, binding, world)
                hit = any(o == actor for o in bound)
            except Exception:
                pass
        if hit:
            bindings.append({"sequence": seq.get_path_name(), "binding": name,
                             "tracks": [t.get_class().get_name() for t in binding.get_tracks()]})
rec["sequences_checked"] = checked
rec["sequence_bindings"] = bindings

json.dump(rec, open(OUT, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"OPENING_FLOOR_PROVENANCE_OK|sequences={checked}|bindings={len(bindings)}"
           f"|data_layers={rec.get('data_layers')}|spatial={rec.get('is_spatially_loaded')}"
           f"|dirty={dirty[0]}+{dirty[1]}|mutated=0")
