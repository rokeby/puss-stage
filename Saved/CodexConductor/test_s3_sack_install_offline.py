"""Offline harness for s3_sack_install.py (no Unreal). Every gate has a NEGATIVE CONTROL that must fail.

Part A: pure helpers on the REAL source files (Blender JSONs, the _SK.fbx / _SK_root.fbx finals, the UE body
        export, the texture manifest), with broken copies as negative controls.
Part B: APPLY -> VERIFY -> REVERT through the tool's own unreal glue against a FAKE `unreal` module (an in-memory
        level with six figures). The fake models what the glue calls; it proves the tool's logic (records, read-back
        gates, census, revert), NOT the UE API behaviour (that is the live DRY's job). IMPORT and BUILD_MAT glue are
        not faked (their APIs are too wide to model honestly): their pure gates are tested in Part A.
Run: python Saved/CodexConductor/test_s3_sack_install_offline.py   -> exit 0 and S3SACK_OFFLINE_OK
"""
import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = []


def load():
    spec = importlib.util.spec_from_file_location("_t_s3_sack_install", os.path.join(HERE, "s3_sack_install.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = load()


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})


def raises(fn, *a, contains=None, **kw):
    try:
        fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001
        return contains is None or contains in str(exc)
    return False


# ================================================================================================ Part A
def t_tables():
    check("six figures, Shore02 uses the 2.0 m back-pin final", len(S.FIGURES) == 6 and
          S.SOURCE_ID["Shore02_F52"] == "Shore02_F52_Sack_alt2p0", S.SOURCE_ID)
    check("Shore02 decision = 2.0 m back pin", S.DECISION["Shore02_F52"] == {"size_x": 2.0, "size_y": 2.0,
                                                                            "crown": "back", "pin_forward": 0.0})
    check("targets under /Game/Metahuman/ShoreCast_20260910/Sack",
          all(S.mesh_path(f).startswith("/Game/Metahuman/ShoreCast_20260910/Sack/SKM_Sack_") for f in S.FIGURES))
    check("slot MIs: Front/Edge outer, Back inner", S.SLOT_MI == {"Front": S.MI_OUTER, "Back": S.MI_INNER,
                                                                  "Edge": S.MI_OUTER})
    check("MIs parent the MASKED master (fringe on every slot, plan 10.3)", S.MI_PARENT == S.M_MASKED)


def t_sources():
    for f in S.FIGURES:
        sf = S.source_files(f)
        src = json.load(open(sf["json"], encoding="utf-8"))
        summ = S.fbx_skeleton_summary(sf["fbx"])
        rx = json.load(open(sf["fbx"] + ".json", encoding="utf-8"))
        probs = (S.reexport_problems(rx, sf) + S.source_problems(f, src, summ) +
                 S.fbx_structure_problems(summ, expected_bones=int(src["skin"]["exported_bones"]) + 1) +
                 S.fbx_content_problems(summ))
        check("source %s (_SK_root.fbx + JSON + re-export report) passes every gate" % f, not probs, probs)
        o, e = S.expected_box_cm(rx["bbox_world_m"])
        check("source %s: exact box agrees with the loose Blender-metric gate (cross-check)" % f,
              not S.bounds_problems(src, o, e), S.bounds_problems(src, o, e))
        check("source %s: re-export head bone == the Blender JSON pose head" % f,
              all(abs(a - b) < 1e-3 for a, b in zip(rx["head_world_m"], src["pose"]["head_bone_m"])))
        orig = S.fbx_skeleton_summary(sf["fbx_original"])
        op = S.fbx_structure_problems(orig, expected_bones=int(src["skin"]["exported_bones"]) + 1)
        check("NEG %s original _SK.fbx fails the root gate (why _SK_root exists)" % f,
              any(p.startswith("ROOT_BONE_MISSING") for p in op) and any(p.startswith("NOT_Z_UP") for p in op), op)
        check("%s: re-exported bone names == UE body export bone names" % f,
              set(summ["bones"]) == set(S.fbx_skeleton_summary(
                  os.path.join(PROJECT, "DerivedAssets", "S3Sackcloth", "bodies", f, f + "_Body.fbx"))["bones"]))
    body = S.fbx_skeleton_summary(os.path.join(PROJECT, "DerivedAssets", "S3Sackcloth", "bodies", "Shore01_M56",
                                               "Shore01_M56_Body.fbx"))
    check("POS control: UE's own body export passes the structure gate (parser + gate agree with UE)",
          not S.fbx_structure_problems(body, expected_bones=342), S.fbx_structure_problems(body))
    # decision controls: the other Shore02 finals must be refused
    for sid, why in (("Shore02_F52_Sack", "1.8 m"), ("Shore02_F52_Sack_altHeadPin", "crown pin")):
        src = json.load(open(S.FINALS + sid + ".json", encoding="utf-8"))
        p = S.source_problems("Shore02_F52", src)
        check("NEG Shore02 %s final is refused by the decision gate" % why, any(x.startswith("DECISION") for x in p), p)
    src = json.load(open(S.source_files("Shore01_M56")["json"], encoding="utf-8"))
    bad = copy.deepcopy(src)
    bad["checks"]["skin_roundtrip_within_5mm"] = False
    check("NEG a failed Blender check is refused", any("BLENDER_CHECKS" in x for x in S.source_problems("Shore01_M56", bad)))
    bad = copy.deepcopy(src)
    bad["skin"]["unweighted_vertices"] = 500
    check("NEG >1% unweighted vertices is refused", any("SKIN_WEIGHTS" in x for x in S.source_problems("Shore01_M56", bad)))
    check("NEG wrong figure's JSON is refused", any("FIGURE_OR_MODE" in x or "DECISION" in x
                                                    for x in S.source_problems("Shore03_M59", src)))
    sf = S.source_files("Shore01_M56")
    rx = json.load(open(sf["fbx"] + ".json", encoding="utf-8"))
    bad = copy.deepcopy(rx)
    bad["checks"]["weights_within_1e-5"] = False
    bad["ok"] = False
    check("NEG a failed re-export report is refused", any("REEXPORT_NOT_OK" in x for x in S.reexport_problems(bad, sf)))
    bad = copy.deepcopy(rx)
    bad["src"] = S.FINALS + "Shore03_M59_Sack_SK.fbx"
    check("NEG a re-export of another file is refused", any("REEXPORT_SOURCE" in x for x in S.reexport_problems(bad, sf)))
    summ = S.fbx_skeleton_summary(sf["fbx"])
    bad = copy.deepcopy(summ)
    bad["materials"] = ["Sack_Front", "Sack_Back"]
    check("NEG a two-slot FBX is refused", any("SLOTS" in x for x in S.fbx_content_problems(bad)))
    bad = copy.deepcopy(summ)
    bad["uv_sets"] = ["UVMap"]
    check("NEG an FBX without the FrayMask UV set is refused", any("UV_SETS" in x for x in S.fbx_content_problems(bad)))


