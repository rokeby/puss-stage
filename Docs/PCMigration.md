# PC migration — completed; transfer record

The transfer plan below was verified 22 August 2026. The active project is now
on Windows at **`E:\PussStage`**, using Unreal Engine 5.8 at
**`D:\Unreal Engine\UE_5.8`**.

Current migration state, verified 28 August:

- clean UE 5.8 builds and command-line automation run on the PC;
- Unreal MCP auto-starts on loopback port 8000 and the guarded project-Python
  route is proven;
- the production Show compiles to 19 segments;
- the latest full suite is 42/43, with one curtain-marker fixture failure;
- `py.exe` and `python.exe` are not currently on PATH, so system Python/numpy
  remains a migration dependency for re-running music analysis; and
- GO1 networking (M.4) and shared `DerivedAssets`/V2 source-path reconciliation
  (M.7) remain open.

An intermediate Google Drive-backed `G:` working copy caused 4–5 second Unreal
autosave stalls. Keep active authoring on `E:\PussStage`; sync or archive outside
the live Editor session.

## Transfer size

**58.94 GB (54.9 GiB) across 16,185 files** using the exclude list. The project
on disk is 62 GiB; the difference is Mac binaries and editor scratch that the PC
regenerates.

## The copy

```bash
rsync -av --exclude-from="Scripts/pc_migration_exclude.txt" "/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/" /Volumes/<YOUR_DISK>/PussStage/
```

Format the disk **exFAT** (cross-platform, no 4 GB file limit — the largest asset
here is ~66 MB, so this is comfortable). Do not use NTFS-via-macOS drivers for a
write this large.

Add `--progress` if you want to watch it, and re-run the same command to resume —
rsync is restartable, which matters for a 59 GB copy.

## Two things the exclude list is actually protecting you from

**1. `Saved/AssetAuditHarness/` contains 22 symlinks** pointing at unpacked
marketplace asset packs inside Google Drive's "UE Assets Pile" — absolute macOS
paths, all currently resolving.

They must be excluded because **exFAT cannot represent a symlink at all**, and
those paths mean nothing on the PC. A tool that *dereferences* them (`rsync -L`,
some GUI copies) would additionally pull whole marketplace packs down out of
Drive and into the transfer.

*Corrected 22 Aug: an earlier draft of this file claimed `cp -R` follows symlinks
and would duplicate the 51 GB `Content/` tree. Both halves were wrong — `cp -R`
and plain `rsync` preserve symlinks rather than following them, and these links
point into Drive, not into `Content/`.*

**2. `Plugins/*/Intermediate/` is 1.24 GB of Mac build objects**, and
`Intermediate/` another 947 MB. All of it is regenerated on the PC and none of it
is portable. Copying it wastes time and risks the PC picking up stale artefacts.

## Windows compatibility — checked, all clear

| Check | Result |
| --- | --- |
| Illegal filename characters (`: * ? " < > \|`) | **0** |
| Path length (Windows MAX_PATH 260) | longest is **161** chars — clear |
| Case-only filename collisions | **0** |
| Reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) | **0** |
| Trailing dots or spaces in names | **0** |
| Symlinks | 22, all excluded |

Nothing in this project needs renaming to survive the move.

## What is deliberately kept

- `Backups/` (85 MB) — **this project has no git repo, so these snapshots are the
  only version control that exists.** Including `PrePCSwitchover-20260822-1450`,
  taken before today's C++ edits.
- `Saved/InfinityStage/` (10 MB) — the regenerated **0.3.0 music analysis**, 26
  files. Re-running it on the PC is currently blocked until a numpy-capable
  Python is installed, so carrying it means the PC starts with working data.
- `Saved/CodexWingIntegration/` — the wing verification evidence the tracker cites.
- `DerivedAssets/` (2.8 GB) — wing art sources.

## Arrival checklist and outcome

1. **Install Unreal Engine 5.8.** Not 5.7, not 5.9 — the plugin declares 5.8 and
   the Master's tick resolution assumptions go with it.
