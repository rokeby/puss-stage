"""Blender entry wrapper: pin the FBX header CreationTimeStamp, then run Tools/FlatV3/build_v3_flat.py unchanged.

Blender 4.4's FBX writer stamps FBXHeaderExtension/CreationTimeStamp with datetime.now()
(io_scene_fbx/export_fbx_bin.py:3145-3155 [decl]); FileId and CreationTime are already fixed by
encode_bin._write_timedate_hack (encode_bin.py:347-365 [decl]).  Pinning the one wall-clock field is what makes two
builds of the same inputs byte-identical.  Nothing else in the build is touched.
Usage: blender --background --factory-startup --python s3_waves_v3_blender_pinned.py -- <build_v3_flat args>
"""
import datetime
import os
import runpy
import sys
import types

PINNED_TIME = datetime.datetime(2026, 10, 7, 0, 0, 0)


class _PinnedDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D401
        return PINNED_TIME


import io_scene_fbx.export_fbx_bin as _efb  # noqa: E402  (addons_core, enabled in factory startup)

_efb.datetime = types.SimpleNamespace(datetime=_PinnedDateTime, date=datetime.date, timedelta=datetime.timedelta)
print("S3WAVESV3_FBX_TIME_PINNED", PINNED_TIME.isoformat(), flush=True)
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.normpath(os.path.join(HERE, "..", "..", "..", "Tools", "FlatV3", "build_v3_flat.py"))
sys.path.insert(0, os.path.dirname(BUILD))
runpy.run_path(BUILD, run_name="__main__")