def t_bounds():
    rx = json.load(open(S.source_files("Shore02_F52")["fbx"] + ".json", encoding="utf-8"))
    src = json.load(open(S.source_files("Shore02_F52")["json"], encoding="utf-8"))
    box = rx["bbox_world_m"]
    o, e = S.expected_box_cm(box)
    check("bounds: exact box passes", not S.bounds_problems(src, o, e, bbox_world_m=box))
    check("NEG bounds: a Y-mirrored import fails", S.bounds_problems(src, [o[0], -o[1], o[2]], e, bbox_world_m=box))
    check("NEG bounds: a 180-degree-turned import fails", S.bounds_problems(src, [-o[0], -o[1], o[2]], e, bbox_world_m=box))
    check("NEG bounds: a 2 cm shift fails", S.bounds_problems(src, [o[0] + 2.0, o[1], o[2]], e, bbox_world_m=box))
    check("NEG bounds: metres-as-cm (x100) fails", S.bounds_problems(src, [v / 100 for v in o], [v / 100 for v in e],
                                                                     bbox_world_m=box))
    check("NEG loose gate: 1.5 m-wide footprint fails", S.bounds_problems(src, o, [75.0, e[1], e[2]]))


def t_slots():
    check("slots classified", S.classify_slots(["Sack_Front", "Sack_Back", "Sack_Edge"]) ==
          {"Front": 0, "Back": 1, "Edge": 2})
    check("slots: any order", S.classify_slots(["Sack_Edge", "Sack_Front", "Sack_Back"])["Front"] == 1)
    check("NEG slots: missing Edge", raises(S.classify_slots, ["Sack_Front", "Sack_Back", "X"], contains="SLOTS"))
    check("NEG slots: two Front", raises(S.classify_slots, ["Sack_Front", "Sack_Front2", "Sack_Back"], contains="SLOTS"))
    check("NEG slots: four slots", raises(S.classify_slots, ["Sack_Front", "Sack_Back", "Sack_Edge", "Y"]))
    exp = S.apply_expectation("Shore01_M56", {"Front": 2, "Back": 0, "Edge": 1})
    check("apply expectation follows slot indices", exp["materials"] == [S.MI_INNER, S.MI_OUTER, S.MI_OUTER])


def t_interchange():
    w = S.interchange_wanted("SKM_Sack_Shore01_M56")
    check("pipeline: wanted == wanted passes", not S.interchange_problems(w, dict(w)))
    for key, val, why in ((("mesh", "update_skeleton_reference_pose"), True, "would rewrite the shared skeleton"),
                          (("mesh", "create_physics_asset"), True, "physics asset"),
                          (("common_skeletal", "skeleton"), "/Game/Other/Skel", "other skeleton"),
                          (("common_skeletal", "use_t0_as_ref_pose"), True, "T0 as ref pose"),
                          (("material", "import_materials"), 1, "int 1 is not True (setter-lie shape)"),
                          (("pipeline", "import_offset_uniform_scale"), 100.0, "x100 scale")):
        g = dict(w)
        g[key] = val
        check("NEG pipeline: %s fails" % why, S.interchange_problems(w, g))
    g = dict(w)
    g.pop(("animation", "import_animations"))
    check("NEG pipeline: an unreadable value fails", S.interchange_problems(w, g))
    check("pipeline never touches the skeleton", w[("mesh", "update_skeleton_reference_pose")] is False and
          w[("common_skeletal", "add_curve_metadata_to_skeleton")] is False)


