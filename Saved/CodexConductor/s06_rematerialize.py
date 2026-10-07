"""Re-materialize Structure 06 after W&T's P06 relayout (P06RL-20261007-081048 left it stale: IsStructureCurrent false),
then report P06's light counts. Precedent: girders_v3_apply.py:762,831 (materialize_structure + is_structure_current).
Census must be clean before; umap copied to Backups/ first; saves only the level; Show must stay clean.
Markers: S06REMAT_OK | S06REMAT_STOP."""
import json
import os
import shutil
import time

import unreal

RUN = "S06REMAT-" + time.strftime("%Y%m%d-%H%M%S")
LABEL = "Infinity Stage - Structure 06"


def stop(why):
    unreal.log_error("S06REMAT_STOP|run=%s|%s" % (RUN, why))
    raise RuntimeError(why)


def census():
    return {"content": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def light_counts(acts):
    p06 = [a for a in acts if a.get_class().get_name() == "InfinityStagePassageActor" and "06" in str(a.get_actor_label())]
    if len(p06) != 1:
        stop("P06_PASSAGES=%d" % len(p06))
    managed = list(p06[0].get_editor_property("managed_attachment_actors"))
    lights = [a for a in managed if a and a.get_component_by_class(unreal.LightComponent)]
    on = [a for a in lights if a.get_component_by_class(unreal.LightComponent).is_visible()]
    return {"passage": str(p06[0].get_actor_label()), "managed": len(managed), "lights": len(lights), "visible": len(on)}


if census() != {"content": [], "maps": []}:
    stop("DIRTY_BEFORE|%s" % json.dumps(census()))
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
acts = eas.get_all_level_actors()
hits = [a for a in acts if str(a.get_actor_label()) == LABEL]
if len(hits) != 1:
    stop("STRUCTURES=%d" % len(hits))
s = hits[0]
before = {"current": bool(s.is_structure_current()), "lights": light_counts(acts)}
unreal.log("S06REMAT_BEFORE|run=%s|%s" % (RUN, json.dumps(before)))

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
pkg = world.get_outermost().get_name()
umap = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()) + pkg[len("/Game/"):] + ".umap"
bdir = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", "PreS06Remat-" + RUN)
os.makedirs(bdir)
shutil.copy2(umap, bdir)

if not s.materialize_structure():
    stop("MATERIALIZE_FALSE")
if not s.is_structure_current():
    stop("NOT_CURRENT_AFTER")
c = census()
if c["content"]:
    stop("SHOW_OR_CONTENT_DIRTIED|%s" % json.dumps(c))
if c["maps"] and not unreal.EditorLoadingAndSavingUtils.save_current_level():
    stop("SAVE_FAILED")
if census() != {"content": [], "maps": []}:
    stop("DIRTY_AFTER|%s" % json.dumps(census()))
acts = eas.get_all_level_actors()
s2 = [a for a in acts if str(a.get_actor_label()) == LABEL][0]
after = {"current": bool(s2.is_structure_current()), "lights": light_counts(acts)}
if not after["current"]:
    stop("POST_SAVE_NOT_CURRENT")
unreal.log("S06REMAT_OK|run=%s|before=%s|after=%s|backup=%s" % (RUN, json.dumps(before), json.dumps(after), bdir))
