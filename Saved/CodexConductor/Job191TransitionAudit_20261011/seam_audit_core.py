"""Pure planning, image analysis and HTML helpers for Job 191 seam audit."""

from __future__ import annotations

import html
import json
import math
import pathlib
import re
import struct
import zlib


RUN_RE = re.compile(r"^J191-SEAMS-[A-Z0-9][A-Z0-9_-]{2,63}$")
SAMPLE_SPECS = (
    ("minus_1s", -1.0, "seam - 1 s"),
    ("minus_1f", None, "seam - 1 frame"),
    ("plus_1f", None, "seam + 1 frame"),
    ("plus_1s", 1.0, "seam + 1 s"),
)


def validate_args(args):
    run = str(args.get("run", ""))
    if not RUN_RE.fullmatch(run):
        raise ValueError("run must match %s" % RUN_RE.pattern)
    if args.get("confirm") != "CONFIRM_JOB191_SEAM_AUDIT":
        raise ValueError("confirm must be CONFIRM_JOB191_SEAM_AUDIT")
    resolution = args.get("resolution", [1280, 720])
    if (not isinstance(resolution, list) or len(resolution) != 2 or
            any(isinstance(v, bool) or int(v) < 64 or int(v) > 4096 for v in resolution)):
        raise ValueError("resolution must be [width,height] in [64,4096]")
    thresholds = {
        "position_cm": float(args.get("position_jump_cm", 25.0)),
        "rotation_deg": float(args.get("rotation_jump_deg", 2.0)),
        "luma_abs": float(args.get("luma_pop_abs", 32.0)),
        "luma_ratio": float(args.get("luma_pop_ratio", 0.40)),
        "black": float(args.get("black_mean_luma", 5.0)),
        "white": float(args.get("white_mean_luma", 250.0)),
    }
    if any(not math.isfinite(v) or v < 0 for v in thresholds.values()):
        raise ValueError("thresholds must be finite and non-negative")
    return run, [int(resolution[0]), int(resolution[1])], thresholds


def segment_kind(label):
    text = str(label)
    if text.startswith("Passage "):
        return "passage"
    if text.startswith("Scene "):
        return "scene"
    if text.startswith("Interaction "):
        return "interaction"
    if text.startswith("Opening"):
        return "opening"
    if text.startswith("Closing"):
        return "closing"
    return "other"


def plan_seams(segments, ticks_per_second=24000, display_fps=24):
    ordered = sorted((dict(row) for row in segments), key=lambda row: (int(row["start"]), int(row["end"])))
    frame_ticks = int(round(float(ticks_per_second) / float(display_fps)))
    seams = []
    for index in range(len(ordered) - 1):
        left, right = ordered[index], ordered[index + 1]
        if int(left["end"]) != int(right["start"]):
            raise ValueError("non-contiguous Master segments %r -> %r" % (left["label"], right["label"]))
        if segment_kind(left["label"]) == "passage" and segment_kind(right["label"]) == "scene":
            seams.append({"kind": "passage_to_scene", "boundary": int(left["end"]),
                          "from": left["label"], "to": right["label"], "master_indices": [index, index + 1]})
    for index, interaction in enumerate(ordered):
        if segment_kind(interaction["label"]) != "interaction":
            continue
        if index == 0 or index + 1 >= len(ordered):
            raise ValueError("interaction is not bracketed in Master order: %s" % interaction["label"])
        before, immediate_after = ordered[index - 1], ordered[index + 1]
        after = None
        for candidate in ordered[index + 1:]:
            kind = segment_kind(candidate["label"])
            if kind == "passage":
                after = candidate
                break
            if kind != "other":
                raise ValueError("interaction is not Scene -> Interaction -> optional other -> Passage: %s" %
                                 interaction["label"])
        if segment_kind(before["label"]) != "scene" or after is None:
            raise ValueError("interaction is not Scene -> Interaction -> optional other -> Passage: %s" %
                             interaction["label"])
        seams.append({"kind": "scene_to_passage_interaction_start", "boundary": int(interaction["start"]),
                      "from": before["label"], "to": interaction["label"], "logical_to": after["label"],
                      "interaction": interaction["label"], "master_indices": [index - 1, index]})
        seams.append({"kind": "scene_to_passage_interaction_end", "boundary": int(interaction["end"]),
                      "from": interaction["label"], "logical_from": before["label"],
                      "to": immediate_after["label"], "logical_to": after["label"],
                      "interaction": interaction["label"], "master_indices": [index, index + 1]})
    seams.sort(key=lambda row: (row["boundary"], row["kind"]))
    for order, seam in enumerate(seams, start=1):
        seam["order"] = order
        seam["id"] = "%02d_%s" % (order, seam["kind"])
        offsets = (-ticks_per_second, -frame_ticks, frame_ticks, ticks_per_second)
        seam["samples"] = [{"key": spec[0], "label": spec[2], "target_frame": seam["boundary"] + offset}
                           for spec, offset in zip(SAMPLE_SPECS, offsets)]
    counts = {
        "passage_to_scene": sum(row["kind"] == "passage_to_scene" for row in seams),
        "interaction_start": sum(row["kind"].endswith("interaction_start") for row in seams),
        "interaction_end": sum(row["kind"].endswith("interaction_end") for row in seams),
    }
    if counts != {"passage_to_scene": 6, "interaction_start": 5, "interaction_end": 5}:
        raise ValueError("expected 6 P->S and 5 Interaction start/end seams, got %r" % counts)
    return {"segments": ordered, "seams": seams, "counts": counts, "ticks_per_second": ticks_per_second,
            "display_fps": display_fps, "display_frame_ticks": frame_ticks}