def t_textures():
    man = json.load(open(S.TEX_SRC + "manifest.json", encoding="utf-8"))
    for key, (src_key, _n, _c, _s) in S.TEXTURES.items():
        path = S.TEX_SRC + man["files"][src_key]["file"]
        check("texture %s source sha256 == manifest" % key, S.sha256_file(path) == man["files"][src_key]["sha256"])
    try:
        from PIL import Image
        modes = {k: Image.open(S.TEX_SRC + man["files"][v[0]]["file"]).mode for k, v in S.TEXTURES.items()}
        sizes = {k: Image.open(S.TEX_SRC + man["files"][v[0]]["file"]).size for k, v in S.TEXTURES.items()}
        check("R/AO/H are 16-bit sources (I;16) -> TC_GRAYSCALE keeps G16 [decl TextureDefines.h:396]",
              all(modes[k] == "I;16" for k in ("R", "AO", "H")), modes)
        check("sources are NPOT (2048 x 2036): pow2 mode needed", all(s == (2048, 2036) for s in sizes.values()), sizes)
    except ImportError:
        check("PIL unavailable: 16-bit check skipped (UNCLEAR)", True)
    good = {"compression": "TextureCompressionSettings.TC_GRAYSCALE", "srgb": False, "flip_green": False,
            "pow2": "TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO", "size_x": 2048, "size_y": 2048}
    check("texture settings: rough correct passes", not S.texture_settings_problems("R", good, "STRETCH_TO_POWER_OF_TWO"))
    for mut, why in (({"srgb": True}, "sRGB on a mask"), ({"compression": "TC_MASKS"}, "TC_MASKS"),
                     ({"size_y": 2036}, "still NPOT"), ({"pow2": "NONE"}, "pow2 not applied")):
        g = dict(good)
        g.update(mut)
        check("NEG texture: %s fails" % why, S.texture_settings_problems("R", g, "STRETCH_TO_POWER_OF_TWO"))
    g = dict(good, size_y=2036)
    check("BUILD_MAT defers the size gate to VERIFY (platform data may lag the setter)",
          not S.texture_settings_problems("R", g, "STRETCH_TO_POWER_OF_TWO", check_size=False))
    n = dict(good, compression="TC_NORMALMAP", flip_green=True)
    check("NEG texture: green-flipped DX normal fails", S.texture_settings_problems("N", n, "STRETCH_TO_POWER_OF_TWO"))
    check("sampler: linear grayscale for TC_GRAYSCALE sRGB off",
          S.sampler_for("TC_GRAYSCALE", False) == "SAMPLERTYPE_LINEAR_GRAYSCALE")
    check("sampler: normal", S.sampler_for("<TextureCompressionSettings.TC_NORMALMAP: 1>", False) == "SAMPLERTYPE_NORMAL")
    check("NEG sampler: unknown compression raises", raises(S.sampler_for, "TC_HDR", False, contains="SAMPLER_UNMAPPED"))


def t_graph():
    check("graph: opaque master spec consistent", not S.graph_problems(False), S.graph_problems(False))
    check("graph: masked master spec consistent", not S.graph_problems(True), S.graph_problems(True))
    nodes, edges, props = S.graph_spec(False)
    check("opaque master has no fringe / opacity", "SK_Fringe" not in nodes and
          all(p[2] != "MP_OPACITY_MASK" for p in props))
    check("masked master wires MP_OPACITY_MASK from SK_Fringe", ("SK_Fringe", "", "MP_OPACITY_MASK") in S.graph_spec(True)[2])
    for code_key, (code, inputs, _t, _m) in S.CUSTOM.items():
        missing = [i for i in inputs if i not in code]
        check("HLSL %s uses every declared input" % code_key, not missing, missing)
    saved = (S.EDGES, S.PROPS, S.CUSTOM)
    try:
        S.EDGES = [e for e in saved[0] if e[2:4] != ("SK_Base", "Fres")]
        check("NEG graph: a dropped edge is caught", any("CUSTOM_PIN" in p for p in S.graph_problems(False)))
        S.EDGES = saved[0] + [("TileM", "", "SK_Base", "Inner", False)]
        check("NEG graph: a pin fed twice is caught", any("CUSTOM_PIN" in p for p in S.graph_problems(False)))
        S.EDGES = saved[0] + [("Desaturate", "", "SK_Rough", "Bogus", False)]
        check("NEG graph: an unknown pin is caught", any("UNKNOWN_PIN" in p for p in S.graph_problems(False)))
        S.EDGES = [e for e in saved[0] if e[0] != "RimExponent"]
        check("NEG graph: an unused parameter is caught",
              any("UNUSED_NODE|RimExponent" in p for p in S.graph_problems(False)))
        S.EDGES = saved[0]
        S.PROPS = [p for p in saved[1] if p[2] != "MP_AMBIENT_OCCLUSION"]
        check("NEG graph: a missing material property is caught", any("PROPS" in p for p in S.graph_problems(False)))
        S.PROPS = saved[1]
        S.EDGES = saved[0] + [("UV1", "", "SK_Base", "Mottle2", False)]
        bad_custom = dict(saved[2])
        bad_custom["SK_Base"] = (saved[2]["SK_Base"][0], saved[2]["SK_Base"][1] + ["Mottle2"], "F3", False)
        S.CUSTOM = bad_custom
        check("NEG graph: one source into two pins of a node is caught",
              any("SOURCE_FEEDS_TWO_PINS" in p for p in S.graph_problems(False)))
    finally:
        S.EDGES, S.PROPS, S.CUSTOM = saved