2. **Install a system Python with numpy.** The engine's bundled Python 3.11 does
   not ship numpy, and the analyzer needs it.
   ```bat
   py -m pip install numpy
   py -c "import numpy; print(numpy.__version__)"
   ```
3. **Run `Scripts\pc_bootstrap.bat`** from a Developer Command Prompt — it
   checks the editor is closed, finds the engine, verifies Python has numpy,
   builds, and proves the new code is in the DLL before you trust it. Edit
   `UE_ROOT` at the top first. *The manual build route is proven; this script is
   still not revalidated and its default UE path remains stale.*
4. **Or do it by hand.** See
   [Windows build procedure](WindowsBuildProcedure.md) — it carries the
   `dumpbin` / UTF-16 string check that replaces the macOS `nm` step, and the
   reason it exists.
5. **Open the project.** First open rebuilds shaders and DDC; expect it to be slow
   once and fast after.
6. **Run the automation suite and record the pass count.** Done on Windows;
   latest complete result is 42/43. The remaining failure is tracked in
   `ShowBuildTodo.md` J.1.
7. **Set the environment variables** if the defaults do not resolve:
   - `PUSS_PROJECT_ROOT` — the project folder, for the Blender scripts
   - `PUSS_DRIVE_ROOT` — the `2026. SHS 3 Evenings` folder on the shared drive
   - `PUSS_SOUND_ROOT` — its `Sound` subfolder
   - `INFINITYSTAGE_PYTHON` — only if `py.exe` / `python.exe` are not found
8. **Re-verify the GO1 chain** (M.4): a Windows Firewall inbound rule for **UDP
   9876**, and a 5 GHz adapter that will associate with the dog's hotspot on
   **channel 165**.

## Current migration follow-up

The **19-cue spine** and MCP loopback are complete. Remaining migration-specific
work is system Python/numpy for analysis, GO1 networking on Windows, and shared
`DerivedAssets`/V2 Wing-source path reconciliation. The authoritative queues are
the three `Show*Todo.md` files.

## What was done today, before the move

- **M.1** Analyzer interpreter fixed — tries `py.exe`, then `python.exe`, honours
  `INFINITYSTAGE_PYTHON`, keeps `/usr/bin/env python3` on Unix. Compiled and
  verified in the linked binary; the Windows branch correctly compiles out on Mac.
- **M.2** All hardcoded `/Users/zhexi-mbp-22/…` paths removed from `Scripts/`.
  Each script resolves its own root — deliberately self-contained rather than a
  shared module, because these run inside Blender's and Unreal's embedded
  interpreters where the script directory is not reliably on `sys.path`.
- **M.3** [Windows build procedure](WindowsBuildProcedure.md) written.
- **0.6 (part)** The dev fixture no longer declares `DeclaredUnpausable` on silent
  placeholder Scenes. **Note the Rehearsal Transport toggle already existed** —
  the tracker was stale on this; no work was needed there.
- **0.1** Music analysis regenerated at 0.3.0 with curves and sections.
- **I.8** [Scene delivery contract](SceneDeliveryContract.md).
- **I.5** [Mountains brief](Brief_S5_Mountains.md) — ready to send, due 5 Sept.
- **D.3** [Sound delivery list](SoundDeliveryList.md) — ready to send to Cameron.

## Deliberately not done on the Mac

**T4 — authoring the 19-cue spine.** It needs the editor open and mutates the
production Show. Doing that unattended on the machine being retired, hours before
a 59 GB copy, would mean migrating a freshly-mutated and less-tested Show — and
it would have to be re-verified on the PC regardless. It is the first job on the
new machine instead. **Outcome:** completed on the PC; the Show now derives 19
segments.

**A full test-suite run.** The Mac pass count is not the number that matters now;
M.5 records the PC one. **Outcome:** exercised and recorded at 42/43; J.1 remains
open until the curtain-marker fixture is green in the full run.
