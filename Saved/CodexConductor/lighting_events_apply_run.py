"""APPLY entrypoint for lighting_events_apply.py (Gary 4 Oct: P06 bays 2-10, denser bursts)."""
import runpy

runpy.run_path(
    "E:/PussStage/Saved/CodexConductor/lighting_events_apply.py",
    init_globals={"LIGHTING_EVENTS_MODE": "APPLY"},
)
