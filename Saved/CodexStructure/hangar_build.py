"""Parametric hangar builder (30 Sep; Gary: "it's only a question of how to scale and resize
the hangars to fit and light scenes in later"). ONE pass builds a complete v2 hangar for
Scene N from NUMBERS, so a resize is a number and a re-run, not a re-authoring.

What it builds, in the Scene's dock frame (its Entry Handoff Camera, pitch/roll ignored,
yaw kept, so Scene 2's rotated dock works; origin on the camera at floor level, +x ahead):
- a fixed APRON (camera -> hinge) and a ROOT on the hinge line (axis Y of the dock frame);
- on the root, in the box frame (origin on the hinge, +x into the box), ASSEMBLED:
  floor tiles (about 20 m squares, rows hinged at their near edge), side walls and far
  wall (hinged at their feet), the roof on the far wall's top (upright at rest), the working
  lattice (beams, three rails, bulbs with a glow light each) flown up at rest, the ghost
  light, one rank of wall practicals, and the far-wall uplights;
- a world-fixed post-process volume pinning exposure over apron and box;
- the root hanging at -90 (the box below the floor), lights at rest dark except the ghost;
- a new sequence LS_S{N}_HangarRise keying the rise, the practical wave, the uplights,
  the roof swing, the lattice fly-in and the glow fade, every time scaled by K.

WHAT IS PARAMETRIC (HANGAR_PARAMS in globals; defaults are Scene 4's): depth, half-width, height, hinge height,
floor/apron/exposure-volume on or off (a site whose own ground is the floor gets none),
wall and floor thickness, apron, lattice height and fly, beam/bulb/practical spacing,
the COUNTS and spacings of rails, bulbs, glow lights (within a light budget), practicals and
uplights, which grow with the hall (Scene 4: 3 rails at +-8 m, 3 uplights at +-6 m), ghost light position, roof
on/off, practical height, pinned exposure, placeholder tag, and K. K defaults to
sqrt(max(depth, 2 x height) / 6000): 1 for Scene 4; a deeper or taller box rises slower
("a taller wall is a longer rise, not a broken one"). Every position derives from those.
WHAT IS NOT: the materials (walnut floor, black steel walls, burnished-steel lattice,
work-bulb emissive), the light colours and intensities, and the beat ORDER (rise, wave,
uplights, roof, lattice). Those are Scene 4's, repeated.

Scene 4 itself was built in five passes; its v2 state is what this reproduces. The dry
run for scene 4 compares the plan with the live Scene 4 hangar, actor by actor, in root-
relative space (the acceptance test). Differences it does not remove: Scene 4's
exposure volume starts 5 m nearer the passage than a rebuild would place it, because the
v2 re-dock moved the box, not the volume.

Checks before anything is built (from the plan, analytically): nothing crosses back over
the apron during the swing, nothing within 1 m of the camera, nothing above the floor
plane while hanging, and nothing else in the swept volume (listed; ALLOW names exempt).
Dry run by default (HANGAR_APPLY to build). Apply: guards (world, no PIE, 0+0 dirty, no
Sequencer, no ZZ_, no hangar for this scene yet, no sequence yet), a plain record first,
a level backup, read-back of the rest pose, saves the new sequence and the level only.
Revert: hangar_revert.py (by tag RigAtmos.Scene{N}Hangar). Lean: all work in main().
"""
import datetime
import json
import math
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_DIR = "/Game/InfinityStage/RigAtmos"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
CUBE, CYL, SPHERE = "/Engine/BasicShapes/Cube.Cube", "/Engine/BasicShapes/Cylinder.Cylinder", "/Engine/BasicShapes/Sphere.Sphere"
FLOOR_MAT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
STEEL_MAT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
LATTICE_MAT = "/Game/StarterContent/Materials/M_Metal_Burnished_Steel.M_Metal_Burnished_Steel"
BULB_MAT = "/Game/InfinityStage/RigAtmos/M_RigAtmos_WorkBulb"
FPS = 30
HANGAR = {"scene": 4, "depth": 6000.0, "half_w": 1000.0, "height": 3000.0, "wall_t": 50.0, "floor_t": 20.0,
          "apron": 500.0, "lattice_z": 1200.0, "lattice_fly": 1600.0, "beam_step": 400.0, "bulb_step": 750.0,
          "rail_pitch": 800.0, "rail_margin": 200.0, "uplight_pitch": 600.0, "uplight_margin": 400.0,
          "glow_budget": 150, "practical_first": 1000.0,
          "practical_step": 800.0, "practical_z": 700.0, "ghost_x": 2500.0, "ghost_y": -400.0, "roof": True,
          "pinned_ev100": 0.5, "placeholder": False, "k": None, "allow": (), "floor": True, "apron_slab": True, "ppv": True, "hinge_z": 0.0}
