using UnrealBuildTool;

public class InfinityStage : ModuleRules
{
    public InfinityStage(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "CinematicCamera",
            "LevelSequence",
            "MovieScene",
            "MovieSceneTracks",
            "UniversalObjectLocator"
        });

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "UMG",
            // The rehearsal bar (Cue Director) is a Slate widget shown in the game viewport too.
            "Slate",
            "SlateCore",
            "Niagara",
            // Scene arrivals play a backcloth's GeometryCache before the Scene (AInfinityStageArrival).
            "GeometryCache",
            "GeometryCacheTracks"
        });

        if (Target.bBuildEditor)
        {
            PrivateDependencyModuleNames.AddRange(new[]
            {
                "UnrealEd"
            });
        }
    }
}
