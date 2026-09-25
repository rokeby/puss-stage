"""Read what a gridiron must be built against, from the materialized panel records."""
import collections, json, os, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert "L_InfinityStage_V1VerticalSlice" in ed.get_editor_world().get_path_name(), "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
out = {}
for a in sub.get_all_level_actors():
    if a.get_class().get_name() != "InfinityStagePassageActor": continue
    lbl = a.get_actor_label()
    if not lbl.startswith("Passage 0"): continue
    panels = a.get_editor_property("materialized_panels")
    by_cue = collections.defaultdict(dict)
    for ref in panels:
        g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
        side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
        by_cue[g][side] = ref.get_editor_property("base_world_transform").translation
    stations = []
    for g, sides in by_cue.items():
        if "LEFT" in sides and "RIGHT" in sides:
            L, R = sides["LEFT"], sides["RIGHT"]
            stations.append(((L.x + R.x) / 2.0, (L.y + R.y) / 2.0, (L.z + R.z) / 2.0,
                             abs(L.y - R.y), max(L.z, R.z)))
    stations.sort()
    xs = [s[0] for s in stations]
    gaps = [round(b - a2) for a2, b in zip(xs, xs[1:])]
    out[lbl[:10]] = {
        "pairs": len(stations),
        "first_station": [round(v) for v in stations[0][:3]] if stations else None,
        "last_station": [round(v) for v in stations[-1][:3]] if stations else None,
        "gap_cm": collections.Counter(gaps).most_common(3),
        "corridor_width_cm": round(sum(s[3] for s in stations) / len(stations)) if stations else None,
        "panel_base_z": round(stations[0][4]) if stations else None,
        "route_len": round(a.get_editor_property("route").get_spline_length()),
    }
json.dump(out, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "gridiron_probe.json"), "w"), indent=1)
unreal.log("PUSS_GRIDIRON_PROBE|" + json.dumps(out))
