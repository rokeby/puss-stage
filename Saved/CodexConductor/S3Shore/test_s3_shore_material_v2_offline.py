"""Offline harness for s3_shore_material_v2.py (no Unreal).

python Saved/CodexConductor/S3Shore/test_s3_shore_material_v2_offline.py
Every check runs on the shipped module (must PASS) and on a broken copy / hostile mock (must FAIL), so a verifier
that cannot fail is caught.  Writes test_s3_shore_material_v2_offline_report.json next to this file.
Tiers: the graph / code / mock checks are MEASURED against this harness's fake `unreal` (they prove the script's
logic and gates, not UE behaviour); the HLSL math checks evaluate the ACTUAL code strings for the rotation path and a
Python MIRROR for the noise (mirror = inferred to match the HLSL).
"""
import ast
import copy
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
V2_PATH = os.path.join(HERE, "s3_shore_material_v2.py")
V1_PATH = os.path.join(HERE, "s3_shore_ground_ue.py")
REPORT = os.path.join(HERE, "test_s3_shore_material_v2_offline_report.json")


def load_v2(source=None, fake=None):
    """Fresh module instance; optional replacement source text and fake unreal."""
    spec = importlib.util.spec_from_file_location("s3mat2_%d" % id(source), V2_PATH)
    mod = importlib.util.module_from_spec(spec)
    saved = sys.modules.get("unreal")
    if fake is not None:
        sys.modules["unreal"] = fake
    else:
        sys.modules.pop("unreal", None)
    try:
        code = source if source is not None else open(V2_PATH, encoding="utf-8").read()
        exec(compile(code, V2_PATH, "exec"), mod.__dict__)
    finally:
        if saved is not None:
            sys.modules["unreal"] = saved
        else:
            sys.modules.pop("unreal", None)
    return mod


