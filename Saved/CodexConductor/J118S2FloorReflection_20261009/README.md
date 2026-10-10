# Jobs 118/129: P01 vs target floor reflection

Offline-built; the conductor runs it later. No Unreal or MCP call was made while authoring.

1. Set `j118_floor_reflection_probe_args.json` target to `S2` or `P02` (delivered as `P02` for job 129).
2. Run `j118_floor_reflection_probe_request.json` through the guarded PussStage project-Python route.
3. Require `J118_S2_FLOOR_REFLECTION_PROBE_OK`, the requested target, `census_before==after=1`, and `saved=0`.
4. Review `j118_probe_<run>.json`. It compares LOD0 mesh, effective material per render section, existing MID
   chains, UV-channel signatures, corner-normal signatures, vertex-colour signatures and rough/spec/wet
   overrides against P01. Unavailable UE mesh-description evidence is explicitly `UNCLEAR`/partial.
5. Property equality is not rendered proof. Use the probe result to choose the narrow fix, then obtain Gary's stills acceptance.

The held J118 PPV fix is superseded by Gary's P01 drag test. Do not run it for job 129.
