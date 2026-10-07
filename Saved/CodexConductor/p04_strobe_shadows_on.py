"""P04 strobes cast shadows (Gary 7 Oct: "P04 strobes should throw the wings' shadows"; field bCastShadows built in
d1e9fe0, InfinityStageStrobeLight.h:97). Sets cast_shadows=True on every InfinityStageStrobeLight whose label starts
with "P04". Records originals to p04_strobe_shadows_on_record.json BEFORE changing anything; umap copied to Backups/.
Saves only the current level; reads back after save. Markers P04STROBESHADOW_OK | P04STROBESHADOW_STOP.
Revert = set the recorded values back."""
import json
import os
import shutil
import time

import unreal

RUN = "P04STROBESHADOW-" + time.strftime("%Y%m%d-%H%M%S")
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


def stop(why):
    unreal.log_error("P04STROBESHADOW_STOP|run=%s|%s" % (RUN, why))
    raise RuntimeError(why)


eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
cls = getattr(unreal, "InfinityStageStrobeLight", None)
if cls is None:
    stop("NO_CLASS")
hits = [a for a in eas.get_all_level_actors() if isinstance(a, cls) and a.get_actor_label().startswith("P04")]
if not hits:
    stop("NO_P04_STROBES")
rec = {"run": RUN, "strobes": [{"label": a.get_actor_label(), "path": a.get_path_name(),
                                "cast_shadows": bool(a.get_editor_property("cast_shadows"))} for a in hits]}
rpath = os.path.join(HERE, "p04_strobe_shadows_on_record.json")
if os.path.exists(rpath):
    stop("RECORD_EXISTS|%s" % rpath)
with open(rpath, "w", encoding="utf-8") as f:
    json.dump(rec, f, indent=1)
unreal.log("P04STROBESHADOW_RECORD|run=%s|%s" % (RUN, json.dumps(rec["strobes"])))

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
pkg = world.get_outermost().get_name()
umap = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()) + pkg[len("/Game/"):] + ".umap"
bdir = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", "PreP04StrobeShadows-" + RUN)
os.makedirs(bdir)
shutil.copy2(umap, bdir)

for a in hits:
    a.modify()
    a.set_editor_property("cast_shadows", True)
    if not bool(a.get_editor_property("cast_shadows")):
        stop("READBACK|%s" % a.get_actor_label())
if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    stop("SAVE_FAILED")
labels = set(s["label"] for s in rec["strobes"])
again = [a for a in eas.get_all_level_actors() if isinstance(a, cls) and a.get_actor_label() in labels]
if len(again) != len(hits) or not all(bool(a.get_editor_property("cast_shadows")) for a in again):
    stop("POST_SAVE_READBACK")
unreal.log("P04STROBESHADOW_OK|run=%s|strobes=%d|labels=%s|backup=%s" % (RUN, len(again), sorted(labels), bdir))
