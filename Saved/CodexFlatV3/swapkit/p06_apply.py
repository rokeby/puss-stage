"""No-edit binding: shared apply.py plus the P06 mapping adapter."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply
import p06_support

p06_support.install(apply.c)
p06_support.install(apply.revert_module.c)
apply.run(str(HERE / "run_p06.json"))
