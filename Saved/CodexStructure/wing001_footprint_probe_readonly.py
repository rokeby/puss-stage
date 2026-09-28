"""Read-only: dump what is needed to find where P01 Wing 001's painted cards are
OPAQUE near the floor, for the curtain pile question (the staging lays a
2.3-3.9 m pile from the curtain line at x 0 across Wing 001 at x 250).

Spawns nothing and captures nothing, so it cannot dirty the level. For each Wing
001 panel it writes the mesh's sections as world-space vertices, UVs and
triangles through the panel's actual ISM instance transform (which carries any
Flip Image Horizontally as a -1 Y scale, see PassageActor materialization), and
each material slot's texture parameters with their source image files on disk.
wing001_footprint_analyze.py then rasterises the alpha file-side.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TARGET = "P01 Wing 001"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "wing001_footprint_probe.json")

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
show = passage.get_editor_property("show_asset")
cue = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == TARGET)
guid = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
pair = cue.get_editor_property("wing_pair")
flips = {}
for side in ("left", "right"):
    try:
        flips[side] = bool(pair.get_editor_property(side).get_editor_property("flip_image_horizontally"))
    except Exception as exc:  # the field layout is not this stream's; record, don't guess
        flips[side] = f"unreadable: {exc}"


def texture_info(material):
    out = []
    names = []
    try:
        names = [str(n) for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)]
    except Exception as exc:
        out.append({"error": f"names: {exc}"})
    for name in names:
        tex = None
        for getter in (lambda: unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, name),
                       lambda: material.k2_get_texture_parameter_value(name)):
            try:
                tex = getter()
                if tex:
                    break
            except Exception:
                continue
        rec = {"parameter": name, "texture": tex.get_path_name() if tex else None}
        if tex:
            try:
                rec["source"] = tex.get_editor_property("asset_import_data").get_first_filename()
            except Exception as exc:
                rec["source"] = f"unreadable: {exc}"
            rec["size"] = [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]
        out.append(rec)
    return out


panels = []
for ref in passage.get_editor_property("materialized_panels"):
    if unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid")) != guid:
        continue
    comp = ref.get_editor_property("component")
    index = ref.get_editor_property("instance_index")
    tf = comp.get_instance_transform(index, True)
    mesh = comp.get_editor_property("static_mesh")
    sections = []
    for s in range(mesh.get_num_sections(0)):
        verts, tris, normals, uvs, tangents = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, s)
        world_verts = [unreal.MathLibrary.transform_location(tf, v) for v in verts]
        sections.append({"section": s,
                         "verts": [[round(v.x, 2), round(v.y, 2), round(v.z, 2)] for v in world_verts],
                         "uvs": [[round(u.x, 5), round(u.y, 5)] for u in uvs],
                         "tris": list(tris)})
    materials = []
    for slot in range(comp.get_num_materials()):
        m = comp.get_material(slot)
        slot_name = None
        try:
            slot_name = str(mesh.get_editor_property("static_materials")[slot].get_editor_property("material_slot_name"))
        except Exception:
            pass
        materials.append({"slot": slot, "slot_name": slot_name, "material": m.get_path_name() if m else None,
                          "textures": texture_info(m) if m else []})
    s = tf.scale3d
    panels.append({"side": str(ref.get_editor_property("side")), "component": comp.get_name(), "instance": index,
                   "mesh": mesh.get_path_name(), "scale": [s.x, s.y, s.z],
                   "base_world": [ref.get_editor_property("base_world_transform").translation.x,
                                  ref.get_editor_property("base_world_transform").translation.y,
                                  ref.get_editor_property("base_world_transform").translation.z],
                   "sections": sections, "materials": materials})

json.dump({"cue": TARGET, "flip_image_horizontally": flips, "panels": panels}, open(OUT, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"WING001_FOOTPRINT_PROBE_OK|panels={len(panels)}|flips={flips}"
           f"|sections={[len(p['sections']) for p in panels]}|dirty={dirty[0]}+{dirty[1]}|mutated=0")
