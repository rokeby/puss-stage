"""READ-ONLY dump (29 Sep) for the light-replication draw-order fix: every Wing Pair cue's GUID (as its 32-hex digits)
and its Light attachments (relative translation, rotation quaternion, intensity, attachment GUID), in stored order.
Offline, Scripts/check_light_variation_order.py then asks: did any saved light come through
ReplicateLightAttachmentsWithVariation (jittered copies of a template), and if so, which argument-evaluation order
reproduces it? Writes only the JSON; the Show is not modified."""
import json
import os

import unreal


def guid_hex(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    out = {"cues": []}
    for i, cue in enumerate(show.get_editor_property("cues")):
        if str(cue.get_editor_property("type")) != str(unreal.InfinityCueType.WING_PAIR):
            continue
        lights = []
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if str(a.get_editor_property("kind")) != str(unreal.InfinityAttachmentKind.LIGHT):
                continue
            tf = a.get_editor_property("relative_transform")
            t, q = tf.translation, tf.rotation
            row = {"t": [t.x, t.y, t.z], "q": [q.x, q.y, q.z, q.w],
                   "i": a.get_editor_property("lighting").get_editor_property("intensity")}
            for gp in ("attachment_guid", "guid"):
                try:
                    row["guid"] = guid_hex(a.get_editor_property(gp))
                    break
                except Exception:  # noqa: BLE001
                    pass
            lights.append(row)
        if lights:
            out["cues"].append({"index": i, "label": str(cue.get_editor_property("label")),
                                "guid": guid_hex(cue.get_editor_property("cue_guid")), "lights": lights})
    del show
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                        "wingpair_lights.json")
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h)
    unreal.log(f"PUSS_SOFTGOODS_LIGHT_DUMP|cues={len(out['cues'])}|lights={sum(len(c['lights']) for c in out['cues'])}")


main()
