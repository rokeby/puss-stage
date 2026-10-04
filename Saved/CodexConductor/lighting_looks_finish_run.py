"""FINISH entrypoint (Gary 4 Oct: finish tune 4 with flare). Completes the in-memory APPLY; lens flare 0.35 allowed."""
import runpy

runpy.run_path(
    "E:/PussStage/Saved/CodexConductor/lighting_looks_apply.py",
    init_globals={"LIGHTING_LOOKS_MODE": "FINISH", "LIGHTING_LOOKS_ALLOW_PPV_CHANGE": True},
)
