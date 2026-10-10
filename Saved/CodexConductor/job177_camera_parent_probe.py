"""Read-only binding/attachment proof for Job 144 active cameras."""
import json
import unreal as u

RUN = "J177-J144-CAMERA-BINDING-PROBE-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_camera_parent_probe.json"
TARGETS = {
    "I2": ("/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips", "I2 Hangar Hold Camera"),
    "I3": ("/Game/InfinityStage/Interactions/LS_Interaction_03_ForgetsHisName", "S3 Sleight Hangar Camera"),
}


def _v(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _eval(channel, seq, frame):
    result = channel.evaluate_keys(seq.make_range(frame, 1), seq.get_display_rate())
    return float(list(result)[0]) if result else None


rows = []
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
for name, (path, label) in TARGETS.items():
    seq = u.load_asset(path)
    bindings = [b for b in seq.get_bindings() if str(b.get_display_name()) == label]
    if len(bindings) != 1:
        raise RuntimeError("JOB177_CAMERA_PARENT_PROBE_FAILED|%s_bindings=%d" % (name, len(bindings)))
    binding = bindings[0]
    objects = list(seq.locate_bound_objects(binding, world))
    if len(objects) != 1:
        raise RuntimeError("JOB177_CAMERA_PARENT_PROBE_FAILED|%s_objects=%d" % (name, len(objects)))
    actor = objects[0]
    parent = actor.get_attach_parent_actor()
    root = actor.get_editor_property("root_component")
    transforms = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
    if len(transforms) != 1 or len(transforms[0].get_sections()) != 1:
        raise RuntimeError("JOB177_CAMERA_PARENT_PROBE_FAILED|%s_transform_shape" % name)
    channels = list(transforms[0].get_sections()[0].get_all_channels())
    rows.append({"interaction": name, "binding": label, "actor_path": actor.get_path_name(),
                 "world_location": _v(actor.get_actor_location()),
                 "relative_location": _v(root.get_editor_property("relative_location")),
                 "attach_parent": str(parent.get_actor_label()) if parent else None,
                 "track_location_at_712": [_eval(channels[i], seq, 712) for i in range(3)],
                 "track_rotation_at_712": [_eval(channels[i], seq, 712) for i in range(3, 6)]})
with open(OUT, "w", encoding="utf-8") as handle:
    json.dump({"run": RUN, "rows": rows}, handle, indent=2)
u.log("JOB177_CAMERA_PARENT_PROBE_OK|run=%s|rows=%s|report=%s" %
      (RUN, ";".join("%s:parent=%s,track=%s" % (r["interaction"], r["attach_parent"], r["track_location_at_712"]) for r in rows), OUT))