def t_mis():
    master_scalars = list(S.SCALARS) + list(S.MASKED_SCALARS)
    for name, want in S.MI_VALUES.items():
        sc = dict(want["scalars"])
        vc = {k: list(v) for k, v in want["vectors"].items()}
        ov = {k: True for k in list(sc) + list(vc)}
        check("MI %s read-back passes" % name.rsplit("/", 1)[1], not S.mi_problems(name, sc, vc, ov, master_scalars))
        ov2 = dict(ov, RoughnessScale=False)
        check("NEG MI %s: value equal to the master default but NOT overridden (setter lie) fails" % name.rsplit("/", 1)[1],
              any("NOT_OVERRIDDEN" in p for p in S.mi_problems(name, sc, vc, ov2, master_scalars)))
        sc2 = dict(sc, Desaturate=0.0)
        check("NEG MI %s: wrong value fails" % name.rsplit("/", 1)[1], S.mi_problems(name, sc2, vc, ov, master_scalars))
        check("NEG MI %s: parameter missing on the master fails" % name.rsplit("/", 1)[1],
              S.mi_problems(name, sc, vc, ov, [m for m in master_scalars if m != "Desaturate"]))
    check("Inner = outer + InnerDarken 0.7 + NormalStrength 0.6",
          S.MI_VALUES[S.MI_INNER]["scalars"]["InnerDarken"] == 0.7 and
          S.MI_VALUES[S.MI_INNER]["scalars"]["NormalStrength"] == 0.6 and
          "InnerDarken" not in S.MI_VALUES[S.MI_OUTER]["scalars"])
    check("old grey: desaturated grey-brown tint (R >= G >= B, all < 0.7)",
          all(S.MI_VALUES[n]["vectors"]["Tint"][0] >= S.MI_VALUES[n]["vectors"]["Tint"][1] >=
              S.MI_VALUES[n]["vectors"]["Tint"][2] and max(S.MI_VALUES[n]["vectors"]["Tint"]) < 0.7
              for n in S.MI_VALUES) and S.MI_VALUES[S.MI_OUTER]["scalars"]["Desaturate"] >= 0.5)


def t_modes():
    none = {"IMPORT": False, "BUILD_MAT": False, "APPLY": False}
    check("default mode DRY, six figures", S.check_mode({}, none)[:2] == ("DRY", list(S.FIGURES)))
    for mode in S.WRITE_MODES:
        check("NEG %s without confirm refuses" % mode, raises(S.check_mode, {"mode": mode}, dict(none, APPLY=True,
                                                                                               IMPORT=True, BUILD_MAT=False),
                                                           contains="CONFIRM_MISSING"))
        check("NEG %s with another tool's word refuses" % mode,
              raises(S.check_mode, {"mode": mode, "confirm": "%s S3SKIN" % mode}, none, contains="CONFIRM"))
    ok = {"mode": "APPLY", "confirm": "APPLY S3SACK"}
    check("APPLY with both prerequisite records passes", S.check_mode(ok, dict(none, IMPORT=True, BUILD_MAT=True))[0] == "APPLY")
    check("NEG APPLY without the mat record refuses", raises(S.check_mode, ok, dict(none, IMPORT=True), contains="PREREQ"))
    check("NEG APPLY twice refuses", raises(S.check_mode, ok, {"IMPORT": True, "BUILD_MAT": True, "APPLY": True},
                                            contains="ALREADY_APPLIED"))
    check("NEG REVERT without a record refuses", raises(S.check_mode, {"mode": "REVERT", "confirm": "REVERT S3SACK"}, none,
                                                        contains="NO_APPLY_RECORD"))
    check("NEG BUILD_MAT twice refuses", raises(S.check_mode, {"mode": "BUILD_MAT", "confirm": "BUILD_MAT S3SACK"},
                                                dict(none, BUILD_MAT=True), contains="ALREADY_BUILT"))
    check("NEG VERIFY with nothing to verify refuses", raises(S.check_mode, {"mode": "VERIFY"}, none))
    check("NEG unknown figure refuses", raises(S.check_mode, {"figures": ["Shore07_X"]}, none, contains="FIGURES"))
    check("NEG duplicate figure refuses", raises(S.check_mode, {"figures": ["Shore01_M56"] * 2}, none, contains="FIGURES"))
    check("NEG bounds_scale 5 refuses", raises(S.check_mode, {"bounds_scale": 5}, none, contains="BOUNDS_SCALE"))
    check("NEG unknown cloth switch refuses", raises(S.check_mode, {"cloth_switch": "delete"}, none, contains="CLOTH_SWITCH"))
    check("NEG original _SK.fbx suffix still allowed only by explicit arg",
          S.check_mode({"fbx_suffix": "_SK.fbx"}, none)[2]["fbx_suffix"] == "_SK.fbx")