def distance_cm(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def angle_delta(a, b):
    return abs((float(b) - float(a) + 180.0) % 360.0 - 180.0)


def rotation_delta_deg(a, b):
    return math.sqrt(sum(angle_delta(a[name], b[name]) ** 2 for name in ("pitch", "yaw", "roll")))


def analyze_seam(seam, thresholds):
    samples = seam["samples"]
    if len(samples) != 4 or any("mean_luminance" not in row or "camera" not in row for row in samples):
        raise ValueError("seam is not fully captured: %s" % seam.get("id"))
    before, after = samples[1], samples[2]
    position = distance_cm(before["camera"]["location"], after["camera"]["location"])
    rotation = rotation_delta_deg(before["camera"]["rotation"], after["camera"]["rotation"])
    luma_before, luma_after = float(before["mean_luminance"]), float(after["mean_luminance"])
    luma_abs = abs(luma_after - luma_before)
    luma_ratio = luma_abs / max(1.0, abs(luma_before))
    flags = []
    if position > thresholds["position_cm"]:
        flags.append("camera_position_jump")
    if rotation > thresholds["rotation_deg"]:
        flags.append("camera_rotation_jump")
    if luma_abs > thresholds["luma_abs"] and luma_ratio > thresholds["luma_ratio"]:
        flags.append("luminance_pop")
    for sample in samples:
        value = float(sample["mean_luminance"])
        if value <= thresholds["black"]:
            flags.append("black_frame:" + sample["key"])
        if value >= thresholds["white"]:
            flags.append("white_frame:" + sample["key"])
    return {
        "across_boundary": {"position_cm": position, "rotation_deg": rotation,
                            "luminance_abs": luma_abs, "luminance_ratio": luma_ratio,
                            "view_target_changed": before.get("view_target", {}).get("path") != after.get("view_target", {}).get("path")},
        "flags": flags,
        "flagged": bool(flags),
    }


def png_mean_luminance(path):
    data = pathlib.Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: %s" % path)
    pos, idat, head, ended = 8, [], None, False
    while pos + 8 <= len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + size]
        if len(body) != size:
            raise ValueError("truncated PNG")
        pos += 12 + size
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            ended = True
            break
    if head is None or not ended:
        raise ValueError("incomplete PNG")
    width, height, depth, color_type, _compression, _filter, interlace = head
    if depth != 8 or interlace != 0 or color_type not in (0, 2, 4, 6):
        raise ValueError("unsupported PNG depth/type/interlace")
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    raw = zlib.decompress(b"".join(idat))
    stride = width * bpp
    previous = bytearray(stride)
    red = green = blue = 0
    for y in range(height):
        base = y * (stride + 1)
        filter_type = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if filter_type == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif filter_type == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, previous))
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 255
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = previous[i]
                c = previous[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                predictor = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + predictor) & 255
        elif filter_type != 0:
            raise ValueError("unsupported PNG filter")
        if color_type in (0, 4):
            value = sum(line[0::bpp])
            red, green, blue = red + value, green + value, blue + value
        else:
            red += sum(line[0::bpp])
            green += sum(line[1::bpp])
            blue += sum(line[2::bpp])
        previous = line
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / float(width * height)


