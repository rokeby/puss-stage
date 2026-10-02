"""No-edit binding: dry.py with run_c_p05.json."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "dry.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_c_p05.json")})