def t_census_and_cloth():
    figs = list(S.FIGURES)
    p = S.planned_packages("IMPORT", figs)
    check("IMPORT plans exactly the six meshes", p == {"content": sorted(S.mesh_path(f) for f in figs), "maps": []})
    check("census: exact passes", S.census_ok(dict(p), p))
    check("NEG census: the shared skeleton dirty fails", not S.census_ok({"content": p["content"] + [S.SKELETON],
                                                                          "maps": []}, p))
    check("NEG census: map dirty during IMPORT fails", not S.census_ok({"content": p["content"], "maps": [S.WORLD]}, p))
    check("BUILD_MAT plans 6 textures + 2 masters + 2 MIs", len(S.planned_packages("BUILD_MAT", [])["content"]) == 10)
    check("APPLY/REVERT plan only the map", S.planned_packages("APPLY", figs) == {"content": [], "maps": [S.WORLD]} ==
          S.planned_packages("REVERT", figs))
    b = {"visible": True, "hidden_in_game": False, "enabled": True, "suspended": False}
    check("cloth: suspend+disable target", S.cloth_target(b, "suspend+disable") ==
          {"visible": False, "hidden_in_game": False, "enabled": False, "suspended": True})
    check("cloth: suspend-only keeps 'enabled'", S.cloth_target(b, "suspend")["enabled"] is True)
    check("cloth target does not mutate 'before'", b["visible"] is True)


# ================================================================================================ Part B: fake unreal
class _Obj:
    def __init__(self, path, name=None):
        self._path, self._name = path, name or path.rsplit(".", 1)[-1].rsplit("/", 1)[-1].rsplit(":", 1)[-1]

    def get_path_name(self):
        return self._path

    def get_name(self):
        return self._name

    def get_class(self):
        return _Cls(type(self).__name__)


class _Cls:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


def make_fake(world_path, quirks):
    """quirks: set of fault injections (negative controls)."""
    st = {"dirty_maps": set(), "dirty_content": set(), "saved_maps": 0, "assets": {}, "actors": [], "quirks": quirks}

    class FakeUnreal:
        pass

    U = FakeUnreal()

    class Text(str):
        pass

    class ActorComponent(_Obj):
        def __init__(self, path, name, owner):
            super().__init__(path, name)
            self.owner, self.props = owner, {}

        def modify(self):
            st["dirty_maps"].add(world_path)

        def get_editor_property(self, k):
            if k not in self.props:
                raise AttributeError(k)
            return self.props[k]

        def set_editor_property(self, k, v):
            st["dirty_maps"].add(world_path)
            if k == "suspend_simulation" and "cloth_suspend_lies" in quirks:
                return
            self.props[k] = v

    class SceneComponent(ActorComponent):
        def __init__(self, path, name, owner, parent=None):
            super().__init__(path, name, owner)
            self.parent = parent
            self.props.update({"hidden_in_game": False, "relative_location": U.Vector(0, 0, 0), "bounds_scale": 1.0})
            self.visible = True

        def get_attach_parent(self):
            return self.parent

        def get_attach_socket_name(self):
            return "None"

        def is_visible(self):
            return self.visible

        def set_visibility(self, v, propagate=False):
            st["dirty_maps"].add(world_path)
            self.visible = bool(v)

    class SkinnedMeshComponent(SceneComponent):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.mesh, self.overrides = None, []
            self.props["leader_pose_component"] = None

        def get_skeletal_mesh_asset(self):
            return self.mesh

        def set_skeletal_mesh_asset(self, m):
            st["dirty_maps"].add(world_path)
            self.mesh = m

        def get_num_materials(self):
            return len(self.mesh.slots) if self.mesh else 0

        def get_material(self, i):
            if i < len(self.overrides) and self.overrides[i] is not None:
                return self.overrides[i]
            return self.mesh.defaults[i]

        def set_material(self, i, m):
            st["dirty_maps"].add(world_path)
            while len(self.overrides) <= i:
                self.overrides.append(None)
            self.overrides[i] = m

        def get_editor_property(self, k):
            if k == "override_materials":
                return list(self.overrides)
            return super().get_editor_property(k)

        def set_leader_pose_component(self, leader, force=False):
            st["dirty_maps"].add(world_path)
            if "leader_lies" not in quirks:
                self.props["leader_pose_component"] = leader

        def get_num_bones(self):
            return len(self.mesh.bones) if self.mesh else 0

        def get_bone_name(self, i):
            return self.mesh.bones[i]

    class SkeletalMeshComponent(SkinnedMeshComponent):
        pass

    class ChaosClothComponent(SceneComponent):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.props.update({"suspend_simulation": False, "enable_simulation": True})

        def is_simulation_enabled(self):
            return self.props["enable_simulation"]

        def is_simulation_suspended(self):
            return self.props["suspend_simulation"]

    class Actor(_Obj):
        def __init__(self, path, label, cls):
            super().__init__(path)
            self.label, self.cls, self.comps = label, cls, []

        def get_actor_label(self):
            return self.label

        def get_class(self):
            return _Cls(self.cls)

        def modify(self):
            st["dirty_maps"].add(world_path)

        def get_components_by_class(self, cls):
            return [c for c in self.comps if isinstance(c, cls)]

    class Mesh(_Obj):
        def __init__(self, path, slots, defaults, bones, skeleton):
            super().__init__(path + "." + path.rsplit("/", 1)[1])
            self.slots, self.defaults, self.bones, self.skeleton = slots, defaults, bones, skeleton

        def get_editor_property(self, k):
            if k == "skeleton":
                return self.skeleton
            if k == "materials":
                return [_Slot(n) for n in self.slots]
            raise AttributeError(k)

    class _Slot:
        def __init__(self, n):
            self.n = n

        def get_editor_property(self, k):
            return self.n

    class Vector:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    class Handle:
        def __init__(self, obj, is_actor=False, valid=True):
            self.obj, self.is_actor, self.valid = obj, is_actor, valid

    class Lib:
        @staticmethod
        def get_data(h):
            return h

        @staticmethod
        def get_object(d):
            return d.obj

        @staticmethod
        def is_handle_valid(h):
            return h.valid

        @staticmethod
        def is_instanced_component(d):
            return getattr(d.obj, "instance", False)

        @staticmethod
        def is_actor(d):
            return d.is_actor

    class AddNewSubobjectParams:
        def __init__(self):
            self.p = {}

        def set_editor_property(self, k, v):
            self.p[k] = v

    class SubobjectDataSubsystem:
        def k2_gather_subobject_data_for_instance(self, actor):
            return [Handle(actor, is_actor=True)] + [Handle(c) for c in actor.comps]

        def add_new_subobject(self, params):
            parent = params.p["parent_handle"].obj
            actor = parent.owner
            c = SkeletalMeshComponent(actor.get_path_name() + ".SkeletalMeshComponent_0", "SkeletalMeshComponent_0",
                                      actor, parent)
            c.instance = True
            actor.comps.append(c)
            st["dirty_maps"].add(world_path)
            return Handle(c), Text("")

        def rename_subobject(self, h, name):
            h.obj._name = str(name)
            return True

        def delete_subobject(self, ctx, target, bp):
            if "delete_fails" in quirks:
                return 0
            actor = ctx.obj
            actor.comps.remove(target.obj)
            st["dirty_maps"].add(world_path)
            return 1

    sub = SubobjectDataSubsystem()

    class World(_Obj):
        def get_outermost(self):
            return _Obj(world_path, world_path)

    world = World(world_path + "." + world_path.rsplit("/", 1)[1])

    class Editor:
        def get_editor_world(self):
            return world

        def get_game_world(self):
            return None

    class ActorSub:
        def get_all_level_actors(self):
            return list(st["actors"])

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def get_dirty_content_packages():
            return [_Obj(p, p) for p in sorted(st["dirty_content"])]

        @staticmethod
        def get_dirty_map_packages():
            return [_Obj(p, p) for p in sorted(st["dirty_maps"])]

        @staticmethod
        def save_map(w, path):
            st["dirty_maps"].discard(path)
            st["saved_maps"] += 1
            return True

    class EditorAssetLibrary:
        @staticmethod
        def does_asset_exist(p):
            return p in st["assets"]

        @staticmethod
        def save_asset(p, only_if_is_dirty=False):
            st["dirty_content"].discard(p)
            return True

    class GameplayStatics:
        @staticmethod
        def get_all_actors_of_class(w, cls):
            return list(st["actors"]) + list(st.get("transient", []))

    U.Text, U.Vector, U.ActorComponent, U.SkeletalMeshComponent = Text, Vector, ActorComponent, SkeletalMeshComponent
    U.SkinnedMeshComponent, U.Actor, U.AddNewSubobjectParams = SkinnedMeshComponent, Actor, AddNewSubobjectParams
    U.SubobjectDataSubsystem, U.SubobjectDataBlueprintFunctionLibrary = SubobjectDataSubsystem, Lib
    U.EditorLoadingAndSavingUtils, U.EditorAssetLibrary, U.GameplayStatics = (EditorLoadingAndSavingUtils,
                                                                              EditorAssetLibrary, GameplayStatics)
    U.UnrealEditorSubsystem, U.EditorActorSubsystem = Editor, ActorSub
    U.get_editor_subsystem = lambda cls: Editor() if cls is Editor else ActorSub()
    U.get_engine_subsystem = lambda cls: sub
    U.load_asset = lambda p: st["assets"].get(p)
    U.logs = []
    U.log = lambda m: U.logs.append(("log", m))
    U.log_warning = lambda m: U.logs.append(("warn", m))
    U.log_error = lambda m: U.logs.append(("error", m))
    U.Mesh, U.ChaosClothComponent, U.st = Mesh, ChaosClothComponent, st
    return U


