"""Offline preview of the proposed bulb placement per passage (after SCALE x3, then RELOCATE), for Gary to approve.

  python fixtures_preview.py [P01 ...]     -> proposals/<P>_fixture_placement_proposal.json,
                                             previews/<P>_overhead.png, previews/<P>_routecam.png, previews/summary.json
SCHEMATIC, not a render (inferred, per AGENTS.md tiers):
* P01/P02/P03/P05 route centres are reconstructed from saved rig-lamp level read-back centres, interpolating bays with
  no TOP pair; P06 uses lighting_events_report.json's saved station coordinates; P04 is the explicit 500 cm fallback;
* positions INSIDE a bay are the proposal's route-relative (pair-frame) numbers -- exact for the saved proposal;
* floor at pair z = 0; the wet-floor reflection is drawn as a mirror image (z -> -z) at 35 % opacity -- the idea of
  what a glossy floor returns, not a Lumen result;
* route camera: pinhole, 60 deg horizontal FOV, 60 cm above the floor on the lane centre, looking down the route.
"""
import json
import math
import os
import runpy
import sys
import types

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "previews")
PROPOSALS = os.path.join(HERE, "proposals")
BAY_PITCH_CM = 600.0
F = types.SimpleNamespace(**runpy.run_path(os.path.join(HERE, "fixtures_common.py"), run_name="_fc_preview"))

COLOURS = {"BULB_HANG": "#3b82f6", "BULB_GROUND_LYING": "#f59e0b", "BULB_GROUND_STANDING": "#d97706",
           "GLIMMER_TO_BULB_HANG": "#db2777", "GLIMMER_TO_BULB_GROUND": "#db2777"}


def apply_changes(cues, plan):
    rows = {c["guid"]: c for t in plan["targets"] for c in t["changes"]}
    out = []
    for cue in cues:
        new = dict(cue)
        new["attachments"] = [dict(rows[r["guid"]]["after"], ext=r.get("ext")) if r["guid"] in rows else r
                              for r in cue["attachments"]]
        out.append(new)
    return out


def plan_for(passage, table):
    cues, meta = F.snapshot_passage(passage)
    h = meta["meshy_housing"]
    sp = F.scale_plan(passage, cues, table, meta["derived_index"], {"lantern": h["lantern"], "body_size_cm": h["body_size_cm"]},
                      F.SCALE_DEFAULTS)
    scaled = apply_changes(cues, sp)
    rp = F.relocate_plan(passage, scaled, table, meta["derived_index"], F.RELOCATE_DEFAULTS)
    return scaled, rp, sp


def _fill_route(count, known):
    """Linear interpolation/extrapolation by station index. ``known`` is saved level evidence, never invented points."""
    keys = sorted(known)
    if len(keys) < 2:
        return [[i * BAY_PITCH_CM, 0.0] for i in range(count)]
    out = []
    for i in range(count):
        if i in known:
            out.append(list(known[i]))
            continue
        lo = max((k for k in keys if k < i), default=keys[0])
        hi = min((k for k in keys if k > i), default=keys[-1])
        if lo == hi:
            if i < keys[0]:
                lo, hi = keys[0], keys[1]
            else:
                lo, hi = keys[-2], keys[-1]
        t = (i - lo) / float(hi - lo)
        out.append([known[lo][j] + t * (known[hi][j] - known[lo][j]) for j in range(2)])
    origin = out[0]
    return [[p[0] - origin[0], p[1] - origin[1]] for p in out]


def route_from_repo(passage, count):
    rig = os.path.join(F.CONDUCTOR, "rig_lamp_drop_record_%s.json" % passage)
    if os.path.isfile(rig):
        record = json.load(open(rig, encoding="utf-8"))
        buckets = {}
        for row in record["plan"]["targets"]:
            buckets.setdefault(int(row["station_index"]), []).append(row["housing_before"]["centre"][:2])
        known = {i: [sum(p[0] for p in rows) / len(rows), sum(p[1] for p in rows) / len(rows)]
                 for i, rows in buckets.items()}
        return _fill_route(count, known), {
            "tier": "measured",
            "file": os.path.relpath(rig, F.CONDUCTOR).replace("\\", "/"),
            "detail": "saved housing centres grouped by station_index; missing bays linearly interpolated (inferred)",
            "known_stations": len(known),
        }
    if passage == "P06":
        path = os.path.join(F.CONDUCTOR, "lighting_events_report.json")
        report = json.load(open(path, encoding="utf-8"))
        known = {int(i): [float(v[0]), float(v[1])] for i, v in report["spacing"]["stations"].items()}
        return _fill_route(count, known), {
            "tier": "measured",
            "file": "lighting_events_report.json",
            "detail": "saved station coordinates 2..10; remaining bays linearly extrapolated/interpolated (inferred)",
            "known_stations": len(known),
        }
    return [[i * 500.0, 0.0] for i in range(count)], {
        "tier": "inferred",
        "file": None,
        "detail": "500 cm straight fallback; no saved station-coordinate record was found for this passage",
        "known_stations": 0,
    }


