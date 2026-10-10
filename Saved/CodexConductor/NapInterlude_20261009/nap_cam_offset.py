import json, os, unreal
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_Nap_BatteryChange"
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/NapInterlude_20261009/nap_cam_offset_record.json"
# Gary 10 Oct: +20 cm, head tilt 35 (resting on a paw), look up-forward to the left -> uniform offsets on every key.
OFF = {"Location.Z": 20.0, "Rotation.X": 35.0, "Rotation.Y": 15.0, "Rotation.Z": -20.0}
import re
lib = unreal.EditorLoadingAndSavingUtils
assert not list(lib.get_dirty_content_packages()) and not list(lib.get_dirty_map_packages()), "DIRTY_BEFORE"
assert not os.path.exists(OUT), "RECORD_EXISTS"
seq = unreal.load_asset(SEQ); assert seq, "SEQ"
found = []
for b in seq.get_bindings():
    for t in b.get_tracks():
        if not isinstance(t, unreal.MovieScene3DTransformTrack): continue
        name = str(b.get_display_name())
        if "cam" not in name.lower(): continue
        for s in t.get_sections():
            for ch in s.get_all_channels():
                base = re.sub(r"_\d+$", "", str(ch.get_name()))
                if base in OFF: found.append((name, base, ch))
names = sorted({n for n, _, _ in found}); assert len(names) == 1, "CAMERA_BINDINGS|%s" % names
assert sorted({b for _, b, _ in found}) == sorted(OFF), "CHANNELS|%s" % sorted({b for _, b, _ in found})
rec = {"binding": names[0], "offsets": OFF, "channels": []}
for _, base, ch in found:
    keys = ch.get_keys()
    row = {"channel": base, "keys": [[k.get_time().frame_number.value, k.get_value()] for k in keys],
           "default": ch.get_default() if ch.has_default() else None}
    rec["channels"].append(row)
with open(OUT, "w") as fh: json.dump(rec, fh, indent=1)
seq.modify()
for _, base, ch in found:
    d = OFF[base]
    keys = ch.get_keys()
    for k in keys: k.set_value(k.get_value() + d)
    if ch.has_default(): ch.set_default(ch.get_default() + d)
for (_, base, ch), row in zip(found, rec["channels"]):
    got = [k.get_value() for k in ch.get_keys()]
    exp = [v + OFF[base] for _, v in row["keys"]]
    assert len(got) == len(exp) and all(abs(a - b) < 1e-3 for a, b in zip(got, exp)), "READBACK|%s" % base
dirty = [p.get_name() for p in lib.get_dirty_content_packages()]
assert dirty == [SEQ], "DIRTY_SCOPE|%s" % dirty
unreal.EditorAssetLibrary.save_asset(SEQ, False)
assert not list(lib.get_dirty_content_packages()), "STILL_DIRTY"
unreal.log("NAP_CAM_OFFSET_APPLY_OK|binding=%s|keys=%s|record=%s" % (names[0], {r["channel"]: len(r["keys"]) for r in rec["channels"]}, OUT))