def build_level(mod, U):
    st = U.st
    bones = ["root", "pelvis", "spine_01", "head"]
    skel = _Obj(mod.SKELETON + ".metahuman_base_skel")
    for p in [mod.MI_OUTER, mod.MI_INNER]:
        st["assets"][p] = _Obj(p + "." + p.rsplit("/", 1)[1])
    skin_rec = {"run": "S3SKIN-FAKE", "target": "level", "saved": True, "plan": {}}
    for i, f in enumerate(mod.FIGURES):
        mp = mod.mesh_path(f)
        st["assets"][mp] = U.Mesh(mp, ["Sack_Front", "Sack_Back", "Sack_Edge"], [None] * 3, bones, skel)
        a = U.Actor("/Game/Map.Map:PersistentLevel.BP_%s_Draped_C_0" % f, f + " Clam", "BP_%s_Draped_C" % f)
        root = U.SkeletalMeshComponent(a.get_path_name() + ".Root", "Root", a)
        body = U.SkeletalMeshComponent(a.get_path_name() + ".Body", "Body", a, root)
        body.mesh = U.Mesh("/Game/Body/SKM_%s" % f, ["body"], [_Obj("/Game/M/MI_Body.MI_Body")], bones, skel)
        skin_mi = _Obj("/Game/Metahuman/ShoreCast_20260910/Skin/MI_S3Skin_%s_Body_v1.x" % f)
        body.overrides = [skin_mi]
        face = U.SkeletalMeshComponent(a.get_path_name() + ".Face", "Face", a, body)
        face.mesh = U.Mesh("/Game/Face/SKM_%s" % f, ["a", "b"], [None, None], bones, skel)
        face_mi = _Obj("/Game/Metahuman/ShoreCast_20260910/Skin/MI_S3Skin_%s_Face_v1.x" % f)
        face.overrides = [None, face_mi]
        cloth = U.ChaosClothComponent(a.get_path_name() + ".ShoreHeadCloth", "ShoreHeadCloth", a, body)
        a.comps = [root, body, face, cloth]
        st["actors"].append(a)
        skin_rec["plan"][f] = {"components": {"Body": {"override_after": [mod._path(skin_mi)]},
                                              "Face": {"override_after": [None, mod._path(face_mi)]}}}
    return skin_rec


