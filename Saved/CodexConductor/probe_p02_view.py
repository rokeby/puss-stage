"""Read-only: what is in front of the P02 camera at the 60% still (pose from PSTILLS-P02-20261007-060756-straight).
Lists actors within 30 m ahead (cone 30 deg) grouped by level + class; counts Passage 02 managed attachments. Marker P02VIEW|"""
import collections
import json
import math

import unreal

loc = unreal.Vector(7320.18, 84554.67, 180.0)
yaw = math.radians(-43.5725)
fwd = (math.cos(yaw), math.sin(yaw))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
pers = world.get_outermost().get_name()
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
p02 = [a for a in acts if a.get_class().get_name() == "InfinityStagePassageActor" and "02" in str(a.get_actor_label())]
managed = set()
for p in p02:
    managed |= set(p.get_editor_property("managed_attachment_actors"))
near = collections.Counter()
close = []
for a in acts:
    l = a.get_actor_location()
    dx, dy = l.x - loc.x, l.y - loc.y
    d = math.hypot(dx, dy)
    if d < 1 or d > 3000:
        continue
    cosang = (dx * fwd[0] + dy * fwd[1]) / d
    if cosang < math.cos(math.radians(30)):
        continue
    lvl = a.get_outermost().get_name().split("/")[-1]
    near[(lvl, a.get_class().get_name(), a in managed)] += 1
    if a in managed:
        along = dx * fwd[0] + dy * fwd[1]
        lat = -dx * fwd[1] + dy * fwd[0]
        inten = None
        lc = a.get_component_by_class(unreal.LightComponent)
        if lc:
            inten = round(float(lc.get_editor_property("intensity")), 2)
        close.append([round(along), round(lat), round(l.z), str(a.get_actor_label())[:44], inten])
unreal.log("P02VIEW|p02=%s|managed=%d|ahead=%s" % ([str(p.get_actor_label()) for p in p02], len(managed),
           json.dumps(sorted([[k[0], k[1], k[2], v] for k, v in near.items()], key=lambda r: -r[3])[:25])))
unreal.log("P02VIEW_CLOSE|%s" % json.dumps(sorted(close)[:30]))
