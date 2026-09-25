"""Read-only: per-Passage temporality settings and every stage-light attachment authored in the Show."""
import json, os, re
import unreal
def s(v):
    if isinstance(v, unreal.Transform):
        return {"loc": str(v.translation), "rot": str(v.rotation.rotator()), "scale": str(v.scale3d)}
    return v if isinstance(v, (int, float, bool, str)) or v is None else str(v)
def props(obj, names):
    out = {}
    for n in names:
        try: out[n] = s(obj.get_editor_property(n))
        except Exception: pass
    return out
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
cues = list(show.get_editor_property("cues"))
def label(i):
    return str(cues[i].get_editor_property("label")) if 0 <= i < len(cues) else None
passages = []
for ps in show.get_editor_property("passage_settings"):
    cc = ps.get_editor_property("celestial_cycle")
    first = show.find_cue_index(ps.get_editor_property("first_cue_guid")) if hasattr(show, "find_cue_index") else -1
    passages.append({"first_cue": label(first), "temporality": props(cc, ["animate", "cycle_duration_seconds", "cycle_rate_multiplier", "entry_phase_offset_cycles"])})
atts = []
LABEL_RE = re.compile(r"^P\d{2} Wing \d{3}$")
for i, cue in enumerate(cues):
    if not LABEL_RE.match(str(cue.get_editor_property("label"))): continue
    try: items = cue.get_editor_property("wing_pair").get_editor_property("attachments")
    except Exception: continue
    for att in items:
        rec = props(att, ["label", "kind", "enabled", "actor_class", "anchor", "relative_transform", "trigger_distance_cm"])
        try:
            L = att.get_editor_property("lighting")
            rec["lighting"] = props(L, ["type", "intensity", "intensity_units", "color", "temperature", "use_temperature", "attenuation_radius",
                                        "inner_cone_angle", "outer_cone_angle", "cast_shadows", "mobility", "source_radius", "soft_source_radius",
                                        "source_width", "source_height", "barn_door_angle", "barn_door_length", "indirect_lighting_intensity",
                                        "volumetric_scattering_intensity", "lighting_channel0", "lighting_channel1", "lighting_channel2"])
        except Exception as exc: rec["lighting_error"] = repr(exc)
        rec["cue"] = str(cue.get_editor_property("label")); atts.append(rec)
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "show_lighting.json")
with open(out, "w", encoding="utf-8") as fh: json.dump({"passages": passages, "attachments": atts}, fh, indent=1, default=str)
unreal.log(f"PUSS_SHOW_LIGHTING_SUCCESS|passages={len(passages)}|attachments={len(atts)}")