HANGAR.update(globals().get("HANGAR_PARAMS", {}))


def fail(msg):
    unreal.log_error("HANGAR_BUILD_STOPPED|" + msg)
    raise RuntimeError(msg)


def ranked(half_w, pitch, margin):
    """Evenly pitched positions across the width, centred, keeping margin from each wall:
    Scene 4's 3 rails (+-8 m) and 3 uplights (+-6 m) at 20 m wide; more as the hall widens."""
    n = int((2.0 * half_w - 2.0 * margin) // pitch) + 1
    return [(-(n - 1) / 2.0 + j) * pitch for j in range(n)]


def plan_for(h):
    """Every piece of the hangar, in the BOX frame (origin on the hinge, +x into the box,
    z up), in the ASSEMBLED rest pose: hinges at 0, the roof upright, the lattice flown."""
    n, d, w, ht = h["scene"], h["depth"], h["half_w"], h["height"]
    wt, ft = h["wall_t"], h["floor_t"]
    P = f"S{n}"
    fly_z = h["lattice_z"] + h["lattice_fly"]
    items = []

    def add(label, kind, loc, size=None, parent=None, rot=(0.0, 0.0, 0.0), **extra):
        items.append(dict(label=label, kind=kind, loc=list(loc), size=list(size) if size else None, parent=parent,
                          rot=list(rot), **extra))

    add(f"{P} Hangar Root", "hinge", (0.0, 0.0, 0.0), tags=["Hinge|edge=mouth|axis=Y|closed=-90|open=0"], root=True)
    rows = max(1, int(round(d / 2000.0)))
    cols = max(1, int(round(2.0 * w / 2000.0)))
    tile_x, tile_y = d / rows, 2.0 * w / cols
    for k in range(rows):
        hinge = f"{P} Hangar Floor {k + 1} Hinge"
        add(hinge, "hinge", (k * tile_x, 0.0, 0.0), parent=f"{P} Hangar Root", tags=["Hinge|edge=near|axis=Y|closed=90|open=0"])
        for c in range(cols if h["floor"] else 0):      # no tiles where the site's own ground is the floor
            label = f"{P} Hangar Floor {k + 1}" if cols == 1 else f"{P} Hangar Floor {k + 1}-{c + 1}"
            add(label, "slab", (k * tile_x + tile_x / 2.0, -w + tile_y * (c + 0.5), -ft / 2.0), (tile_x, tile_y, ft), hinge,
                mat="floor", shadows=True)
    for side, sign, closed in (("Left", -1.0, -90), ("Right", 1.0, 90)):
        y = sign * (w + wt / 2.0)
        hinge = f"{P} Hangar {side} Wall Hinge"
        add(hinge, "hinge", (d / 2.0, y, 0.0), parent=f"{P} Hangar Root", tags=[f"Hinge|edge=bottom|axis=X|closed={closed}|open=0"])
        add(f"{P} Hangar {side} Wall", "slab", (d / 2.0, y, ht / 2.0), (d, wt, ht), hinge, mat="steel", shadows=True)
    far = f"{P} Hangar Far Wall Hinge"
    add(far, "hinge", (d + wt / 2.0, 0.0, 0.0), parent=f"{P} Hangar Root", tags=["Hinge|edge=bottom|axis=Y|closed=90|open=0"])
    add(f"{P} Hangar Far Wall", "slab", (d + wt / 2.0, 0.0, ht / 2.0), (wt, 2.0 * (w + wt), ht), far, mat="steel", shadows=True)
    if h["roof"]:
        # Built lying over the box, then upright: the hinge's relative pitch is -90 at rest.
        add(f"{P} Hangar Roof Hinge", "hinge", (d + wt / 2.0, 0.0, ht), parent=far, rest_pitch=-90.0,
            tags=[f"Hinge|edge=far|axis=Y|closed=180|open=0|rides={far}"])
        add(f"{P} Hangar Roof", "slab", ((d + wt) / 2.0, 0.0, ht + wt / 2.0), (d + wt, 2.0 * (w + wt), wt),
            f"{P} Hangar Roof Hinge", mat="steel", shadows=True)
    fly = f"{P} Hangar Lattice Fly"
    add(fly, "hinge", (d / 2.0, 0.0, fly_z), parent=f"{P} Hangar Root", tags=["Fly|axis=Z|closed=1800|open=0"])
    x, beams = h["beam_step"], 0
    while x < d - 100.0:
        beams += 1
        add(f"{P} Hangar Lattice Beam {beams:02d}", "slab", (x, 0.0, fly_z), (26.0, 2.0 * w, 34.0), fly, mat="lattice", shadows=False)
        x += h["beam_step"]
    rails = ranked(w, h["rail_pitch"], h["rail_margin"])
    for r, ry in enumerate(rails):
        add(f"{P} Hangar Lattice Rail {r + 1}", "slab", (d / 2.0, ry, fly_z + 34.0), (d, 26.0, 34.0), fly, mat="lattice", shadows=False)
    per_rail = max(1, int(round(d / h["bulb_step"])))
    step = d / per_rail
    # Every bulb glows as an emissive; a real light rides only every Nth one past the budget,
    # so a big hall's lattice reads without hundreds of lights.
    every = max(1, -(-len(rails) * per_rail // int(h["glow_budget"])))
    for r, ry in enumerate(rails):
        for i in range(per_rail):
            bulb = f"{P} Lattice Bulb {r + 1}-{i + 1}"
            add(bulb, "bulb", (step / 2.0 + i * step, ry, fly_z + 11.0), (6.0, 6.0, 6.0), fly)
            if (r * per_rail + i) % every == 0:
                add(f"{P} Lattice Glow {r + 1}-{i + 1}", "glow", (step / 2.0 + i * step, ry, fly_z + 11.0), parent=bulb)
    gx, gy = h["ghost_x"], h["ghost_y"]
    ghost_row = min(rows - 1, int(gx // tile_x))
    ghost_parent = f"{P} Hangar Floor {ghost_row + 1} Hinge"
    add(f"{P} Ghost Light Stand", "stand", (gx, gy, 90.0), (4.0, 4.0, 180.0), ghost_parent)
    add(f"{P} Ghost Light Bulb", "sphere", (gx, gy, 188.0), (12.0, 12.0, 12.0), ghost_parent)
    add(f"{P} Ghost Light", "ghost", (gx, gy, 188.0), parent=ghost_parent)
    px, i = h["practical_first"], 0
    xs = []
    while px <= d - 200.0:
        xs.append(px)
        px += h["practical_step"]
    for side, sign in (("L", -1.0), ("R", 1.0)):
        hinge = f"{P} Hangar {'Left' if sign < 0 else 'Right'} Wall Hinge"
        for i, px in enumerate(xs):
            add(f"{P} Practical {side}{i + 1} Body", "slab", (px, sign * (w - 15.0), h["practical_z"]), (30.0, 30.0, 22.0), hinge,
                mat="steel", shadows=False)
            add(f"{P} Practical {side}{i + 1}", "practical", (px, sign * (w - 40.0), h["practical_z"] - 10.0), parent=hinge,
                rot=(0.0, -35.0, -90.0 * sign), order=i)
    ups = ranked(w, h["uplight_pitch"], h["uplight_margin"])
    for i, uy in enumerate(ups):
        add(f"{P} Uplight {i + 1}", "uplight", (d - 150.0, uy, 30.0), parent=far, rot=(0.0, 89.0, 0.0), order=i)
    return items, {"rows": rows, "cols": cols, "beams": beams, "rails": len(rails), "bulbs": per_rail * len(rails),
                   "glows": sum(1 for it in items if it["kind"] == "glow"), "practicals": 2 * len(xs), "uplights": len(ups)}


def corners(item):
    """Box-frame corners of a mesh piece in the assembled pose (the roof turned upright)."""
    cx, cy, cz = item["loc"]
    sx, sy, sz = [s / 2.0 for s in item["size"]]
    pts = [(cx + a * sx, cy + b * sy, cz + c * sz) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    return pts


def main():
    h = HANGAR
    n = h["scene"]
    apply = bool(globals().get("HANGAR_APPLY"))
    k = h["k"] if h["k"] else math.sqrt(max(h["depth"], 2.0 * h["height"]) / 6000.0)
    TAG, SEQ_NAME = f"RigAtmos.Scene{n}Hangar", f"LS_S{n}_HangarRise"
    FOLDER = f"Infinity Stage/Scene 0{n} Hangar"
    RECORD = os.path.join(HERE, f"hangar_s{n}_record.json")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    cams = [a for a in actors if a.get_actor_label().startswith(f"Scene {n} ") and "Entry Handoff Camera" in a.get_actor_label()]
    if len(cams) != 1:
        fail(f"expected one Scene {n} Entry Handoff Camera, found {len(cams)}")
    cam = cams[0]
    cl, cr = cam.get_actor_location(), cam.get_actor_rotation()
    dock = unreal.Transform(location=unreal.Vector(cl.x, cl.y, 0.0), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=cr.yaw))
    items, counts = plan_for(h)
    by_label = {it["label"]: it for it in items}

    # ---- Analytic checks, in the dock frame --------------------------------------------
    apron = h["apron"]
    mesh_items = [it for it in items if it["size"]]
    pts = []
    for it in mesh_items:
        c = corners(it)
        if it["parent"] == f"S{n} Hangar Roof Hinge":      # upright: turn about the roof hinge by -90
            hx, _, hz = by_label[it["parent"]]["loc"]
            c = [(hx + (z - hz), y, hz - (x - hx)) for (x, y, z) in c]
        pts.extend(c)
    problems = []
    cam_local = (0.0, 0.0, cl.z)
    for s in range(0, 91, 3):
        phi = math.radians(-90.0 + s)
        moved = [(apron + x * math.cos(phi) - z * math.sin(phi), y, h["hinge_z"] + x * math.sin(phi) + z * math.cos(phi)) for (x, y, z) in pts]
        if min(p[0] for p in moved) < apron - 25.0:
            problems.append(f"crosses back over the apron at {math.degrees(phi):.0f} deg")
        if min(math.dist(p, cam_local) for p in moved) < 100.0:
            problems.append(f"within 1 m of the camera at {math.degrees(phi):.0f} deg")
        if s == 0 and max(p[2] for p in moved) > 5.0:
            problems.append(f"hanging, something stands {max(p[2] for p in moved):.1f} cm above the floor plane")
    reach = max(math.hypot(x, z) for (x, _, z) in pts) + 100.0
    half_y = h["half_w"] + h["wall_t"] + 100.0
    blockers = []
    for a in actors:
        if a == cam or a.get_actor_label().startswith(f"S{n} ") or isinstance(a, (unreal.PostProcessVolume, unreal.CameraActor)):
            continue
        o, e = a.get_actor_bounds(False)
        if e.length() < 1.0 or max(e.x, e.y) > 1.0e6:
            continue
        # The actor's world box, its 8 corners in the dock frame, against the swept box.
        cs = [unreal.MathLibrary.inverse_transform_location(dock, unreal.Vector(o.x + sx * e.x, o.y + sy * e.y, o.z + sz * e.z))
              for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        def hits(cs):
            return (max(c.x for c in cs) >= apron - 25.0 and min(c.x for c in cs) <= apron + reach
                    and max(c.y for c in cs) >= -half_y and min(c.y for c in cs) <= half_y
                    and max(c.z for c in cs) >= -reach and min(c.z for c in cs) <= reach)
        if hits(cs):
            # A Passage, its structure or its camera rig spans far more than it occupies: test
            # its instanced pieces one by one and keep it only if one of them is in the way.
            isms = [c for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent) if c.get_instance_count()]
            if isms:
                inside = 0
                for comp in isms:
                    mesh = comp.get_editor_property("static_mesh")
                    if not mesh:
                        continue
                    bb = mesh.get_bounding_box()
                    for i in range(comp.get_instance_count()):
                        t = comp.get_instance_transform(i, True)
                        pcs = [unreal.MathLibrary.inverse_transform_location(dock, t.transform_location(unreal.Vector(x, y, z)))
                               for x in (bb.min.x, bb.max.x) for y in (bb.min.y, bb.max.y) for z in (bb.min.z, bb.max.z)]
                        inside += 1 if hits(pcs) else 0
                if inside == 0:
                    continue
                cs = cs + [unreal.Vector(0.0, 0.0, float(inside))]
            if a.get_actor_label() not in h["allow"]:
                blockers.append(f"{a.get_actor_label()} ({a.get_class().get_name()}) pieces_in_way={int(cs[-1].z) if len(cs) > 8 else 'n/a'} dock-frame x[{min(c.x for c in cs):.0f},{max(c.x for c in cs):.0f}]"
                                f" y[{min(c.y for c in cs):.0f},{max(c.y for c in cs):.0f}] z[{min(c.z for c in cs):.0f},{max(c.z for c in cs):.0f}]")
    # ---- Scene 4 acceptance: the plan against the live hangar, root-relative ----------------
    compare = None
    if n == 4:
        live = {a.get_actor_label(): a for a in actors if a.get_actor_label().startswith("S4 ")}
        root = live.get("S4 Hangar Root")
        if root:
            rt = root.get_actor_transform()
            worst, missing, off = 0.0, [], []
            for it in items:
                a = live.get(it["label"])
                if a is None:
                    missing.append(it["label"])
                    continue
                got = unreal.MathLibrary.inverse_transform_location(rt, a.get_actor_location())
                want = it["loc"]
                if it["parent"] == "S4 Hangar Roof Hinge":          # the live roof stands upright
                    hx, _, hz = by_label[it["parent"]]["loc"]
                    want = [hx + (want[2] - hz), want[1], hz - (want[0] - hx)]
                err = math.dist((got.x, got.y, got.z), want)
                if err > worst:
                    worst = err
                if err > 1.0:
                    off.append(f"{it['label']} {err:.1f} cm")
            extra = sorted(l for l in live if l not in by_label and l not in ("S4 Hangar Apron", "S4 Hangar Pinned Exposure"))
            compare = {"worst_cm": round(worst, 3), "missing": missing, "off_by_more_than_1cm": off[:20], "extra_live": extra[:20]}
    plan = {"scene": n, "dock": {"loc": [cl.x, cl.y, cl.z], "yaw": cr.yaw}, "k": round(k, 3), "counts": counts, "pieces": len(items),
            "reach_cm": round(reach), "problems": problems, "blockers": blockers[:30], "compare_with_live_s4": compare, "hangar": h}
    json.dump(plan, open(os.path.join(HERE, f"hangar_s{n}_plan.json"), "w"), indent=1, default=str)
    unreal.log(f"HANGAR_PLAN|S{n}|pieces={len(items)}|k={k:.3f}|counts={counts}|problems={len(problems)}|blockers={len(blockers)}"
               f"|compare={json.dumps(compare) if compare else None}")
    if not apply:
        unreal.log("HANGAR_DRY_RUN_OK|mutated=0")
        return
    if problems or blockers:
        fail(f"checks: problems={problems[:4]} blockers={blockers[:6]}")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    if any(a.get_actor_label().startswith("ZZ_") for a in actors):
        fail("bench actors (ZZ_) in the level")
    if any(TAG in [str(t) for t in a.get_editor_property("tags")] for a in actors) or os.path.exists(RECORD):
        fail(f"a Scene {n} hangar (or its record) already exists; revert first")
    if unreal.EditorAssetLibrary.does_asset_exist(f"{SEQ_DIR}/{SEQ_NAME}"):
        fail(f"{SEQ_NAME} already exists")
    mats = {"floor": unreal.load_asset(FLOOR_MAT), "steel": unreal.load_asset(STEEL_MAT), "lattice": unreal.load_asset(LATTICE_MAT),
            "bulb": unreal.load_asset(BULB_MAT)}
    meshes = {"cube": unreal.load_asset(CUBE), "cyl": unreal.load_asset(CYL), "sphere": unreal.load_asset(SPHERE)}
    if not all(mats.values()) or not all(meshes.values()):
        fail("a material or engine shape did not load")
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "scene": n, "tag": TAG,
              "sequence": f"{SEQ_DIR}/{SEQ_NAME}", "labels": [it["label"] for it in items] + [f"S{n} Hangar Apron", f"S{n} Hangar Pinned Exposure"],
              "hangar": {k2: (list(v) if isinstance(v, tuple) else v) for k2, v in h.items()}, "k": k,
              "dock": {"loc": [cl.x, cl.y, cl.z], "yaw": cr.yaw}}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", f"PreHangarS{n}-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(RECORD, backup)

    # ---- Build, ASSEMBLED with the root level ----------------------------------------
    hinge_world = dock.transform_location(unreal.Vector(apron, 0.0, h["hinge_z"]))
    root_level = unreal.Transform(location=hinge_world, rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=cr.yaw))
    tags_common = [TAG, "RigAtmos.Hangar"] + (["RigAtmos.Placeholder"] if h["placeholder"] else [])
    spawned = {}

    def world_of(loc):
        return root_level.transform_location(unreal.Vector(*loc))

    def world_rot(rot):
        q = unreal.MathLibrary.compose_rotators(unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]),
                                                unreal.Rotator(roll=0.0, pitch=0.0, yaw=cr.yaw))
        return q

    def finish(actor, it, extra_tags=()):
        actor.set_actor_label(it["label"])
        actor.set_folder_path(FOLDER)
        actor.set_editor_property("tags", [unreal.Name(t) for t in tags_common + list(it.get("tags", [])) + list(extra_tags)])
        spawned[it["label"]] = actor
        return actor

    def light(cls, it, cd, radius, kelvin, shadows, **props):
        a = sub.spawn_actor_from_class(cls, world_of(it["loc"]), world_rot(it["rot"]))
        c = a.get_component_by_class(unreal.LightComponent)
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        c.set_editor_property("intensity", cd)
        c.set_editor_property("attenuation_radius", radius)
        c.set_editor_property("use_temperature", True)
        c.set_editor_property("temperature", kelvin)
        c.set_editor_property("cast_shadows", shadows)
        for p, v in props.items():
            c.set_editor_property(p, v)
        return a

    for it in items:
        kind = it["kind"]
        if kind == "hinge":
            a = sub.spawn_actor_from_class(unreal.StaticMeshActor, world_of(it["loc"]), world_rot(it["rot"]))
            a.get_editor_property("static_mesh_component").set_mobility(unreal.ComponentMobility.MOVABLE)
            finish(a, it, [f"RigAtmos.Scene{n}Root"] if it.get("root") else [])
        elif kind in ("slab", "bulb", "stand", "sphere"):
            a = sub.spawn_actor_from_class(unreal.StaticMeshActor, world_of(it["loc"]), world_rot(it["rot"]))
            smc = a.get_editor_property("static_mesh_component")
            smc.set_mobility(unreal.ComponentMobility.MOVABLE)
            smc.set_static_mesh(meshes["cyl" if kind == "stand" else "sphere" if kind == "sphere" else "cube"])
            mat = mats.get(it.get("mat")) if kind == "slab" else mats["bulb"] if kind == "bulb" else mats["steel"] if kind == "stand" else None
            if mat:
                smc.set_material(0, mat)
            smc.set_cast_shadow(bool(it.get("shadows", kind == "stand")))
            a.set_actor_scale3d(unreal.Vector(*[s / 100.0 for s in it["size"]]))
            finish(a, it, ["Prop|role=bulb"] if kind == "bulb" else [])
        elif kind == "glow":
            finish(light(unreal.PointLight, it, 0.0, 800.0, 2700.0, False, source_radius=4.0), it, ["RigAtmos.LatticeGlow"])
        elif kind == "ghost":
            finish(light(unreal.PointLight, it, 60.0, 1500.0, 2600.0, True, source_radius=3.0), it, ["Light|role=ghost"])
        elif kind == "practical":
            finish(light(unreal.SpotLight, it, 0.0, 2500.0, 2900.0, False, inner_cone_angle=30.0, outer_cone_angle=55.0,
                         volumetric_scattering_intensity=0.5), it, ["Light|role=practical"])
        elif kind == "uplight":
            finish(light(unreal.SpotLight, it, 0.0, h["height"] + h["depth"] + 500.0, 3200.0, False, inner_cone_angle=8.0,
                         outer_cone_angle=12.5, volumetric_scattering_intensity=1.0), it, [f"RigAtmos.Scene{n}Uplight", "Light|role=uplight"])
    for it in items:
        if it["parent"]:
            spawned[it["label"]].attach_to_actor(spawned[it["parent"]], unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                                                  unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    # The rest pose inside the box: the roof upright (built flat, turned about its hinge).
    roof_hinge = spawned.get(f"S{n} Hangar Roof Hinge")
    if roof_hinge:
        roof_hinge.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0), False, True)
    # The apron (fixed, not on the root) and the pinned exposure (world-fixed).
    apron_it = {"label": f"S{n} Hangar Apron", "tags": [f"RigAtmos.Scene{n}Apron"]}
    if h["apron_slab"]:
        ap = sub.spawn_actor_from_class(unreal.StaticMeshActor, dock.transform_location(unreal.Vector(apron / 2.0, 0.0, -h["floor_t"] / 2.0)),
                                        unreal.Rotator(roll=0.0, pitch=0.0, yaw=cr.yaw))
        asmc = ap.get_editor_property("static_mesh_component")
        asmc.set_static_mesh(meshes["cube"])
        asmc.set_material(0, mats["floor"])
        ap.set_actor_scale3d(unreal.Vector(apron / 100.0, 2.0 * h["half_w"] / 100.0, h["floor_t"] / 100.0))
        finish(ap, apron_it)
    span = apron + h["depth"] + 200.0
    ppv = None if not h["ppv"] else sub.spawn_actor_from_class(unreal.PostProcessVolume,
                                     dock.transform_location(unreal.Vector(span / 2.0 - 100.0, 0.0, h["height"] / 2.0)),
                                     unreal.Rotator(roll=0.0, pitch=0.0, yaw=cr.yaw))
    if ppv:
        ppv.set_actor_scale3d(unreal.Vector(span / 200.0, (2.0 * h["half_w"] + 200.0) / 200.0, (h["height"] + 200.0) / 200.0))
        ppv.set_editor_property("unbound", False)
        st = ppv.get_editor_property("settings")
        for name, v in (("auto_exposure_min_brightness", h["pinned_ev100"]), ("auto_exposure_max_brightness", h["pinned_ev100"]),
                        ("local_exposure_highlight_contrast_scale", 1.0), ("local_exposure_shadow_contrast_scale", 1.0)):
            st.set_editor_property("override_" + name, True)
            st.set_editor_property(name, v)
        ppv.set_editor_property("settings", st)
        finish(ppv, {"label": f"S{n} Hangar Pinned Exposure", "tags": ["PostProcess|exposure=pinned"]})
    root = spawned[f"S{n} Hangar Root"]
    fly = spawned[f"S{n} Hangar Lattice Fly"]
    fly_rel = [float(v) for v in unreal.MathLibrary.inverse_transform_location(root.get_actor_transform(), fly.get_actor_location()).to_tuple()]
    roof_rel = [float(v) for v in roof_hinge.root_component.get_editor_property("relative_location").to_tuple()] if roof_hinge else None
    root.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=-90.0, yaw=cr.yaw), False, True)

    # ---- The sequence: every beat at Scene 4's time times K ------------------------------
    T = lambda s: s * k
    RISE, ROOF, LATTICE, END = (T(1.0), T(16.0)), (T(18.5), T(24.5)), (T(24.5), T(28.5)), T(31.0)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    seq = tools.create_asset(SEQ_NAME, SEQ_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if not seq:
        fail("sequence not created")
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    end = int(round(END * FPS))
    seq.set_playback_start(0)
    seq.set_playback_end(end)
    f = lambda s: unreal.FrameNumber(int(round(s * FPS)))

    def key_transform(actor, loc, rot, channel, keys):
        b = seq.add_possessable(actor)
        tr = b.add_track(unreal.MovieScene3DTransformTrack)
        sec = tr.add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()
        for i, v in enumerate(list(loc) + list(rot) + [1.0, 1.0, 1.0]):
            ch[i].set_default(float(v))
        for t_s, v in keys:
            ch[channel].add_key(f(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=unreal.MovieSceneKeyInterpolation.AUTO)

    def key_intensity(actor, keys):
        b = seq.add_possessable(actor.get_component_by_class(unreal.LightComponent))
        tr = b.add_track(unreal.MovieSceneFloatTrack)
        tr.set_property_name_and_path("Intensity", "Intensity")
        sec = tr.add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()[0]
        for t_s, v in keys:
            ch.add_key(f(t_s), float(v), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)

    key_transform(root, [hinge_world.x, hinge_world.y, hinge_world.z], [0.0, 0.0, cr.yaw], 4, [(0.0, -90.0), (RISE[0], -90.0), (RISE[1], 0.0)])
    if roof_hinge:
        key_transform(roof_hinge, roof_rel, [0.0, 0.0, 0.0], 4, [(0.0, -90.0), (ROOF[0], -90.0), (ROOF[1], 0.0)])
    key_transform(fly, fly_rel, [0.0, 0.0, 0.0], 2, [(0.0, fly_rel[2]), (LATTICE[0], fly_rel[2]), (LATTICE[1], fly_rel[2] - h["lattice_fly"])])
    pracs = sorted((it for it in items if it["kind"] == "practical"), key=lambda it: (it["order"], it["label"]))
    for i, it in enumerate(pracs):
        t = T(16.5) + (i // 2) * T(0.3)
        key_intensity(spawned[it["label"]], [(0.0, 0.0), (t, 0.0), (t + T(0.2), 400.0)])
    for it in (it for it in items if it["kind"] == "uplight"):
        t = T(18.0) + (it["order"] % 3) * T(0.15)            # Scene 4's three strikes, repeated along a wider wall
        key_intensity(spawned[it["label"]], [(0.0, 0.0), (t, 0.0), (t + T(0.2), 10000.0)])
    for it in (it for it in items if it["kind"] == "glow"):
        key_intensity(spawned[it["label"]], [(0.0, 0.0), (T(4.0), 0.0), (T(8.0), 20.0)])

    # ---- Read back, save ----------------------------------------------------------------
    got = root.root_component.get_editor_property("relative_rotation")
    if abs(got.pitch + 90.0) > 0.05:
        fail(f"the root did not hang: {got}")
    rt = root.get_actor_transform()
    worst = 0.0
    for it in items:
        if it["kind"] in ("hinge",) and it.get("root"):
            continue
        a = spawned[it["label"]]
        rel = unreal.MathLibrary.inverse_transform_location(rt, a.get_actor_location())
        want = list(it["loc"])
        if it["parent"] == f"S{n} Hangar Roof Hinge" or it["label"] == f"S{n} Hangar Roof Hinge":
            continue                                   # turned upright: checked by the hinge's own rotation
        worst = max(worst, math.dist((rel.x, rel.y, rel.z), want))
    if worst > 0.5:
        fail(f"a piece landed {worst:.2f} cm off its plan (root-relative); NOTHING saved, backup {backup}")
    dirty_c = sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if dirty_c != [f"{SEQ_DIR}/{SEQ_NAME}"]:
        fail(f"unexpected dirty content {dirty_c}; NOTHING saved")
    if not unreal.EditorAssetLibrary.save_asset(f"{SEQ_DIR}/{SEQ_NAME}", only_if_is_dirty=False):
        fail("sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"HANGAR_BUILD_OK|S{n}|pieces={len(spawned)}|k={k:.3f}|counts={counts}|worst_cm={worst:.3f}|sequence={SEQ_NAME}"
               f"|end_s={END:.2f}|backup={backup}|dirty_after={after[0]}+{after[1]}")


main()
