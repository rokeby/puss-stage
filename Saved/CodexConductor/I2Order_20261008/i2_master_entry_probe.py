"""READ-ONLY (9 Oct): what does the Master show at the S2 -> I2 boundary?  Gary's recording: "i2 with the boy shadow
initially cut to P03? then glitched back to P02".  I2's own cut track is clean after P27 ([0,1250) hangar hold,
[1250,2226) mouth), so this reads the MASTER: every camera-cut section and every sub/shot section overlapping
[I2 start - PAD, I2 start + PAD] (master display frames), with bound camera names, ranges, start offsets, row index.
No transport, no Sequencer open, no save; asserts the census is unchanged.  Marker I2ENTRY_OK|run=.. / I2ENTRY_FAILED."""
import datetime
import json

MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
I2 = "LS_Interaction_02_Turnips"
PAD = 400
OUT = "E:/PussStage/Saved/CodexConductor/I2Order_20261008/i2_master_entry_%s.json"


def main():
    import unreal as u
    run = "I2ENTRY-" + datetime.datetime.now().strftime("%H%M%S")
    lib = u.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    c0 = census()
    m = u.load_asset(MASTER)
    names = {}
    for b in m.get_bindings():
        names[str(b.get_id())] = str(b.get_display_name())

    def rng(s):
        a = s.get_start_frame() if s.has_start_frame() else None
        b = s.get_end_frame() if s.has_end_frame() else None
        return [a, b]

    subs, cuts = [], []
    i2 = None
    for t in m.get_tracks():
        cls = t.get_class().get_name()
        for s in t.get_sections():
            r = rng(s)
            row = {"track": cls, "track_name": str(t.get_display_name()), "range": r, "active": bool(s.is_active()),
                   "row": int(s.get_row_index())}
            if isinstance(s, u.MovieSceneSubSection):
                sq = s.get_sequence()
                row["sequence"] = sq.get_name() if sq else None
                try:
                    p = s.get_editor_property("parameters")
                    row["start_frame_offset"] = int(p.get_editor_property("start_frame_offset").value)
                    row["time_scale"] = str(p.get_editor_property("time_scale"))
                except Exception as exc:  # noqa: BLE001
                    row["params_err"] = type(exc).__name__
                subs.append(row)
                if row["sequence"] == I2:
                    i2 = row
            elif isinstance(s, u.MovieSceneCameraCutSection):
                try:
                    bid = s.get_camera_binding_id()
                    row["camera_guid"] = str(bid.get_editor_property("guid"))
                    row["camera"] = names.get(row["camera_guid"], "?(not a master binding: nested/space)")
                except Exception as exc:  # noqa: BLE001
                    row["camera"] = "ERR %s" % type(exc).__name__
                cuts.append(row)
    if i2 is None:
        u.log_error("I2ENTRY_FAILED|run=%s|no I2 sub-section in master" % run)
        return
    a0 = i2["range"][0]

    def near(r):
        lo = r[0] if r[0] is not None else -10 ** 9
        hi = r[1] if r[1] is not None else 10 ** 9
        return lo < a0 + PAD and hi > a0 - PAD
    out = {"run": run, "master_display_rate": str(m.get_display_rate()), "i2": i2,
           "subs_near": [s for s in subs if near(s["range"])], "cuts_near": [c for c in cuts if near(c["range"])],
           "cut_count_total": len(cuts)}
    c1 = census()
    out["census_unchanged"] = c0 == c1
    p = OUT % run
    json.dump(out, open(p, "w"), indent=1, default=str)
    u.log("I2ENTRY_OK|run=%s|i2=%s|subs_near=%d|cuts_near=%d|census_unchanged=%d|file=%s" % (
        run, i2["range"], len(out["subs_near"]), len(out["cuts_near"]), int(c0 == c1), p))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("I2ENTRY_FAILED|%s: %s" % (type(exc).__name__, exc))
