"""No-edit binding: verify.py with run_d_p01.json."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "verify.py"), run_name="__main__",
               init_globals={"FLATV3_CONFIG": str(HERE / "run_d_p01.json")})

