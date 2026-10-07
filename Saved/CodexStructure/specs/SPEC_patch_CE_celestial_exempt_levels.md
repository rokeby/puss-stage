# Spec: HELD PATCH CE: celestial rig foreign-lighting exemption by level

Output: `Scripts/patches/2026-10-07_CE_celestial_exempt_levels.patch`, a `git diff` against HEAD (CRLF, like the other
held patches).
- It must apply with `git apply --check --ignore-whitespace` ALONE, and on top of each of
  `2026-10-04_LD_flash_events.draft.patch`, `2026-10-07_CH_cat_counters_height_offset.patch`,
  `2026-10-07_PS_puss_shadow_spot.patch` and `2026-10-07_SS_strobe_cast_shadows.patch`. Report each result.
- Leave the source tree UNCHANGED (only the patch file is new). Don't build or run Unreal.

## Why
Gary (7 Oct): Klara's S1/S4 dioramas stream into the S1/S4 hangars as plain sublevels. During her cinematic, HER
sun/sky/fog light it, and our rig's actors are hidden by the Scene sequence (`Saved/CodexConductor/KlaraIngest/HOOKIN_PLAN.md`,
lighting section).
- `AInfinityStageCelestialRig` silences every foreign exterior light: `bSuppressForeignEnvironmentLighting`,
  `InfinityStageCelestialRig.h:95-107`, and `SuppressIfForeign` in `InfinityStageCelestialRig.cpp:254-298`.
- It does so at BeginPlay (`:91-110`), on every level add (`:352-359`), on spawn (`:346-348`) and in a throttled re-hide
  (`:320-340`, `:362-386`).
- So it would re-hide her lighting.

## Change
1. Header: add `UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting") TArray<TSoftObjectPtr<UWorld>> ForeignLightingExemptLevels;`
   - Tooltip: actors in these levels are never treated as foreign. The DEFAULT IS EMPTY, which means no behaviour
     change. World-global lights from an exempt level also light everything else while visible, so hide them via
     sequence outside their window.
2. `SuppressIfForeign`: right after the own-actor check and BEFORE ANY MUTATION (no SetVisibility, no hidden flag, no
   set insert), `return false` when the actor's level is exempt.
3. Put the exemption test in a small pure static helper, unit-testable without a world, e.g.
   `static bool IsExemptLevelPackage(const FString& LevelPackageName, const FString& StreamingWorldAssetPackage, const TArray<TSoftObjectPtr<UWorld>>& Exempt)`.
   A level is exempt when EITHER of these equals an exempt entry's long package name:
   - a) `UWorld::RemovePIEPrefix(Level->GetOutermost()->GetName())`. This covers plain sublevels in PIE (`UEDPIE_N_`)
     and in the editor.
   - b) the long package name of the world asset of the `ULevelStreaming` whose `GetLoadedLevel()` is that level, found
     via `GetWorld()->GetStreamingLevels()`. This covers dynamically loaded instances, whose package gets a unique
     `_LevelInstance_N` name.
   - Compare case-insensitively. Ignore null or empty entries.
4. Do NOT touch `ApplyCyclePhase`, the bound actors, the walk/re-hide scheduling, or the logging of suppressed actors.
5. Optional: log `CELESTIAL_FOREIGN_LIGHTING_EXEMPT|world=…|actor=…|level=…` once per actor (a TSet of weak pointers,
   like `SuppressedForeignActors`). Keep it cheap: no per-frame cost.

## Tests (`InfinityStageCelestialRigTests.cpp`, same style as the existing foreign-lighting tests)
- **Helper:**
  - an exempt name matches;
  - a `UEDPIE_0_`-prefixed exempt name matches (via RemovePIEPrefix at the call site; test the full path through
    whatever function takes the raw name);
  - a streaming world-asset name matches while the package name is `…_LevelInstance_1`;
  - a non-exempt name does NOT match;
  - an empty list never matches.
- **Actor-level, one exempt and one non-exempt level:**
  - The test world has one level. Run the existing "foreign arrival" fixture twice:
    - (i) with `ForeignLightingExemptLevels` naming the test world's own package: the foreign directional-light actor
      stays visible and the suppressed count stays 0;
    - (ii) with the list naming a different package: it's suppressed, count 1.
  - If a second real level can be added to a test world cheaply, do that instead. Say which you did.
- **Negative control:** with an empty list, the existing tests are unchanged and pass.

## Traps
- Keep the exemption BEFORE any mutation in `SuppressIfForeign`.
- Never compare `UWorld*` or soft pointers by object identity across PIE duplication: compare package-name strings.
- `TSoftObjectPtr<UWorld>::ToSoftObjectPath().GetLongPackageName()` gives `/Game/KK_S1_Animals/L_Animals` for an
  entry. Verify the API in the UE 5.8 headers (`D:\Unreal Engine\UE_5.8\Engine\Source\Runtime\CoreUObject\Public\UObject\SoftObjectPath.h`)
  and cite the line.
- Same for `UWorld::RemovePIEPrefix` and `ULevelStreaming::GetLoadedLevel` / `GetWorldAssetPackageFName`: cite the
  header lines.
- UE 5.8 has headers only, no private .cpp.

Final message:
- the patch path;
- the five apply checks;
- the test list;
- header citations;
- each claim marked declaration-proven / inferred;
- what you couldn't verify.
