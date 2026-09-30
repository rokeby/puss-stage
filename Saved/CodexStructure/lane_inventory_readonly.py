"""READ-ONLY (30 Sep): the uncounted remainder of the hangar-exit docking cost (Docs/HangarExitCost_2026-09-30.md).
For each Passage lane that docking would move (LANES, default 2..6), what rides free, what must be moved by hand,
and which sequence bindings hold WORLD-SPACE transform data that a move would have to re-key.

Lanes: Passage N runs +X at y = (N-1) x 800 m; an actor belongs to lane N if its y lies within +-400 m of that.
Actors within 50 m of a lane boundary are listed as "boundary" (the dev Scene sites sit exactly there, at x = 0,
y = lane + 400 m), never silently assigned.

Per actor (root actors only; an attached actor is counted under its root and rides with it):
  the_move     the lane's Passage actor and Structure actor (Show content anchored to them rides along)
  stage_actor  any other InfinityStage* actor (camera rig, curtain rig, shadow cat...): listed, how it follows not assumed
  hangar       tagged RigAtmos.Scene{N}Hangar (rebuilt at the new dock, not moved)
  arrival      InfinityStageArrival (re-applied at the new dock)
  landscape    LandscapeProxy (hidden, stays; delete pending)
  global       sky, fog, sun/moon, celestial rig, world-fixed volumes (they do not belong to a lane)
  hand_move    everything else: moved by hand, with its attached children
Per sequence binding with a 3D transform track: whether its Location channels hold keys or a default, and so world-
space data a move must re-key. The lane comes from the bound ACTOR (possessable matched by label: declaration-level,
labels can drift) or, failing that, from the keyed position itself (marked "lane_by_key_position": INFERRED). A binding
with an attach track, or a possessable whose actor is attached, is relative and rides with its parent.

Guards: expected world, no PIE. Mutates nothing: no modify, no set, no save; checks the dirty set is unchanged at the
end. Never calls GetBoundObjects. Everything inside main(). Writes lane_inventory_<run>.json and logs
LANE_INVENTORY|run=<id>|... (wait for THIS run id)."""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
LANE_CM, HALF_CM, EDGE_CM = 80000.0, 40000.0, 5000.0
GLOBAL_CLASSES = ("ExponentialHeightFog", "SkyAtmosphere", "SkyLight", "DirectionalLight", "VolumetricCloud",
                  "InfinityStageCelestialRig", "WorldSettings", "WorldDataLayers", "AtmosphericFog", "LevelBounds",
                  "InfinityStageShowRoot", "Brush", "DefaultPhysicsVolume", "GameplayDebuggerPlayerManager")


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    lanes = tuple(globals().get("LANES", (2, 3, 4, 5, 6)))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        unreal.log_error(f"LANE_INVENTORY|refused|run={run}|wrong world, or PIE")
        return
    dirty0 = sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()

    def lane_of_y(y):
        n = int(round(y / LANE_CM)) + 1
        off = y - (n - 1) * LANE_CM
        return n, abs(off) > HALF_CM - EDGE_CM

    def root_of(a):
        p = a.get_attach_parent_actor()
        while p is not None:
            a, p = p, p.get_attach_parent_actor()
        return a

    rows, by_label, children = {}, {}, {}
    for a in actors:
        label = a.get_actor_label()
        by_label.setdefault(label, []).append(a)
        r = root_of(a)
        if r is not a:
            children[r.get_actor_label()] = children.get(r.get_actor_label(), 0) + 1
    lanes_out = {n: {"the_move": [], "stage_actor": [], "hangar": 0, "arrival": [], "landscape": [], "global": [], "hand_move": [], "boundary": []} for n in lanes}
    for a in actors:
        if a.get_attach_parent_actor() is not None:
            continue
        label, cls = a.get_actor_label(), a.get_class().get_name()
        loc = a.get_actor_location()
        n, edge = lane_of_y(loc.y)
        if n not in lanes_out:
            continue
        row = {"label": label, "class": cls, "loc_m": [round(loc.x / 100, 1), round(loc.y / 100, 1), round(loc.z / 100, 1)],
               "attached_children": children.get(label, 0)}
        tags = [str(t) for t in a.get_editor_property("tags")]
        L = lanes_out[n]
        if cls in GLOBAL_CLASSES or any(g in cls for g in ("Sky", "Fog", "Celestial")):
            L["global"].append(label)
        elif edge:
            L["boundary"].append(row)
        elif cls == "InfinityStageArrival":            # before the hangar test: an Arrival carries its hangar's tag
            L["arrival"].append(label)
        elif any(t.startswith("RigAtmos.Scene") and t.endswith("Hangar") for t in tags):
            L["hangar"] += 1 + children.get(label, 0)
        elif cls in ("InfinityStagePassageActor", "InfinityStageStructureActor"):
            L["the_move"].append(row)
        elif cls.startswith("InfinityStage"):          # camera rig, curtain rig, shadow cat, effect source, wing proxy:
            L["stage_actor"].append(row)               # how each follows its Passage is not assumed here
        elif isinstance(a, unreal.LandscapeProxy):
            L["landscape"].append(label)
        else:
            L["hand_move"].append(row)

    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    seq_paths = sorted({str(d.package_name) for d in reg.get_assets_by_path("/Game", recursive=True)
                        if str(d.asset_class_path.asset_name) == "LevelSequence"})
    rekey, relative, unresolved, seq_errors, located = [], 0, [], [], []
    for path in seq_paths:
        seq = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(seq, unreal.LevelSequence):
            continue
        try:
            spawn_ids = {str(b.get_id()) for b in seq.get_spawnables()}
            for b in seq.get_bindings():
                tracks = list(b.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
                if not tracks:
                    continue
                name = str(b.get_display_name())
                attached = bool(list(b.find_tracks_by_type(unreal.MovieScene3DAttachTrack)))
                keys, has_def, sample, names = 0, False, None, []
                for t in tracks:
                    for s in t.get_sections():
                        loc = [ch for ch in s.get_all_channels() if str(ch.get_name()).startswith("Location")]
                        names = [str(ch.get_name()) for ch in loc]
                        for i, ch in enumerate(loc):
                            k = ch.get_keys()
                            keys += len(k)
                            d = ch.has_default()
                            has_def = has_def or d
                            # the second Location channel is Y (order X, Y, Z; the name is recorded to check)
                            if i == 1 and sample is None:
                                sample = k[0].get_value() if k else (ch.get_default() if d else None)
                if not keys and not has_def:
                    continue
                spawnable = str(b.get_id()) in spawn_ids
                matched = by_label.get(name, []) if not spawnable else []
                entry = {"sequence": path, "binding": name, "spawnable": spawnable, "location_keys": keys, "location_default": has_def,
                         "location_channels": names, "y_sample_cm": sample, "label_matches": len(matched)}
                if attached or (len(matched) == 1 and matched[0].get_attach_parent_actor() is not None):
                    relative += 1
                    continue
                if len(matched) == 1:
                    n, edge = lane_of_y(matched[0].get_actor_location().y)
                    entry["lane_by"] = "bound_actor_label"
                elif sample is not None:
                    n, edge = lane_of_y(float(sample))
                    entry["lane_by"] = "lane_by_key_position (INFERRED: relative data would read as lane 1)"
                else:
                    unresolved.append(entry)
                    continue
                entry["lane"], entry["boundary"] = n, edge
                located.append(entry)
                if n in lanes_out:
                    rekey.append(entry)
        except Exception as exc:  # noqa: BLE001  read-only: report API drift, never stop the inventory
            seq_errors.append(f"{path}: {exc}")

    refs = {}
    for path in sorted({e["sequence"] for e in located}):
        refs[path] = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False) if str(r) != path]
    dirty1 = sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    out = {"run": run, "lanes": lanes_out, "sequences_scanned": len(seq_paths), "rekey": rekey, "relative_bindings": relative,
           "unresolved": unresolved, "located_all_lanes": located, "referencers": refs, "sequence_errors": seq_errors, "dirty_before": dirty0, "dirty_after": dirty1}
    path = os.path.join(HERE, f"lane_inventory_{run}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    summary = {n: {"move": len(L["the_move"]), "stage_actor": len(L["stage_actor"]), "hand_move": len(L["hand_move"]),
                   "hand_move_with_children": sum(1 + r["attached_children"] for r in L["hand_move"]),
                   "hangar": L["hangar"], "arrival": len(L["arrival"]), "boundary": len(L["boundary"]),
                   "rekey_bindings": sum(1 for r in rekey if r["lane"] == n)} for n, L in lanes_out.items()}
    unreal.log(f"LANE_INVENTORY|run={run}|{json.dumps(summary)}|sequences={len(seq_paths)}|relative={relative}|unresolved={len(unresolved)}"
               f"|seq_errors={len(seq_errors)}|dirty_unchanged={dirty0 == dirty1}|file={path}")


main()
