"""AS-IS binding: queue SavedMasterMatchesShow for FV3S4-20261002-01."""
from pathlib import Path
import runpy
TARGET = Path(__file__).resolve().parents[1] / "slot_v_queue_test.py"
runpy.run_path(str(TARGET), run_name="__main__",
               init_globals={"FLATV3_V_RUN": "FV3S4-20261002-01"})
