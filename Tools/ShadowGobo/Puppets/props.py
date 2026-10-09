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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
    "page": {"attach": "boy_near_hand", "size_boy_height": 0.34, "page_text": "Cagliuso",
             # PG7d: a font remains an explicit opt-in; the production default is carved polygonal lettering.
             "page_font": None, "page_text_width": 0.85, "page_text_bold": 0.003,
             "page_text_angle_deg": -18.0, "page_text_diagonal_fill": 0.85,
             "page_text_seed": 1709, "page_wedge_down": 0.066, "page_wedge_thin": 0.038},
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
        (-.68, .08), (-.55, -.02), (-.42, -.34), (-.25, -.13),
        (-.14, -.42), (-.03, -.12), (.12, -.38), (.20, -.10),
        (.42, -.31), (.34, -.04), (.59, .06),
    ]
    right_edge = [(0.72, .19), (0.69, .38), (0.56, .57), (0.34, .68)]
    notches = [
        ((.72, .16), (.55, .20), (.49, .27), (.58, .34), (.68, .37)),
        ((.54, .31), (.34, .35), (.27, .44), (.39, .52), (.52, .56)),
        ((.44, .52), (.21, .53), (.14, .62), (.25, .69), (.36, .70)),
    ]
    if bites:
        right_edge = list(notches[0])
        if bites >= 2:
            right_edge += list(notches[1][1:])
        if bites >= 3:
            right_edge += list(notches[2][1:])
    lower = [(0.16, .72), (.07, .74), (.025, .84), (0, .91), (-.035, .84),
             (-.09, .74), (-.28, .70), (-.48, .61), (-.63, .45), (-.72, .23)]
    return _poly(leaves_and_left + right_edge + lower)


