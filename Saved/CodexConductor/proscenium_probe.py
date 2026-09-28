"""What geometry is near P01's start that could read as a proscenium?"""
import unreal
from collections import defaultdict
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = next((a for a in ps if "01" in a.get_actor_label()), ps[0])
by_cue = defaultdict(dict)
for ref in p1.get_editor_property("materialized_panels"):
    g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
    side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
    t = ref.get_editor_property("base_world_transform").translation
    by_cue[g][side] = t
rows = []
for sides in by_cue.values():
    if "LEFT" in sides and "RIGHT" in sides:
        L, R = sides["LEFT"], sides["RIGHT"]
        rows.append((min(L.x, R.x), L.y, R.y, abs(L.y - R.y)))
rows.sort()
unreal.log("P01_FIRST_STATIONS|(x, Ly, Ry, gap_cm)")
for r in rows[:6]:
    unreal.log("  STATION|x=%.0f|L_y=%.0f|R_y=%.0f|gap=%.0f" % r)
tops = 0
for ref in p1.get_editor_property("materialized_panels"):
    side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
    t = ref.get_editor_property("base_world_transform").translation
    if "TOP" in side and t.x < 2000:
        tops += 1
        unreal.log("  TOP_NEAR_START|x=%.0f z=%.0f" % (t.x, t.z))
unreal.log("P01_TOPS_BEFORE_X2000|%d" % tops)
