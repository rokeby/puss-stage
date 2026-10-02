"""No-edit binding: shared saved-state verifier with the bound P06 config."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_saved
import p06_support

p06_support.install(verify_saved.c)
p06_support.install(verify_saved.verifier.c)
verify_saved.main(str(HERE / "run_p06.json"))
