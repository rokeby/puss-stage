"""No-edit binding: revert.py with run_c_p05.json."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "revert.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_c_p05.json")})

