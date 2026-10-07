"""READ-ONLY: S3 clam / pedestal / table-rock actors: label, name, class, mesh, world AABB, parent, hidden, tags.
Writes probe_s3_clam_rock.json; marker S3CLAMROCK_OK|n=.. / S3CLAMROCK_FAILED."""
import json, re


def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    pat = re.compile(r"clam|pedas|pedest|tg0pfjxda|source_anim|rock|table|pearl|stone|slab", re.I)
    rows = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        lab, nm = str(a.get_actor_label()), str(a.get_name())
        o, e = a.get_actor_bounds(False)
        near = abs(o.x - 14417) < 200 and abs(o.y - 160000) < 200 and -200 < o.z < 400   # within ~2 m of the clam
        if not near:
            continue
        p = a.get_attach_parent_actor()
        meshes = []
        for c in a.get_components_by_class(unreal.MeshComponent):
            m = None
            try:
                m = c.get_editor_property("static_mesh")
            except Exception:
                try:
                    m = c.get_editor_property("skeletal_mesh_asset")
                except Exception:
                    m = None
            mats = []
            try:
                mats = [str(x.get_path_name()) if x else None for x in c.get_materials()]
            except Exception:
                pass
            meshes.append({"comp": c.get_name(), "mesh": m.get_path_name() if m else None, "materials": mats})
        rows.append({"label": lab, "name": nm, "class": a.get_class().get_name(),
                     "level": a.get_outermost().get_name(), "parent": str(p.get_actor_label()) if p else None,
                     "hidden_ed": bool(a.is_hidden_ed()), "hidden_game": bool(a.get_editor_property("hidden")),
                     "tags": [str(t) for t in a.tags], "min": [o.x - e.x, o.y - e.y, o.z - e.z],
                     "max": [o.x + e.x, o.y + e.y, o.z + e.z], "meshes": meshes})
    path = "E:/PussStage/Saved/CodexConductor/probe_s3_clam_rock.json"
    json.dump(rows, open(path, "w", encoding="utf-8"), indent=1)
    unreal.log("S3CLAMROCK_OK|n=%d|path=%s" % (len(rows), path))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3CLAMROCK_FAILED|%r" % (exc,))