def _fmt(value, digits=2):
    return ("%%.%df" % digits) % float(value)


def contact_sheet_html(seam, image_prefix="../../shots/"):
    analysis = seam["analysis"]
    cards = []
    for sample in seam["samples"]:
        camera, target = sample["camera"], sample["view_target"]
        cards.append("""<figure><img src="%s%s" alt="%s"><figcaption><b>%s</b><br>
frame %d (target %d)<br>view: %s<br>loc: %s<br>rot P/Y/R: %s<br>mean luma: %s</figcaption></figure>""" % (
            html.escape(image_prefix), html.escape(pathlib.Path(sample["path"]).name), html.escape(sample["label"]),
            html.escape(sample["label"]), int(sample["actual_frame"]), int(sample["target_frame"]),
            html.escape(target.get("label") or target.get("path") or "none"),
            ", ".join(_fmt(v) for v in camera["location"]),
            ", ".join(_fmt(camera["rotation"][name]) for name in ("pitch", "yaw", "roll")),
            _fmt(sample["mean_luminance"])))
    flags = ", ".join(analysis["flags"]) or "none"
    delta = analysis["across_boundary"]
    return """<!doctype html><meta charset="utf-8"><title>%s</title>
<style>body{font:15px system-ui;background:#151515;color:#eee;margin:24px}h1{font-size:22px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}figure{margin:0;background:#252525;padding:10px}img{width:100%%;height:auto}figcaption{line-height:1.45;margin-top:8px}.flag{color:#ffb36b}code{color:#9bd}</style>
<h1>%s</h1><p>%s &rarr; %s; Master boundary %d</p>
<p class="flag"><b>Flags:</b> %s</p><p>Across boundary (-1f to +1f): position %s cm; rotation %s deg; luminance %s (%s ratio); view target changed: %s.</p>
<div class="grid">%s</div>""" % (
        html.escape(seam["id"]), html.escape(seam["id"]), html.escape(seam["from"]), html.escape(seam["to"]),
        int(seam["boundary"]), html.escape(flags), _fmt(delta["position_cm"]), _fmt(delta["rotation_deg"]),
        _fmt(delta["luminance_abs"]), _fmt(delta["luminance_ratio"], 3), str(delta["view_target_changed"]).lower(),
        "\n".join(cards))


def index_html(run, seams):
    rows = []
    for seam in seams:
        flags = ", ".join(seam["analysis"]["flags"]) or "none"
        rows.append('<tr><td>%02d</td><td><a href="seams/%s/contact_sheet.html">%s</a></td><td>%s</td><td>%s</td></tr>' %
                    (seam["order"], html.escape(seam["id"]), html.escape(seam["kind"]),
                     html.escape(seam["from"] + " -> " + seam["to"]), html.escape(flags)))
    return ("""<!doctype html><meta charset="utf-8"><title>%s seam audit</title>
<style>body{font:15px system-ui;background:#151515;color:#eee;margin:24px}a{color:#8bd}table{border-collapse:collapse;width:100%%}th,td{border:1px solid #555;padding:8px;text-align:left}th{background:#292929}</style>
<h1>%s seam audit</h1><p>Six Passage-to-Scene boundaries and five logical Scene-to-Passage transitions, each represented by its Interaction start and end, in Master order.</p>
<table><thead><tr><th>#</th><th>kind/contact sheet</th><th>boundary</th><th>flags</th></tr></thead><tbody>%s</tbody></table>""" %
            (html.escape(run), html.escape(run), "\n".join(rows)))


def json_text(value):
    return json.dumps(value, indent=2, sort_keys=True)
