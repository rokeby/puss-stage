"""Q14 read-only dump: live WingPair.Mechanism export_text + LocalOverrideMask for every row of TOPPLE-20261007-114412.
No writes, no saves. Writes q14_live_dump_<run>.json next to this file and logs Q14_LIVE_DUMP_OK|run=..|path=.."""
import datetime, json, os
import unreal

RUN = datetime.datetime.now().strftime("Q14D-%Y%m%d-%H%M%S")
HERE = os.path.join(unreal.Paths.project_saved_dir(), "CodexFlatV3", "q14")
ORIG = os.path.join(unreal.Paths.project_saved_dir(), "CodexFlatV3", "topple", "topple_originals_TOPPLE-20261007-114412.json")


def main():
    rows = json.load(open(ORIG, encoding="utf-8"))["rows"]
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    by_guid = {}
    for c in show.get_editor_property("cues"):
        g = str(unreal.GuidLibrary.conv_guid_to_string(c.get_editor_property("cue_guid"))).upper()
        by_guid.setdefault(g, []).append(c)
    out = []
    for r in rows:
        hit = by_guid.get(r["cue_guid"], [])
        if len(hit) != 1:
            out.append({"cue_guid": r["cue_guid"], "label": r["label"], "error": "CUE_COUNT %d" % len(hit)})
            continue
        pair = hit[0].get_editor_property("wing_pair")
        out.append({"cue_guid": r["cue_guid"], "label": r["label"], "action": r["action"],
                    "mech_text": pair.get_editor_property("mechanism").export_text(),
                    "mask": int(pair.get_editor_property("local_override_mask"))})
    path = os.path.join(HERE, "q14_live_dump_%s.json" % RUN)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"run": RUN, "rows": out}, f, indent=1)
    unreal.log("Q14_LIVE_DUMP_OK|run=%s|rows=%d|path=%s" % (RUN, len(out), path))


main()
