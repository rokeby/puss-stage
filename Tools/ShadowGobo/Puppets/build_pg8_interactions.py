"""Build PG8's five offline boy/Puss interaction shadow clips.

DRY writes nothing. APPLY requires ``APPLY_PG8_INTERACTIONS_<run-id>``, records
the exact git/package census, backs up every predecessor, writes only the named
offline artifacts, reads them back, and emits a run-id success marker. REVERT is
recoverable and requires ``REVERT_PG8_INTERACTIONS_<run-id>``.

The script imports no Unreal, MCP, or Blender modules. Motion is authored at
25 fps; byte-identical holds are de-duplicated by the atlas packer.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOL_DIR))

import boy_rig  # noqa: E402
import build_boy_puss_composite as composite  # noqa: E402
import cat_rig  # noqa: E402
import clip_render  # noqa: E402
import gobo_twin  # noqa: E402
import pack_rig_flipbook  # noqa: E402
import props  # noqa: E402


DISPLAY_FPS = 25.0
GUTTER_PX = 8
OUTPUT_ROOT = HERE / "interaction_clips"
SOURCE_TABLE = "Docs/Conductor/SHADOW_SHOTLIST_INTERACTIONS_2026-10-11.md:68-82"
DEFAULT_LOOK = {
    "small_whimper_jaw_deg": 13.0,
    "big_whimper_jaw_deg": 24.0,
    "mournful_jaw_deg": 18.0,
    "tongue_length_boy_height": 0.105,
    "bucket_size_boy_height": props.LOOK["bucket"]["size_boy_height"],
    "turnip_size_boy_height": props.LOOK["turnip"]["size_boy_height"],
    "pearl_size_boy_height": props.LOOK["pearl"]["size_boy_height"],
    "page_size_boy_height": props.LOOK["page"]["size_boy_height"],
    "crown_size_boy_height": props.LOOK["crown"]["size_boy_height"],
    "boots_size_boy_height": 0.115,
    "curtain": dict(gobo_twin.CURTAIN_DEFAULTS),
}


@dataclass(frozen=True)
class Interaction:
    code: str
    slug: str
    title: str
    durations: tuple[float, float, float, float, float]
    beat_labels: tuple[str, str, str, str, str]
    prop: str

    @property
    def length(self):
        return 3.0 + sum(self.durations)

    def timing(self):
        rows = [{"id": "plate_in", "label": "opening still plate", "start_s": 0.0, "duration_s": 1.5}]
        cursor = 1.5
        for index, (label, duration) in enumerate(zip(self.beat_labels, self.durations), 1):
            beat_id = "whimper" if index == 5 else "B%d" % index
            rows.append({"id": beat_id, "label": label, "start_s": cursor, "duration_s": duration})
            cursor += duration
        rows.append({"id": "plate_out", "label": "closing still plate", "start_s": cursor, "duration_s": 1.5})
        return rows


INTERACTIONS = (
    Interaction("I1", "washing_the_boy", "Washing the Boy", (6, 10, 14, 8, 5),
                ("boy hunched", "bucket emerges, tips and drains", "Puss licks/washes", "boy straightens", "small whimper"), "bucket"),
    Interaction("I2", "turnips", "Turnips", (6, 6, 12, 10, 5),
                ("Puss brings turnip", "boy grabs", "boy eats all", "sad stillness and slow head down", "small whimper"), "turnip"),
    Interaction("I3", "forgets_his_name", "Forgets His Name", (14, 10, 10, 6, 8),
                ("Puss sings and gives pearl", "boy sways", "tongue lolls", "boy coughs", "BIG snivelling whimper"), "pearl"),
    Interaction("I4", "gets_a_name", "Gets a Name", (8, 8, 10, 6, 5),
                ("scroll arrives", "boy holds Cagliuso up", "boy turns scroll over", "pause and lower", "small whimper"), "page"),
    Interaction("I5", "becomes_king", "Becomes King", (6, 8, 14, 10, 8),
                ("crown falls, then boots pop in", "Puss admires boots", "Puss pulls boots on", "Puss struts", "mournful sag and whimper"), "crown_then_boots"),
)
PROP_BEATS = {"I1": ("B2",), "I2": ("B1", "B2", "B3"),
              "I3": ("B1", "B2", "B3", "B4"), "I4": ("B1", "B2", "B3", "B4"),
              "I5": ("B1", "B2", "B3", "B4")}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")


def git_census():
    result = subprocess.run(["git", "status", "--short"], cwd=PROJECT_ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    packages = [line for line in dirty if line.lower().endswith((".uasset", ".umap"))]
    return {"dirty_packages": packages, "dirty_package_count": len(packages),
            "source_dirty": dirty, "git_status_exit": result.returncode,
            "git_stderr": result.stderr.strip()}


def beat_map(spec):
    return {row["id"]: row for row in spec.timing()}


def key(time_s, pose, move=0.16, ease="ease_in_out"):
    return (round(float(time_s), 4), pose, float(move), ease)


def boy_whimper(keys, start, duration, jaw, *, big=False, mournful=False):
    face = {"eyes": "squint", "brows": "worried", "mouth": "blubber" if not mournful else "sad", "tears": [0.0]}
    base = dict(lean=10.0 if mournful else 7.0, neck=17.0 if mournful else 10.0, face=face)
    keys.append(key(start, boy_rig.P(**base, jaw=0.0), 0.24))
    step = 0.58 if big else 0.82
    t = start + 0.45
    flip = False
    while t < start + duration - 0.35:
        keys.append(key(t, boy_rig.P(**base, jaw=jaw if not flip else jaw * 0.58), 0.16))
        flip = not flip
        t += step
    keys.append(key(start + duration - 0.25, boy_rig.P(**base, jaw=0.0), 0.16))


def blank_prop(kind):
    return {"kind": kind, "visible": 0.0, "x": 0.5, "y": 0.5, "angle": 0.0, "flip": 1.0,
            "variant": 0.0, "phase": "off", "tongue": 0.0,
            "crown_visible": 0.0, "boots_visible": 0.0, "boots_phase": 0.0}


def timelines(spec, look):
    t = beat_map(spec)
    b1, b2, b3, b4, wh = (t[name]["start_s"] for name in ("B1", "B2", "B3", "B4", "whimper"))
    end = spec.length
    boy = [key(0, boy_rig.P(), 0, "snap")]
    puss = [key(0, cat_rig.make_pose("sit_upright"), 0, "snap")]
    prop = [key(0, blank_prop(spec.prop), 0, "snap")]

    if spec.code == "I1":
        hunched = boy_rig.P(**boy_rig.HEAD_IN_HANDS, face={"eyes": "shut", "brows": "worried", "mouth": "sad"})
        boy += [key(b1, hunched, 0, "snap"), key(b4, boy_rig.P(neck=2, face={"brows": "worried", "mouth": "sad"}), .48)]
        boy_whimper(boy, wh, t["whimper"]["duration_s"], look["small_whimper_jaw_deg"])
        puss += [key(b3, cat_rig.make_pose("washing", offset=(-190, -115)), .32)]
        for n in range(9):
            puss.append(key(b3 + 1.0 + n * 1.08, cat_rig.make_pose("washing" if n % 2 == 0 else "paw_lick",
                                                                    offset=(-210, -132 if n % 2 == 0 else -106)), .24))
        puss.append(key(b4, cat_rig.make_pose("sit_look_up"), .40))
        p = blank_prop("bucket")
        prop += [key(b2 + .5, dict(p, visible=1, x=1.08, y=.22, phase="enter"), 0, "snap"),
                 key(b2 + 1.3, dict(p, visible=1, x=.56, y=.22, phase="clear_hold"), .64),
                 key(b2 + 2.0, dict(p, visible=1, x=.56, y=.22, angle=55, phase="stream"), .48),
                 key(b2 + 5.2, dict(p, visible=1, x=.56, y=.22, angle=55, phase="splash", variant=2), .16),
                 key(b2 + 7.1, dict(p, visible=1, x=.56, y=.22, angle=55, phase="drips"), .16),
                 key(b3 - .25, dict(p, visible=0, x=1.08, y=.22, phase="off"), .48)]
    elif spec.code == "I2":
        boy += [key(b2, boy_rig.P(near_hand_on_head=(850, 470), face={"brows": "raised", "mouth": "surprised"}), .32)]
        for n, bite in enumerate((0, 1, 2, 3)):
            boy.append(key(b3 + .6 + n * 2.35, boy_rig.P(neck=-13 if n % 2 == 0 else -5,
                                                        near_hand_on_head=(870, 445),
                                                        face={"eyes": "shut" if n % 2 else "open", "mouth": "surprised"}), .20))
        boy += [key(b4, boy_rig.P(neck=13, lean=7, face={"brows": "worried", "mouth": "sad"}), .55)]
        boy_whimper(boy, wh, t["whimper"]["duration_s"], look["small_whimper_jaw_deg"])
        puss += [key(b1, cat_rig.make_pose("sit_proud", offset=(-55, -25)), .32),
                 key(b2, cat_rig.make_pose("sit_look_up"), .32)]
        p = blank_prop("turnip")
        prop += [key(b1 + .4, dict(p, visible=1, x=.73, y=.57), .16),
                 key(b2 + .8, dict(p, visible=1, x=.39, y=.39, angle=-35), .48)]
        for n in range(4):
            prop.append(key(b3 + .7 + n * 2.35, dict(p, visible=1, x=.40, y=.35, angle=-35, variant=n), .16))
        prop.append(key(b4 - .3, dict(p, visible=0, x=.40, y=.35, variant=3), 0, "snap"))
    elif spec.code == "I3":
        for n in range(12):
            puss.append(key(b1 + .45 + n * 1.02, cat_rig.make_pose("meow" if n % 2 == 0 else "sit_look_up",
                                                                   offset=(-20, -25)), .18))
        puss.append(key(b2, cat_rig.make_pose("sit_upright"), .32))
        boy += [key(b2, boy_rig.P(lean=-7, neck=-5, face={"brows": "raised", "mouth": "surprised"}), .40)]
        for n in range(6):
            boy.append(key(b2 + 1.0 + n * 1.45, boy_rig.P(lean=7 if n % 2 else -7, neck=4 if n % 2 else -4,
                                                         face={"brows": "raised", "mouth": "surprised"}), .32))
        boy += [key(b3, boy_rig.P(jaw=18, face={"eyes": "wide", "brows": "raised", "mouth": "surprised"}), .32)]
        for n in range(6):
            boy.append(key(b4 + .5 + n * .75, boy_rig.P(lean=6 if n % 2 else -4, neck=-16 if n % 2 else 13,
                                                        jaw=8 if n % 2 else 18,
                                                        face={"eyes": "shut", "brows": "worried", "mouth": "blubber"}), .14))
        boy_whimper(boy, wh, t["whimper"]["duration_s"], look["big_whimper_jaw_deg"], big=True)
        p = blank_prop("pearl")
        prop += [key(b1 + 5, dict(p, visible=1, x=.66, y=.43), .16),
                 key(b1 + 9, dict(p, visible=1, x=.43, y=.38), .64),
                 key(b3, dict(p, visible=1, x=.43, y=.38, tongue=1), .24),
                 key(b4, dict(p, visible=1, x=.43, y=.38, tongue=.25), .20),
                 key(wh, dict(p, visible=1, x=.43, y=.38, tongue=0), .16)]
    elif spec.code == "I4":
        boy += [key(b2, boy_rig.P(near_hand_on_head=(845, 410), far_hand_on_head=(810, 610),
                                  face={"brows": "raised", "mouth": "surprised"}), .48),
                key(b4, boy_rig.P(neck=10, near_hand_on_head=(780, 660), face={"brows": "worried", "mouth": "sad"}), .48)]
        boy_whimper(boy, wh, t["whimper"]["duration_s"], look["small_whimper_jaw_deg"])
        puss += [key(b1, cat_rig.make_pose("sit_proud", offset=(-65, -20)), .32),
                 key(b2, cat_rig.make_pose("sit_look_up"), .32)]
        p = blank_prop("page")
        prop += [key(b1 + .3, dict(p, visible=1, x=.78, y=.44, angle=-15), .16),
                 key(b2, dict(p, visible=1, x=.39, y=.38, angle=-8), .64),
                 key(b3, dict(p, visible=1, x=.39, y=.38, angle=8, flip=-1), .48),
                 key(b3 + 4.8, dict(p, visible=1, x=.39, y=.38, angle=-8, flip=1), .48),
                 key(b4, dict(p, visible=1, x=.41, y=.56, angle=12, flip=1), .48)]
    else:  # I5
        boy += [key(b1 + 2.7, boy_rig.P(face={"eyes": "wide", "brows": "raised", "mouth": "surprised"}), .24)]
        boy_whimper(boy, wh, t["whimper"]["duration_s"], look["mournful_jaw_deg"], mournful=True)
        puss += [key(b2, cat_rig.make_pose("sit_look_up"), .16)]
        for n in range(7):
            puss.append(key(b3 + .8 + n * 1.65, cat_rig.make_pose("stretch" if n % 2 == 0 else "sit_proud",
                                                                  offset=(-8 + n * 5, 12)), .16))
        for n in range(6):
            puss.append(key(b4 + .6 + n * 1.45, cat_rig.make_pose("sit_proud", offset=(n * 17, -8 if n % 2 else 4),
                                                                  body_lean=-13 if n % 2 else -4), .16))
        puss.append(key(wh, cat_rig.make_pose("sit_look_up"), .16))
        p = blank_prop("crown_then_boots")
        prop += [key(b1 + .2, dict(p, crown_visible=1, x=.32, y=.03, angle=-18), .16),
                 key(b1 + 2.4, dict(p, crown_visible=1, x=.32, y=.278, angle=0), .55),
                 key(b1 + 3.4, dict(p, crown_visible=1, boots_visible=1, boots_phase=0, x=.32, y=.278), .16),
                 key(b2, dict(p, crown_visible=1, boots_visible=1, boots_phase=1, x=.32, y=.278), .40),
                 key(b3, dict(p, crown_visible=1, boots_visible=1, boots_phase=2, x=.32, y=.278), .32),
                 key(b4, dict(p, crown_visible=1, boots_visible=1, boots_phase=3, x=.32, y=.278), .32)]

    # Closing plate holds the final keyed pose; a key at clip end is intentionally unnecessary.
    return {"boy": sorted(boy), "puss": sorted(puss), "prop": sorted(prop)}


def placement_view(placement, px):
    return composite.placement_view(placement, px)


def draw_prop_state(state, px, look):
    image = Image.new("L", (px, px), 255)
    lib = props.library()
    boy_h = (composite.VISIBLE_BAND["bottom"] - composite.VISIBLE_BAND["top"]) * px
    kind = state["kind"]
    if kind == "bucket" and state["visible"] >= .5:
        centre = (state["x"] * px, state["y"] * px)
        size = look["bucket_size_boy_height"] * boy_h
        props.draw_prop(image, lib["bucket"], centre, size, state["angle"], rod=(.985 * px, .02 * px))
        target = (.405 * px, .31 * px)
        tip = props.bucket_stream_origin(centre, size, state["angle"])
        water_state = {"phase": state["phase"], "splash": int(round(state["variant"]))}
        props._draw_bucket_water(image, water_state, tip, target, size)
    elif kind == "turnip" and state["visible"] >= .5:
        props.draw_prop(image, lib["turnip"], (state["x"] * px, state["y"] * px),
                        look["turnip_size_boy_height"] * boy_h, state["angle"], state=int(round(state["variant"])))
    elif kind == "pearl" and state["visible"] >= .5:
        size = look["pearl_size_boy_height"] * boy_h
        props.draw_prop(image, lib["pearl"], (state["x"] * px, state["y"] * px), size)
        if state["tongue"] > .02:
            draw = ImageDraw.Draw(image)
            mouth = (.405 * px, .315 * px)
            length = look["tongue_length_boy_height"] * boy_h * state["tongue"]
            width = max(4, int(.16 * length))
            draw.rounded_rectangle((mouth[0], mouth[1] - width / 2, mouth[0] + length, mouth[1] + width / 2),
                                   radius=width // 2, fill=0)
    elif kind == "page" and state["visible"] >= .5:
        centre = (state["x"] * px, state["y"] * px)
        size = look["page_size_boy_height"] * boy_h
        props.draw_prop(image, lib["page"], centre, size, state["angle"], state["flip"])
        if state["flip"] > .5:
            polygons = props.page_text_polygons("Cagliuso", centre, size, angle_deg=state["angle"],
                                                diagonal_fill=props.LOOK["page"]["page_text_diagonal_fill"],
                                                seed=props.LOOK["page"]["page_text_seed"])
            draw = ImageDraw.Draw(image)
            for polygon in polygons:
                draw.polygon([tuple(point) for point in polygon], fill=255)
    elif kind == "crown_then_boots":
        if state["crown_visible"] >= .5:
            props.draw_prop(image, lib["crown"], (state["x"] * px, state["y"] * px),
                            look["crown_size_boy_height"] * boy_h, state["angle"], rod=True)
        if state["boots_visible"] >= .5:
            phase = int(round(state["boots_phase"]))
            centres = {0: ((.64, .19), (.77, .14)), 1: ((.62, .69), (.76, .69)),
                       2: ((.61, .64), (.70, .60)), 3: ((.58, .71), (.70, .68))}[phase]
            for n, centre in enumerate(centres):
                props.draw_prop(image, lib["boot"], (centre[0] * px, centre[1] * px),
                                look["boots_size_boy_height"] * boy_h, -10 + n * 20, -1 if n else 1)
    return image


def pose_key(pose):
    return json.dumps(pose, sort_keys=True, separators=(",", ":"))


def render_frames(spec, keys, out_dir, px, look):
    results = {name: clip_render.clip_frames(track, spec.length, fps=DISPLAY_FPS,
                                              point_keys=("near_hand_on_head", "far_hand_on_head") if name == "boy" else (),
                                              point_resolver=boy_rig.hand_target_for_pose if name == "boy" else None,
                                              tear_speed=.45 if name == "boy" else 0.0)
               for name, track in keys.items()}
    boy_view = placement_view(composite.BOY_PLACEMENT, px)
    puss_view = placement_view(composite.PUSS_PLACEMENT, px)
    layer_cache = {"boy": {}, "puss": {}, "prop": {}}
    frame_cache = {}
    hashes = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for frame in range(len(results["boy"].poses)):
        states = {name: results[name].poses[frame] for name in results}
        state_keys = {name: pose_key(value) for name, value in states.items()}
        for name in ("boy", "puss", "prop"):
            if state_keys[name] in layer_cache[name]:
                continue
            if name == "boy":
                image = boy_rig.render_pose(states[name], ss=2, view=boy_view)
            elif name == "puss":
                image = cat_rig.render_pose(states[name], view=puss_view, ss=2)
            else:
                image = draw_prop_state(states[name], px, look)
            layer_cache[name][state_keys[name]] = image
        combined_key = tuple(state_keys[name] for name in ("boy", "puss", "prop"))
        if combined_key not in frame_cache:
            frame_cache[combined_key] = clip_render.product_transmissions(
                layer_cache[name][state_keys[name]] for name in ("boy", "puss", "prop"))
        image = frame_cache[combined_key]
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        hashes.append(digest)
        image.save(out_dir / ("f%04d.png" % frame))
    return results, hashes


def curtain_image(transmission, look, px):
    light = np.asarray(transmission.resize((px, px), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.35)),
                       dtype=np.float64) / 255.0
    axis = (np.arange(px) + .5) / px
    sx, sy = np.meshgrid(axis, axis)
    rgb = gobo_twin.curtain_look(light, sx, sy, px, look["curtain"])
    return Image.fromarray(np.rint(rgb * 255).astype(np.uint8), "RGB")


def save_curtain_gif(frame_dir, out, length, look, preview_px, gif_fps):
    sample_count = int(round(length * gif_fps))
    frames = []
    for index in range(sample_count):
        source_index = min(int(round(index * DISPLAY_FPS / gif_fps)), int(round(length * DISPLAY_FPS)) - 1)
        with Image.open(frame_dir / ("f%04d.png" % source_index)) as image:
            frame = curtain_image(image.convert("L"), look, preview_px).quantize(colors=32, method=Image.Quantize.MEDIANCUT)
            frames.append(frame)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=round(1000 / gif_fps), loop=0,
                   optimize=True, disposal=1)
    if out.stat().st_size >= 4 * 1024 * 1024:
        raise RuntimeError("curtain GIF exceeds 4 MB: %s (%d bytes)" % (out, out.stat().st_size))


def save_strips(spec, frame_dir, out_dir, look):
    strips = []
    for row in spec.timing():
        if row["id"] not in ("B1", "B2", "B3", "B4", "whimper"):
            continue
        times = np.linspace(row["start_s"] + .04, row["start_s"] + row["duration_s"] - .04, 6)
        panels = []
        for value in times:
            index = min(int(round(value * DISPLAY_FPS)), int(round(spec.length * DISPLAY_FPS)) - 1)
            with Image.open(frame_dir / ("f%04d.png" % index)) as image:
                panels.append(curtain_image(image.convert("L"), look, 220))
        strip = Image.new("RGB", (220 * 6, 220), (30, 18, 14))
        for n, panel in enumerate(panels):
            strip.paste(panel, (n * 220, 0))
        path = out_dir / ("strip_%s_6.png" % row["id"])
        strip.save(path)
        strips.append(path)
    return strips


def add_manifest_metadata(path, spec, results, max_cells, hashes, look, part=None):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["interaction"] = {
        "code": spec.code, "title": spec.title, "length_s": spec.length,
        "source_timing": SOURCE_TABLE, "timing_table": spec.timing(),
        "whimper_last": True, "prop": spec.prop, "part": part,
        "prop_presence_beats": list(PROP_BEATS[spec.code]),
        "max_cells": max_cells, "unique_cells_measured": len(set(hashes)),
        "handheld_wobble_baked": False, "creative_defaults": look,
        "tracks": {name: {"move_frames": {str(k): v for k, v in result.move_frames.items()},
                          "original_move_frames": {str(k): v for k, v in result.original_move_frames.items()}}
                   for name, result in results.items()},
        "claims": [
            {"tier": "declaration-proven", "claim": "Beat order and durations reproduce Gary's revised 11 Oct table.",
             "evidence": SOURCE_TABLE},
            {"tier": "measured", "claim": "Frames were rendered at 25 fps, de-duplicated, SDF-packed, and read back offline.",
             "evidence": relative(OUTPUT_ROOT / spec.code / "atlas" / "manifest.json")},
            {"tier": "inferred", "claim": "The curtain preview is a first-pass look proposal; Gary remains look authority.",
             "evidence": relative(OUTPUT_ROOT / spec.code / "curtain_preview.gif")},
        ],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def pack_interaction(spec, frame_dir, deliver, results, hashes, atlas_px, max_cells, render_scale, spread, wide,
                     look, preview_px, gif_fps):
    unique = len(set(hashes))
    if unique > max_cells:
        raise RuntimeError("%s exceeds %d cells at the four-frame move floor (%d); split required" %
                           (spec.code, max_cells, unique))
    atlas_dir = deliver / "atlas"
    manifest = pack_rig_flipbook.pack(frame_dir, atlas_dir, "PG8_%s" % spec.code, DISPLAY_FPS,
                                      atlas_px=atlas_px, gutter_px=GUTTER_PX, preview=True,
                                      sdf=True, spread=spread, wide=wide)
    manifest_path = atlas_dir / "manifest.json"
    manifest = add_manifest_metadata(manifest_path, spec, results, max_cells, hashes, look)
    timing = {"interaction": spec.code, "display_fps": DISPLAY_FPS, "length_s": spec.length,
              "rows": spec.timing(), "source": SOURCE_TABLE}
    (deliver / "timing_table.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")
    save_curtain_gif(frame_dir, deliver / "curtain_preview.gif", spec.length, look, preview_px, gif_fps)
    save_strips(spec, frame_dir, deliver, look)
    return manifest


def run_harness(root, report_path):
    command = [sys.executable, str(HERE / "test_pg8_interactions_offline.py"),
               "--root", str(root), "--report", str(report_path)]
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError("PG8 harness failed:\n" + result.stdout)
    return result.stdout.strip()


def build_scratch(root, atlas_px, max_cells, render_scale, spread, wide, look, preview_px, gif_fps):
    summaries = {}
    for spec in INTERACTIONS:
        keys = timelines(spec, look)
        frame_dir = root / "frames" / spec.code
        # Iterate source resolution until the measured cell count and the grid
        # implied by that count agree. Thin cuts can alias at probe resolution,
        # so a one-shot probe is not a safe SDF source-size decision.
        render_px = 256
        for _attempt in range(4):
            results, hashes = render_frames(spec, keys, frame_dir, render_px, look)
            unique = len(set(hashes))
            if unique > max_cells:
                raise RuntimeError("%s final render uses %d cells (cap %d); split required" %
                                   (spec.code, unique, max_cells))
            budget = pack_rig_flipbook.atlas_budget(unique, atlas_px)
            required_px = clip_render.scaled_render_size(budget["cell_px"] - 2 * GUTTER_PX, render_scale)
            if render_px >= required_px:
                break
            render_px = required_px
        else:
            raise RuntimeError("%s source-resolution/cell-grid iteration did not converge" % spec.code)
        deliver = root / "deliver" / spec.code
        deliver.mkdir(parents=True, exist_ok=True)
        manifest = pack_interaction(spec, frame_dir, deliver, results, hashes, atlas_px, max_cells,
                                    render_scale, spread, wide, look, preview_px, gif_fps)
        summaries[spec.code] = {"title": spec.title, "length_s": spec.length,
                                "rendered_frames": int(round(spec.length * DISPLAY_FPS)),
                                "unique_cells": len(set(hashes)), "cell_budget": manifest["cell_budget"],
                                "atlas": manifest["atlas"], "gif_bytes": (deliver / "curtain_preview.gif").stat().st_size}
        shutil.rmtree(frame_dir)
    harness_path = root / "deliver" / "offline_harness_report.json"
    harness_stdout = run_harness(root / "deliver", harness_path)
    report = {
        "schema_version": 1, "source_timing": SOURCE_TABLE, "display_fps": DISPLAY_FPS,
        "interactions": summaries, "harness_stdout": harness_stdout,
        "claims": [
            {"tier": "measured", "claim": "Five interaction clips were rendered, SDF-packed, read back and tested offline.",
             "evidence": "Tools/ShadowGobo/Puppets/interaction_clips/PG8_INTERACTIONS_REPORT.json"},
            {"tier": "inferred", "claim": "First-pass staging and look require Gary's review before Unreal application.",
             "evidence": "Tools/ShadowGobo/Puppets/interaction_clips/*/curtain_preview.gif"},
        ],
    }
    (root / "deliver" / "PG8_INTERACTIONS_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return [path for path in (root / "deliver").rglob("*") if path.is_file()], report


def record_path(run_id):
    return PROJECT_ROOT / "Backups" / ("PrePG8Interactions-" + run_id) / "record.json"


def output_plan():
    return {"root": relative(OUTPUT_ROOT), "interactions": [spec.code for spec in INTERACTIONS],
            "per_interaction": ["atlas/T_Gobo_PG8_<I#>_<grid>.png", "atlas/manifest.json",
                                "atlas/cells_contact.png", "curtain_preview.gif", "timing_table.json",
                                "strip_B1_6.png", "strip_B2_6.png", "strip_B3_6.png", "strip_B4_6.png",
                                "strip_whimper_6.png"],
            "shared": ["offline_harness_report.json", "PG8_INTERACTIONS_REPORT.json"],
            "unreal_access": False, "unreal_packages_saved": []}


def parse_look(raw):
    look = copy.deepcopy(DEFAULT_LOOK)
    if raw:
        changes = json.loads(raw)
        curtain = changes.pop("curtain", None)
        look.update(changes)
        if curtain:
            look["curtain"].update(curtain)
    return look


def apply(run_id, confirm, **options):
    expected = "APPLY_PG8_INTERACTIONS_" + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    with tempfile.TemporaryDirectory(prefix="pg8_interactions_") as temp:
        scratch = Path(temp)
        files, report = build_scratch(scratch, **options)
        backup_root = record_path(run_id).parent
        if backup_root.exists():
            raise SystemExit("backup run already exists: %s" % backup_root)
        backup_root.mkdir(parents=True)
        record = {"schema_version": 1, "run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(),
                  "mode": "APPLY", "confirm": expected, "census": git_census(), "targets": [],
                  "unreal_access": False, "unreal_packages_saved": [], "success_marker": None}
        for source in files:
            rel = source.relative_to(scratch / "deliver")
            target = OUTPUT_ROOT / rel
            entry = {"path": relative(target), "existed": target.is_file(),
                     "pre_sha256": sha256(target) if target.is_file() else None}
            if target.is_file():
                saved = backup_root / "files" / relative(target)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                entry["backup"] = relative(saved)
            record["targets"].append(entry)
        record_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
        for source in files:
            target = OUTPUT_ROOT / source.relative_to(scratch / "deliver")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        expected_hashes = {relative(OUTPUT_ROOT / source.relative_to(scratch / "deliver")): sha256(source)
                           for source in files}
        actual_hashes = {path: sha256(PROJECT_ROOT / path) for path in expected_hashes}
        if expected_hashes != actual_hashes:
            raise SystemExit("read-back hash mismatch")
        cells = sum(item["unique_cells"] for item in report["interactions"].values())
        marker = "PG8_INTERACTIONS_APPLY_OK|run=%s|files=%d|clips=5|cells=%d|dirty_packages=%d" % (
            run_id, len(files), cells, record["census"]["dirty_package_count"])
        record["post_sha256"] = actual_hashes
        record["success_marker"] = marker
        record_path(run_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
        if json.loads(record_path(run_id).read_text(encoding="utf-8"))["success_marker"] != marker:
            raise SystemExit("record read-back failed")
        print(marker)


def revert(run_id, confirm):
    expected = "REVERT_PG8_INTERACTIONS_" + run_id
    if confirm != expected:
        raise SystemExit("confirmation mismatch; expected %s" % expected)
    path = record_path(run_id)
    if not path.is_file():
        raise SystemExit("record not found: %s" % path)
    record = json.loads(path.read_text(encoding="utf-8"))
    stash = PROJECT_ROOT / "Backups" / ("RevertedPG8Interactions-" + run_id)
    if stash.exists():
        raise SystemExit("revert stash already exists: %s" % stash)
    stash.mkdir(parents=True)
    for entry in record["targets"]:
        target = PROJECT_ROOT / entry["path"]
        if target.is_file():
            saved = stash / "replaced" / entry["path"]
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(target, saved)
        if entry["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / entry["backup"], target)
    marker = "PG8_INTERACTIONS_REVERT_OK|run=%s|files=%d" % (run_id, len(record["targets"]))
    (stash / "revert_record.json").write_text(json.dumps({"run_id": run_id, "marker": marker}, indent=2),
                                               encoding="utf-8")
    print(marker)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("DRY", "APPLY", "REVERT"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--atlas", type=int, default=8192, choices=(8192,))
    parser.add_argument("--max-cells", type=int, default=196)
    parser.add_argument("--render-scale", type=float, default=2.0)
    parser.add_argument("--spread", type=float, default=6.0)
    parser.add_argument("--wide", type=float, default=4.0)
    parser.add_argument("--preview-px", type=int, default=360)
    parser.add_argument("--gif-fps", type=float, default=8.0)
    parser.add_argument("--look-json", default="", help="JSON overrides for Gary-owned creative defaults")
    args = parser.parse_args(argv)
    look = parse_look(args.look_json)
    if args.mode == "DRY":
        print(json.dumps({"mode": "DRY", "run_id": args.run_id, "plan": output_plan(),
                          "census": git_census(), "creative_defaults": look,
                          "apply_confirm": "APPLY_PG8_INTERACTIONS_" + args.run_id,
                          "revert_confirm": "REVERT_PG8_INTERACTIONS_" + args.run_id}, indent=2))
        print("PG8_INTERACTIONS_DRY_OK|run=%s" % args.run_id)
    elif args.mode == "APPLY":
        apply(args.run_id, args.confirm, atlas_px=args.atlas, max_cells=args.max_cells,
              render_scale=args.render_scale, spread=args.spread, wide=args.wide, look=look,
              preview_px=args.preview_px, gif_fps=args.gif_fps)
    else:
        revert(args.run_id, args.confirm)


if __name__ == "__main__":
    main()