def library():
    bucket = Prop("bucket", _poly([(-.61,-.43),(.61,-.43),(.55,-.34),(.42,.49),(-.42,.49),(-.55,-.34)]),
                  (_poly([(-.52,-.31),(.52,-.31),(.49,-.22),(-.49,-.22)]),
                   _poly([(-.48,.17),(.47,.15),(.45,.23),(-.47,.26)])),
                  (.58, -.35), .24, "world", .050)
    page = Prop("page", _poly([(-.50,-.54),(-.61,-.58),(-.67,-.51),(-.62,-.43),(-.49,-.39),
                                (-.47,-.23),(-.51,-.05),(-.47,.15),(-.50,.38),(-.61,.43),
                                (-.66,.51),(-.60,.59),(-.48,.62),(-.20,.58),(.05,.64),(.29,.58),
                                (.49,.62),(.61,.58),(.67,.50),(.61,.42),(.49,.38),(.46,.17),
                                (.50,-.03),(.46,-.24),(.49,-.39),(.61,-.43),(.66,-.51),(.60,-.59),
                                (.48,-.62),(.24,-.58),(-.03,-.64),(-.27,-.58)]),
                (_tapered_crescent(-.53,-.50,.105,.035,120,300,18),
                 _tapered_crescent(.53,.50,.105,.035,-60,120,18)),
                (0,0), .28, "boy_near_hand", .035)
    turnip = Prop("turnip", _turnip(0),
                  (_tapered_crescent(-.12,.30,.40,.055,205,302,18),
                   _tapered_crescent(-.05,.49,.29,.045,205,300,16)),
                  (0,.18), .12, "boy_near_hand", .055)
    pearl = Prop("pearl", _circle(0,0,.50),
                 (_tapered_crescent(0, 0, .355, .105, 195, 292),),
                 (0,0), .10, "puss_mouth", .045)
    crown = Prop("crown", _poly([(-.52,.38),(-.50,-.34),(-.39,-.08),(-.28,-.48),(-.18,-.08),(0,-.55),
                                  (.18,-.08),(.28,-.48),(.39,-.08),(.50,-.34),(.52,.38)]),
                 (_circle(-.28,.18,.07), _circle(0,.17,.07), _circle(.28,.18,.07),
                  _poly([(-.43,.25),(.42,.23),(.42,.30),(-.43,.33)])), (0,.38), .18, "boy_head_top", .055)
    boot = Prop("boot", _poly([(-.39,-.52),(-.22,-.59),(-.05,-.52),(.12,-.59),(.34,-.50),
                                (.29,-.37),(.23,-.30),(.22,.16),(.38,.20),(.57,.29),(.69,.42),
                                (.68,.54),(.60,.64),(.48,.70),(.29,.72),(.08,.68),(-.11,.61),
                                (-.27,.53),(-.34,.40),(-.32,.25),(-.23,.17),(-.22,-.29),(-.34,-.36)]),
                (_poly([(-.27,-.42),(-.12,-.45),(.04,-.40),(.23,-.44),(.25,-.39),(.07,-.36),(-.12,-.40),(-.26,-.36)]),
                 _poly([(-.19,-.17),(.19,-.16),(.20,-.11),(-.19,-.11)]),
                 _circle(.18,-.135,.045,16),
                 _tapered_crescent(.19,.43,.39,.045,28,151,18),
                 _poly([(-.12,.52),(.04,.57),(.24,.61),(.44,.59),(.52,.55),(.52,.59),(.42,.63),(.23,.64),(.03,.61),(-.13,.57)])),
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


PAGE_GLYPHS = {
    # Centre-lines in a small, deliberately blunt Roman hand. The role selects
    # a broad down-cut or a finer upstroke/crossbar; all are expanded to wedges.
    "C": (((.86,-.42),(.54,-.55),(.18,-.43),(.05,-.05),(.12,.34),(.50,.53),(.88,.35),"down"),),
    "A": (((.08,.52),(.48,-.54),"up"),((.48,-.54),(.92,.52),"down"),((.25,.12),(.75,.12),"cross")),
    "G": (((.86,-.40),(.55,-.55),(.17,-.42),(.05,-.04),(.13,.35),(.52,.54),(.90,.33),(.90,.07),(.58,.07),"down"),),
    "L": (((.18,-.53),(.18,.49),(.90,.49),"down"),),
    "I": (((.10,-.50),(.88,-.50),"cross"),((.49,-.50),(.49,.50),"down"),((.08,.50),(.90,.50),"cross")),
    "U": (((.12,-.52),(.12,.27),(.29,.51),(.68,.53),(.88,.27),(.88,-.52),"down"),),
    "S": (((.88,-.40),(.55,-.55),(.18,-.43),(.13,-.12),(.73,.08),(.88,.34),(.58,.54),(.15,.41),"down"),),
    "O": (((.50,-.55),(.17,-.42),(.07,-.02),(.18,.40),(.51,.55),(.84,.39),(.93,-.03),(.82,-.43),(.50,-.55),"down"),),
    "M": (((.10,.52),(.10,-.52),(.50,.08),(.90,-.52),(.90,.52),"down"),),
}


def _knife_wedge(points, middle_width):
    """Expand a centre-line into a pointed, asymmetric hand-pushed knife cut."""
    source=np.asarray(points,dtype=float)
    # Every segment needs interior samples: a two-point stroke would otherwise
    # have zero width at both pointed ends and collapse to a line.
    dense=[]
    for index in range(len(source)-1):
        samples=np.linspace(source[index],source[index+1],5,endpoint=False)
        dense.extend(samples)
    dense.append(source[-1]);p=np.asarray(dense,dtype=float)
    if len(p)<2: return _poly(())
    delta=np.gradient(p,axis=0); lengths=np.linalg.norm(delta,axis=1);lengths[lengths<1e-9]=1.0
    normal=np.column_stack((-delta[:,1]/lengths,delta[:,0]/lengths))
    t=np.linspace(0.0,1.0,len(p))
    profile=np.sin(np.pi*np.power(t,.78)); profile[0]=profile[-1]=0.0
    half=.5*middle_width*profile
    left=p+normal*(half*(1.08-.10*t))[:,None]
    right=p-normal*(half*(.92+.08*t))[:,None]
    return _poly(np.vstack((left,right[::-1])))


def _wedge_serif(point, toward, width):
    """Triangular end nick joined to a stroke point, never a typographic cap."""
    point=np.asarray(point,float); direction=np.asarray(toward,float)-point
    length=np.linalg.norm(direction)
    if length<1e-9: return _poly(())
    direction/=length; normal=np.array((-direction[1],direction[0]))
    shoulder=point+direction*width*.72
    return _poly((point, shoulder+normal*width*.55, shoulder-normal*width*.55))


def page_text_polygons(text, centre, size_px, *, angle_deg=None, diagonal_fill=None, seed=None):
    """Return independent knife-cut polygons for deterministic hand-carved capitals."""
    word="".join(c for c in str(text).upper() if c in PAGE_GLYPHS)
    if not word: return []
    angle=LOOK["page"]["page_text_angle_deg"] if angle_deg is None else angle_deg
    fill=LOOK["page"]["page_text_diagonal_fill"] if diagonal_fill is None else diagonal_fill
    rng=np.random.default_rng(LOOK["page"]["page_text_seed"] if seed is None else seed)
    advance=1.0; spacing=.22; raw_width=len(word)*advance+(len(word)-1)*spacing
    # The irregular scroll narrows at its curled ends; 1.01 is its safe diagonal
    # chord after the required card margin, and ``fill`` occupies that chord.
    target_width=1.01*float(fill)*size_px; unit=target_width/raw_width; glyph_height=.38*size_px
    x0=-target_width/2; polygons=[]
    for index,char in enumerate(word):
        letter_scale=float(rng.uniform(.965,1.035)); letter_angle=float(rng.uniform(-2.2,2.2))
        origin=np.array((x0+(index*(advance+spacing)+.5)*unit,float(rng.uniform(-.018,.018))*size_px))
        local_angle=math.radians(letter_angle); local_rot=np.array(((math.cos(local_angle),-math.sin(local_angle)),(math.sin(local_angle),math.cos(local_angle))))
        for raw in PAGE_GLYPHS[char]:
            role=raw[-1]; pts=np.asarray(raw[:-1],float)
            pts[:,0]=(pts[:,0]-.5)*unit*.82*letter_scale
            pts[:,1]=pts[:,1]*glyph_height*letter_scale
            pts=pts@local_rot.T+origin
            ratio=LOOK["page"]["page_wedge_down"] if role=="down" else LOOK["page"]["page_wedge_thin"]
            width=ratio*glyph_height*letter_scale
            polygons.append(_knife_wedge(pts,width))
            polygons.append(_wedge_serif(pts[0],pts[1],width*.85))
            polygons.append(_wedge_serif(pts[-1],pts[-2],width*.72))
        if index==0:
            swash=np.asarray(((-.44,.22),(-.62,.37),(-.47,.52),(-.19,.45)),float)
            swash[:,0]=swash[:,0]*unit;swash[:,1]=swash[:,1]*glyph_height
            swash=swash@local_rot.T+origin
            polygons.append(_knife_wedge(swash,LOOK["page"]["page_wedge_thin"]*glyph_height))
    a=math.radians(float(angle)); rotation=np.array(((math.cos(a),-math.sin(a)),(math.sin(a),math.cos(a))))
    c=np.asarray(centre,float)
    return [_poly(np.asarray(poly)@rotation.T+c) for poly in polygons if len(poly)>=3]


def page_text_strokes(text, centre, size_px):
    """Compatibility entry point: PG7d strokes are closed knife-cut polygons."""
    return page_text_polygons(text,centre,size_px)


def page_narrowest_wedge_middle_px(size_px):
    """Smallest designed maximum width, before per-letter positive size jitter."""
    return LOOK["page"]["page_wedge_thin"]*.38*size_px*.965


def _page_font(size_px, text):
    """Largest font size whose rendered width fits page_text_width of the page; None if the font is missing."""
    path = LOOK["page"].get("page_font")
    if not path or not Path(path).is_file():
        return None
    target = LOOK["page"]["page_text_width"] * size_px
    lo, hi = 4, 2000
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ImageFont.truetype(path, mid).getlength(text) <= target:
            lo = mid
        else:
            hi = mid
    return ImageFont.truetype(path, lo)


def draw_page_text(draw, centre, size_px, text=None):
    """Cut the selected page name; default path is polygonal carved lettering."""
    text = text or LOOK["page"]["page_text"]
    font = _page_font(size_px, text)
    if font is not None:
        bold = max(1, round(LOOK["page"]["page_text_bold"] * size_px))
        box=max(16,int(math.ceil(size_px*2.0))); layer=Image.new("L",(box,box),0)
        ImageDraw.Draw(layer).text((box/2,box/2),text,font=font,fill=255,anchor="mm",stroke_width=bold,stroke_fill=255)
        layer=layer.rotate(-LOOK["page"]["page_text_angle_deg"],resample=Image.Resampling.BICUBIC,expand=False)
        draw.bitmap((round(centre[0]-box/2),round(centre[1]-box/2)),layer,fill=255)
        return
    for polygon in page_text_polygons(text,centre,size_px):
        draw.polygon(polygon,fill=255)


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


BUCKET_RIM_LIP_LOCAL = (-.61, -.43)
BUCKET_BASE_ORIGIN_LOCAL = (-.42, .49)


def bucket_stream_origin(centre, size, angle, local_origin=BUCKET_RIM_LIP_LOCAL):
    """Transform the mouth lip nearest the boy; the base is never a pour origin."""
    return transform((local_origin,), centre, size, angle)[0]


def bucket_origin_lip_distance(centre, size, angle, local_origin=BUCKET_RIM_LIP_LOCAL):
    origin=bucket_stream_origin(centre,size,angle,local_origin)
    lip=bucket_stream_origin(centre,size,angle,BUCKET_RIM_LIP_LOCAL)
    return float(np.linalg.norm(origin-lip))


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
        tip=bucket_stream_origin(centre,size,state["angle"])
        target=(LOOK["bucket"]["target_xy"][0]*px,(VISIBLE_BAND["top"]+LOOK["bucket"]["target_xy"][1])*px)
        _draw_bucket_water(water_layer,state,tip,target,size)
    elif name == "page":
        x,y,a,sx=state["motion"]; size=LOOK["page"]["size_boy_height"]*boy_h
        draw_prop(prop_layer, lib["page"], (x*px,y*px), size, a, sx, rod=False)
        if state["label"] and sx > .72:
            draw_page_text(ImageDraw.Draw(prop_layer),(x*px,y*px),size)
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
        if name=="page":
            draw_page_text(ImageDraw.Draw(im),(500,500),360)
            closeup=Image.new("L",(2000,2000),255);draw_prop(closeup,prop,(1000,1000),720,state=0)
            draw_page_text(ImageDraw.Draw(closeup),(1000,1000),720)
            closeup.save(root/"page_flat_closeup.png")
        im.save(root/(name+"_template.png")); thumbs.append((name,im.resize((280,280))))
        def d(poly): return "M"+" L".join("%.2f,%.2f"%(x,y) for x,y in transform(poly,(500,500),360))+" Z"
        outline=_turnip(0) if name=="turnip" else prop.outline
        path=d(outline)+" "+" ".join(d(c) for c in prop.cuts)
        text_svg=""
        if name=="page":
            chunks=[]
            font=_page_font(360, LOOK["page"]["page_text"])
            if font is not None:
                chunks.append('<text x="500" y="500" text-anchor="middle" dominant-baseline="middle" font-family="Gabriola" '
                              'font-size="%d" fill="#fff" stroke="#fff" stroke-width="%d">%s</text>' % (
                                  font.size, max(1, round(LOOK["page"]["page_text_bold"] * 360)),
                                  LOOK["page"]["page_text"]))
            for polygon in ([] if chunks else page_text_polygons(LOOK["page"]["page_text"],(500,500),360)):
                chunks.append('<polygon points="%s" fill="#fff"/>'%(" ".join("%.2f,%.2f"%p for p in polygon)))
            text_svg="".join(chunks)
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path fill="#000" fill-rule="evenodd" d="%s"/>%s</svg>'%(path,text_svg)
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
            {"tier":"measured","claim":"Frames were rendered, SDF-packed and read back offline.","evidence":"Tools/ShadowGobo/Puppets/props.py:606"},
            {"tier":"inferred","claim":"The proposed scale and staging need Gary's visual approval.","evidence":"Tools/ShadowGobo/Puppets/props.py:53"},
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
        if name=="page":
            page_size=relative_size*(VISIBLE_BAND["bottom"]-VISIBLE_BAND["top"])*manifest["atlas"]["inner_px"]
            min_width=min(min_width,page_narrowest_wedge_middle_px(page_size))
        add_manifest(atlas/"manifest.json",name,states,min_width)
        curtain_gif(atlas/"manifest.json",out/"curtain_preview_defocus025.gif")
        metrics[name]={"rendered_frames":len(states),"unique_cells":manifest["take"]["frames_packed"],"grid":"%dx%d"%(manifest["atlas"]["cols"],manifest["atlas"]["rows"]),"cell_px":manifest["atlas"]["cell_px"],"minimum_feature_width_px":round(min_width,3),"gif_bytes":(out/"curtain_preview_defocus025.gif").stat().st_size,"source_scale":source_scale,"frame_strip":"frame_strip_6.png"}
        if name=="page":
            metrics[name].update({"narrowest_wedge_middle_px":round(page_narrowest_wedge_middle_px(page_size),3),
                                  "page_size_boy_height":LOOK["page"]["size_boy_height"],
                                  "page_text_angle_deg":LOOK["page"]["page_text_angle_deg"],
                                  "page_text_diagonal_fill":LOOK["page"]["page_text_diagonal_fill"],
                                  "flat_closeup":"prop_templates/page_flat_closeup.png"})
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
    lines=["# PG7d carved page lettering report","","[measured] The table is read from the offline APPLY output; each demo uses the current 0.5625 Puss framing and knee crop imported from `build_boy_puss_composite.py`. `Tools/ShadowGobo/Puppets/props.py:640`","","| Demo | Frames | Unique cells | Grid | Min feature | GIF |","|---|---:|---:|---:|---:|---:|"]
    for n,m in metrics.items(): lines.append("| %s | %d | %d | %s | %.2f px | %.2f MB |"%(n,m["rendered_frames"],m["unique_cells"],m["grid"],m["minimum_feature_width_px"],m["gif_bytes"]/1048576))
    bucket=metrics.get("bucket",{}).get("pour_visibility",{})
    page=metrics.get("page",{})
    lines += ["","[measured] The page demo has `curtain_preview_defocus025.gif` and `frame_strip_6.png`; its atlas is SDF 8192 and the preview uses BlurUV 0. `Tools/ShadowGobo/Puppets/prop_demos/clip_prop_page/atlas/manifest.json:14` `Tools/ShadowGobo/Puppets/prop_demos/clip_prop_page/atlas/manifest.json:49`",
              "[measured] Carved page: angle %s degrees, diagonal fill %s, narrowest wedge middle %.3f px, page size %.2f boy height. `Tools/ShadowGobo/Puppets/props.py:294`"%(page.get("page_text_angle_deg","n/a"),page.get("page_text_diagonal_fill","n/a"),page.get("narrowest_wedge_middle_px",float("nan")),page.get("page_size_boy_height",float("nan"))),
              "[declaration-proven] The default `page_font` is None; the generated page SVG therefore uses closed polygons rather than a font reference. `Tools/ShadowGobo/Puppets/props.py:55`",
              "[measured] The offline controls verify separate cut-outs, the requested principal-axis angle, a six-unit card margin, no font open, and all earlier prop checks. `Tools/ShadowGobo/Puppets/test_props_offline.py:45`",
              "[inferred] Gary should visually approve the larger page scale (0.28 to 0.34 boy height), carved treatment, and spelling `Cagliuso`. `Tools/ShadowGobo/Puppets/props.py:53`"]
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
