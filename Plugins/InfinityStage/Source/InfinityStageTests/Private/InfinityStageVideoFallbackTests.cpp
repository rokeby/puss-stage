#include "InfinityStageCueSheet.h"
#include "InfinityStageVideoFallback.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageVideoRegistryTest,
    "InfinityStage.CueDirector.VideoFallbackReadsRenderContract",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// The conductor's MRQ contract (MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md section 6): scenes.S<n> with paths
// relative to Renders/Fallbacks; "muxed" is optional.
bool FInfinityStageVideoRegistryTest::RunTest(const FString& Parameters)
{
    const FString Root = TEXT("E:/Show/Renders/Fallbacks");
    const FString Json = TEXT(R"({"schema":1,"scenes":{
        "S1":{"video":"S1/PussFB_S1_P_v01.mp4","audio":"S1/PussFB_S1_P_v01.wav","frames":5000,"fps":25},
        "S3":{"video":"S3/PussFB_S3_P_v01.mp4","muxed":"S3/PussFB_S3_P_v01_muxed.mp4","frames":6500,"fps":25},
        "S4":{"audio":"S4/only_audio.wav"},
        "Opening":{"video":"x.mp4"}}})");
    TArray<FString> Warnings;
    const TMap<int32, FInfinityFallbackClip> Clips = InfinityStageVideoFallback::ParseRegistry(Json, Root, Warnings);
    TestEqual(TEXT("Two usable Scenes"), Clips.Num(), 2);
    TestTrue(TEXT("S1 is Scene 1"), Clips.Contains(1));
    TestTrue(TEXT("Paths are absolute under the fallback root"),
        Clips.Contains(1) && Clips[1].VideoPath.EndsWith(TEXT("Renders/Fallbacks/S1/PussFB_S1_P_v01.mp4")));
    TestTrue(TEXT("No muxed file: empty (UE plays it silent; desk WAV)"), Clips.Contains(1) && Clips[1].MuxedPath.IsEmpty());
    TestTrue(TEXT("S3 keeps its muxed file for UE sound"), Clips.Contains(3) && !Clips[3].MuxedPath.IsEmpty());
    TestEqual(TEXT("Frames read"), Clips.Contains(3) ? Clips[3].Frames : 0, 6500);
    TestEqual(TEXT("Control: an entry with no video and a non-Scene key both warn"), Warnings.Num(), 2);

    TArray<FString> BadWarnings;
    TestEqual(TEXT("Control: broken JSON gives nothing, with a warning"),
        InfinityStageVideoFallback::ParseRegistry(TEXT("{not json"), Root, BadWarnings).Num(), 0);
    TestEqual(TEXT("...one warning"), BadWarnings.Num(), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageVideoClockTest,
    "InfinityStage.CueDirector.VideoFollowsTheMasterClock",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageVideoClockTest::RunTest(const FString& Parameters)
{
    FInfinityFallbackClip Clip;
    Clip.Frames = 250;   // 10 s at 25 fps
    Clip.Fps = 25.0;
    const double Ticks = 24000.0;
    TestEqual(TEXT("Scene start = clip start"), InfinityStageVideoFallback::MediaSecondsForLocalFrame(0, Ticks, Clip), 0.0);
    TestTrue(TEXT("4 s into the Scene = 4 s into the clip"),
        FMath::IsNearlyEqual(InfinityStageVideoFallback::MediaSecondsForLocalFrame(96000, Ticks, Clip), 4.0, 1.0e-6));
    TestTrue(TEXT("Past the clip end clamps to its last frame (never loops)"),
        FMath::IsNearlyEqual(InfinityStageVideoFallback::MediaSecondsForLocalFrame(24000 * 60, Ticks, Clip), 249.0 / 25.0, 1.0e-6));
    TestEqual(TEXT("Control: before the Scene clamps to 0"), InfinityStageVideoFallback::MediaSecondsForLocalFrame(-500, Ticks, Clip), 0.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageVideoSettingsTest,
    "InfinityStage.CueDirector.UseVideoSettingsRoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageVideoSettingsTest::RunTest(const FString& Parameters)
{
    FInfinityCueDirectorSettings Settings;
    Settings.UseVideoScenes = {TEXT("S3"), TEXT("S5")};
    Settings.VideoAudio = TEXT("desk");
    const FString Text = Settings.Serialize([](const FGuid&) { return FString(); });
    FInfinityCueDirectorSettings Read;
    TArray<FString> Warnings;
    Read.Parse(Text, Warnings);
    TestEqual(TEXT("No warnings on our own output"), Warnings.Num(), 0);
    TestTrue(TEXT("The video Scenes survive"), Read.UseVideoScenes == Settings.UseVideoScenes);
    TestEqual(TEXT("Who plays the sound survives"), Read.VideoAudio, FString(TEXT("desk")));

    FInfinityCueDirectorSettings Defaults;
    Defaults.Parse(TEXT("use_video = s2\nvideo_audio = speakers\n"), Warnings);
    TestTrue(TEXT("Scene keys are normalised to upper case"), Defaults.UseVideoScenes.Contains(TEXT("S2")));
    TestEqual(TEXT("Control: an unknown sound owner warns and keeps the default"), Defaults.VideoAudio, FString(TEXT("ue")));
    TestEqual(TEXT("...with exactly one warning"), Warnings.Num(), 1);
    return true;
}

#endif
