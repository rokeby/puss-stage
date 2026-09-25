using UnrealBuildTool;

public class Go1Input : ModuleRules
{
    public Go1Input(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine"
        });

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Sockets",
            "Networking",
            "Json",
            "LevelSequence",
            "MovieScene",
            // Camera ownership is authored in the Show. This dependency is
            // deliberately one-way: InfinityStage must not depend on Go1Input.
            "InfinityStage"
        });
    }
}
