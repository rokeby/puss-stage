"""No-edit binding: shared read-only verify.py plus the P06 mapping adapter."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify
import p06_support

p06_support.install(verify.c)
verify.main(str(HERE / "run_p06.json"))
