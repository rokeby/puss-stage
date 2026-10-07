"""Turn the 'S6 Ghost Light' OFF in the level (Gary 7 Oct: "Yes, off in P06 too" - P06 ends in total darkness; the
S6 hangar is hidden for all of S6 by klara_void_s6, so nothing else uses it).
Writes the original values to s6_ghost_light_off_record.json BEFORE changing anything; copies the umap to Backups/.
Saves only the current level; reads back. Markers S6GHOST_OFF_OK | S6GHOST_STOP. Revert = set the recorded values back."""
import json
import os
import shutil
import time

import unreal

LABEL = "S6 Ghost Light"
RUN = "S6GHOST-" + time.strftime("%Y%m%d-%H%M%S")
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor", "KlaraIngest")


def stop(why):
    unreal.log_error("S6GHOST_STOP|run=%s|%s" % (RUN, why))
    raise RuntimeError(why)


eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
hits = [a for a in eas.get_all_level_actors() if a.get_actor_label() == LABEL]
if len(hits) != 1:
    stop("ACTORS=%d" % len(hits))
actor = hits[0]
comps = actor.get_components_by_class(unreal.LightComponent)
if not comps:
    stop("NO_LIGHT_COMPONENT")
rec = {"run": RUN, "actor": actor.get_path_name(), "lights": [
    {"comp": c.get_name(), "intensity": float(c.get_editor_property("intensity"))} for c in comps]}
rpath = os.path.join(HERE, "s6_ghost_light_off_record.json")
if os.path.exists(rpath):
    stop("RECORD_EXISTS|%s" % rpath)
with open(rpath, "w", encoding="utf-8") as f:
    json.dump(rec, f, indent=1)
unreal.log("S6GHOST_RECORD|run=%s|%s|%s" % (RUN, rpath, json.dumps(rec["lights"])))

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
pkg = world.get_outermost().get_name()
umap = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()) + pkg[len("/Game/"):] + ".umap"
bdir = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", "PreS6GhostOff-" + RUN)
os.makedirs(bdir)
shutil.copy2(umap, bdir)
unreal.log("S6GHOST_BACKUP_OK|run=%s|%s" % (RUN, bdir))

actor.modify()
for c in comps:
    c.modify()
    c.set_editor_property("intensity", 0.0)
    if abs(float(c.get_editor_property("intensity"))) > 1e-6:
        stop("READBACK|%s" % c.get_name())
if not unreal.EditorLoadingAndSavingUtils.save_current_level():
    stop("SAVE_FAILED")
again = [a for a in eas.get_all_level_actors() if a.get_actor_label() == LABEL][0]
vals = [float(c.get_editor_property("intensity")) for c in again.get_components_by_class(unreal.LightComponent)]
if any(abs(v) > 1e-6 for v in vals):
    stop("POST_SAVE_READBACK|%s" % vals)
unreal.log("S6GHOST_OFF_OK|run=%s|lights=%d|was=%s|backup=%s" % (RUN, len(vals), [l["intensity"] for l in rec["lights"]], bdir))
