"""PG7 offline shadow-prop library and deterministic demo builder.

DRY writes nothing. APPLY requires ``APPLY_SHADOW_PROPS_<run-id>`` and writes
only the named PG7 deliverables after a recoverable pre-change record. REVERT
requires ``REVERT_SHADOW_PROPS_<run-id>``. No Unreal, MCP, or Blender access.
"""
from __future__ import annotations

import argparse
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

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
PROJECT_ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(TOOL_DIR)]

import boy_rig  # noqa: E402
import cat_rig  # noqa: E402
import clip_render  # noqa: E402
import gobo_twin  # noqa: E402
import pack_rig_flipbook  # noqa: E402
from build_boy_puss_composite import (  # noqa: E402
    BOY_PLACEMENT, PUSS_PLACEMENT, VISIBLE_BAND, map_point, placement_view,
)

FPS = 25.0
ATLAS_PX = 8192
GUTTER_PX = 8
OUTPUT_ROOT = HERE / "prop_demos"
TEMPLATE_ROOT = HERE / "prop_templates"
SHEET_PATH = HERE / "props_sheet.png"
REPORT_PATH = HERE / "PG7_SHADOW_PROPS_REPORT.md"
HARNESS_PATH = HERE / "props_harness_report.json"
LOOK = {
    "bucket": {"holder": "world rod", "size_boy_height": 0.24, "enter_seconds": 0.80,
               "tip_seconds": 0.48, "min_water_light_pixels_480": 120,
               # Review 9 Oct: the pour read as a trickle; a bucketful needs a fat ribbon and big splash cut-outs.
               "stream_width": 0.30, "splash_scale": 2.2,
               # stop higher/forward and pour onto the FRONT of the face so the stream crosses light (review 9 Oct)
               "stop_xy": (0.55, 0.030), "target_xy": (0.402, 0.165)},
    "page": {"attach": "boy_near_hand", "size_boy_height": 0.28, "show_cagliuso": True},
    "turnip": {"attach": "boy_near_hand", "size_boy_height": 0.12, "bite_seconds": 0.24},
    "pearl": {"attach_from": "puss_mouth", "attach_to": "boy_near_hand", "size_boy_height": 0.10},
    "crown": {"attach": "boy_head_top", "size_boy_height": 0.18, "restitution": 0.25},
    "boots": {"attach": "world", "size_vs_puss_height": 0.31, "restitution": 0.34, "spacing_widths": 1.22},
    "curtain": dict(gobo_twin.CURTAIN_DEFAULTS),
}
ATTACH_MODES = ("world", "boy_near_hand", "boy_far_hand", "boy_head_top", "puss_mouth", "puss_front_paw")


@dataclass(frozen=True)
class Prop:
    name: str
    outline: tuple
    cuts: tuple
    pivot: tuple
    size_relative_to_boy: float
    attach: str
    min_feature_local: float


def _poly(points):
    return tuple((float(x), float(y)) for x, y in points)


def _circle(cx, cy, r, n=28):
    return _poly((cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False))


def _star(cx, cy, r, n=5):
    points=[]
    for i in range(n*2):
        a=-math.pi/2+i*math.pi/n; radius=r if i%2==0 else r*.42
        points.append((cx+radius*math.cos(a),cy+radius*math.sin(a)))
    return _poly(points)


def _tapered_crescent(cx, cy, radius, width, start_deg=205, end_deg=305, n=22):
    """Smooth knife-cut crescent with tapered ends, following a circular edge."""
    angles = np.radians(np.linspace(start_deg, end_deg, n))
    outer, inner = [], []
    for i, angle in enumerate(angles):
        taper = math.sin(math.pi * i / (n - 1))
        half = width * taper * .5
        outer.append((cx + (radius + half) * math.cos(angle),
                      cy + (radius + half) * math.sin(angle)))
        inner.append((cx + (radius - half) * math.cos(angle),
                      cy + (radius - half) * math.sin(angle)))
    return _poly(outer + inner[::-1])


def _turnip(bites=0):
    leaves_and_left = [
        (-.50, .02), (-.42, -.08), (-.62, -.58), (-.31, -.22),
        (-.24, -.76), (-.10, -.20), (.02, -.82), (.10, -.19),
        (.38, -.68), (.28, -.13), (.48, -.42), (.42, -.04), (.52, .03),
    ]
    right_edge = [(0.59, .16), (0.56, .30), (0.47, .43), (0.32, .52)]
    notches = [
        ((.59, .13), (.45, .17), (.40, .23), (.48, .29), (.56, .31)),
        ((.54, .27), (.39, .30), (.35, .36), (.41, .42), (.48, .44)),
        ((.45, .40), (.31, .41), (.27, .47), (.32, .52), (.37, .54)),
    ]
    if bites:
        right_edge = list(notches[0])
        if bites >= 2:
            right_edge += list(notches[1][1:])
        if bites >= 3:
            right_edge += list(notches[2][1:])
    lower = [(0.17, .58), (.07, .62), (.035, .78), (0, .96), (-.04, .78),
             (-.09, .62), (-.25, .57), (-.42, .48), (-.54, .34), (-.60, .18)]
    return _poly(leaves_and_left + right_edge + lower)


