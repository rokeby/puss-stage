"""AS-IS binding: P04 inner-shift dry plan."""
from pathlib import Path
import runpy
HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "shift_dry.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_shift_p04.json")})
