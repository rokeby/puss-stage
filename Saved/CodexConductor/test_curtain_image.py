"""Offline harness for curtain_image.py (system Python, no Unreal). Every gate has a failing control.
Also checks the graph TABLE (every custom input wired once, every parameter used, node count) and a Python port of the
HLSL (picture centre, outside -> velvet, PlanarMinZCm, mirroring).
Run: python test_curtain_image.py -> CURTAIN_IMAGE_HARNESS|tests=..|checks=..|failed=..
"""
import importlib.util
import os
import re
import struct
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ci", os.path.join(HERE, "curtain_image.py"))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
assert ci.unreal is None, "harness must run without Unreal"

CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def raises(fn, prefix):
    try:
        fn()
    except ci.PlanError as exc:
        return str(exc).startswith(prefix)
    return False


def png_bytes(w, h):
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * w for _ in range(min(h, 2)))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@test
def t_defaults():
    d = ci.mi_defaults(1)
    check(d == {"PlanarY0Cm": -940.0, "PlanarWidthCm": 1880.0, "PlanarTopZCm": 1020.0, "PlanarHeightCm": 1000.0},
          "P01 final13 front: %r" % d)
    d = ci.mi_defaults(4)
    check(d["PlanarWidthCm"] == 1000.0 and d["PlanarHeightCm"] == 1200.0, "P04 backcloth front 10 x 12 m: %r" % d)
    check(raises(lambda: ci.mi_defaults(6), "OUT_OF_SCOPE"), "-control P06 refused")


@test
def t_png():
    tmp = tempfile.mkdtemp()
    good = os.path.join(tmp, "Gary's sky #1.png")
    open(good, "wb").write(png_bytes(4096, 2048))
    check(ci.png_size(good) == (4096, 2048), "IHDR size read")
    bad = os.path.join(tmp, "x.png")
    open(bad, "wb").write(b"JFIF" + b"\x00" * 40)
    check(raises(lambda: ci.png_size(bad), "NOT_A_PNG"), "-control a non-PNG refused")
    check(not ci.png_warnings((4096, 2048), 1), "+control 4096x2048 on an 18.8 x 10 m drape: no warnings")
    w = ci.png_warnings((3000, 1600), 1)
    check(any(x.startswith("NOT_POWER_OF_TWO") for x in w), "-control 3000x1600 warned NPOT")
    w = ci.png_warnings((2048, 2048), 1)
    check(any(x.startswith("ASPECT") for x in w), "-control square on a 1.88:1 drape warned")
    check(not any(x.startswith("ASPECT") for x in ci.png_warnings((2048, 2048), 1, {"PlanarWidthCm": 1000.0})),
          "+control mi_scalars rectangle changes the aspect check")
    check(any(x.startswith("LARGER_THAN_8192") for x in ci.png_warnings((16384, 8192), 1)), "-control 16k warned")
    name = ci.texture_name(4, good, "20261006013000")
    check(re.fullmatch(r"T_CurtainImage_P04_[A-Za-z0-9_]+_20261006013000", name) is not None, "asset-safe name: %s" % name)


@test
def t_args():
    ok = {"mode": "SET", "passage": 4, "png": "x.png", "confirm": "SET P04"}
    check(ci.validate_args(ok) == ("SET", 4), "SET P04 valid")
    check(raises(lambda: ci.validate_args(dict(ok, confirm="SET P4")), "CONFIRM_MISMATCH"), "-control confirm")
    check(raises(lambda: ci.validate_args(dict(ok, passage=6, confirm="SET P06")), "PASSAGE_OUT_OF_SCOPE"), "-control P06")
    check(raises(lambda: ci.validate_args(dict(ok, texture="/Game/T")), "SET_NEEDS_ONE_OF"), "-control png AND texture")
    check(raises(lambda: ci.validate_args(dict(ok, png=None)), "SET_NEEDS_ONE_OF"), "-control neither")
    check(raises(lambda: ci.validate_args(dict(ok, png=None, texture="C:/x.uasset")), "TEXTURE_NOT_GAME_PATH"),
          "-control texture outside /Game")
    check(raises(lambda: ci.validate_args(dict(ok, mi_scalars={"Glow": 1})), "UNKNOWN_MI_SCALARS"), "-control scalar")
    a = {"mode": "ASSIGN", "passage": 2, "confirm": "ASSIGN P02"}
    check(raises(lambda: ci.validate_args(a), "NOT_DECIDED"), "-control ASSIGN without decided_by")
    check(ci.validate_args(dict(a, decided_by="Gary 6 Oct"))[0] == "ASSIGN", "+control ASSIGN decided")
    check(ci.validate_args({"mode": "BUILD", "confirm": "BUILD ALL"}) == ("BUILD", None), "BUILD ALL")
    check(raises(lambda: ci.validate_args({"mode": "PAINT", "confirm": "PAINT ALL"}), "MODE_INVALID"), "-control mode")
    check(ci.set_values({}) == {"ImageAmount": 1.0}, "SET turns the picture on")
    check(ci.set_values({"mi_scalars": {"ImageAmount": 0.5}})["ImageAmount"] == 0.5, "mi_scalars override")