def library():
    bucket = Prop("bucket", _poly([(-.52,-.38),(.52,-.38),(.45,.48),(-.45,.48)]),
                  (_poly([(-.43,-.13),(.42,-.11),(.39,-.045),(-.41,-.07)]),
                   _poly([(-.45,.22),(.43,.19),(.42,.27),(-.44,.30)]),
                   _poly([(-.18,-.28),(-.08,-.25),(-.14,.10),(-.20,.16)])),
                  (.50, -.30), .24, "world", .045)
    page = Prop("page", _poly([(-.48,-.62),(-.34,-.67),(-.12,-.61),(.08,-.68),(.48,-.60),(.46,.62),(.21,.57),
                                (.02,.65),(-.22,.58),(-.48,.63)]),
                tuple(_poly([(-.32,y),(.31,y),(.31,y+.035),(-.32,y+.035)]) for y in (-.34,-.18,-.02,.14,.30)),
                (0,0), .28, "boy_near_hand", .035)
    turnip = Prop("turnip", _turnip(0),
                  (_poly([(-.48,.02),(-.22,.075),(.18,.08),(.48,.025),(.46,.095),(.14,.15),(-.22,.14),(-.45,.08)]),),
                  (0,.18), .12, "boy_near_hand", .055)
    pearl = Prop("pearl", _circle(0,0,.50),
                 (_tapered_crescent(0, 0, .355, .105, 195, 292), _star(.23,-.20,.065)),
                 (0,0), .10, "puss_mouth", .045)
    crown = Prop("crown", _poly([(-.52,.38),(-.50,-.34),(-.39,-.08),(-.28,-.48),(-.18,-.08),(0,-.55),
                                  (.18,-.08),(.28,-.48),(.39,-.08),(.50,-.34),(.52,.38)]),
                 (_circle(-.28,.18,.07), _circle(0,.17,.07), _circle(.28,.18,.07),
                  _poly([(-.43,.25),(.42,.23),(.42,.30),(-.43,.33)])), (0,.38), .18, "boy_head_top", .055)
    boot = Prop("boot", _poly([(-.42,-.56),(.40,-.56),(.32,-.34),(.23,-.30),(.20,.25),
                                (.39,.30),(.67,.43),(.62,.54),(.45,.59),(-.02,.58),(-.05,.46),
                                (-.28,.46),(-.34,.31),(-.23,.25),(-.22,-.30),(-.34,-.34)]),
                (_poly([(-.33,-.42),(.31,-.43),(.27,-.34),(-.29,-.33)]),
                 _poly([(-.20,.34),(.36,.39),(.52,.47),(.48,.51),(.30,.45),(-.19,.41)])),
                (0,.58), .14, "world", .050)
    return {p.name: p for p in (bucket, page, turnip, pearl, crown, boot)}


