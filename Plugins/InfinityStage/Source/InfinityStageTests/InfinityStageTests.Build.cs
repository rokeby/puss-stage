using UnrealBuildTool;

public class InfinityStageTests : ModuleRules
{
    public InfinityStageTests(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "MovieScene",
            "MovieSceneTracks",
            "LevelSequence",
            "InfinityStage"
        });
    }
}
