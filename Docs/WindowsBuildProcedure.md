# Windows build and verification procedure

Task **M.3**. Replaces the macOS build steps in the handover once the project is
on the PC. The *reason* for each step is unchanged — only the tooling differs.

Last validated 28 August 2026 with project `E:\PussStage` and engine
`D:\Unreal Engine\UE_5.8`.

## The failure this exists to prevent

On macOS, building while the editor was open produced numbered side-libraries
(`libUnrealEditor-InfinityStageEditor-0002.dylib`). The base library kept the old
code, the `.modules` manifest still pointed at the base, and a headless test run
then passed **against stale binaries** — a false green. It happened three times.

Windows has the same class of problem with a different shape: hot-reload DLLs
(`UnrealEditor-InfinityStage-####.dll`). Windows also *does* have Live Coding,
which macOS lacks — convenient, but Live Coding patches a running process and is
**not** a substitute for a clean build before testing.

**The rule is unchanged: close the editor, build, prove the new code is in the
binary, then test.**

## Build

```bat
"D:\Unreal Engine\UE_5.8\Engine\Build\BatchFiles\Build.bat" PussStageEditor Win64 Development -Project="E:\PussStage\PussStage.uproject" -waitmutex -NoUBA
```

Those are the current verified paths. Adjust only if the workspace or engine is
deliberately moved.

## Prove the new code is in the binary

The macOS step was `nm | grep <new symbol>`. The Windows equivalents:

```bat
dumpbin /exports Plugins\InfinityStage\Binaries\Win64\UnrealEditor-InfinityStageEditor.dll | findstr /i <SymbolName>
```

`dumpbin` needs a Visual Studio Developer Command Prompt. Without one, `llvm-nm`
ships with the engine's toolchain and works the same way.

**Symbols are not always enough.** A function in an anonymous namespace may be
inlined and never appear in the export table — this happened on the Mac with
`GatherPythonCandidates`. The reliable check is a **string literal** from the new
code. Note UE's `TEXT()` literals are UTF-16, so a plain ASCII search finds
nothing:

```bat
python -c "d=open(r'Plugins\InfinityStage\Binaries\Win64\UnrealEditor-InfinityStageEditor.dll','rb').read(); print(d.count('INFINITYSTAGE_PYTHON'.encode('utf-16-le')))"
```

Non-zero means the new code is really linked. Zero means you are about to test
stale binaries.

## Then check for hot-reload leftovers

```bat
dir /b Plugins\InfinityStage\Binaries\Win64\ | findstr /r "-[0-9][0-9][0-9][0-9]\."
```

Any hit is a hot-reload DLL. Close the editor and quarantine the numbered files
in a timestamped backup before testing; do not permanently delete them without
explicit approval. A clean verified build has zero hits.

## Run focused tests, then the suite

```bat
"D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "E:\PussStage\PussStage.uproject" -Unattended -NoP4 -NullRHI -NoSplash -ExecCmds="Automation RunTests InfinityStage; Quit" -TestExit="Automation Test Queue Empty" -AbsLog="E:\PussStage\Saved\Logs\<RunName>.log" -stdout -FullStdOutLogOutput
```

Require `**** TEST COMPLETE. EXIT CODE: 0 ****` and zero `Result={Fail}` lines.
Exit code 3 means at least one automation failure.

The latest full run on 28 August is **42/43**, not green. The sole failure is
`PussStage.InfinityStage.Functional.SavedFixturePIE`, which did not evaluate the
interaction curtain as fully lowered at its hidden-changeover marker. Its focused
post-repair rerun passed, so retain both logs and treat the discrepancy as
order/state-sensitive until diagnosed:

- `Saved/Logs/CueDeskTransformUI-FullInfinityStage-20260828.log`
- `Saved/Logs/CodexCurtainStaging-SavedFixturePIE-20260828-Rerun.log`

## Python

The analyzer needs a system Python with **numpy** — the engine's bundled Python
3.11 does not ship it. `InfinityStageMusicAnalysisImporter.cpp` now tries
`py.exe`, then `python.exe`, and honours `INFINITYSTAGE_PYTHON` if you want to
name an interpreter explicitly.

Current 28 August check: neither `py.exe` nor `python.exe` resolves from the
standard project shell. This does not block C++ builds or importing the already
generated analysis JSON, but it does block regenerating analysis on this PC.

Verify before relying on it:

```bat
py -c "import numpy; print(numpy.__version__)"
```

## Preflight guard

`Scripts/pc_bootstrap.bat` already refuses to run while `UnrealEditor.exe` is in
the task list. Its default `UE_ROOT` still points at the old Epic install path and
the script has not been revalidated end to end on this PC; set it to
`D:\Unreal Engine\UE_5.8` before relying on it. The manual command above is the
currently proven route.