def ease(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def bounce_motion(start, target, frames, restitution=.3, spin=18.0):
    """Deterministic gravity/restitution sample ending exactly at target."""
    out = []
    impact = max(2, int(frames * .68))
    for f in range(frames):
        if f <= impact:
            u = f / impact
            y = start[1] + (target[1] - start[1]) * u * u
            x = start[0] + (target[0] - start[0]) * ease(u)
            angle = spin * u
        else:
            u = (f - impact) / max(1, frames - 1 - impact)
            hop = (target[1] - start[1]) * .10 * restitution * math.sin(math.pi * u)
            x, y, angle = target[0], target[1] - abs(hop), spin * (1 - u)
        out.append((round(x, 4), round(y, 4), round(angle, 3), 1.0))
    out[-1] = (float(target[0]), float(target[1]), 0.0, 1.0)
    return out


def leaf_drift(start, target, frames, amplitude=.10, period=1.25):
    out = []
    for f in range(frames):
        u = f / max(1, frames - 1)
        phase = 2 * math.pi * (u / period)
        out.append((round(start[0] + (target[0]-start[0])*ease(u) + amplitude*math.sin(phase), 4),
                    round(start[1] + (target[1]-start[1])*ease(u), 4),
                    round(22*math.sin(phase), 3), round(max(.18, abs(math.cos(phase))), 3)))
    out[-1] = (float(target[0]), float(target[1]), 0.0, 1.0)
    return out


def transform(poly, centre, scale, angle=0.0, flip_x=1.0):
    points = np.asarray(poly, dtype=float) * np.array([scale * flip_x, scale])
    a = math.radians(angle)
    rotation = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return points @ rotation.T + np.asarray(centre)


def draw_prop(image, prop, centre, size_px, angle=0.0, flip_x=1.0, *, state=0, rod=False, extras=()):
    draw = ImageDraw.Draw(image)
    outline = _turnip(state) if prop.name == "turnip" else prop.outline
    p = transform(outline, centre, size_px, angle, flip_x)
    draw.polygon([tuple(v) for v in p], fill=0)
    for cut in prop.cuts:
        q = transform(cut, centre, size_px, angle, flip_x)
        draw.polygon([tuple(v) for v in q], fill=255)
    if prop.name == "bucket":
        # Articulated handle remains connected to the pail at both lugs.
        handle_local = ((-.48,-.30),(-.42,-.72),(0,-.90),(.42,-.72),(.48,-.30))
        handle = transform(handle_local, centre, size_px, angle, flip_x)
        draw.line([tuple(v) for v in handle], fill=0, width=max(3, round(.055*size_px)), joint="curve")
    if rod:
        pivot = transform((prop.pivot,), centre, size_px, angle, flip_x)[0]
        endpoint = rod if isinstance(rod, tuple) else (pivot[0], max(0, pivot[1]-size_px*1.25))
        draw.line([tuple(pivot), tuple(endpoint)], fill=0, width=max(3, round(.045*size_px)))
    for item in extras:
        if item[0] == "drop":
            x, y, r = item[1:]
            draw.ellipse((x-r, y-r*1.45, x+r, y+r*1.45), fill=0)
        elif item[0] == "crumb":
            x, y, r = item[1:]
            draw.ellipse((x-r, y-r, x+r, y+r), fill=0)


def draw_cagliuso(draw, centre, size_px):
    """Broad single-stroke cut lettering sized for projection, not typography."""
    glyphs={
        "C":[((1,0),(0,0),(0,2),(1,2))], "A":[((0,2),(.5,0),(1,2)),((.2,1.1),(.8,1.1))],
        "G":[((1,0),(0,0),(0,2),(1,2),(1,1.15),(.55,1.15))], "L":[((0,0),(0,2),(1,2))],
        "I":[((0,0),(1,0)),((.5,0),(.5,2)),((0,2),(1,2))], "U":[((0,0),(0,1.65),(.2,2),(.8,2),(1,1.65),(1,0))],
        "S":[((1,0),(0,0),(0,1),(1,1),(1,2),(0,2))], "O":[((0,0),(1,0),(1,2),(0,2),(0,0))],
    }
    word="CAGLIUSO"; total=.78*size_px; advance=total/len(word); height=.19*size_px
    x0=centre[0]-total/2; y0=centre[1]-.02*size_px; width=max(2,round(.020*size_px))
    for index,char in enumerate(word):
        gx=x0+index*advance
        for stroke in glyphs[char]:
            points=[(gx+x*.72*advance,y0+(y-1)*height/2) for x,y in stroke]
            draw.line(points,fill=255,width=width,joint="curve")


def base_layers(px, boy_pose=None, puss_pose=None):
    boy_pose = boy_rig.P() if boy_pose is None else boy_pose
    puss_pose = cat_rig.make_pose("sit_look_up") if puss_pose is None else puss_pose
    boy = boy_rig.render_pose(boy_pose, ss=2, view=placement_view(BOY_PLACEMENT, px))
    puss = cat_rig.render_pose(puss_pose, view=placement_view(PUSS_PLACEMENT, px), ss=2)
    return boy, puss


def turnip_boy_pose(state):
    """Keep the eating hand in the lit face-profile gap throughout all bites."""
    return boy_rig.P(neck=-12.0 if state["snap"] else 0.0,
                     near_hand_on_head=(880.0, 430.0))


def cell_anchor(px, owner, pose):
    if owner.startswith("boy_"):
        key = owner[4:]
        point = boy_rig.prop_anchors(pose)[key]
        return tuple(map_point(point, BOY_PLACEMENT) * px)
    key = owner[5:]
    point = cat_rig.prop_anchors(pose)[key]
    return tuple(map_point(point, PUSS_PLACEMENT) * px)


def demo_states(name, frames=100):
    """Plain deterministic state dictionaries; all transforms sampled at 25 fps."""
    states = []
    band_top, band_bottom = VISIBLE_BAND["top"], VISIBLE_BAND["bottom"]
    if name == "bucket":
        for f in range(frames):
            start = np.array((1.08, band_top + .035))
            stop = np.array((LOOK["bucket"]["stop_xy"][0], band_top + LOOK["bucket"]["stop_xy"][1]))
            if f < 20:
                u = ease(f / 19); xy = (1-u)*start + u*stop; angle = 0.0; phase = "enter"
            elif f < 28:
                xy = stop; angle = 0.0; phase = "clear_hold"
            elif f < 38:
                xy = stop; angle = 55.0 * ease((f-28)/9); phase = "tip"
            elif f < 53:
                xy = stop; angle = 55.0; phase = "stream"
            elif f < 69:
                xy = stop; angle = 55.0; phase = "splash"
            elif f < 80:
                xy = stop; angle = 55.0; phase = "drips"
            elif f < 89:
                xy = stop; angle = 55.0 * (1-ease((f-80)/8)); phase = "right"
            elif f < 98:
                u = ease((f-89)/8); xy = (1-u)*stop + u*start; angle = 0.0; phase = "exit"
            else:
                xy = start; angle = 0.0; phase = "off"
            states.append({"xy": tuple(round(float(v), 5) for v in xy), "angle": round(angle, 4),
                           "phase": phase, "splash": min(3, max(0, (f-53)//4)), "hold": f >= 98})
    elif name == "page":
        motion = leaf_drift((.58, band_top-.12), (.39, .51), 70)
        states = [{"motion": motion[min(f,69)], "label": True, "hold": f >= 70} for f in range(frames)]
    elif name == "turnip":
        for f in range(frames):
            bite = min(3, max(0, (f-18)//20)); snap = (f % 20) in range(3,8) and f >= 18 and bite <= 3
            hold = f >= 82
            states.append({"bite": int(bite), "snap": False if hold else bool(snap),
                           "crumb": False if hold else f >= 18 and f % 20 in range(7,13), "hold": hold})
    elif name == "pearl":
        for f in range(frames):
            u = ease(np.clip((f-12)/58, 0, 1)); states.append({"u": float(u), "hold": f >= 72})
    elif name == "crown":
        motion = bounce_motion((.30, band_top-.18), (.30, band_top+.065), 64, LOOK["crown"]["restitution"], 24)
        states = [{"motion": motion[min(f,63)], "hold": f >= 64} for f in range(frames)]
    elif name == "boots":
        motions = [bounce_motion((.55+i*.08, band_top-.15-i*.035), (.48+i*.083, band_bottom-.015), 38,
                                 LOOK["boots"]["restitution"], (-1)**i*(18+i*3)) for i in range(4)]
        for f in range(frames):
            states.append({"boots": [m[min(max(f-i*10,0),37)] for i,m in enumerate(motions)], "hold": f >= 72})
    else:
        raise KeyError(name)
    return states


def _draw_bucket_water(image, state, tip, target, size):
    """Draw replacement cut-outs for stream, four splash beats, then drips."""
    draw = ImageDraw.Draw(image)
    phase = state["phase"]
    if phase == "stream":
        ys = np.linspace(tip[1], target[1], 18)
        centre_x = np.linspace(tip[0], target[0], 18)
        wave = np.sin(np.linspace(0, 5*math.pi, 18)) * .032 * size * LOOK["bucket"]["splash_scale"]
        width = LOOK["bucket"]["stream_width"] * size * (1.0 + .18*np.sin(np.linspace(0, 3*math.pi, 18)))
        left = list(zip(centre_x + wave - width/2, ys))
        right = list(zip((centre_x + wave + width/2)[::-1], ys[::-1]))
        draw.polygon(left + right, fill=0)
        k = LOOK["bucket"]["splash_scale"]
        draw.ellipse((target[0]-.07*size*k, target[1]-.035*size*k,
                      target[0]+.07*size*k, target[1]+.045*size*k), fill=0)
    elif phase == "splash":
        size = size * LOOK["bucket"]["splash_scale"]
        variants = (
            ((0,0),(.18,-.18),(.13,-.02),(.34,-.04),(.14,.08),(.22,.25),(0,.11)),
            ((0,0),(.10,-.30),(.17,-.08),(.38,-.18),(.20,.03),(.39,.14),(.13,.13),(.12,.34)),
            ((0,0),(.26,-.25),(.18,-.02),(.46,-.01),(.20,.10),(.31,.32),(.05,.17),(-.05,.30)),
            ((0,0),(.12,-.18),(.09,-.01),(.31,.02),(.12,.10),(.20,.24),(.02,.15),(-.08,.20)),
        )
        points = [(target[0]+x*size, target[1]+y*size) for x,y in variants[state["splash"]]]
        draw.polygon(points, fill=0)
        x,y=target[0]+.28*size,target[1]+.04*size; r=.07*size
        draw.ellipse((x-r,y-r*1.20,x+r,y+r*1.20),fill=0)
        x,y=target[0]+.43*size,target[1]+.02*size; r=.055*size
        draw.ellipse((x-r,y-r*1.35,x+r,y+r*1.35),fill=0)
        for i, (dx,dy,r) in enumerate(((.43,-.18,.040),(.48,.08,.032),(.31,.31,.035),(.08,.39,.027))):
            if i <= state["splash"]:
                x,y = target[0]+dx*size, target[1]+dy*size
                draw.ellipse((x-r*size,y-r*1.35*size,x+r*size,y+r*1.35*size),fill=0)
    elif phase == "drips":
        size = size * LOOK["bucket"]["splash_scale"] * 0.7
        for i, (dx,dy) in enumerate(((.08,.16),(.22,.25),(.36,.12))):
            r=(.036-.005*i)*size; x,y=target[0]+dx*size,target[1]+dy*size
            draw.ellipse((x-r,y-r*1.55,x+r,y+r*1.55),fill=0)


def render_state(name, state, px, *, return_layers=False, bucket_xy_override=None):
    lib = library(); boy_pose = boy_rig.P(); puss_pose = cat_rig.make_pose("sit_look_up")
    if name == "turnip":
        boy_pose = turnip_boy_pose(state)
    boy, puss = base_layers(px, boy_pose, puss_pose)
    prop_layer = Image.new("L", (px, px), 255)
    water_layer = Image.new("L", (px, px), 255)
    bucket_card = Image.new("L", (px, px), 255)
    boy_h = (VISIBLE_BAND["bottom"]-VISIBLE_BAND["top"]) * px
    if name == "bucket":
        x,y = bucket_xy_override or state["xy"]; centre=(x*px,y*px); size=LOOK["bucket"]["size_boy_height"]*boy_h
        rod_end=(.985*px, max(0.0,(VISIBLE_BAND["top"]-.16)*px))
        draw_prop(prop_layer, lib["bucket"], centre, size, state["angle"], rod=rod_end)
        draw_prop(bucket_card, lib["bucket"], centre, size, state["angle"], rod=False)
        tip=transform(((-.48,.42),),centre,size,state["angle"])[0]
        target=(LOOK["bucket"]["target_xy"][0]*px,(VISIBLE_BAND["top"]+LOOK["bucket"]["target_xy"][1])*px)
        _draw_bucket_water(water_layer,state,tip,target,size)
    elif name == "page":
        x,y,a,sx=state["motion"]; size=LOOK["page"]["size_boy_height"]*boy_h
        draw_prop(prop_layer, lib["page"], (x*px,y*px), size, a, sx, rod=False)
        if state["label"] and sx > .72:
            draw_cagliuso(ImageDraw.Draw(prop_layer),(x*px,y*px),size)
    elif name == "turnip":
        anchor=cell_anchor(px,"boy_near_hand",boy_pose); size=LOOK["turnip"]["size_boy_height"]*boy_h
        centre=(anchor[0]+.07*size,anchor[1]-.03*size)
        extras=[]
        if state["crumb"]:
            for i in range(3): extras.append(("crumb",centre[0]+(.30+i*.10)*size,centre[1]+(.15+i*.16)*size,.035*size))
        draw_prop(prop_layer,lib["turnip"],centre,size,-38,state=state["bite"],extras=extras)
    elif name == "pearl":
        a=np.asarray(cell_anchor(px,"puss_mouth",puss_pose)); b=np.asarray(cell_anchor(px,"boy_near_hand",boy_pose)); u=state["u"]
        point=(1-u)*a+u*b; size=LOOK["pearl"]["size_boy_height"]*boy_h
        draw_prop(prop_layer,lib["pearl"],point,size)
    elif name == "crown":
        x,y,a,sx=state["motion"]; size=LOOK["crown"]["size_boy_height"]*boy_h
        draw_prop(prop_layer,lib["crown"],(x*px,y*px),size,a,sx,rod=True)
    elif name == "boots":
        size=LOOK["boots"]["size_vs_puss_height"]*.45*boy_h
        for x,y,a,sx in state["boots"]: draw_prop(prop_layer,lib["boot"],(x*px,y*px),size,a,sx,rod=False)
    frame = clip_render.product_transmissions((boy,puss,prop_layer,water_layer))
    if return_layers:
        return {"frame":frame,"boy":boy,"puss":puss,"prop":prop_layer,
                "bucket_card":bucket_card,"water":water_layer}
    return frame


def bucket_visibility_measurements(states=None, px=480, bucket_xy_override=None):
    states = states or demo_states("bucket")
    rows=[]
    for index,state in enumerate(states):
        layers=render_state("bucket",state,px,return_layers=True,bucket_xy_override=bucket_xy_override)
        boy=np.asarray(layers["boy"]); water=np.asarray(layers["water"]); card=np.asarray(layers["bucket_card"])
        light=int(np.sum((boy>200)&(water<80)))
        overlap=int(np.sum((boy<80)&(card<80)))
        threshold=LOOK["bucket"]["min_water_light_pixels_480"]
        required=state["phase"] in ("stream","splash")
        rows.append({"frame":index,"phase":state["phase"],"water_light_pixels":light,
                     "bucket_boy_overlap_pixels":overlap,
                     "passes_pour_gate":(not required) or (light>=threshold and overlap==0)})
    return rows


def unique_count(name, states, px=420):
    return len({hashlib.sha256(render_state(name,s,px).tobytes()).digest() for s in states})


def render_frames(name, states, out, px):
    out.mkdir(parents=True, exist_ok=True)
    for i,state in enumerate(states): render_state(name,state,px).save(out/("f%04d.png"%i))


def ensure_sdf_source_scale(frame_dir, atlas_px=ATLAS_PX, gutter_px=GUTTER_PX):
    files=sorted(frame_dir.glob("*.png")); hashes=set()
    for path in files:
        with Image.open(path) as image: hashes.add(hashlib.sha256(image.convert("L").tobytes()).digest())
    budget=pack_rig_flipbook.atlas_budget(len(hashes),atlas_px)
    required=2*(budget["cell_px"]-2*gutter_px)
    with Image.open(files[0]) as first: current=first.width
    if current < required:
        for path in files:
            with Image.open(path) as image: resized=image.resize((required,required),Image.Resampling.LANCZOS)
            resized.save(path)
    return {"actual_unique_before_pack":len(hashes),"source_px":max(current,required),"required_px":required}


def save_templates(root):
    root.mkdir(parents=True, exist_ok=True); lib=library(); thumbs=[]
    for name,prop in lib.items():
        im=Image.new("L",(1000,1000),255); draw_prop(im,prop,(500,500),360,state=0)
        im.save(root/(name+"_template.png")); thumbs.append((name,im.resize((280,280))))
        def d(poly): return "M"+" L".join("%.2f,%.2f"%(x,y) for x,y in transform(poly,(500,500),360))+" Z"
        outline=_turnip(0) if name=="turnip" else prop.outline
        path=d(outline)+" "+" ".join(d(c) for c in prop.cuts)
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path fill="#000" fill-rule="evenodd" d="%s"/></svg>'%path
        (root/(name+".svg")).write_text(svg,encoding="utf-8")
    sheet=Image.new("RGB",(840,600),(238,232,216)); dr=ImageDraw.Draw(sheet)
    for i,(name,im) in enumerate(thumbs):
        x=(i%3)*280;y=(i//3)*300;sheet.paste(Image.merge("RGB",(im,im,im)),(x,y));dr.text((x+12,y+270),name.upper(),fill=(15,15,15))
    return sheet


def add_manifest(path,name,states,min_width_px):
    data=json.loads(path.read_text(encoding="utf-8")); data["prop_demo"]={
        "name":name,"look":LOOK[name],"attach_modes":list(ATTACH_MODES),"quantized_transforms":True,
        "product_transmissions":True,"minimum_feature_width_px":round(min_width_px,3),"meets_2px":min_width_px>=2,
        "claims":[
            {"tier":"measured","claim":"Frames were rendered, SDF-packed and read back offline.","evidence":"Tools/ShadowGobo/Puppets/props.py:380"},
            {"tier":"inferred","claim":"The proposed scale and staging need Gary's visual approval.","evidence":"Tools/ShadowGobo/Puppets/props.py:266"},
        ]}
    path.write_text(json.dumps(data,indent=2),encoding="utf-8")


def curtain_gif(manifest,out):
    prepared=gobo_twin.prepare_render(manifest,params={"BorderDepth":1.0,"BorderAspect":1.88,"Scale":.7071,"Defocus":.25},
                                      fps=FPS,px=960,curtain=True,curtain_params=LOOK["curtain"])
    frames=[]; strip_frames=[]
    data=json.loads(Path(manifest).read_text(encoding="utf-8")); count=data["take"]["frames_rendered"]
    strip_indices=set(int(x) for x in np.linspace(0,count-1,6))
    for i in range(count):
        rendered=gobo_twin.render_prepared(prepared,i/FPS)
        if i in strip_indices: strip_frames.append(rendered.convert("RGB").resize((320,320),Image.Resampling.LANCZOS))
        frames.append(rendered.convert("P",palette=Image.Palette.ADAPTIVE,colors=48))
    frames[0].save(out,save_all=True,append_images=frames[1:],duration=40,loop=0,optimize=True)
    if out.stat().st_size>=4*1024*1024: raise RuntimeError("GIF exceeds 4 MB: %s"%out)
    strip=Image.new("RGB",(320*6,320),(255,255,255))
    for i,frame in enumerate(strip_frames): strip.paste(frame,(i*320,0))
    strip.save(out.with_name("frame_strip_6.png"))


def git_census():
    p=subprocess.run(["git","status","--short"],cwd=PROJECT_ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    dirty=[x for x in p.stdout.splitlines() if x.strip()]
    return {"source_dirty":dirty,"dirty_packages":[x for x in dirty if x.lower().endswith((".uasset",".umap"))],"git_status_exit":p.returncode}


def build_scratch(root, demos=None):
    demos=tuple(demos or ("bucket","page","turnip","pearl","crown","boots")); deliver=root/"deliver"
    templates=deliver/"prop_templates"; sheet=save_templates(templates); sheet.save(deliver/"props_sheet.png")
    metrics={}
    for name in demos:
        states=demo_states(name); count=unique_count(name,states); budget=pack_rig_flipbook.atlas_budget(count,ATLAS_PX)
        inner=budget["cell_px"]-2*GUTTER_PX; px=max(2048,2*inner)
        frame_dir=root/(name+"_frames"); render_frames(name,states,frame_dir,px)
        source_scale=ensure_sdf_source_scale(frame_dir)
        out=deliver/("clip_prop_"+name); atlas=out/"atlas"
        manifest=pack_rig_flipbook.pack(frame_dir,atlas,"Prop"+name.title(),FPS,ATLAS_PX,GUTTER_PX,preview=True,sdf=True)
        prop=library()["boot" if name=="boots" else name]
        relative_size = (LOOK[name]["size_boy_height"] if "size_boy_height" in LOOK[name]
                         else LOOK[name]["size_vs_puss_height"] * .45)
        min_width=prop.min_feature_local*relative_size*(VISIBLE_BAND["bottom"]-VISIBLE_BAND["top"])*manifest["atlas"]["inner_px"]
        add_manifest(atlas/"manifest.json",name,states,min_width)
        curtain_gif(atlas/"manifest.json",out/"curtain_preview_defocus025.gif")
        metrics[name]={"rendered_frames":len(states),"unique_cells":manifest["take"]["frames_packed"],"grid":"%dx%d"%(manifest["atlas"]["cols"],manifest["atlas"]["rows"]),"cell_px":manifest["atlas"]["cell_px"],"minimum_feature_width_px":round(min_width,3),"gif_bytes":(out/"curtain_preview_defocus025.gif").stat().st_size,"source_scale":source_scale,"frame_strip":"frame_strip_6.png"}
        if name=="bucket":
            visibility=bucket_visibility_measurements(states,480)
            (out/"pour_visibility_per_frame.json").write_text(json.dumps({
                "measurement_px":480,"threshold":LOOK["bucket"]["min_water_light_pixels_480"],
                "definition":"black water pixels on light outside the boy silhouette; pail/head overlap must be zero during stream/splash",
                "frames":visibility},indent=2),encoding="utf-8")
            required=[r for r in visibility if r["phase"] in ("stream","splash")]
            metrics[name]["pour_visibility"]={"required_frames":len(required),
                "minimum_water_light_pixels":min(r["water_light_pixels"] for r in required),
                "maximum_bucket_boy_overlap_pixels":max(r["bucket_boy_overlap_pixels"] for r in required),
                "all_pass":all(r["passes_pour_gate"] for r in required)}
    if len(demos)<6 and REPORT_PATH.with_suffix(".json").is_file():
        combined=json.loads(REPORT_PATH.with_suffix(".json").read_text(encoding="utf-8"));combined.update(metrics);metrics=combined
    (deliver/"metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    harness=subprocess.run([sys.executable,str(HERE/"test_props_offline.py"),"--report",str(deliver/"props_harness_report.json")],cwd=PROJECT_ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if harness.returncode: raise RuntimeError("prop harness failed:\n"+harness.stdout)
    return deliver,metrics


def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def targets_for(deliver):
    result=[]
    for source in deliver.rglob("*"):
        if not source.is_file(): continue
        rel=source.relative_to(deliver)
        if rel.parts[0]=="prop_templates": target=TEMPLATE_ROOT/Path(*rel.parts[1:])
        elif rel.name=="props_sheet.png": target=SHEET_PATH
        elif rel.name=="metrics.json": target=REPORT_PATH.with_suffix(".json")
        elif rel.name=="props_harness_report.json": target=HARNESS_PATH
        elif rel.name=="report.md": continue
        else: target=OUTPUT_ROOT/rel
        result.append((source,target))
    return result


def write_report(metrics,path):
    lines=["# PG7b shadow props revision report","","[measured] The table is read from the offline APPLY output; each demo uses the current 0.5625 Puss framing and knee crop imported from `build_boy_puss_composite.py`. `Tools/ShadowGobo/Puppets/props.py`","","| Demo | Frames | Unique cells | Grid | Min feature | GIF |","|---|---:|---:|---:|---:|---:|"]
    for n,m in metrics.items(): lines.append("| %s | %d | %d | %s | %.2f px | %.2f MB |"%(n,m["rendered_frames"],m["unique_cells"],m["grid"],m["minimum_feature_width_px"],m["gif_bytes"]/1048576))
    bucket=metrics.get("bucket",{}).get("pour_visibility",{})
    lines += ["","[measured] Every demo has `curtain_preview_defocus025.gif` and `frame_strip_6.png` beside it. `Tools/ShadowGobo/Puppets/props.py`",
              "[measured] Bucket pour gate: %s required frames; minimum %s water-on-light pixels at 480 px; maximum pail/boy overlap %s pixels; all pass=%s. Per-frame evidence: `clip_prop_bucket/pour_visibility_per_frame.json`. `Tools/ShadowGobo/Puppets/props.py`"%(bucket.get("required_frames","n/a"),bucket.get("minimum_water_light_pixels","n/a"),bucket.get("maximum_bucket_boy_overlap_pixels","n/a"),bucket.get("all_pass","n/a")),
              "[measured] Shorter falls and fewer droplets reduce unique cells directly; static holds already de-duplicate to one cell. `Tools/ShadowGobo/Puppets/props.py`",
              "[inferred] Gary should decide whether the Cagliuso word remains and visually approve the revised bucket staging, turnip, pearl gleam, and Puss-sized cavalier boots before Unreal application. `Tools/ShadowGobo/Puppets/props.py`"]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def record_path(run): return PROJECT_ROOT/"Backups"/("PreShadowProps-"+run)/"record.json"


def apply(run,confirm,only_demo=None):
    expected="APPLY_SHADOW_PROPS_"+run
    if confirm!=expected: raise SystemExit("confirmation mismatch; expected "+expected)
    with tempfile.TemporaryDirectory(prefix="pg7_props_") as temp:
        deliver,metrics=build_scratch(Path(temp),None if only_demo is None else (only_demo,)); write_report(metrics,deliver/"report.md")
        pairs=targets_for(deliver); pairs.append((deliver/"report.md",REPORT_PATH))
        backup=record_path(run).parent
        if backup.exists(): raise SystemExit("backup run already exists: "+str(backup))
        backup.mkdir(parents=True); record={"run_id":run,"created_utc":datetime.now(timezone.utc).isoformat(),"mode":"APPLY","confirm":expected,"census":git_census(),"unreal_access":False,"unreal_packages_saved":[],"targets":[],"success_marker":None}
        for source,target in pairs:
            entry={"path":str(target.relative_to(PROJECT_ROOT)).replace('\\','/'),"existed":target.is_file(),"pre_sha256":sha256(target) if target.is_file() else None}
            if target.is_file():
                saved=backup/"files"/target.relative_to(PROJECT_ROOT);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved);entry["backup"]=str(saved.relative_to(PROJECT_ROOT)).replace('\\','/')
            record["targets"].append(entry)
        record_path(run).write_text(json.dumps(record,indent=2),encoding="utf-8")
        for source,target in pairs: target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        actual={e["path"]:sha256(PROJECT_ROOT/e["path"]) for e in record["targets"]}
        marker="SHADOW_PROPS_APPLY_OK|run=%s|files=%d|demos=%s|dirty_packages=%d"%(run,len(pairs),only_demo or 6,len(record["census"]["dirty_packages"]))
        record["post_sha256"]=actual;record["success_marker"]=marker;record["metrics"]=metrics
        record_path(run).write_text(json.dumps(record,indent=2),encoding="utf-8")
        if json.loads(record_path(run).read_text(encoding="utf-8"))["success_marker"]!=marker: raise RuntimeError("record read-back failed")
        print(marker)


def revert(run,confirm):
    expected="REVERT_SHADOW_PROPS_"+run
    if confirm!=expected: raise SystemExit("confirmation mismatch; expected "+expected)
    record=json.loads(record_path(run).read_text(encoding="utf-8")); stash=PROJECT_ROOT/"Backups"/("RevertedShadowProps-"+run)
    if stash.exists(): raise SystemExit("revert stash already exists")
    stash.mkdir(parents=True)
    for e in record["targets"]:
        target=PROJECT_ROOT/e["path"]
        if target.is_file(): saved=stash/"replaced"/e["path"];saved.parent.mkdir(parents=True,exist_ok=True);shutil.move(target,saved)
        if e["existed"]: target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PROJECT_ROOT/e["backup"],target)
    print("SHADOW_PROPS_REVERT_OK|run=%s|files=%d"%(run,len(record["targets"])))


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument("--mode",required=True,choices=("DRY","APPLY","REVERT"));ap.add_argument("--run-id",required=True);ap.add_argument("--confirm",default="");ap.add_argument("--only-demo",choices=("bucket","page","turnip","pearl","crown","boots"));a=ap.parse_args(argv)
    if a.mode=="DRY":
        print(json.dumps({"mode":"DRY","run_id":a.run_id,"outputs":[str(OUTPUT_ROOT.relative_to(PROJECT_ROOT)),str(TEMPLATE_ROOT.relative_to(PROJECT_ROOT)),str(SHEET_PATH.relative_to(PROJECT_ROOT)),str(REPORT_PATH.relative_to(PROJECT_ROOT)),str(HARNESS_PATH.relative_to(PROJECT_ROOT))],"census":git_census(),"apply_confirm":"APPLY_SHADOW_PROPS_"+a.run_id,"revert_confirm":"REVERT_SHADOW_PROPS_"+a.run_id},indent=2));print("SHADOW_PROPS_DRY_OK|run="+a.run_id)
    elif a.mode=="APPLY": apply(a.run_id,a.confirm,a.only_demo)
    else: revert(a.run_id,a.confirm)


if __name__=="__main__": raise SystemExit(main())
