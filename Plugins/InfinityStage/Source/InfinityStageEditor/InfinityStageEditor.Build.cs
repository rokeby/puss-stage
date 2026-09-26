using UnrealBuildTool;

public class InfinityStageEditor : ModuleRules
{
    public InfinityStageEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "AssetRegistry",
            "CinematicCamera",
            "AudioEditor",
            "Json",
            "JsonUtilities",
            "MeshDescription",
            "StaticMeshDescription",
            "Slate",
            "SlateCore",
            "InputCore",
            "UnrealEd",
            "LevelSequence",
            "MovieScene",
            "MovieSceneTracks",
            "LevelEditor",
            "ToolMenus",
            "PropertyEditor",
            "AssetTools",
            "ContentBrowser",
            "DesktopPlatform",
            "Sequencer",
            "MovieSceneTools",
            "MovieRenderPipelineCore",
            "MovieRenderPipelineEditor",
            "CurveEditor",
            "UniversalObjectLocator",
            // UInfinityStageHandoffWatchSubsystem derives from UEditorSubsystem.
            "EditorSubsystem",
            "InfinityStage"
        });
    }
}