def v1_constants():
    """CODE_* / SCALARS / TEX / TEX_PARAMS from v1 by ast (v1 is never imported or executed)."""
    tree = ast.parse(open(V1_PATH, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.startswith("CODE_") or name in ("SCALARS", "TEX", "TEX_PARAMS", "MASTER", "MI", "ASSET_DIR"):
                try:
                    out[name] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    out["MASTER"] = "/Game/InfinityStage/Dev/Generated/S3Shore/M_S3_ShoreGround"   # v1: ASSET_DIR + "/M_..."
    out["MI"] = "/Game/InfinityStage/Dev/Generated/S3Shore/MI_S3_ShoreGround"
    return out


# ----------------------------------------------------------------------------- checks (pure)
def check_graph(mod, spec=None):
    return mod.graph_problems(spec)


def check_v1_port(mod, v1):
    probs = []
    for k in ("CODE_TILE", "CODE_MUDW", "CODE_BASE", "CODE_ROUGH", "CODE_NORMAL"):
        if getattr(mod, k) != v1[k]:
            probs.append("CODE_DIFFERS|" + k)
    for k, v in v1["SCALARS"].items():
        if mod.SCALARS.get(k) != v:
            probs.append("SCALAR_DIFFERS|%s|%s|%s" % (k, mod.SCALARS.get(k), v))
    if mod.PARAM_TEX != v1["TEX_PARAMS"]:
        probs.append("TEX_PARAMS_DIFFER")
    for k, path in v1["TEX"].items():
        if k != "MossNormal" and mod.TEX.get(k) != path:
            probs.append("TEX_DIFFERS|" + k)
    # the v1 custom wiring of SH_Base/SH_Rough/SH_Normal: same pin set and code
    for key in ("SH_Base", "SH_Rough", "SH_Normal", "MudW"):
        code, ins, _t = mod.CUSTOM[key]
        v1code = {"SH_Base": v1["CODE_BASE"], "SH_Rough": v1["CODE_ROUGH"], "SH_Normal": v1["CODE_NORMAL"],
                  "MudW": v1["CODE_MUDW"]}[key]
        if code != v1code:
            probs.append("CUSTOM_CODE_DIFFERS|" + key)
    return probs


FORBIDDEN = [r"\bdelete_", r"\bdestroy", r"reload_packages", r"save_dirty", r"save_directory", r"save_packages",
             r"\bsave_map\b", r"save_current_level", r"rename_asset", r"duplicate_asset", r"consolidate"]


def check_source_safety(src, v1):
    probs = []
    code_only = "\n".join(l.split("#", 1)[0] for l in src.splitlines())
    tree = ast.parse(src)
    strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for pat in FORBIDDEN:
        # strip docstrings/strings: only look at call attribute names in the AST
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and re.search(pat, n.attr):
                probs.append("FORBIDDEN_CALL|%s" % n.attr)
    # create_asset / save_asset targets must be MASTER2 / MI2 (or the `planned` list built from them)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "create_asset":
            a0 = ast.unparse(n.args[0]) if n.args else ""
            if "MASTER2" not in a0 and "MI2" not in a0:
                probs.append("CREATE_TARGET|%s" % a0)
    if re.search(r"set_editor_property\(\s*\"parent\"", code_only):
        probs.append("REPARENT_CALL")
    # v1 names may appear ONLY inside V1_ASSETS (hash / refusal) -- never as a create/save target
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("MASTER2", "MI2") for t in n.targets):
            val = ast.unparse(n.value)
            if val.endswith("/M_S3_ShoreGround'") or val.endswith("/MI_S3_ShoreGround'") \
                    or val.endswith("/M_S3_ShoreGround\"") or val.endswith("/MI_S3_ShoreGround\""):
                probs.append("V2_NAME_IS_V1|%s" % val)
    if not any("S3SHOREMAT2_OK" in x for x in strings) or not any("S3SHOREMAT2_FAILED" in x for x in strings):
        probs.append("MARKERS")
    return probs


def check_names(mod, v1):
    probs = []
    if mod.MASTER2 in (v1["MASTER"], v1["MI"]) or mod.MI2 in (v1["MASTER"], v1["MI"]):
        probs.append("V2_NAME_EQUALS_V1")
    if not (mod.MASTER2.endswith("_v2") and mod.MI2.endswith("_v2")):
        probs.append("V2_SUFFIX")
    return probs


# ----------------------------------------------------------------------------- HLSL evaluation (actual strings)
class V:
    def __init__(self, *c):
        self.c = [float(x) for x in c]

    x = property(lambda s: s.c[0])
    y = property(lambda s: s.c[1])
    z = property(lambda s: s.c[2])

    def _op(self, o, f):
        oc = o.c if isinstance(o, V) else [o] * len(self.c)
        return V(*[f(a, b) for a, b in zip(self.c, oc)])

    def __add__(self, o): return self._op(o, lambda a, b: a + b)
    __radd__ = __add__
    def __sub__(self, o): return self._op(o, lambda a, b: a - b)
    def __mul__(self, o): return self._op(o, lambda a, b: a * b)
    __rmul__ = __mul__
    def __truediv__(self, o): return self._op(o, lambda a, b: a / b)


def eval_hlsl_lines(code, env, stop_after=None):
    """Straight-line HLSL subset: 'type name = expr;' / 'return expr;'.  Returns (env, return value)."""
    g = {"float2": V, "float3": V, "radians": math.radians, "sin": math.sin, "cos": math.cos, "max": max,
         "saturate": lambda v: min(max(v, 0.0), 1.0)}
    g.update(env)
    ret = None
    for line in code.split("\n"):
        line = line.strip().rstrip(";")
        m = re.match(r"^(?:float[23]?\s+)?(\w+)\s*=\s*(.+)$", line)
        if line.startswith("return "):
            ret = eval(line[len("return "):], g)
            break
        if m:
            g[m.group(1)] = eval(m.group(2), g)
            if stop_after and m.group(1) == stop_after:
                break
        else:
            raise ValueError("UNSUPPORTED_LINE|" + line)
    return g, ret


def check_rotation(mod, code_tile=None, code_norm=None):
    """Tangent-frame check on the REAL strings: a surface direction v maps to texture direction R(a)v under
    TileSandB; SH_SandNormal must rotate a texture-frame vector R(a)v back to v.  Returns problems."""
    code_tile = code_tile or mod.CODE_TILE_ROT
    code_norm = code_norm or mod.CODE_SAND_NORMAL
    probs = []
    rot = mod.SCALARS["SandRot2Deg"][0]
    tile = mod.SCALARS["SandTileM2"][0]
    for vdeg in (0.0, 30.0, 90.0, 200.0):
        v = (math.cos(math.radians(vdeg)), math.sin(math.radians(vdeg)))
        p0 = V(3.0, 2.0)
        eps = 1e-3

        def tf(p):
            return eval_hlsl_lines(code_tile, {"UV": p, "TileM": tile, "Rot": rot, "OffX": 0.37, "OffY": 0.61})[1]
        t0, t1 = tf(p0), tf(p0 + V(v[0] * eps, v[1] * eps))
        tv = ((t1.x - t0.x) / eps * tile, (t1.y - t0.y) / eps * tile)      # = R(a) v
        nb = V(tv[0], tv[1], 1.0)
        g, _ = eval_hlsl_lines(code_norm, {"NB": nb, "Rot": rot, "N": V(0.5, 0.5), "BC": 1.0}, stop_after="b")
        b = g["b"]
        if abs(b.x - v[0]) > 1e-3 or abs(b.y - v[1]) > 1e-3:
            probs.append("NORMAL_NOT_BACK_ROTATED|v=%s|b=(%.3f,%.3f)" % (vdeg, b.x, b.y))
    return probs


# ----------------------------------------------------------------------------- noise (Python MIRROR of CODE_NOISE)
def noise_mirror(uv, blend_m, macro_m):
    def fr(x):
        return x - math.floor(x)
    res = [0.5, 0.5]
    for k in range(2):
        per = max(blend_m, 0.01) if k == 0 else max(macro_m, 0.01)
        p = [uv[0] / per + 17.3 * k, uv[1] / per + 5.1 * k]
        acc, amp, nrm = 0.0, 0.5, 0.0
        for _o in range(3):
            i = [math.floor(p[0]), math.floor(p[1])]
            f = [p[0] - i[0], p[1] - i[1]]
            u = [f[0] * f[0] * (3 - 2 * f[0]), f[1] * f[1] * (3 - 2 * f[1])]

            def h(a, b):
                return fr(math.sin(a * 127.1 + b * 311.7) * 43758.5453)
            h00, h10, h01, h11 = h(i[0], i[1]), h(i[0] + 1, i[1]), h(i[0], i[1] + 1), h(i[0] + 1, i[1] + 1)
            a = h00 + (h10 - h00) * u[0]
            b = h01 + (h11 - h01) * u[0]
            acc += amp * (a + (b - a) * u[1])
            nrm += amp
            amp *= 0.5
            p = [p[0] * 2.03 + 3.7, p[1] * 2.03 + 1.9]
        res[k] = acc / nrm
    return res


def check_noise_coverage(blend_m, macro_m, bc):
    """Over the 60 x 20 m floor (UV metres, LANDED_LOCAL_BOX of v1): both scales must win somewhere (w < 0.2 and
    w > 0.8 each on >= 5 % of samples) and w must differ between x and x + SandTileM on >= 50 % of samples
    (otherwise the 1.5 m repeat survives the blend)."""
    probs = []
    ws, shifted, n = [], 0, 0
    for ix in range(0, 61):
        for iy in range(-10, 11):
            x, y = float(ix), float(iy)
            nz = noise_mirror((x, y), blend_m, macro_m)
            nz2 = noise_mirror((x + 1.5, y), blend_m, macro_m)
            if not (0.0 <= nz[0] <= 1.0 and 0.0 <= nz[1] <= 1.0):
                probs.append("NOISE_RANGE|%s" % nz)
            w = min(max((nz[0] - 0.5) * bc + 0.5, 0.0), 1.0)
            w2 = min(max((nz2[0] - 0.5) * bc + 0.5, 0.0), 1.0)
            ws.append(w)
            shifted += abs(w - w2) > 0.02
            n += 1
    lo = sum(w < 0.2 for w in ws) / n
    hi = sum(w > 0.8 for w in ws) / n
    if lo < 0.05 or hi < 0.05:
        probs.append("BLEND_COVERAGE|lo=%.3f|hi=%.3f" % (lo, hi))
    if shifted / n < 0.5:
        probs.append("BLEND_REPEATS_WITH_TILE|%.3f" % (shifted / n))
    return probs, {"w_lt_0.2": round(lo, 3), "w_gt_0.8": round(hi, 3), "differs_at_+1.5m": round(shifted / n, 3)}


# ----------------------------------------------------------------------------- fake unreal for the build path
def make_fake(state):
    fake = types.ModuleType("unreal")
    fake._S3SHOREMAT2_FAKE = True
    log = state.setdefault("log", [])
    dirty = state.setdefault("dirty", set())
    assets = state.setdefault("assets", {})                 # path -> object
    saved = state.setdefault("saved", [])
    created = state.setdefault("created", [])

    class Pkg:
        def __init__(self, n): self.n = n
        def get_name(self): return self.n

    class Obj:
        def __init__(self, path=None):
            self.props, self.path = {}, path
        def set_editor_property(self, k, v): self.props[k] = v
        def get_editor_property(self, k): return self.props.get(k)
        def get_path_name(self): return self.path
        def modify(self): return True

    class Texture2D(Obj):
        def blueprint_get_size_x(self): return self.props.get("size", 2048)
        def blueprint_get_size_y(self): return self.props.get("size", 2048)

    class Material(Obj):
        def __init__(self, path):
            super().__init__(path)
            self.nodes, self.links, self.out = [], [], {}

    class MaterialInstanceConstant(Obj):
        def __init__(self, path):
            super().__init__(path)
            self.tex = {}

    class CustomInput(Obj):
        pass

    class Expr(Obj):
        kind = "x"

    def expr_cls(name, kind):
        return type(name, (Expr,), {"kind": kind})

    fake.Texture2D, fake.Material, fake.MaterialInstanceConstant, fake.CustomInput = \
        Texture2D, Material, MaterialInstanceConstant, CustomInput
    fake.MaterialExpressionScalarParameter = expr_cls("Scalar", "scalar")
    fake.MaterialExpressionTextureSampleParameter2D = expr_cls("TexP", "texture")
    fake.MaterialExpressionTextureCoordinate = expr_cls("TC", "fixed")
    fake.MaterialExpressionVertexColor = expr_cls("VCx", "fixed")
    fake.MaterialExpressionCustom = expr_cls("Custom", "custom")
    fake.MaterialFactoryNew = fake.MaterialInstanceConstantFactoryNew = lambda: None
    fake.BlendMode = types.SimpleNamespace(BLEND_OPAQUE="BLEND_OPAQUE")
    fake.MaterialShadingModel = types.SimpleNamespace(MSM_DEFAULT_LIT="MSM_DEFAULT_LIT")
    fake.CustomMaterialOutputType = types.SimpleNamespace(CMOT_FLOAT1=1, CMOT_FLOAT2=2, CMOT_FLOAT3=3)
    fake.MaterialSamplerType = types.SimpleNamespace(**{k: k for k in (
        "SAMPLERTYPE_COLOR", "SAMPLERTYPE_NORMAL", "SAMPLERTYPE_LINEAR_GRAYSCALE", "SAMPLERTYPE_GRAYSCALE",
        "SAMPLERTYPE_MASKS", "SAMPLERTYPE_LINEAR_COLOR")})
    fake.MaterialProperty = types.SimpleNamespace(MP_BASE_COLOR="BC", MP_ROUGHNESS="R", MP_NORMAL="N", MP_SPECULAR="S")
    fake.log = lambda m: log.append(("log", m))
    fake.log_error = lambda m: log.append(("error", m))
    fake.SystemLibrary = types.SimpleNamespace(collect_garbage=lambda: log.append(("gc", "")))

    textures = state.setdefault("textures", {})

    def load_asset(p):
        return textures.get(p) or assets.get(p)
    fake.load_asset = load_asset

    def create_asset(name, folder, cls, _factory):
        path = folder + "/" + name
        if path in assets:
            return None
        o = cls(path)
        assets[path] = o
        dirty.add(path)
        created.append(path)
        return o
    fake.AssetToolsHelpers = types.SimpleNamespace(
        get_asset_tools=lambda: types.SimpleNamespace(create_asset=create_asset))

    def save_asset(p, only_if_is_dirty=True):
        saved.append(p)
        dirty.discard(p)
        hook = state.get("on_save")
        if hook:
            hook(p)
        return True
    fake.EditorAssetLibrary = types.SimpleNamespace(
        does_asset_exist=lambda p: p in assets, does_directory_exist=lambda p: True,
        list_assets=lambda d, recursive=True: [p + "." + p.rsplit("/", 1)[1] for p in assets if p.startswith(d)],
        save_asset=save_asset)
    fake.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_content_packages=lambda: [Pkg(p) for p in sorted(dirty) if not p.endswith(".umap")],
        get_dirty_map_packages=lambda: [Pkg(p) for p in sorted(dirty) if p.endswith(".umap")])

    def cme(mat, cls, _x, _y):
        n = cls()
        mat.nodes.append(n)
        return n

    def input_names(n):
        if n.kind == "custom":
            return [c.get_editor_property("input_name") for c in n.get_editor_property("inputs")]
        if n.kind == "texture":
            return ["UVs", "Tex", "ApplyViewMipBias"]
        return []

    def connect(a, o, b, pin):
        if pin not in input_names(b):
            return False
        for m in state.get("mats", []):
            pass
        state.setdefault("links", []).append((id(a), o, id(b), pin))
        return True

    def tex_names(mat):
        return sorted({n.get_editor_property("parameter_name") for n in mat.nodes if n.kind == "texture"})

    def mi_tex_get(mi, p):
        if p in mi.tex:
            return mi.tex[p]
        par = mi.get_editor_property("parent")
        for n in par.nodes:
            if n.kind == "texture" and n.get_editor_property("parameter_name") == p:
                return n.get_editor_property("texture")
        return None

    def mi_tex_set(mi, p, t):
        if state.get("setter_drops"):
            return True                               # hostile: claims success, stores nothing
        mi.tex[p] = t
        return False                                  # the UE 5.8 lie (memory): stored, returns False

    def mi_scalar(mi, k):
        for n in mi.get_editor_property("parent").nodes:
            if n.kind == "scalar" and n.get_editor_property("parameter_name") == k:
                return n.get_editor_property("default_value")
        return 0.0

    fake.MaterialEditingLibrary = types.SimpleNamespace(
        create_material_expression=cme, connect_material_expressions=connect,
        get_material_expression_input_names=input_names,
        connect_material_property=lambda n, o, prop: True,
        recompile_material=lambda m: state.get("compile_errors", []),
        get_material_expressions=lambda m: list(m.nodes),
        set_material_instance_parent=lambda mi, m: mi.set_editor_property("parent", m),
        get_texture_parameter_names=tex_names,
        set_material_instance_texture_parameter_value=mi_tex_set,
        update_material_instance=lambda mi: None,
        get_material_instance_texture_parameter_value=mi_tex_get,
        get_material_instance_scalar_parameter_value=mi_scalar)
    return fake


