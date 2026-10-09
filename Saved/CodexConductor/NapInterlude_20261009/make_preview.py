"""Generate the analytical default P79 timing/breath preview; no Unreal import."""
import os

import nap_interlude as n
from test_nap_interlude import fixture, args

HERE = os.path.dirname(__file__)
plan = n.build_plan(fixture(), args())
print(n.write_preview(plan, os.path.join(HERE, "nap_interlude_preview_default.png")))
