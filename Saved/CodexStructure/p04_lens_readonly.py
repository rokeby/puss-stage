"""Read-only (30 Sep): is P04's passage lens constant over its last 10 m (the last 4.0 s at 2.5 m/s)?
Finds P04's Passage section in the Master by passage GUID, reads the section's focal-length channel
(keys, default) and lists its keys inside, and the last key before, the last 4.0 s before Scene 4. Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"


def main():
    p04_guid = next(r["passage_guid"] for r in json.load(open(os.path.join(HERE, "arrivals_probe.json"), encoding="utf-8")) if r.get("scene") == 4)
    master = unreal.load_asset(MASTER)
    tick = master.get_tick_resolution()
    rate = tick.numerator / tick.denominator
    out = {"p04_passage_guid": p04_guid, "tick_rate": rate}
    for track in master.get_tracks():
        for sec in track.get_sections():
            try:
                g = sec.get_editor_property("passage_guid").to_string()
            except Exception:  # noqa: BLE001
                continue
            if g != p04_guid:
                continue
            end = sec.get_end_frame()
            out["section_s"] = [sec.get_start_frame() / rate, end / rate]
            chans = {}
            for ch in sec.get_all_channels():
                name = str(ch.get_name())
                if "focal" in name.lower() or "fov" in name.lower() or "lens" in name.lower():
                    keys = [(k.get_time().frame_number.value / rate, k.get_value()) for k in ch.get_keys()]
                    end_s = end / rate
                    inside = [(round(t - end_s, 3), v) for t, v in keys if end_s - 4.0 <= t <= end_s]
                    before = [(round(t - end_s, 3), v) for t, v in keys if t < end_s - 4.0][-1:]
                    chans[name] = {"n_keys": len(keys), "default": ch.get_default() if ch.has_default() else None,
                                   "keys_in_last_4s_rel_end": inside, "last_key_before_window_rel_end": before,
                                   "all_values": sorted({round(v, 3) for _, v in keys})[:12]}
            out["channels"] = chans
    json.dump(out, open(os.path.join(HERE, "p04_lens.json"), "w"), indent=1, default=str)
    unreal.log(f"P04_LENS|{json.dumps(out, default=str)[:1500]}")


main()
