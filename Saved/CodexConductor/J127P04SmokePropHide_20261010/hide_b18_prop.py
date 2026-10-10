import json, os, unreal
LABEL = "FX SMOKE P04 B18 L"
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/J127P04SmokePropHide_20261010/hide_b18_prop_record.json"
lib = unreal.EditorLoadingAndSavingUtils
assert not list(lib.get_dirty_content_packages()), "DIRTY_CONTENT_BEFORE"  # the map may be dirty from attempt 1 (same edit, same actor)
assert not os.path.exists(OUT), "RECORD_EXISTS"
hits = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label() == LABEL]
assert len(hits) == 1, "COUNT|%d" % len(hits)
a = hits[0]
comps = [c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name() == "Apparatus"]
assert comps, "NO_CUBE_MESH"
rec = {"label": LABEL, "components": [{"name": c.get_name(), "mesh": "/Engine/BasicShapes/Cube.Cube"} for c in comps]}
with open(OUT, "w") as fh: json.dump(rec, fh, indent=1)
a.modify()
for c in comps:
    c.modify(); c.set_static_mesh(None)  # BP_Effect_SmokePot construction resets visibility flags (live 10 Oct); clear the mesh instead, as job 127 planned
for c in comps:
    m = c.get_editor_property("static_mesh")
    assert m is None, "READBACK|%s|mesh=%s" % (c.get_name(), m)
dirty = [p.get_name() for p in lib.get_dirty_map_packages()]
assert len(dirty) == 1 and not list(lib.get_dirty_content_packages()), "DIRTY_SCOPE|%s" % dirty
lib.save_dirty_packages(True, False)
assert not list(lib.get_dirty_map_packages()), "STILL_DIRTY"
unreal.log("HIDE_B18_PROP_OK|components=%d|record=%s" % (len(comps), OUT))
