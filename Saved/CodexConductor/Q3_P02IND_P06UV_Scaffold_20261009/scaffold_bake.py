"""Dormant headless bake stage for FlatV3_ScaffoldBay.blend. Do not run during this task."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys

EXPECTED_BLEND = "E:/PussStage/DerivedAssets/FlatV3/BlenderTest/FlatV3_ScaffoldBay.blend"
OUTPUT = "E:/PussStage/DerivedAssets/FlatV3/BlenderTest/ScaffoldBake"
MAPS = ("BaseColor", "Normal", "Roughness", "NetOpacity")


def _require(value, message):
    if not value: raise RuntimeError(message)


def parse(argv):
    p = argparse.ArgumentParser(); p.add_argument("--mode", default="DRY", choices=("DRY", "APPLY", "REVERT")); p.add_argument("--confirm", default=""); a = vars(p.parse_args(argv))
    if a["mode"] != "DRY": _require(a["confirm"] == "%s P06SCAFFOLDBAKE" % a["mode"], "CONFIRM")
    return a


def plan(bpy):
    _require(bpy.app.background, "BACKGROUND_MODE_REQUIRED"); _require(os.path.normcase(os.path.abspath(bpy.data.filepath)) == os.path.normcase(os.path.abspath(EXPECTED_BLEND)), "WRONG_BLEND")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    _require(meshes, "NO_MESH_OBJECTS")
    return {"mode": "DRY", "run": "P06SCAFFOLDBAKE-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "marker": "P06SCAFFOLDBAKE_DRY_OK", "source": EXPECTED_BLEND, "mesh_objects": len(meshes), "outputs": [os.path.join(OUTPUT, "T_Scaffold_%s.png" % x) for x in MAPS],
            "resolution": 2048, "net_policy": "procedural alpha baked to NetOpacity; runtime material is dark gauze nearby and opaque at distance", "source_blend_saved": False}


def _image_node(bpy, material, image):
    material.use_nodes = True; node = material.node_tree.nodes.new("ShaderNodeTexImage"); node.name = "CODEX_BAKE_TARGET"; node.image = image; material.node_tree.nodes.active = node; node.select = True; return node


def _route_net_alpha(bpy, material):
    nodes, links = material.node_tree.nodes, material.node_tree.links
    output = next((n for n in nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    _require(output is not None and bsdf is not None and bsdf.inputs.get("Alpha") is not None, "NET_ALPHA_GRAPH|" + material.name)
    surface = output.inputs.get("Surface"); old = surface.links[0].from_socket if surface.links else None
    alpha = bsdf.inputs.get("Alpha"); emit = nodes.new("ShaderNodeEmission"); emit.name = "CODEX_NET_ALPHA_EMIT"
    if alpha.is_linked: links.new(alpha.links[0].from_socket, emit.inputs["Color"])
    else: emit.inputs["Color"].default_value = (float(alpha.default_value),) * 3 + (1.0,)
    for link in list(surface.links): links.remove(link)
    links.new(emit.outputs["Emission"], surface)
    return output, surface, old, emit


def _restore_route(material, route):
    output, surface, old, emit = route; links = material.node_tree.links
    for link in list(surface.links): links.remove(link)
    if old is not None: links.new(old, surface)
    material.node_tree.nodes.remove(emit)


def apply(bpy):
    p = plan(bpy); exists = [x for x in p["outputs"] if os.path.exists(x)]; _require(not exists, "CREATE_ONLY_EXISTS|" + json.dumps(exists)); os.makedirs(OUTPUT, exist_ok=True)
    run = "P06SCAFFOLDBAKE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"); record = os.path.join(OUTPUT, "bake_record.json")
    with open(record, "x", encoding="utf-8") as h: json.dump({"run": run, "plan": p}, h, indent=2)
    bpy.context.scene.render.engine = "CYCLES"; bpy.context.scene.cycles.device = "CPU"; bpy.context.scene.render.bake.margin = 16
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in objects: o.select_set(True)
    for map_name, bake_type in (("BaseColor", "DIFFUSE"), ("Normal", "NORMAL"), ("Roughness", "ROUGHNESS"), ("NetOpacity", "EMIT")):
        image = bpy.data.images.new("T_Scaffold_" + map_name, width=2048, height=2048, alpha=True)
        nodes = []
        for mat in {m for o in objects for m in o.data.materials if m}:
            nodes.append((mat, _image_node(bpy, mat, image)))
        routes = []
        if map_name == "NetOpacity":
            net_mats = [m for m, _ in nodes if "net" in m.name.lower()]; _require(net_mats, "NET_MATERIAL_MISSING")
            routes = [(m, _route_net_alpha(bpy, m)) for m in net_mats]
        bpy.ops.object.bake(type=bake_type, use_clear=True)
        image.filepath_raw = os.path.join(OUTPUT, "T_Scaffold_%s.png" % map_name); image.file_format = "PNG"; image.save()
        for mat, node in nodes: mat.node_tree.nodes.remove(node)
        for mat, route in routes: _restore_route(mat, route)
    result = {"mode": "APPLY", "run": run, "outputs": p["outputs"], "source_blend_saved": False, "marker": "P06SCAFFOLDBAKE_APPLY_OK"}; print(result["marker"]); return result


def revert():
    run = "P06SCAFFOLDBAKE-REVERT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"); record = os.path.join(OUTPUT, "bake_record.json"); _require(os.path.isfile(record), "NO_ACTIVE_RECORD")
    retired = os.path.join(os.path.dirname(EXPECTED_BLEND), "Backups", "PreP06ScaffoldBakeRevert-" + run, "retired_outputs"); os.makedirs(retired, exist_ok=False); moved = []
    for name in MAPS:
        path = os.path.join(OUTPUT, "T_Scaffold_%s.png" % name)
        if os.path.isfile(path):
            dest = os.path.join(retired, os.path.basename(path)); shutil.move(path, dest); moved.append(dest)
    archived = record + ".reverted-" + run; os.replace(record, archived)
    return {"mode": "REVERT", "run": run, "recoverable_outputs": moved, "record": archived, "marker": "P06SCAFFOLDBAKE_REVERT_OK"}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []; args = parse(argv); import bpy  # type: ignore
    result = plan(bpy) if args["mode"] == "DRY" else apply(bpy) if args["mode"] == "APPLY" else revert(); print("%s|run=%s" % (result["marker"], result["run"])); print(json.dumps(result, indent=2)); return result


if __name__ == "__main__": main()
