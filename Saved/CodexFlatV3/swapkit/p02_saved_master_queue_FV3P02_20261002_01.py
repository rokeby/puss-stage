"""Queue SavedMasterMatchesShow once for bound P02 run FV3P02-20261002-01."""
from pathlib import Path
import runpy

TARGET = Path(__file__).resolve().parents[1] / "slot_v_queue_test.py"
runpy.run_path(
    str(TARGET),
    run_name="__main__",
    init_globals={"FLATV3_V_RUN": "FV3P02-20261002-01"},
)
