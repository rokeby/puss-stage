#!/usr/bin/env python3
"""Offline P21B Scene 3 clustered-crowd planner and review previews.

Inputs are read only from --source-root (normally E:/PussStage). APPLY writes
the plan and three PNGs in --project-root after recording a backup. REVERT
restores the backup or parks newly-created outputs; it never permanently deletes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import os
import random
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

FPS = 24
SCENE_TO_CLAMS = 22
TARGET_COUNT = 20
TARGET_PERIOD_S = 3.6
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
CLAM_LOCAL = (4562.427, 169.5)
MILLSTONE_LOCAL = (2995.03, 0.0)
EXCLUSION_RADIUS_CM = {"clam": 360.0, "millstone": 260.0, "camera": 185.0}

FIGURES = [
    {"id": "Shore01_M56", "actor": "Shore01_M56 Clam", "animation": "AS_Shore01_M56_shoreguy1_Full",
     "hero_xy": (3649.13, -212.98), "calm": (5.7083, 12.0833)},
    {"id": "Shore02_F52", "actor": "Shore02_F52 Clam", "animation": "AS_Shore02_F52_shoreguy12_Full",
     "hero_xy": (3199.30, 109.45), "calm": (4.3750, 13.2083)},
    {"id": "Shore03_M59", "actor": "Shore03_M59 Clam", "animation": "AS_Shore03_M59_shoreguy3_Full",
     "hero_xy": (3390.55, 300.70), "calm": (1.1667, 19.1250)},
    {"id": "Shore04_F55", "actor": "Shore04_F55 Clam", "animation": "AS_Shore04_F55_shoreguy4_Full",
     "hero_xy": (3683.54, 262.13), "calm": (71.7083, 89.5417), "rhythmic": True},
    {"id": "Shore06_F25", "actor": "Shore06_F25 Clam", "animation": "AS_Shore06_F25_shoreguy6_Full",
     "hero_xy": (3760.0, 0.0), "calm": (78.1667, 91.4583), "rhythmic": True},
]

CAMERAS = [
    {"label": "S3 Shot B02", "xy": (2700.0, -250.0)},
    {"label": "S3 Shot B03", "xy": (3050.0, 40.0)},
    {"label": "S3 Shot B04", "xy": (3500.0, -750.0)},
    {"label": "S3 Shot B05", "xy": (3200.0, 0.0)},
    {"label": "S3 Shot B06", "xy": (3380.0, 0.0)},
    {"label": "S3 Shot B07", "xy": (3300.0, 60.0)},
    {"label": "S3 Shot B08", "xy": (3360.0, -40.0)},
    {"label": "S3 Shot B09/B10", "xy": (2600.0, 0.0)},
]

CLUSTER_SPECS = [
    {"id": "A", "centre_local_xy_cm": [4000.0, -500.0], "size": 5,
     "phase_base_deg": 0.0,
     "offsets_cm": [(-110, -60), (0, -60), (110, -60), (-55, 60), (55, 60)]},
    {"id": "B", "centre_local_xy_cm": [3600.0, 700.0], "size": 7,
     "phase_base_deg": 90.0,
     "offsets_cm": [(-120, -110), (0, -110), (120, -110), (-120, 0),
                    (0, 0), (120, 0), (0, 110)]},
    {"id": "C", "centre_local_xy_cm": [2500.0, 550.0], "size": 8,
     "phase_base_deg": 180.0,
     "offsets_cm": [(-120, -120), (0, -120), (120, -120), (-120, 0),
                    (0, 0), (120, 0), (-60, 120), (60, 120)]},
]

# Ranges below are root Scene frames. The 8 Oct live census was reported in
# LS_Clams frames; subtract SCENE_TO_CLAMS (22) to compare with root cuts.
LIVE_CUTS_LS_CLAMS = {
    "S3 Shot B03": [420, 860],
    "S3 Shot B02": [856, 1733],
    "S3 Shot B07": [1540, 2828],
    "S3 Shot B06": [2820, 4548],
    "S3 Shot B08": [4538, 4858],
}
EXPECTED_LIVE_CUTS = {
    label: [a - SCENE_TO_CLAMS, b - SCENE_TO_CLAMS]
    for label, (a, b) in LIVE_CUTS_LS_CLAMS.items()
}

SHOT_PLAN = [
    {"label": "S3 Crowd Establishing", "range": [360, 552], "lens_mm": 35.0,
     "location_local": [2250.0, -960.0, 360.0], "look_local": [3350.0, 0.0, 95.0],
     "purpose": "wide establishing; replaces the active cut in this interval"},
    {"label": "S3 Choir Cluster Wide", "range": [2806, 3360], "lens_mm": 35.0,
     "location_local": [2500.0, 1050.0, 180.0], "look_local": [3600.0, 700.0, 105.0],
     "purpose": "cluster wide bridges the live B07 end and carries into chorus at 3072"},
    {"label": "S3 Choir Close A", "range": [3360, 3720], "lens_mm": 50.0,
     "location_local": [4300.0, 1000.0, 165.0], "look_local": [3600.0, 700.0, 105.0],
     "purpose": "50 mm group close-up of 3-4 singers in cluster B"},
    {"label": "S3 Choir Close B", "range": [3720, 4166], "lens_mm": 50.0,
     "location_local": [4500.0, -950.0, 165.0], "look_local": [4000.0, -500.0, 105.0],
     "purpose": "50 mm group close-up of 3-4 singers in cluster A before B06 tail"},
]


class PlanError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def outputs(root: Path) -> dict[str, Path]:
    return {
        "plan": root / "Saved/CodexConductor/s3_crowd_structure_plan.json",
        "placement": root / "Docs/Conductor/Previews/P21_S3_CROWD_PLACEMENT_preview.png",
        "timeline": root / "Docs/Conductor/Previews/P21_S3_CROWD_TIMELINE_preview.png",
        "shots": root / "Docs/Conductor/Previews/P21_S3_CROWD_SHOTS_preview.png",
    }


def longest_segment(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    hits = [r for r in rows if r["class"] == kind]
    if not hits:
        raise PlanError(f"NO_{kind}_SEGMENT")
    return dict(max(hits, key=lambda r: float(r["source_out_seconds"]) - float(r["source_in_seconds"])))


def sway_row(sway: dict[str, Any], figure: dict[str, Any]) -> dict[str, Any]:
    src = next((r for r in sway["figures"] if r["id"] == figure["id"]), None)
    if src is None:
        raise PlanError("SWAY_FIGURE_MISSING|" + figure["id"])
    a, b = figure["calm"]
    hits = [r for r in src["calm_runs"] if abs(float(r["source_in"]) - a) < 0.06 and
            abs(float(r["source_out"]) - b) < 0.06]
    if len(hits) != 1 or "period_s_source" not in hits[0]:
        raise PlanError("SWAY_SPAN_MISSING|" + figure["id"])
    row = dict(hits[0])
    row["source_in"], row["source_out"] = a, b
    row["play_rate"] = float(row["period_s_source"]) / TARGET_PERIOD_S
    if not 0.45 <= row["play_rate"] <= 0.78:
        raise PlanError("SWAY_RATE_OUT_OF_RANGE|" + figure["id"])
    return row


def point_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def placement_violations(xy: tuple[float, float]) -> list[str]:
    bad = []
    if point_distance(xy, CLAM_LOCAL) < EXCLUSION_RADIUS_CM["clam"]:
        bad.append("clam")
    if point_distance(xy, MILLSTONE_LOCAL) < EXCLUSION_RADIUS_CM["millstone"]:
        bad.append("millstone")
    for cam in CAMERAS:
        if point_distance(xy, cam["xy"]) < EXCLUSION_RADIUS_CM["camera"]:
            bad.append("camera:" + cam["label"])
    for cam in SHOT_PLAN:
        new_xy = tuple(cam["location_local"][:2])
        if point_distance(xy, new_xy) < EXCLUSION_RADIUS_CM["camera"]:
            bad.append("new_camera:" + cam["label"])
    return bad


def build_cluster_layout(seed: int, count: int = TARGET_COUNT) -> list[dict[str, Any]]:
    if count != TARGET_COUNT or sum(c["size"] for c in CLUSTER_SPECS) != TARGET_COUNT:
        raise PlanError("TARGET_COUNT_MUST_BE_20")
    rng = random.Random(seed)
    pool = ["Shore06_F25", "Shore04_F55", "Shore06_F25", "Shore04_F55",
            "Shore06_F25", "Shore04_F55", "Shore01_M56", "Shore02_F52", "Shore03_M59"]
    rows, existing_index, duplicate_index = [], 0, 0
    for cluster in CLUSTER_SPECS:
        if len(cluster["offsets_cm"]) != cluster["size"]:
            raise PlanError("CLUSTER_OFFSET_COUNT|" + cluster["id"])
        for cluster_index, (ox, oy) in enumerate(cluster["offsets_cm"]):
            # Four fixed draws per member make the seed stable across future source-pool edits.
            jx = (rng.random() * 2.0 - 1.0) * 5.0
            jy = (rng.random() * 2.0 - 1.0) * 5.0
            yaw_jitter = (rng.random() * 2.0 - 1.0) * 4.0
            source_draw = rng.random()
            cx, cy = cluster["centre_local_xy_cm"]
            xy = (round(cx + ox + jx, 3), round(cy + oy + jy, 3))
            if cluster["id"] == "A":
                figure = FIGURES[existing_index]; existing_index += 1
                source, role, label = figure["id"], "existing", figure["actor"]
            else:
                duplicate_index += 1
                source = pool[min(int(source_draw * len(pool)), len(pool) - 1)]
                role, label = "duplicate", "S3 Crowd %02d (from %s)" % (duplicate_index, source)
            aim_yaw = math.degrees(math.atan2(CLAM_LOCAL[1] - xy[1], CLAM_LOCAL[0] - xy[0]))
            phase = (float(cluster["phase_base_deg"]) +
                     (cluster_index - (cluster["size"] - 1) / 2.0) * 8.0) % 360.0
            violations = placement_violations(xy)
            if violations:
                raise PlanError("PLACEMENT_EXCLUSION|cluster=%s|slot=%d|%s" %
                                (cluster["id"], cluster_index + 1, ",".join(violations)))
            rows.append({"index": len(rows) + 1, "role": role, "label": label,
                         "source_id": source, "local_xy_cm": list(xy),
                         "yaw_deg": round(aim_yaw + yaw_jitter, 3), "phase_deg": round(phase, 3),
                         "cluster_id": cluster["id"], "cluster_index": cluster_index + 1,
                         "tag": "P21.S3Crowd", "random_draws": 4})
    return rows


def build_placements(seed: int, count: int = TARGET_COUNT) -> list[dict[str, Any]]:
    return [dict(row) for row in build_cluster_layout(seed, count) if row["role"] == "duplicate"]


def nearest_cluster_spacing(rows: list[dict[str, Any]], member: dict[str, Any]) -> float:
    peers = [r for r in rows if r["cluster_id"] == member["cluster_id"] and r is not member]
    return min(point_distance(tuple(member["local_xy_cm"]), tuple(r["local_xy_cm"])) for r in peers)


def timeline(index: int) -> list[dict[str, Any]]:
    onset = 552 + (index % 10) * 18 + (index // 10) * 9
    frenzy = onset + 120
    soothe = 2160 + (index % 8) * 12
    calm = soothe + 288
    return [
        {"class": "CALM", "range": [360, onset]},
        {"class": "MEDIUM", "range": [onset, frenzy]},
        {"class": "FRENZY", "range": [frenzy, soothe]},
        {"class": "MEDIUM", "range": [soothe, calm]},
        {"class": "CALM", "range": [calm, 4488]},
        {"class": "ORIGINAL", "range": [4488, 6240]},
    ]


def look_rotation(location: list[float], target: list[float]) -> list[float]:
    dx, dy, dz = (target[i] - location[i] for i in range(3))
    return [0.0, round(math.degrees(math.atan2(dz, math.hypot(dx, dy))), 4),
            round(math.degrees(math.atan2(dy, dx)), 4)]


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.source_root).resolve()
    seg_path = source / "DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json"
    sway_path = source / "DerivedAssets/S3MocapIntensity/s3_sway_runs.json"
    if not seg_path.is_file() or not sway_path.is_file():
        raise PlanError("ABSOLUTE_INPUT_MISSING")
    segments = json.loads(seg_path.read_text(encoding="utf-8"))
    sway = json.loads(sway_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in segments["figures"]}
    sources = {}
    for figure in FIGURES:
        row = by_id.get(figure["id"])
        if row is None:
            raise PlanError("SEGMENT_FIGURE_MISSING|" + figure["id"])
        sources[figure["id"]] = {
            **figure,
            "calm_span": sway_row(sway, figure),
            "medium_span": longest_segment(row["segments"], "MEDIUM"),
            "frenzy_span": longest_segment(row["segments"], "FRENZY"),
            "source_fbx": row["source_path"], "source_fbx_sha256": row["source_sha256"],
        }
    layout = build_cluster_layout(args.seed, args.target_count)
    placements = [dict(row) for row in layout if row["role"] == "duplicate"]
    members = []
    for i, row in enumerate(layout):
        source_id, phase = row["source_id"], row["phase_deg"]
        bands = timeline(i)
        choir_calm = next(row["range"][0] for row in bands if row["class"]=="CALM" and row["range"][0]>2160)
        members.append({**row, "timeline": bands,
                        "transform_sway": {"roll_degrees": args.roll_degrees,
                                           "period_seconds": args.target_period,
                                           "phase_deg": phase,
                                           "windows": [[360, 552], [choir_calm, 4488]]}})
    shots = []
    for row in SHOT_PLAN:
        camera = dict(row)
        camera["rotation_rpy_deg"] = look_rotation(camera["location_local"], camera["look_local"])
        shots.append(camera)
    return {
        "schema": "p21b_s3_crowd_replan/1", "run": args.run,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "evidence_tier": "measured source JSON; inferred staging defaults pending DRY and rendered acceptance",
        "fps": FPS, "scene_to_ls_clams_frames": SCENE_TO_CLAMS,
        "world": "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
        "root_sequence": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03",
        "figure_sequence": "/Game/Scenes/LS_Clams",
        "target_count": args.target_count, "seed": args.seed, "target_period_s": args.target_period,
        "roll_degrees": args.roll_degrees, "dock_origin_world_cm": list(DOCK_ORIGIN),
        "inputs": {"segments": seg_path.as_posix(), "segments_sha256": sha256_file(seg_path),
                   "sway": sway_path.as_posix(), "sway_sha256": sha256_file(sway_path)},
        "exclusions": {"clam_local_xy_cm": list(CLAM_LOCAL), "millstone_local_xy_cm": list(MILLSTONE_LOCAL),
                       "radii_cm": EXCLUSION_RADIUS_CM, "camera_points": CAMERAS},
        "sources": sources, "clusters": CLUSTER_SPECS,
        "duplicate_placements": placements, "members": members,
        "shots": shots, "handprint_trim": {"camera": "S3 Shot B06",
                                            "expected_before": EXPECTED_LIVE_CUTS["S3 Shot B06"],
                                            "after": [4166, EXPECTED_LIVE_CUTS["S3 Shot B06"][1]],
                                            "duration_frames": 360,
                                            "original_end_frame": EXPECTED_LIVE_CUTS["S3 Shot B06"][1]},
        "expected_live_cuts": EXPECTED_LIVE_CUTS,
        "cut_policy": {"nested_cuts_must_be_inactive": True, "root_playback": [0, 6240],
                       "live_scene_offset_frames": SCENE_TO_CLAMS,
                       "chorus_start": 3072, "b03_starts_after_establishing": 552},
        "performance_gate": {"baseline_required_before_apply": True, "baseline_expected_visible": 5,
                             "windows": {"establishing": [360, 552], "choir": [2160, 4488]},
                             "gpu_timeout_token": "GPU timeout"},
    }


def validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema") != "p21b_s3_crowd_replan/1" or len(plan.get("members", [])) != plan.get("target_count"):
        raise PlanError("PLAN_SCHEMA_OR_COUNT")
    labels = [m["label"] for m in plan["members"]]
    if len(labels) != len(set(labels)):
        raise PlanError("DUPLICATE_MEMBER_LABEL")
    if sum(m["role"] == "existing" for m in plan["members"]) != 5 or len(plan["duplicate_placements"]) != 15:
        raise PlanError("FIVE_PLUS_FIFTEEN_REQUIRED")
    if not 2 <= len(plan["clusters"]) <= 3 or any(not 5 <= c["size"] <= 8 for c in plan["clusters"]):
        raise PlanError("CLUSTER_COUNT_OR_SIZE")
    if any(placement_violations(tuple(m["local_xy_cm"])) for m in plan["members"]):
        raise PlanError("PLACEMENT_EXCLUSION")
    if any(placement_violations(tuple(c["centre_local_xy_cm"])) for c in plan["clusters"]):
        raise PlanError("CLUSTER_CENTRE_EXCLUSION")
    if any(not 80.0 <= nearest_cluster_spacing(plan["members"], m) <= 150.0 for m in plan["members"]):
        raise PlanError("CLUSTER_SPACING_OUT_OF_RANGE")
    phases = [float(c["phase_base_deg"]) for c in plan["clusters"]]
    if any(abs(((b-a) % 360.0) - 90.0) > 1e-6 for a, b in zip(phases, phases[1:])):
        raise PlanError("CLUSTER_PHASE_OFFSET")
    handprint = plan["handprint_trim"]
    if handprint["after"][1] - handprint["after"][0] != 360:
        raise PlanError("HANDPRINT_NOT_FIFTEEN_SECONDS")
    if handprint["after"][1] != handprint["expected_before"][1]:
        raise PlanError("HANDPRINT_FINAL_GLINT_MOVED")
    if plan["shots"][0]["range"] != [360, 552] or plan["shots"][1]["range"][0] != EXPECTED_LIVE_CUTS["S3 Shot B07"][1]:
        raise PlanError("SHOT_LAYOUT_NOT_LIVE_ALIGNED")


def canvas(width: int, height: int, title: str, subtitle: str):
    im = Image.new("RGB", (width, height), "#11161d")
    d = ImageDraw.Draw(im); font = ImageFont.load_default()
    d.text((28, 22), title, fill="#f3f6fa", font=font)
    d.text((28, 45), subtitle, fill="#aeb9c7", font=font)
    return im, d, font


def png_bytes(im: Image.Image) -> bytes:
    b = io.BytesIO(); im.save(b, "PNG", optimize=True); return b.getvalue()


def render_placement(plan: dict[str, Any]) -> bytes:
    im, d, font = canvas(1600, 980, "P21B - S3 clustered crowd placement (offline plan)",
                         "20 total in clusters 5/7/8 | local cm | protected set pieces and camera points")
    left, top, w, h = 120, 100, 1380, 790
    xmin, xmax, ymin, ymax = 2100, 4850, -1100, 1100
    sx=lambda x: left+(x-xmin)/(xmax-xmin)*w; sy=lambda y: top+(ymax-y)/(ymax-ymin)*h
    d.rectangle((left, top, left+w, top+h), outline="#405064", fill="#18212b")
    for name, xy, radius, color in (("clam", CLAM_LOCAL, EXCLUSION_RADIUS_CM["clam"], "#bc6e50"),
                                     ("millstone", MILLSTONE_LOCAL, EXCLUSION_RADIUS_CM["millstone"], "#9a7b55")):
        rx=radius/(xmax-xmin)*w; ry=radius/(ymax-ymin)*h; x,y=sx(xy[0]),sy(xy[1])
        d.ellipse((x-rx,y-ry,x+rx,y+ry),outline=color,width=3); d.text((x+6,y+6),name,fill=color,font=font)
    for cam in CAMERAS:
        x,y=sx(cam["xy"][0]),sy(cam["xy"][1]); r=EXCLUSION_RADIUS_CM["camera"]/(xmax-xmin)*w
        d.ellipse((x-r,y-r,x+r,y+r),outline="#527aa3"); d.text((x+4,y+4),cam["label"],fill="#7da8d4",font=font)
    cluster_colors={"A":"#f0c36a","B":"#72d6c4","C":"#8fa8ef"}
    for cluster in plan["clusters"]:
        x,y=sx(cluster["centre_local_xy_cm"][0]),sy(cluster["centre_local_xy_cm"][1])
        d.ellipse((x-18,y-18,x+18,y+18),outline=cluster_colors[cluster["id"]],width=2)
        d.text((x+20,y-17),"cluster %s | n=%d | phase %.0f deg"%
               (cluster["id"],cluster["size"],cluster["phase_base_deg"]),
               fill=cluster_colors[cluster["id"]],font=font)
    for member in plan["members"]:
        x,y=sx(member["local_xy_cm"][0]),sy(member["local_xy_cm"][1])
        color=cluster_colors[member["cluster_id"]]
        if member["role"]=="existing": d.rectangle((x-7,y-7,x+7,y+7),fill=color)
        else: d.ellipse((x-7,y-7,x+7,y+7),fill=color)
        d.text((x+9,y-6),str(member["index"]),fill=color,font=font)
    for shot in plan["shots"]:
        x,y=sx(shot["location_local"][0]),sy(shot["location_local"][1]); tx,ty=sx(shot["look_local"][0]),sy(shot["look_local"][1])
        d.polygon([(x-7,y+7),(x+7,y+7),(x,y-8)],fill="#e58fc8"); d.line((x,y,tx,ty),fill="#8e5d83",width=2)
        d.text((x+9,y-7),shot["label"],fill="#e58fc8",font=font)
    d.text((left,920),"squares = five retained actors; circles = 15 copies; colour = cluster; pink = proposed cameras",fill="#c6cfda",font=font)
    return png_bytes(im)


def render_timeline(plan: dict[str, Any]) -> bytes:
    im,d,font=canvas(1800,1280,"P21B - S3 clustered crowd timeline (offline plan)",
                     "phase ripples within clusters; cluster bases offset by one quarter-period")
    left,right,top,row_h=230,45,95,52; x0,x1=360,4488; pw=1800-left-right
    colors={"CALM":"#4db6ac","MEDIUM":"#d8a13d","FRENZY":"#d75a64","ORIGINAL":"#637083"}
    x=lambda f:left+(f-x0)/(x1-x0)*pw
    for i,m in enumerate(plan["members"]):
        y=top+i*row_h; d.text((22,y+12),"%02d [%s] %s"%(m["index"],m["cluster_id"],m["source_id"]),fill="#dce4ed",font=font)
        for band in m["timeline"]:
            a,b=band["range"]
            if b<=x0 or a>=x1: continue
            d.rectangle((x(max(a,x0)),y,x(min(b,x1)),y+32),fill=colors[band["class"]])
        phase=m["phase_deg"]/360.0*plan["target_period_s"]*FPS
        for f in range(360,553,round(plan["target_period_s"]*FPS)):
            xx=x(min(552,f+phase)); d.line((xx,y,xx,y+32),fill="#dffcf6")
    for f,label in ((360,"0:15"),(552,"0:23"),(1080,"0:45"),(2160,"1:30"),(3000,"2:05"),(3480,"2:25"),(4488,"3:07")):
        xx=x(f); d.line((xx,top-12,xx,top+20*row_h),fill="#62758b",width=2); d.text((xx+3,top-28),label,fill="#b8c4d2",font=font)
    return png_bytes(im)


def render_shots(plan: dict[str, Any]) -> bytes:
    im,d,font=canvas(1800,720,"P21B - S3 shot plan over audio beats",
                     "live cut layout -22f | crowd wide/close-ups first, then final 15 s of B06")
    left,right,top,pw=100,50,125,1650; x=lambda f:left+f/6240*pw
    beats=[(0,"arrival"),(360,"sway"),(552,"frenzy"),(1080,"clam"),(1440,"cello"),(2160,"soothe"),(2880,"choir"),(4488,"crying")]
    for f,name in beats:
        xx=x(f); d.line((xx,top-35,xx,620),fill="#35475a"); d.text((xx+4,top-55),name,fill="#aebbc9",font=font)
    b07=plan["expected_live_cuts"]["S3 Shot B07"]
    b06=plan["handprint_trim"]["after"]
    d.rectangle((x(b07[0]),top,x(b07[1]),top+55),fill="#3c5670"); d.text((x(b07[0])+8,top+18),"live B07 orbit",fill="#edf4fb",font=font)
    d.rectangle((x(b06[0]),top+85,x(b06[1]),top+140),fill="#8d6440"); d.text((x(b06[0])+5,top+103),"B06 final 15 s -> original glint",fill="#fff0d8",font=font)
    for i,s in enumerate(plan["shots"]):
        y=top+180+i*78; a,b=s["range"]
        d.rectangle((x(a),y,x(b),y+42),fill="#b65b9c")
        d.text((x(a)+5,y+13),"%s | %.0f mm"%(s["label"],s["lens_mm"]),fill="#fff4fc",font=font)
    d.text((left,650),"Wide bridges the B07 seam and chorus start at 2:08; two 50 mm group close-ups lead into B06.",fill="#d6dce5",font=font)
    return png_bytes(im)


def make_backup(root: Path, run: str, out: dict[str, Path]) -> Path:
    backup=root/f"Backups/PreS3CrowdPlan-{run}"
    if backup.exists(): raise PlanError("BACKUP_EXISTS|"+str(backup))
    backup.mkdir(parents=True)
    manifest={"run":run,"outputs":[]}
    for key,path in out.items():
        row={"key":key,"target":path.relative_to(root).as_posix(),"existed":path.is_file()}
        if path.is_file():
            dst=backup/row["target"]; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dst)
            row.update({"backup_file":dst.relative_to(root).as_posix(),"sha256_before":sha256_file(path)})
        manifest["outputs"].append(row)
    atomic_write(backup/"backup_manifest.json",(json.dumps(manifest,indent=2)+"\n").encode())
    return backup


def apply(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    if args.confirm != "APPLY S3CROWDPLAN": raise PlanError("CONFIRM_REQUIRED|APPLY S3CROWDPLAN")
    root=Path(args.project_root).resolve(); out=outputs(root); backup=make_backup(root,args.run,out)
    data={"plan":(json.dumps(plan,indent=2)+"\n").encode(),"placement":render_placement(plan),
          "timeline":render_timeline(plan),"shots":render_shots(plan)}
    for key,value in data.items(): atomic_write(out[key],value)
    print("S3_CROWD_PLAN_APPLY_OK|run=%s|backup=%s|outputs=%d|target=%d"%(args.run,backup, len(out),plan["target_count"]))


def revert(args: argparse.Namespace) -> None:
    if args.confirm != "REVERT S3CROWDPLAN": raise PlanError("CONFIRM_REQUIRED|REVERT S3CROWDPLAN")
    root=Path(args.project_root).resolve(); backup=root/f"Backups/PreS3CrowdPlan-{args.revert_run or args.run}"
    manifest=json.loads((backup/"backup_manifest.json").read_text())
    park=root/f"Backups/PreS3CrowdPlanRevert-{args.run}"; park.mkdir(parents=True,exist_ok=False)
    for row in manifest["outputs"]:
        target=root/row["target"]
        if target.exists():
            dst=park/row["target"]; dst.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(target),str(dst))
        if row["existed"]:
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(root/row["backup_file"],target)
    print("S3_CROWD_PLAN_REVERT_OK|run=%s|source_backup=%s|parked=%s"%(args.run,backup,park))


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(); p.add_argument("--mode",choices=("DRY","APPLY","REVERT"),default="DRY")
    p.add_argument("--run",required=True); p.add_argument("--confirm",default="")
    p.add_argument("--source-root",default="E:/PussStage"); p.add_argument("--project-root",default=str(Path(__file__).resolve().parents[2]))
    p.add_argument("--target-count",type=int,default=20); p.add_argument("--seed",type=int,default=2103)
    p.add_argument("--target-period",type=float,default=3.6); p.add_argument("--roll-degrees",type=float,default=2.5)
    p.add_argument("--revert-run",default=""); return p


def main() -> int:
    args=parser().parse_args()
    if args.mode=="REVERT": revert(args); return 0
    plan=build_plan(args); validate_plan(plan)
    if args.mode=="DRY":
        print("S3_CROWD_PLAN_DRY_OK|run=%s|target=%d|duplicates=%d|shots=%d|writes=0"%(args.run,plan["target_count"],len(plan["duplicate_placements"]),len(plan["shots"])))
    else: apply(args,plan)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
