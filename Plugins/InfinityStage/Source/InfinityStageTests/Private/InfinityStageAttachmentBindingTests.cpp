#include "InfinityStageAttachmentBinding.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneBindingReferences.h"
#include "Misc/AutomationTest.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "MovieScenePossessable.h"
#include "InfinityStageTypes.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
const FName LampTag(TEXT("InfinityStage.Attachment.AAAA|BBBB"));
const FName OtherTag(TEXT("InfinityStage.Attachment.CCCC|DDDD"));

AActor* SpawnTagged(UWorld& World, AInfinityStagePassageActor& Passage, const FName Tag)
{
    AActor* Actor = World.SpawnActor<AActor>();
    if (!Tag.IsNone())
    {
        Actor->Tags.Add(Tag);
    }
    Passage.ManagedAttachmentActors.Add(Actor);
    return Actor;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageAttachmentBindingRespawnTest,
    "InfinityStage.Cueing.Binding.ResolvesByTagAcrossRespawn",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageAttachmentBindingRespawnTest::RunTest(const FString& Parameters)
{
    InfinityStageAttachmentBinding::ResetCacheForTests();
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    SpawnTagged(*World, *Passage, NAME_None);                 // control: an untagged neighbour
    AActor* First = SpawnTagged(*World, *Passage, LampTag);

    const int64 Scans0 = InfinityStageAttachmentBinding::GetScanCount();
    TestTrue(TEXT("Resolves the tagged lamp"), InfinityStageAttachmentBinding::FindAttachmentActor(World, LampTag) == First);
    TestEqual(TEXT("First resolve costs one scan"), InfinityStageAttachmentBinding::GetScanCount(), Scans0 + 1);
    TestTrue(TEXT("Cached resolve returns the same lamp"), InfinityStageAttachmentBinding::FindAttachmentActor(World, LampTag) == First);
    TestEqual(TEXT("Cached resolve costs no scan"), InfinityStageAttachmentBinding::GetScanCount(), Scans0 + 1);

    // Materialize: the lamp is destroyed and a new actor carries the same identity.
    Passage->ManagedAttachmentActors.Remove(First);
    World->DestroyActor(First);
    AActor* Second = SpawnTagged(*World, *Passage, LampTag);
    TestTrue(TEXT("After respawn the binding finds the new lamp"), InfinityStageAttachmentBinding::FindAttachmentActor(World, LampTag) == Second);
    TestEqual(TEXT("A stale entry costs exactly one scan"), InfinityStageAttachmentBinding::GetScanCount(), Scans0 + 2);

    // A tag with no lamp: null, one warning, at most one scan this frame.
    AddExpectedMessagePlain(TEXT("INFINITY_ATTACHMENT_BINDING_MISSING"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
    TestNull(TEXT("A missing tag resolves to nothing"), InfinityStageAttachmentBinding::FindAttachmentActor(World, OtherTag));
    TestNull(TEXT("Asked again the same frame, still nothing"), InfinityStageAttachmentBinding::FindAttachmentActor(World, OtherTag));
    TestEqual(TEXT("A missing tag scans once per frame, not per call"), InfinityStageAttachmentBinding::GetScanCount(), Scans0 + 3);

    World->DestroyWorld(false);
    InfinityStageAttachmentBinding::ResetCacheForTests();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageAttachmentBindingMaterializeTest,
    "InfinityStage.Cueing.Binding.SurvivesRealMaterialize",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageAttachmentBindingMaterializeTest::RunTest(const FString& Parameters)
{
    InfinityStageAttachmentBinding::ResetCacheForTests();
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FGuid LampCue;
    FGuid LampAttachment;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
        if (Index == 0)
        {
            FInfinityCueAttachment& Lamp = Cue.WingPair.Attachments.AddDefaulted_GetRef();
            Lamp.AttachmentGuid = FGuid::NewGuid();
            Lamp.Kind = EInfinityAttachmentKind::Light;
            Lamp.Anchor = EInfinityAttachmentAnchor::Station;
            LampCue = Cue.CueGuid;
            LampAttachment = Lamp.AttachmentGuid;
        }
    }
    Show->ReconcilePassageSettings();
    const FName Tag(*FString::Printf(TEXT("InfinityStage.Attachment.%s|%s"),
        *LampCue.ToString(EGuidFormats::Digits), *LampAttachment.ToString(EGuidFormats::Digits)));

    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    TestTrue(TEXT("First materialize succeeds"), Passage->MaterializePassage());
    AActor* Before = InfinityStageAttachmentBinding::FindAttachmentActor(World, Tag);
    TestNotNull(TEXT("The spawned lamp carries the identity tag the binding uses"), Before);
    const FName Minted = InfinityStageAttachmentBinding::GetAttachmentTag(Before);
    TestEqual(TEXT("GetAttachmentTag reads the minted tag back"), Minted, Tag);

    TestTrue(TEXT("Re-materialize succeeds"), Passage->MaterializePassage());
    AActor* After = InfinityStageAttachmentBinding::FindAttachmentActor(World, Tag);
    TestNotNull(TEXT("After re-materialize the binding still resolves"), After);
    TestTrue(TEXT("...to the re-spawned actor, not the destroyed one"), After != nullptr && After != Before);

    World->DestroyWorld(false);
    InfinityStageAttachmentBinding::ResetCacheForTests();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageAttachmentBindingCreationTest,
    "InfinityStage.Cueing.Binding.CreatedOnlyForAttachments",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageAttachmentBindingCreationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AActor* Tagged = World->SpawnActor<AActor>();
    Tagged->Tags.Add(LampTag);
    AActor* Plain = World->SpawnActor<AActor>();
    Plain->Tags.Add(TEXT("SomethingElse"));

    const UInfinityStageAttachmentBinding* Default = GetDefault<UInfinityStageAttachmentBinding>();
    TestTrue(TEXT("A Show attachment can be bound by tag"), Default->SupportsBindingCreationFromObject(Tagged));
    TestFalse(TEXT("Control: an ordinary actor is left to the engine's bindings"), Default->SupportsBindingCreationFromObject(Plain));

    ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
    Sequence->Initialize();
    UInfinityStageAttachmentBinding* Made = Cast<UInfinityStageAttachmentBinding>(
        GetMutableDefault<UInfinityStageAttachmentBinding>()->CreateNewCustomBinding(Tagged, *Sequence->GetMovieScene()));
    TestTrue(TEXT("The new binding stores the actor's tag"), Made && Made->AttachmentTag == LampTag);
    TestNull(TEXT("Control: no binding is made for an ordinary actor"),
        GetMutableDefault<UInfinityStageAttachmentBinding>()->CreateNewCustomBinding(Plain, *Sequence->GetMovieScene()));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageAttachmentBindingHierarchyTest,
    "InfinityStage.Cueing.Binding.SequenceBindsTagFindsNested",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageAttachmentBindingHierarchyTest::RunTest(const FString& Parameters)
{
    ULevelSequence* Root = NewObject<ULevelSequence>(GetTransientPackage());
    Root->Initialize();
    ULevelSequence* Child = NewObject<ULevelSequence>(GetTransientPackage());
    Child->Initialize();

    UInfinityStageAttachmentBinding* Binding =
        NewObject<UInfinityStageAttachmentBinding>(Child->GetMovieScene(), NAME_None, RF_Transactional);
    Binding->AttachmentTag = LampTag;
    static_cast<UMovieSceneSequence*>(Child)->GetBindingReferences()->AddBinding(FGuid::NewGuid(), Binding);

    TestTrue(TEXT("The child itself binds the tag"), InfinityStageAttachmentBinding::SequenceBindsTag(Child, LampTag));
    TestFalse(TEXT("Control: before nesting, the root does not"), InfinityStageAttachmentBinding::SequenceBindsTag(Root, LampTag));
    Root->GetMovieScene()->AddTrack<UMovieSceneSubTrack>()->AddSequence(Child, 0, 1000);
    TestTrue(TEXT("Once nested, the root finds it"), InfinityStageAttachmentBinding::SequenceBindsTag(Root, LampTag));
    TestFalse(TEXT("Control: a different tag is not found"), InfinityStageAttachmentBinding::SequenceBindsTag(Root, OtherTag));
    TestFalse(TEXT("Control: depth 0 does not descend"), InfinityStageAttachmentBinding::SequenceBindsTag(Root, LampTag, 0));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCaptureGuardTest,
    "InfinityStage.Cueing.Capture.KeyedValueKeptOutOfShow",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// The capture guard's data path: a sequence keys a stage lamp's Intensity (on its
// light component, the way Sequencer adds it) and moves its transform. A hand
// edit of Color must still reach the Show; the keyed Intensity must not.
bool FInfinityStageCaptureGuardTest::RunTest(const FString& Parameters)
{
    ULevelSequence* Root = NewObject<ULevelSequence>(GetTransientPackage());
    Root->Initialize();
    ULevelSequence* Child = NewObject<ULevelSequence>(GetTransientPackage());
    Child->Initialize();
    UMovieScene* Scene = Child->GetMovieScene();

    const FGuid LampGuid = Scene->AddPossessable(TEXT("House L"), AActor::StaticClass());
    UInfinityStageAttachmentBinding* Binding = NewObject<UInfinityStageAttachmentBinding>(Scene, NAME_None, RF_Transactional);
    Binding->AttachmentTag = LampTag;
    static_cast<UMovieSceneSequence*>(Child)->GetBindingReferences()->AddBinding(LampGuid, Binding);
    const FGuid ComponentGuid = Scene->AddPossessable(TEXT("LightComponent0"), UObject::StaticClass());
    Scene->FindPossessable(ComponentGuid)->SetParent(LampGuid, Scene);
    Scene->AddTrack<UMovieSceneFloatTrack>(ComponentGuid)->SetPropertyNameAndPath(TEXT("Intensity"), TEXT("Intensity"));
    Root->GetMovieScene()->AddTrack<UMovieSceneSubTrack>()->AddSequence(Child, 0, 1000);

    TSet<FName> Animated;
    bool bTransform = false;
    TestTrue(TEXT("The nested sequence binds the lamp"),
        InfinityStageAttachmentBinding::CollectAnimatedProperties(Root, LampTag, Animated, bTransform));
    TestTrue(TEXT("Intensity on the child component binding is found"), Animated.Contains(TEXT("Intensity")));
    TestFalse(TEXT("No transform track yet"), bTransform);

    TSet<FName> OtherAnimated;
    bool bOtherTransform = false;
    TestFalse(TEXT("Control: another lamp is not bound"),
        InfinityStageAttachmentBinding::CollectAnimatedProperties(Root, OtherTag, OtherAnimated, bOtherTransform));
    TestEqual(TEXT("Control: nothing is animated on it"), OtherAnimated.Num(), 0);

    Scene->AddTrack<UMovieScene3DTransformTrack>(LampGuid);
    Animated.Reset();
    InfinityStageAttachmentBinding::CollectAnimatedProperties(Root, LampTag, Animated, bTransform);
    TestTrue(TEXT("A transform track is reported"), bTransform);

    FInfinityStageLightSettings Authored;
    Authored.Intensity = 1740.0f;
    Authored.Color = FLinearColor::White;
    FInfinityStageLightSettings Captured = Authored;
    Captured.Intensity = 0.0f;                        // the keyed value on screen
    Captured.Color = FLinearColor(1.0f, 0.5f, 0.2f);  // Gary's hand edit
    FString Unmapped;
    TestTrue(TEXT("Every animated setting is mapped"),
        InfinityStageAttachmentBinding::RestoreAnimatedLightFields(Captured, Authored, Animated, Unmapped));
    TestEqual(TEXT("The keyed Intensity is NOT written as authored"), Captured.Intensity, 1740.0f);
    TestTrue(TEXT("The hand edit of Color IS written"), Captured.Color.Equals(FLinearColor(1.0f, 0.5f, 0.2f)));

    FInfinityStageLightSettings Untouched = Authored;
    Untouched.Intensity = 900.0f;
    TestTrue(TEXT("Control: with nothing animated, a hand edit of Intensity is written"),
        InfinityStageAttachmentBinding::RestoreAnimatedLightFields(Untouched, Authored, TSet<FName>(), Unmapped)
        && Untouched.Intensity == 900.0f);

    TSet<FName> Strange;
    Strange.Add(TEXT("SomeUnmappedProperty"));
    FInfinityStageLightSettings Refused = Authored;
    TestFalse(TEXT("An unmapped animated setting refuses the whole capture"),
        InfinityStageAttachmentBinding::RestoreAnimatedLightFields(Refused, Authored, Strange, Unmapped));
    TestEqual(TEXT("...and names it"), Unmapped, FString(TEXT("SomeUnmappedProperty")));
    return true;
}

#endif
