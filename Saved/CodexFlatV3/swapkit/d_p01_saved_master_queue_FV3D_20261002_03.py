"""Queue the approved SavedMasterMatchesShow test with the bound Slot D run ID."""
from pathlib import Path
import runpy

TARGET = Path(__file__).resolve().parents[1] / "slot_v_queue_test.py"
runpy.run_path(
    str(TARGET),
    run_name="__main__",
    init_globals={"FLATV3_V_RUN": "FV3D-20261002-03"},
)