def run_fake(quirks=(), figures=None, steps=("APPLY", "VERIFY", "REVERT"), mutate_between=None, transient=None):
    mod = load()
    tmp = tempfile.mkdtemp(prefix="s3sack_")
    try:
        U = make_fake(mod.WORLD, set(quirks))
        skin_rec = build_level(mod, U)
        if transient:
            U.st["transient"] = [U.Actor("/T", transient, "Actor")]
        mod.unreal = U
        mod.HERE = tmp + "/"
        mod.ARGS = tmp + "/args.json"
        mod.RECORDS = {k: tmp + "/" + os.path.basename(v) for k, v in mod.RECORDS.items()}
        mod.DRY_OUT, mod.VERIFY_OUT = tmp + "/dry.json", tmp + "/verify.json"
        mod.BACKUP_ROOT = tmp + "/Backups/PreS3Sack-"
        mod.UMAP = tmp + "/L.umap"
        mod.SKIN_RECORD = tmp + "/skin.json"
        with open(mod.UMAP, "wb") as h:
            h.write(b"umap-bytes")
        json.dump(skin_rec, open(mod.SKIN_RECORD, "w"))
        figs = figures or list(mod.FIGURES)
        json.dump({"figures": {f: {"saved": True, "mesh": mod.mesh_path(f)} for f in figs}},
                  open(mod.RECORDS["IMPORT"], "w"))
        json.dump({"saved": True, "opts": {"pow2_mode": "STRETCH_TO_POWER_OF_TWO"}}, open(mod.RECORDS["BUILD_MAT"], "w"))
        out = {"errors": [], "states": {}}
        before = {f: _snapshot(mod, U, f) for f in figs}
        out["states"]["before"] = before
        for step in steps:
            args = {"mode": step, "confirm": "%s S3SACK" % step if step in mod.WRITE_MODES else "", "figures": figs}
            json.dump(args, open(mod.ARGS, "w"))
            if mutate_between and step in mutate_between:
                mutate_between[step](mod, U)
            # VERIFY reads the IMPORT/BUILD_MAT records too; the fake has no assets for them -> hide them for VERIFY
            hidden = {}
            if step == "VERIFY":
                for k in ("IMPORT", "BUILD_MAT"):
                    if os.path.exists(mod.RECORDS[k]):
                        os.replace(mod.RECORDS[k], mod.RECORDS[k] + ".hidden")
                        hidden[k] = True
            try:
                mod.main()
                out[step] = "OK"
            except Exception as exc:  # noqa: BLE001
                out[step] = "FAILED"
                out["errors"].append("%s|%s" % (step, exc))
            for k in hidden:
                os.replace(mod.RECORDS[k] + ".hidden", mod.RECORDS[k])
            out["states"][step] = {f: _snapshot(mod, U, f) for f in figs}
            out["dirty_after_" + step] = sorted(U.st["dirty_maps"])
            if out[step] == "FAILED":
                break
        out["saved_maps"] = U.st["saved_maps"]
        out["apply_record_exists"] = os.path.exists(mod.RECORDS["APPLY"])
        out["logs"] = [l for l in U.logs if "S3SACK_" in l[1]]
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _snapshot(mod, U, f):
    a = [x for x in U.st["actors"] if x.label == f + " Clam"][0]
    cl = [c for c in a.comps if c.get_name() == "ShoreHeadCloth"][0]
    sack = [c for c in a.comps if c.get_name() == "SackSK"]
    body = [c for c in a.comps if c.get_name() == "Body"][0]
    face = [c for c in a.comps if c.get_name() == "Face"][0]
    return {"cloth": (cl.visible, cl.props["suspend_simulation"], cl.props["enable_simulation"]),
            "sack": len(sack), "sack_leader": sack[0].props["leader_pose_component"] is body if sack else None,
            "sack_mats": [mod._path(m) for m in sack[0].overrides] if sack else None,
            "body": [mod._path(m) for m in body.overrides], "face": [mod._path(m) for m in face.overrides]}