def make_textures(mod, fake, state, sampler_override=None):
    def tex(path, comp, srgb):
        t = fake.Texture2D(path)
        t.set_editor_property("compression_settings", comp)
        t.set_editor_property("srgb", srgb)
        return t
    kinds = {"Albedo": ("TC_Default", True), "Normal": ("TC_Normalmap", False), "Roughness": ("TC_Grayscale", False),
             "_col": ("TC_Default", True)}
    paths = list(mod.TEX.values()) + [p for s in mod.MI_TEXTURE_SETS.values() for p in s.values()]
    for p in paths:
        for suf, (comp, srgb) in kinds.items():
            if p.endswith(suf):
                state["textures"][p] = tex(p, comp, srgb)
    for p, (comp, srgb) in (sampler_override or {}).items():
        state["textures"][p] = tex(p, comp, srgb)


def mock_build(scenario):
    """Run run_build_mat_v2 against the fake.  Returns (ok, reason, state)."""
    state = {}
    fake = make_fake(state)
    mod = load_v2(fake=fake)
    tmp = tempfile.mkdtemp(prefix="s3mat2_")
    v1a, v1b = os.path.join(tmp, "M_v1.uasset"), os.path.join(tmp, "MI_v1.uasset")
    for p in (v1a, v1b):
        open(p, "wb").write(b"v1-bytes-" + p.encode())
    mod.V1_FILES = (v1a, v1b)
    mod.RECORD = os.path.join(tmp, "record.json")
    make_textures(mod, fake, state, scenario.get("textures"))
    for p in mod.V1_ASSETS:                                   # v1 exists in the folder (as live)
        state["assets"][p] = fake.Material(p)
    for p in scenario.get("existing", []):
        state["assets"][p] = fake.Material(p)
    for p in scenario.get("dirty", []):
        state["dirty"].add(p)
    state["setter_drops"] = scenario.get("setter_drops", False)
    if scenario.get("touch_v1_on_save"):
        state["on_save"] = lambda p: open(v1a, "ab").write(b"x")
    for k, v in scenario.get("patch", {}).items():
        setattr(mod, k, v)
    try:
        rec = mod.run_build_mat_v2("TEST", scenario.get("args", {}))
        return True, rec, state
    except RuntimeError as exc:
        return False, str(exc), state


