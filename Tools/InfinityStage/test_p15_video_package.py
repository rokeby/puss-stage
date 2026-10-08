#!/usr/bin/env python3
"""Offline positive/negative controls for p15_video_package.py."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import p15_video_package as p15


passed = 0
positive = 0
negative = 0


def check(name, condition, kind="positive"):
    global passed, positive, negative
    if not condition:
        raise AssertionError(name)
    passed += 1
    if kind == "positive":
        positive += 1
    else:
        negative += 1


def stops(name, fn):
    try:
        fn()
    except p15.Stop:
        check(name, True, "negative")
    else:
        raise AssertionError(name + " did not stop")


g = p15.presentation_geometry(1920, 1080, 1920, 1080, "fit")
check("16:9 exact fit", g["pillarbox_each_px"] == 0 and g["letterbox_each_px"] == 0)
g = p15.presentation_geometry(1920, 1080, 3840, 1600, "fit")
check("wide LED pillarboxes", g["pillarbox_each_px"] == 497.778 and g["letterbox_each_px"] == 0)
g = p15.presentation_geometry(1920, 1080, 3840, 1600, "fill")
check("wide LED fill crops vertically", g["crop_each_fraction"] == [0.0, 0.12962963])
stops("zero dimensions", lambda: p15.presentation_geometry(0, 1080, 1920, 1080, "fit"))
stops("bad fit mode", lambda: p15.presentation_geometry(1920, 1080, 1920, 1080, "stretch"))
stops("native mismatch", lambda: p15.presentation_geometry(1920, 1080, 3840, 2160, "native"))

profile = p15.build_display_profile({"render": {"width": 1920, "height": 1080, "fps": 25}})
check("profile drives game and MRQ", profile["game_launch_args"][:2] == ["-ResX=1920", "-ResY=1080"]
      and profile["mrq_output_resolution"] == [1920, 1080])
check("Super35 25 mm HFOV", round(p15.horizontal_fov_deg(23.76, 25.0), 3) == 50.834)
stops("odd render rejected", lambda: p15.build_display_profile({"render": {"width": 1919, "height": 1080, "fps": 25}}))

real_which = p15.shutil.which
try:
    p15.shutil.which = lambda name: None
    fallback_plan = p15.plan({"audio_owner": "ue_muxed"}, "NOFFMPEG")
    check("no-ffmpeg falls back to ImgMedia", fallback_plan["kind"] == "imgmedia")
    check("ImgMedia delegates separate WAV", fallback_plan["audio_owner"] == "desk"
          and fallback_plan["audio_owner_fallback"] is not None)
finally:
    p15.shutil.which = real_which

check("scene start maps to media zero", p15.master_to_media_frame(100, 100, 200, True) == 0)
check("scrub loops deterministically", p15.master_to_media_frame(351, 100, 200, True) == 51)
check("pre-scene is black", p15.master_to_media_frame(99, 100, 200, True) is None)
check("non-loop end is black", p15.master_to_media_frame(300, 100, 200, False) is None)

p15.validate_audio_owner("ue_muxed", True, False)
check("single UE muxed owner accepted", True)
p15.validate_audio_owner("desk", False, False)
check("single desk owner accepted", True)
stops("double audio rejected", lambda: p15.validate_audio_owner("ue_muxed", True, True))
stops("desk plus muxed rejected", lambda: p15.validate_audio_owner("desk", True, False))
stops("unknown owner rejected", lambda: p15.validate_audio_owner("both", True, True))

root = p15.PROJECT_ROOT / "Saved" / "CodexConductor" / ("P15Harness-" + uuid.uuid4().hex[:12])
old_root = p15.PROJECT_ROOT
p15.PROJECT_ROOT = root
try:
    out = root / "DerivedAssets" / "P15"
    out.mkdir(parents=True)
    target = out / "display_profile.json"
    target.write_bytes(b"before")
    plan = {"test": True}
    backup = root / "Backups" / "PreP15VideoTransitions-TEST"
    pre = p15.snapshot_before(out, backup, [Path("display_profile.json"), Path("new.bin")], "TEST", plan)
    check("backup captures prior bytes", (backup / "before" / "display_profile.json").read_bytes() == b"before")
    target.write_bytes(b"after")
    (out / "new.bin").write_bytes(b"new")
    record = dict(pre)
    record["applied"] = True
    record_path = backup / "apply_record.json"
    p15.write_json(record_path, record)
    cfg = {"confirm": p15.REVERT_CONFIRM, "record": str(record_path)}
    result = p15.revert(cfg, "REVERTTEST")
    check("revert restores prior bytes", target.read_bytes() == b"before")
    check("revert archives applied bytes", (backup / "Reverted-REVERTTEST" / "applied" / "display_profile.json").read_bytes() == b"after")
    check("revert removes new target without deletion", not (out / "new.bin").exists()
          and (backup / "Reverted-REVERTTEST" / "applied" / "new.bin").read_bytes() == b"new")
    check("revert record exists", result.is_file())
finally:
    p15.PROJECT_ROOT = old_root

stops("APPLY confirm required", lambda: p15.apply({}, {"run": "X"}))
stops("REVERT record required", lambda: p15.revert({"confirm": p15.REVERT_CONFIRM}, "X"))

print("P15_HARNESS_OK|passed=%d|positive=%d|negative=%d" % (passed, positive, negative))