def t_fake():
    r = run_fake()
    check("FAKE happy path: APPLY, VERIFY, REVERT all OK", (r.get("APPLY"), r.get("VERIFY"), r.get("REVERT")) ==
          ("OK", "OK", "OK"), r["errors"])
    a = r["states"].get("APPLY", {})
    check("FAKE after APPLY: one SackSK per figure, leader = Body, slot MIs, cloth hidden+suspended+disabled",
          a and all(s["sack"] == 1 and s["sack_leader"] and s["cloth"] == (False, True, False) and
                    s["sack_mats"] == [S.MI_OUTER, S.MI_INNER, S.MI_OUTER] for s in a.values()), a)
    check("FAKE skin overrides untouched by APPLY", a and all(a[f]["body"] == r["states"]["before"][f]["body"] and
                                                              a[f]["face"] == r["states"]["before"][f]["face"] for f in a))
    check("FAKE REVERT restores the exact before-state", r["states"].get("REVERT") == r["states"]["before"],
          r["states"].get("REVERT"))
    check("FAKE saves: one map save each for APPLY and REVERT, nothing left dirty",
          r["saved_maps"] == 2 and r.get("dirty_after_REVERT") == [], (r["saved_maps"], r.get("dirty_after_REVERT")))
    check("FAKE OK markers carry the run id", any(l[1].startswith("S3SACK_APPLY_OK|run=S3SACK-") for l in r["logs"]))

    r = run_fake(quirks={"leader_lies"}, steps=("APPLY",))
    check("NEG FAKE leader setter that does nothing: APPLY fails before saving",
          r["APPLY"] == "FAILED" and r["saved_maps"] == 0 and "SACK_LEADER" in " ".join(r["errors"]), r["errors"])
    check("NEG FAKE failed APPLY leaves no live apply record (renamed .failed)", not r["apply_record_exists"])
    r = run_fake(quirks={"cloth_suspend_lies"}, steps=("APPLY",))
    check("NEG FAKE cloth suspend setter that lies: APPLY fails, nothing saved",
          r["APPLY"] == "FAILED" and r["saved_maps"] == 0 and "CLOTH_READBACK" in " ".join(r["errors"]), r["errors"])

    def dirty_extra(mod, U):
        U.st["dirty_content"].add("/Game/Someone/Else")
    r = run_fake(steps=("APPLY",), mutate_between={"APPLY": dirty_extra})
    check("NEG FAKE editor dirty before APPLY: refuses with nothing touched",
          r["APPLY"] == "FAILED" and "DIRTY_BEFORE" in " ".join(r["errors"]) and
          all(s["sack"] == 0 for s in r["states"]["APPLY"].values()), r["errors"])

    def skin_changed(mod, U):
        orig = U.SkeletalMeshComponent.set_leader_pose_component

        def evil(self, leader, force=False):
            orig(self, leader, force)
            body = [c for c in self.owner.comps if c.get_name() == "Body"][0]
            body.overrides = [None]
        U.SkeletalMeshComponent.set_leader_pose_component = evil
    r = run_fake(steps=("APPLY",), mutate_between={"APPLY": skin_changed})
    check("NEG FAKE a skin override changed during APPLY: refused, not saved",
          r["APPLY"] == "FAILED" and r["saved_maps"] == 0 and "UNTOUCHED_CHANGED" in " ".join(r["errors"]), r["errors"])

    def drift(mod, U):
        a = [x for x in U.st["actors"] if x.label == "Shore03_M59 Clam"][0]
        s = [c for c in a.comps if c.get_name() == "SackSK"][0]
        s.overrides[0] = _Obj("/Game/Other/MI_X.MI_X")
    r = run_fake(steps=("APPLY", "REVERT"), mutate_between={"REVERT": drift})
    check("NEG FAKE REVERT after drift refuses (state changed since APPLY)",
          r["APPLY"] == "OK" and r["REVERT"] == "FAILED" and "DRIFT_SINCE_APPLY" in " ".join(r["errors"]), r["errors"])
    r = run_fake(steps=("APPLY", "VERIFY"), mutate_between={"VERIFY": drift})
    check("NEG FAKE VERIFY catches a changed sack material", r["VERIFY"] == "FAILED" and
          "SACK_MATERIALS" in " ".join(r["errors"]), r["errors"])
    r = run_fake(quirks={"delete_fails"}, steps=("APPLY", "REVERT"))
    check("NEG FAKE delete_subobject returning 0: REVERT fails, map not saved again",
          r["REVERT"] == "FAILED" and r["saved_maps"] == 1 and "DELETE_SUBOBJECT" in " ".join(r["errors"]), r["errors"])
    r = run_fake(steps=("APPLY",), transient="ZZ_BenchProbe")
    check("NEG FAKE a transient ZZ_ bench actor blocks APPLY",
          r["APPLY"] == "FAILED" and "TEMP_ACTORS_PRESENT" in " ".join(r["errors"]), r["errors"])
    r = run_fake(figures=["Shore02_F52"], steps=("APPLY", "VERIFY", "REVERT"))
    check("FAKE pilot (Shore02 only) APPLY/VERIFY/REVERT OK", (r.get("APPLY"), r.get("VERIFY"), r.get("REVERT")) ==
          ("OK", "OK", "OK"), r["errors"])


def main():
    for t in (t_tables, t_sources, t_bounds, t_slots, t_interchange, t_textures, t_graph, t_mis, t_modes,
              t_census_and_cloth, t_fake):
        try:
            t()
        except Exception as exc:  # noqa: BLE001 - a crashed test is a failed test
            check("%s crashed" % t.__name__, False, repr(exc))
    fails = [r for r in RESULTS if not r["pass"]]
    report = {"checks": len(RESULTS), "fails": fails, "results": RESULTS}
    with open(os.path.join(HERE, "test_s3_sack_install_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    for r in fails:
        print("FAIL", r["check"], r["detail"])
    print("S3SACK_OFFLINE_%s|checks=%d|fails=%d" % ("OK" if not fails else "FAILED", len(RESULTS), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
