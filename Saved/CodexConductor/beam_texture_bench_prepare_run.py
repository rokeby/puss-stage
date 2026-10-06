"""Run beam_texture_bench.py PREPARE: create the three bench materials CREATE-ONLY under /Game/ZZ_Bench/BeamTexture and
spawn the hidden ZZ_BEAMTEX_* pool into the EDITOR world. PIE must NOT be running and the dirty census must be clean.
It dirties the map and adds unsaved packages; it never saves. Wait ~30 s (shader compiles) before starting PIE.
Discard everything with a Don't-Save editor restart after the PIE capture + RESTORE.
Watch for BEAM_TEXTURE_BENCH_PREPARE_OK|run=... or BEAM_TEXTURE_BENCH_FAILED|run=...."""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
args = {}
if os.path.isfile(os.path.join(HERE, "beam_texture_bench_args.json")):
    with open(os.path.join(HERE, "beam_texture_bench_args.json"), encoding="utf-8") as handle:
        args = json.load(handle)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "beam_texture_bench.py"), init_globals={
    "BENCH_MODE": "PREPARE",
    "BENCH_PARAMS": dict(args.get("params", {}) or {}),
})