@test
def t_graph_table():
    params = set(ci.SCALARS) | set(ci.VECTORS) | set(ci.TEXTURES)
    keys = {"UV0", "WPos", "LPos"} | set(ci.CUSTOM) | params
    check(len(keys) == ci.EXPECTED_EXPRESSIONS, "node count %d == EXPECTED %d" % (len(keys), ci.EXPECTED_EXPRESSIONS))
    for s, _, d, _ in ci.EDGES:
        check(s in keys and d in keys, "edge keys exist: %s->%s" % (s, d))
    for key, (code, inputs, _) in ci.CUSTOM.items():
        wired = [e for e in ci.EDGES if e[2] == key]
        check(sorted(e[3] for e in wired) == sorted(inputs), "%s: every input wired exactly once" % key)
        for pin in inputs:
            check(re.search(r"\b%s\b" % pin, code) is not None, "%s uses its input %s" % (key, pin))
    used = {e[0] for e in ci.EDGES} | {p[0] for p in ci.PROPS}
    for p in params:
        check(p in used, "parameter %s is wired" % p)
    for p in ci.mi_defaults(1):
        check(p in ci.SCALARS, "MI default %s is a master scalar" % p)


def hlsl(uv, lp, s):
    """Python port of CODE_UV / CODE_MASK / CODE_BASE with the master defaults overridden by s."""
    S = {k: v[0] for k, v in ci.SCALARS.items()}
    S.update(s)
    sat = lambda x: max(0.0, min(1.0, x))
    a = ((uv[0] - S["RectU0"]) / S["RectUW"], (uv[1] - S["RectV0"]) / S["RectVH"])
    b = ((lp[1] - S["PlanarY0Cm"]) / S["PlanarWidthCm"], (S["PlanarTopZCm"] - lp[2]) / S["PlanarHeightCm"])
    t = sat(S["PlanarMapping"])
    p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    inside = float(0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0)
    above = 1.0 + ((1.0 if lp[2] >= S["PlanarMinZCm"] else 0.0) - 1.0) * t
    return p, inside * above


@test
def t_hlsl_port():
    d = dict(ci.mi_defaults(1), ImageAmount=1.0)
    p, m = hlsl((0.3, 0.3), (0.0, 0.0, 520.0), d)
    check(abs(p[0] - 0.5) < 1e-9 and abs(p[1] - 0.5) < 1e-9 and m == 1.0, "planar: drape centre is the picture centre")
    p, m = hlsl((0.3, 0.3), (0.0, -940.0, 1020.0), d)
    check(abs(p[0]) < 1e-9 and abs(p[1]) < 1e-9, "planar: top-left corner (y -940, z 1020) = (0, 0)")
    p, m = hlsl((0.3, 0.3), (0.0, 1200.0, 520.0), d)
    check(m == 0.0, "-control outside the drape's width: velvet")
    p, m = hlsl((0.3, 0.3), (0.0, 0.0, 60.0), dict(d, PlanarMinZCm=120.0))
    check(m == 0.0, "PlanarMinZCm 120 hides the picture on the pile")
    p, m = hlsl((0.3, 0.3), (0.0, 0.0, 60.0), d)
    check(m == 1.0, "+control default PlanarMinZCm shows it")
    p, _ = hlsl((0.3, 0.3), (0.0, -900.0, 520.0), dict(d, PlanarY0Cm=940.0, PlanarWidthCm=-1880.0))
    check(abs(p[0] - (940.0 + 900.0) / 1880.0) < 1e-9, "negative width mirrors left/right")
    p, m = hlsl((0.25, 0.75), (0.0, 5000.0, -50.0), dict(d, PlanarMapping=0.0))
    check(abs(p[0] - 0.25) < 1e-9 and abs(p[1] - 0.75) < 1e-9 and m == 1.0, "UV mode ignores position")


def main():
    for fn in TESTS:
        before = len(CHECKS["failed"])
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            CHECKS["failed"].append("%s raised %s: %s" % (fn.__name__, type(exc).__name__, exc))
        print("%-20s %s" % (fn.__name__, "ok" if len(CHECKS["failed"]) == before else "FAIL"))
    for f in CHECKS["failed"]:
        print("  FAILED: " + f)
    print("CURTAIN_IMAGE_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