def route_frame(route, index):
    a = route[max(0, index - 1)]
    b = route[min(len(route) - 1, index + 1)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    along = [dx / n, dy / n]
    return along, [-along[1], along[0]]


def bulb_items(plan, cues, table):
    order = {c["guid"]: i for i, c in enumerate(cues)}
    items = []
    for t in plan["targets"]:
        bay = order.get(t["cue_guid"], 0)
        cords = {c["guid"]: c for c in t["changes"] if "CORD" in c["what"]}
        for c in t["changes"]:
            if c["what"] not in COLOURS:
                continue
            variant = c.get("variant")
            s = c["after"]["relative_transform"]["scale"][0]
            fx = table[variant]
            items.append({"bay": bay, "cue_guid": t["cue_guid"], "cue": t["cue_label"], "guid": c["guid"],
                          "what": c["what"], "x": c["glass"][0], "y": c["glass"][1],
                          "z": c["glass"][2] if "HANG" in c["what"] else fx["glass_width"] * s * 0.5,
                          "r": fx["glass_width"] * s * 0.5, "label": c["label"], "variant": variant,
                          "cord_guid": c.get("cord_guid"), "body": c["after"]["ext"]["body"]})
        for c in cords.values():
            tr = c["after"]["relative_transform"]
            lo, hi = plan["cord_bounds"]
            items.append({"bay": bay, "what": "CORD", "x": tr["location"][0], "y": tr["location"][1],
                          "z0": tr["location"][2] + lo[2] * tr["scale"][2], "z1": tr["location"][2] + hi[2] * tr["scale"][2]})
    return items


def housed(cues):
    out = []
    for i, cue in enumerate(cues):
        for r in cue["attachments"]:
            if F.is_kind(r, "LIGHT") and r["enabled"] and F.is_station(r):
                loc = r["relative_transform"]["location"]
                out.append((i, loc[0], loc[1], loc[2], r["label"].split(" ")[-1]))
    return out


def topdown(passage, cues, plan, items, path, bays_per_row=12):
    n = len(cues)
    rows = max(1, math.ceil(n / bays_per_row))
    fig, axes = plt.subplots(rows, 1, figsize=(18, 3.2 * rows), squeeze=False)
    lane, lat = plan["opts"]["lane_half_width_cm"], plan["opts"]["lateral_max_cm"]
    lights_after = housed(apply_changes(cues, plan))
    for r in range(rows):
        ax = axes[r][0]
        b0, b1 = r * bays_per_row, min(n, (r + 1) * bays_per_row)
        x0, x1 = b0 * BAY_PITCH_CM - 400, b1 * BAY_PITCH_CM
        ax.add_patch(Rectangle((x0, -lane), x1 - x0, 2 * lane, color="#e5e7eb", zorder=0))
        for s in (-1, 1):
            ax.axhline(s * lat, color="#9ca3af", lw=0.6, ls="--")
        for bay in range(b0, b1):
            ax.axvline(bay * BAY_PITCH_CM, color="#d1d5db", lw=0.5)
            ax.text(bay * BAY_PITCH_CM, 1480, cues[bay]["label"].replace("Wing ", "W"), fontsize=6, ha="center")
        for bay, x, y, z, role in lights_after:
            if b0 <= bay < b1:
                ax.plot(bay * BAY_PITCH_CM + x, y, "s", ms=3, color="#6b7280", alpha=0.6)
        for it in items:
            if not (b0 <= it["bay"] < b1) or it["what"] == "CORD":
                continue
            ax.add_patch(plt.Circle((it["bay"] * BAY_PITCH_CM + it["x"], it["y"]), max(it["r"], 12),
                                    color=COLOURS[it["what"]], alpha=0.85))
        ax.set_xlim(x0, x1)
        ax.set_ylim(-1550, 1550)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=6)
    axes[0][0].set_title("%s proposed bulbs (schematic top-down; bays unrolled at %d cm): blue hang, amber ground, pink "
                         "ex-glimmer; grey squares = housed lights AFTER (lanterns that remain); grey band = camera lane"
                         % (passage, BAY_PITCH_CM), fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def overhead(passage, cues, plan, items, route, route_source, path, bays_per_row=18):
    """True route-shaped XY overhead, split into panels only for legibility. Pair-local placements are transformed by
    the saved route tangent; P04's fallback is called out in the title and proposal JSON."""
    rows = max(1, math.ceil(len(cues) / bays_per_row))
    fig, axes = plt.subplots(rows, 1, figsize=(18, 4.5 * rows), squeeze=False)
    lane = float(plan["opts"]["lane_half_width_cm"])
    for panel in range(rows):
        ax = axes[panel][0]
        b0, b1 = panel * bays_per_row, min(len(cues), (panel + 1) * bays_per_row)
        base = route[b0]
        seg = [[p[0] - base[0], p[1] - base[1]] for p in route[b0:b1]]
        ax.plot([p[0] for p in seg], [p[1] for p in seg], color="#111827", lw=2.0, label="camera route")
        for bay in range(b0, b1):
            along, across = route_frame(route, bay)
            o = [route[bay][0] - base[0], route[bay][1] - base[1]]
            ax.plot([o[0] - across[0] * lane, o[0] + across[0] * lane],
                    [o[1] - across[1] * lane, o[1] + across[1] * lane], color="#d1d5db", lw=5, alpha=0.45)
            ax.text(o[0], o[1] + 80, str(bay + 1), fontsize=6, ha="center")
        for it in items:
            bay = it["bay"]
            if it["what"] == "CORD" or not b0 <= bay < b1:
                continue
            along, across = route_frame(route, bay)
            origin = [route[bay][0] - base[0], route[bay][1] - base[1]]
            x = origin[0] + along[0] * it["x"] + across[0] * it["y"]
            y = origin[1] + along[1] * it["x"] + across[1] * it["y"]
            ax.add_patch(plt.Circle((x, y), max(it["r"], 18), color=COLOURS[it["what"]], alpha=0.88))
        ax.set_aspect("equal")
        ax.grid(color="#e5e7eb", lw=0.4)
        ax.tick_params(labelsize=6)
        ax.set_ylabel("world Y delta (cm)", fontsize=7)
    axes[-1][0].set_xlabel("world X delta (cm)", fontsize=7)
    axes[0][0].set_title("%s fixture proposal overhead | %s | blue hanging, amber ground, pink ex-glimmer; grey = protected lane"
                         % (passage, route_source["tier"]), fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def proposal_json(passage, cues, rp, sp, items, route, route_source):
    placements = []
    for it in items:
        if it["what"] == "CORD":
            continue
        along, across = route_frame(route, it["bay"])
        origin = route[it["bay"]]
        placements.append({
            "bay_index": it["bay"], "cue_guid": it["cue_guid"], "cue_label": it["cue"],
            "body_guid": it["guid"], "label": it["label"], "placement": it["what"], "variant": it["variant"],
            "pair_relative_glass_cm": [round(it["x"], 2), round(it["y"], 2), round(it["z"], 2)],
            "overhead_world_delta_cm": [round(origin[0] + along[0] * it["x"] + across[0] * it["y"], 2),
                                         round(origin[1] + along[1] * it["x"] + across[1] * it["y"], 2)],
            "cord_guid": it["cord_guid"], "glow": {k: v for k, v in it["body"].items()
                                                       if k.startswith("point_light_") or k in ("full_intensity", "flicker", "emit_point_light")},
            "sway": {k: v for k, v in it["body"].items()
                       if k.startswith("swing_") or k in ("swing_on_cord", "sway_seed", "cord_attachment_guid")},
        })
    return {
        "schema_version": 1, "status": "PROPOSAL_ONLY_NOT_APPLIED", "passage": passage,
        "proof": {
            "placement_rows": "measured from tracked 7 Oct Meshy/scores records; live state not read in this offline run",
            "route": route_source,
            "rendered_appearance": "inferred; PNG is an overhead diagram, not an Unreal render",
        },
        "scale": {"housing_factor": sp["opts"]["housing_factor"], "bulb_factor": sp["opts"]["bulb_factor"],
                  "bulb_scale_after": sp["opts"]["expected_bulb_scale"] * sp["opts"]["bulb_factor"],
                  "housing": sp["housing"]},
        "creative_defaults_require_gary_approval": {k: rp["opts"][k] for k in (
            "hang_fraction", "hang_fraction_by_passage", "lane_half_width_cm", "lateral_max_cm", "ground_x_range_cm",
            "hang_x_range_cm", "hang_glass_z_range_cm", "lying_fraction", "glow_mode", "emissive_full_intensity",
            "glow_flicker", "glow_flicker_rate_hz", "glow_slight_depth", "point_light_lumens",
            "point_light_attenuation_radius_cm", "point_light_source_radius_cm", "point_light_soft_source_radius_cm",
            "point_light_temperature_kelvin", "cord_sway_mode", "sway_yaw_amplitude_degrees",
            "sway_pitch_amplitude_degrees", "sway_period_seconds", "sway_seed")},
        "counts": rp["counts"], "plan_sha256_offline": F.plan_sha(rp), "placements": placements,
        "open_gates": ["run live RELOCATE DRY after the new binary is built", "resolve live floor bounds",
                       "approve overhead proposal and creative defaults", "apply one passage first", "rendered visual acceptance"],
    }


def routecam(passage, cues, plan, items, path, bays_ahead=7):
    cam = [-350.0, 0.0, 60.0]
    f = 1.0 / math.tan(math.radians(30.0))
    W, H = 1600, 900

    def proj(p):
        d = p[0] - cam[0]
        if d < 30.0:
            return None
        return (W / 2 + f * (p[1] - cam[1]) / d * W / 2, H / 2 - f * (p[2] - cam[2]) / d * W / 2, d)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#0b0b10")
    ax.set_facecolor("#0b0b10")
    for yline in (-600, -plan["opts"]["lateral_max_cm"], plan["opts"]["lateral_max_cm"], 600):
        a, b = proj([0, yline, 0]), proj([bays_ahead * BAY_PITCH_CM, yline, 0])
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#374151", lw=0.8)
    for bay in range(bays_ahead + 1):
        a, b = proj([bay * BAY_PITCH_CM, -700, 0]), proj([bay * BAY_PITCH_CM, 700, 0])
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#1f2937", lw=0.6)
        top = proj([bay * BAY_PITCH_CM, -1350, plan["cord_top_z_cm"]]), proj([bay * BAY_PITCH_CM, 1350, plan["cord_top_z_cm"]])
        if top[0] and top[1]:
            ax.plot([top[0][0], top[1][0]], [top[0][1], top[1][1]], color="#4b5563", lw=1.5)
    drawn = sorted([it for it in items if it["bay"] <= bays_ahead], key=lambda it: -(it["bay"] * BAY_PITCH_CM + it["x"]))
    for it in drawn:
        wx = it["bay"] * BAY_PITCH_CM + it["x"]
        if it["what"] == "CORD":
            a, b = proj([wx, it["y"], it["z0"]]), proj([wx, it["y"], it["z1"]])
            if a and b:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#6b7280", lw=0.7)
            continue
        p = proj([wx, it["y"], it["z"]])
        m = proj([wx, it["y"], -it["z"]])
        if not p:
            continue
        rad = f * it["r"] / p[2] * W / 2
        c = COLOURS[it["what"]]
        ax.add_patch(plt.Circle((p[0], p[1]), max(rad, 1.5), color="#fde68a", alpha=0.95))
        ax.add_patch(plt.Circle((p[0], p[1]), max(rad, 1.5) * 1.8, color=c, alpha=0.18))
        if m:
            ax.add_patch(plt.Circle((m[0], m[1]), max(rad, 1.5), color="#fde68a", alpha=0.35))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("%s route camera (schematic pinhole, 60 cm high, first %d bays): bulbs + mirrored wet-floor reflections; "
                 "top line = crossbeam underside the cords hang from" % (passage, bays_ahead), fontsize=9, color="white")
    fig.tight_layout()
    fig.savefig(path, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PROPOSALS, exist_ok=True)
    table = F.M.load_fixture_table(check_files=False)
    passages = [a for a in argv if a in F.PASSAGES] or list(F.PASSAGES)
    summary = {"schematic": True, "route_geometry": "repo-backed where available; see each passage.route_source",
               "routecam_bay_pitch_cm_nominal": BAY_PITCH_CM, "passages": {}}
    for p in passages:
        cues, rp, sp = plan_for(p, table)
        items = bulb_items(rp, cues, table)
        route, route_source = route_from_repo(p, len(cues))
        overhead(p, cues, rp, items, route, route_source, os.path.join(OUT, "%s_overhead.png" % p))
        routecam(p, cues, rp, items, os.path.join(OUT, "%s_routecam.png" % p))
        proposal = proposal_json(p, cues, rp, sp, items, route, route_source)
        proposal_path = os.path.join(PROPOSALS, "%s_fixture_placement_proposal.json" % p)
        with open(proposal_path, "w", encoding="utf-8") as handle:
            json.dump(proposal, handle, indent=1, sort_keys=True)
        summary["passages"][p] = {"relocate_counts": rp["counts"], "bulb_scale_after_scale": sp["opts"]["expected_bulb_scale"] * sp["opts"]["bulb_factor"],
                                  "glimmer_bulb_scale": rp["glimmer_bulb_scale"], "plan_sha256_offline": F.plan_sha(rp),
                                  "route_source": route_source,
                                  "proposal": os.path.relpath(proposal_path, HERE).replace("\\", "/"),
                                  "proposed_bulbs": len(proposal["placements"])}
        print("FIXPREVIEW|%s|%s" % (p, json.dumps(rp["counts"]["by_kind"], sort_keys=True)))
    summary["total_proposed_bulbs"] = sum(row["proposed_bulbs"] for row in summary["passages"].values())
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print("FIXPREVIEW_OK|%s" % OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