# ----------------------------------------------------------------------------- main
def main():
    results = []

    def record(name, positive_ok, negatives, detail=None):
        """positive_ok: shipped passes.  negatives: list of (label, failed_as_expected)."""
        ok = bool(positive_ok) and all(f for _l, f in negatives)
        results.append({"check": name, "pass": ok, "shipped_ok": bool(positive_ok),
                        "controls": [{"control": l, "failed_as_expected": bool(f)} for l, f in negatives],
                        "detail": detail})

    mod = load_v2()
    v1 = v1_constants()
    src = open(V2_PATH, encoding="utf-8").read()

    # 1 graph wiring
    gp = check_graph(mod)
    nodes, edges, props = mod.graph_spec()
    neg = []
    e2 = [e for e in edges if e != ("SandNormalD", "RGB", "SH_SandNormal", "ND")]
    neg.append(("drop detail-normal edge", bool(check_graph(mod, (nodes, e2, props)))))
    neg.append(("pin fed twice", bool(check_graph(mod, (nodes, edges + [("SandTileM", "", "TileSandA", "TileM")], props)))))
    n3 = dict(nodes)
    n3["Noise"] = ("custom", (mod.CODE_NOISE.replace("MacroM", "Macro_"), ["UV", "BlendM", "MacroM"], "F2"))
    neg.append(("custom pin unused in code", bool(check_graph(mod, (n3, edges, props)))))
    neg.append(("cycle", bool(check_graph(mod, (nodes, edges + [("SH_Base", "", "TileSandA", "Rot")], props)))))
    neg.append(("texture UV unfed", bool(check_graph(mod, (nodes, [e for e in edges if e[2] != "SandRoughB"], props)))))
    record("graph_wiring", not gp, neg, {"problems": gp, "nodes": len(nodes), "edges": len(edges)})

    # 2 v1 logic ported verbatim
    p2 = check_v1_port(mod, v1)
    bad = copy.deepcopy(v1)
    bad["CODE_BASE"] = bad["CODE_BASE"].replace("WetD", "WetD * 0.9")
    bad2 = copy.deepcopy(v1)
    bad2["SCALARS"]["WetDarken"] = (0.6, "30 Wet")
    record("v1_vertex_colour_logic_verbatim", not p2,
           [("v1 CODE_BASE changed", bool(check_v1_port(mod, bad))),
            ("v1 scalar default changed", bool(check_v1_port(mod, bad2)))], {"problems": p2})

    # 3 v1 untouched (static): names + source safety
    p3 = check_names(mod, v1) + check_source_safety(src, v1)
    hostile = src.replace("    for p in planned:\n", "    mel.delete_material_expression(mat, None)\n    for p in planned:\n", 1)
    hostile2 = src.replace('MASTER2 = ASSET_DIR + "/M_S3_ShoreGround_v2"', 'MASTER2 = ASSET_DIR + "/M_S3_ShoreGround"')
    mod_h2 = load_v2(source=hostile2)
    record("v1_untouched_static", not p3,
           [("delete call injected", bool(check_source_safety(hostile, v1))),
            ("v2 master named as v1", bool(check_names(mod_h2, v1) + check_source_safety(hostile2, v1)))],
           {"problems": p3})

    # 4 mocked build: success + refusals
    ok, rec, st = mock_build({})
    pos = ok and sorted(st["saved"]) == sorted([mod.MASTER2, mod.MI2]) and sorted(st["created"]) == sorted([mod.MASTER2, mod.MI2])
    ok4, rec4, st4 = mock_build({"args": {"mi_texture_set": "PJUUZ_4K"}})
    pos4 = ok4 and rec4["mi_textures"]["SandAlbedo"].endswith("pjuuz_4K_Albedo") \
        and rec4["mi_textures"]["MossAlbedo"].endswith("TEX_MWL_GroundMoss_col")
    record("mock_build_success_saves_only_v2", pos and pos4, [],
           {"saved": st["saved"], "created": st["created"], "nodes": rec["nodes"] if ok else rec,
            "pjuuz4k_ok": pos4, "pjuuz4k_detail": rec4 if not ok4 else rec4["mi_textures"]})

    refusals = [
        ("v2 master exists", {"existing": [mod.MASTER2]}, "EXISTS|"),
        ("v2 MI exists", {"existing": [mod.MI2]}, "EXISTS|"),
        ("dirty editor", {"dirty": ["/Game/Somewhere/Else"]}, "DIRTY_EDITOR"),
        ("name pointed at v1", {"patch": {"MASTER2": mod.V1_ASSETS[0]}}, "EXISTS|"),
        ("override sampler mismatch", {"args": {"mi_textures": {"SandRoughT": "/Game/X/T_Wrong"}},
                                       "textures": {"/Game/X/T_Wrong": ("TC_Default", True)}}, "MI_OVERRIDE_SAMPLER"),
        ("unknown override param", {"args": {"mi_textures": {"NotAParam": "/Game/X"}}}, "MI_TEXTURE_PARAM_UNKNOWN"),
        ("setter claims success, stores nothing", {"args": {"mi_texture_set": "PJUUZ_4K"}, "setter_drops": True},
         "MI_TEXTURE_READBACK"),
        ("v1 file changes during run", {"touch_v1_on_save": True}, "V1_CHANGED"),
        ("compile error", {}, "RECOMPILE"),
    ]
    neg = []
    detail = {}
    for label, sc, want in refusals:
        if label == "compile error":
            state = {}
            fake = make_fake(state)
            m = load_v2(fake=fake)
            make_textures(m, fake, state)
            state["compile_errors"] = ["boom"]
            tmp = tempfile.mkdtemp(prefix="s3mat2_")
            m.V1_FILES = ()
            m.RECORD = os.path.join(tmp, "r.json")
            try:
                m.run_build_mat_v2("T", {})
                got_ok, reason = True, "no refusal"
            except RuntimeError as exc:
                got_ok, reason = False, str(exc)
            created = state["created"]
            saved = state["saved"]
        else:
            got_ok, reason, s = mock_build(sc)
            created, saved = s["created"], s["saved"]
        refused = (not got_ok) and reason.startswith(want)
        pre_create = want in ("EXISTS|", "DIRTY_EDITOR", "MI_OVERRIDE_SAMPLER", "MI_TEXTURE_PARAM_UNKNOWN")
        nothing_saved_early = (not saved) if want != "V1_CHANGED" else True
        nothing_created = (not created) if pre_create else True
        neg.append((label, refused and nothing_saved_early and nothing_created))
        detail[label] = {"reason": reason, "created": created, "saved": saved}
    record("mock_build_refusals", ok, neg, detail)   # positive = the clean scenario does NOT refuse

    # 5 rotation of the B-scale normal (actual HLSL strings, straight-line subset evaluated)
    p5 = check_rotation(mod)
    wrong = mod.CODE_SAND_NORMAL.replace("float2(c * NB.x + s * NB.y, -s * NB.x + c * NB.y)",
                                         "float2(c * NB.x - s * NB.y, s * NB.x + c * NB.y)")
    record("b_scale_normal_back_rotated", not p5, [("rotation sign flipped", bool(check_rotation(mod, code_norm=wrong)))],
           {"problems": p5})

    # 6 anti-tiling coverage (noise MIRROR)
    s = mod.SCALARS
    p6, stats = check_noise_coverage(s["BlendNoiseM"][0], s["MacroNoiseM"][0], s["BlendContrast"][0])
    p6b, stats_b = check_noise_coverage(1000.0, s["MacroNoiseM"][0], s["BlendContrast"][0])
    p6c, stats_c = check_noise_coverage(s["BlendNoiseM"][0], s["MacroNoiseM"][0], 0.0)   # w stuck at 0.5
    record("anti_tiling_blend_coverage", not p6,
           [("blend noise period 1000 m (no variation)", bool(p6b)),
            ("BlendContrast 0 (both scales always 50/50)", bool(p6c))],
           {"shipped": stats, "period_1000": stats_b, "contrast_0": stats_c, "tier": "mirror (inferred == HLSL)"})

    allpass = all(r["pass"] for r in results)
    out = {"all_pass": allpass, "results": results}
    with open(REPORT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, default=str)
    for r in results:
        print("%-40s %s  controls=%s" % (r["check"], "PASS" if r["pass"] else "FAIL",
                                         [c["failed_as_expected"] for c in r["controls"]]))
    print("ALL_PASS" if allpass else "SOME_FAIL", REPORT)
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
