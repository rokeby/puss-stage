#include "InfinityStageDevFixtureBuilder.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "CineCameraActor.h"
#include "Editor.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "FileHelpers.h"
#include "Factories/Factory.h"
#include "Factories/SoundFactory.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCelestialRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageWingAssetAuditor.h"
#include "InfinityStageWingLibraryAsset.h"
#include "LevelSequence.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "MovieScene.h"
#include "MovieSceneObjectBindingID.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Sound/SoundWave.h"
#include "Tracks/MovieSceneCameraCutTrack.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageFixture, Log, All);

namespace
{
struct FSourceMusic
{
    const TCHAR* Filename;
    const TCHAR* AssetName;
    double DurationSeconds;
};

const FSourceMusic SourceMusic[] =
{
    { TEXT("Intro_WalkingMusic_1.wav"), TEXT("SW_P01_IntroWalking"), 96.336054 },
    { TEXT("WalkingMusic_2.wav"), TEXT("SW_P02_Walking"), 47.431338 },
    { TEXT("WalkingMusic_3.wav"), TEXT("SW_P03_Walking"), 43.687891 },
    { TEXT("WalkingMusic_4.wav"), TEXT("SW_P04_Walking"), 42.673878 },
    { TEXT("WalkingMusic_5_with_Tennis_Ball_Moment.wav"), TEXT("SW_P05_TennisBall"), 186.363605 },
    { TEXT("WalkingMusic_6_into_void.wav"), TEXT("SW_P06_IntoVoid"), 110.561134 },
};

constexpr int32 FixtureSideVariantsPerHand = 14;
constexpr int32 FixtureTopVariantsPerPassage = 2;
constexpr int32 FixtureDistinctMeshesPerPassage =
    FixtureSideVariantsPerHand * 2 + FixtureTopVariantsPerPassage;
constexpr int32 FixtureComponentBudget = 64;

template <typename AssetType>
AssetType* LoadOrCreateAsset(const FString& PackageName, const FString& AssetName)
{
    const FString ObjectPath = FString::Printf(TEXT("%s.%s"), *PackageName, *AssetName);
    if (AssetType* Existing = LoadObject<AssetType>(nullptr, *ObjectPath))
    {
        return Existing;
    }

    UPackage* Package = CreatePackage(*PackageName);
    AssetType* Asset = NewObject<AssetType>(Package, *AssetName, RF_Public | RF_Standalone | RF_Transactional);
    FAssetRegistryModule::AssetCreated(Asset);
    Package->MarkPackageDirty();
    return Asset;
}

ULevelSequence* LoadOrCreateSequence(const FString& AssetName)
{
    const FString PackageName = FString::Printf(TEXT("/Game/InfinityStage/Dev/Sequences/%s"), *AssetName);
    ULevelSequence* Sequence = LoadOrCreateAsset<ULevelSequence>(PackageName, AssetName);
    if (!Sequence->GetMovieScene())
    {
        Sequence->Initialize();
    }
    return Sequence;
}

USoundWave* ImportSound(const FSourceMusic& Source, const FString& SourceDirectory, TArray<UPackage*>& Packages)
{
    UE_LOG(LogInfinityStageFixture, Display, TEXT("Import step: %s"), Source.Filename);
    const FString ObjectPath = FString::Printf(TEXT("/Game/InfinityStage/Audio/Passages/%s.%s"), Source.AssetName, Source.AssetName);
    if (USoundWave* Existing = LoadObject<USoundWave>(nullptr, *ObjectPath))
    {
        Packages.AddUnique(Existing->GetOutermost());
        return Existing;
    }

    const FString SourcePath = FPaths::Combine(SourceDirectory, Source.Filename);
    if (!FPaths::FileExists(SourcePath))
    {
        return nullptr;
    }

    const FString PackageName = FString::Printf(TEXT("/Game/InfinityStage/Audio/Passages/%s"), Source.AssetName);
    UPackage* Package = CreatePackage(*PackageName);
    USoundFactory* Factory = NewObject<USoundFactory>();
    Factory->SuppressImportDialogs();
    bool bCanceled = false;
    UE_LOG(LogInfinityStageFixture, Display, TEXT("Synchronous WAV factory begin: %s"), *SourcePath);
    USoundWave* Sound = Cast<USoundWave>(UFactory::StaticImportObject(
        USoundWave::StaticClass(),
        Package,
        FName(Source.AssetName),
        RF_Public | RF_Standalone | RF_Transactional,
        bCanceled,
        *SourcePath,
        nullptr,
        Factory));
    UE_LOG(LogInfinityStageFixture, Display, TEXT("Synchronous WAV factory end: %s (sound=%s canceled=%d)"), Source.Filename, Sound ? TEXT("yes") : TEXT("no"), bCanceled);
    if (Sound && !bCanceled)
    {
        FAssetRegistryModule::AssetCreated(Sound);
        Sound->MarkPackageDirty();
        Packages.AddUnique(Package);
        return Sound;
    }
    return nullptr;
}

struct FFixtureWingPalette
{
    TArray<FSoftObjectPath> Left;
    TArray<FSoftObjectPath> Right;
    TArray<FSoftObjectPath> GenericSide;
    TArray<FSoftObjectPath> Top;

    int32 Num() const
    {
        return Left.Num() + Right.Num() + GenericSide.Num() + Top.Num();
    }
};

bool ContainsAny(const FString& Value, const std::initializer_list<const TCHAR*>& Needles)
{
    for (const TCHAR* Needle : Needles)
    {
        if (Value.Contains(Needle))
        {
            return true;
        }
    }
    return false;
}

FFixtureWingPalette FindWingMeshes(const UInfinityStageWingLibraryAsset* Library)
{
    if (Library && !Library->Entries.IsEmpty())
    {
        FFixtureWingPalette FromLibrary;
        for (const FInfinityWingAssetEntry& Entry : Library->Entries)
        {
            if (!Entry.bGeometryCanonical || Entry.Mesh.IsNull())
            {
                continue;
            }
            switch (Entry.Role)
            {
            case EInfinityWingAssetRole::LeftArchitectural: FromLibrary.Left.Add(Entry.Mesh.ToSoftObjectPath()); break;
            case EInfinityWingAssetRole::RightArchitectural: FromLibrary.Right.Add(Entry.Mesh.ToSoftObjectPath()); break;
            case EInfinityWingAssetRole::SideNeutral: FromLibrary.GenericSide.Add(Entry.Mesh.ToSoftObjectPath()); break;
            case EInfinityWingAssetRole::Top: FromLibrary.Top.Add(Entry.Mesh.ToSoftObjectPath()); break;
            default: break;
            }
        }
        if ((!FromLibrary.Left.IsEmpty() || !FromLibrary.GenericSide.IsEmpty())
            && (!FromLibrary.Right.IsEmpty() || !FromLibrary.GenericSide.IsEmpty()))
        {
            return FromLibrary;
        }
    }
    FARFilter Filter;
    Filter.PackagePaths.Add(TEXT("/Game/Wings"));
    Filter.PackagePaths.Add(TEXT("/Game/KK_S2_Shrine/WINGS"));
    Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
    Filter.bRecursivePaths = true;

    TArray<FAssetData> Assets;
    FAssetRegistryModule& AssetRegistry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    AssetRegistry.Get().GetAssets(Filter, Assets);
    Assets.Sort([](const FAssetData& A, const FAssetData& B)
    {
        return A.PackageName.LexicalLess(B.PackageName);
    });

    FFixtureWingPalette Result;
    for (const FAssetData& Asset : Assets)
    {
        FString Name = Asset.AssetName.ToString().ToLower();
        Name.RemoveFromStart(TEXT("sm_"));
        const FSoftObjectPath Path = Asset.ToSoftObjectPath();
        if (ContainsAny(Name, { TEXT("ceiling"), TEXT("celing"), TEXT("overhead"), TEXT("canopy") }))
        {
            Result.Top.Add(Path);
        }
        else if (Name.StartsWith(TEXT("l_")) || ContainsAny(Name, { TEXT("_l_"), TEXT("left") }))
        {
            Result.Left.Add(Path);
        }
        else if (Name.StartsWith(TEXT("r_")) || ContainsAny(Name, { TEXT("_r_"), TEXT("right") }))
        {
            Result.Right.Add(Path);
        }
        else if (ContainsAny(Name, { TEXT("wing"), TEXT("pillar"), TEXT("curtain"), TEXT("wall"), TEXT("tree"), TEXT("barn"), TEXT("building") }))
        {
            Result.GenericSide.Add(Path);
        }
    }
    return Result;
}

const FSoftObjectPath& PickFixtureSideMesh(
    const TArray<FSoftObjectPath>& Preferred,
    const TArray<FSoftObjectPath>& Generic,
    const int32 Index,
    const int32 GenericOffset)
{
    check(!Preferred.IsEmpty() || !Generic.IsEmpty());
    if (!Generic.IsEmpty() && (Preferred.IsEmpty() || Index % 4 == 3))
    {
        return Generic[(Index / 4 + GenericOffset) % Generic.Num()];
    }
    return Preferred[Index % Preferred.Num()];
}

FTransform MakeFixtureTopTransform(const FSoftObjectPath& MeshPath)
{
    FTransform Transform(FRotator(180.0, 0.0, 0.0));
    if (const UStaticMesh* Mesh = Cast<UStaticMesh>(MeshPath.TryLoad()))
    {
        const double WidthAcrossPassage = FMath::Max(1.0, Mesh->GetBoundingBox().GetSize().Y);
        const double UniformScale = FMath::Min(0.60, 1200.0 / WidthAcrossPassage);
        Transform.SetScale3D(FVector(UniformScale));
        Transform.SetTranslation(FVector(0.0, 0.0, 650.0));
    }
    else
    {
        Transform.SetTranslation(FVector(0.0, 0.0, 650.0));
    }
    return Transform;
}

void ConfigureSceneSequence(ULevelSequence& Sequence, ACineCameraActor& Camera, UWorld& World, const int32 DurationFrames)
{
    Sequence.Modify();
    UMovieScene* MovieScene = Sequence.GetMovieScene();
    MovieScene->Modify();
    MovieScene->SetDisplayRate(FFrameRate(25, 1));
    MovieScene->SetTickResolutionDirectly(FFrameRate(24000, 1));
    MovieScene->SetPlaybackRange(0, DurationFrames);

    const FGuid CameraGuid = MovieScene->AddPossessable(Camera.GetActorLabel(), Camera.GetClass());
    Sequence.BindPossessableObject(CameraGuid, Camera, &World);
    UMovieSceneCameraCutTrack* CutTrack = Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack());
    if (!CutTrack)
    {
        CutTrack = CastChecked<UMovieSceneCameraCutTrack>(MovieScene->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
    }
    CutTrack->RemoveAllAnimationData();
    const UE::MovieScene::FRelativeObjectBindingID RelativeBinding(
        MovieSceneSequenceID::Root,
        MovieSceneSequenceID::Root,
        CameraGuid,
        &Sequence);
    UMovieSceneCameraCutSection* Cut = CutTrack->AddNewCameraCut(FMovieSceneObjectBindingID(RelativeBinding), 0);
    Cut->SetRange(TRange<FFrameNumber>(TRangeBound<FFrameNumber>::Inclusive(0), TRangeBound<FFrameNumber>::Exclusive(DurationFrames)));
}
}

bool FInfinityStageDevFixtureBuilder::Build(const FString& MusicSourceDirectory, FString& OutReport)
{
    OutReport.Reset();
    if (!GEditor)
    {
        OutReport = TEXT("Editor engine is unavailable.");
        return false;
    }

    UE_LOG(LogInfinityStageFixture, Display, TEXT("Fixture build begin. Music root: %s"), *MusicSourceDirectory);
    TArray<UPackage*> PackagesToSave;
    TArray<USoundWave*> Sounds;
    for (const FSourceMusic& Source : SourceMusic)
    {
        USoundWave* Sound = ImportSound(Source, MusicSourceDirectory, PackagesToSave);
        if (!Sound)
        {
            OutReport = FString::Printf(TEXT("Could not import %s from %s."), Source.Filename, *MusicSourceDirectory);
            return false;
        }
        Sounds.Add(Sound);
    }

    UE_LOG(LogInfinityStageFixture, Display, TEXT("All WAV imports complete; collecting wing meshes."));
    UInfinityStageWingLibraryAsset* WingLibrary = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
    const FFixtureWingPalette WingMeshes = FindWingMeshes(WingLibrary);
    UE_LOG(LogInfinityStageFixture, Display,
        TEXT("Found %d role-compatible meshes: %d left, %d right, %d generic side, %d top."),
        WingMeshes.Num(), WingMeshes.Left.Num(), WingMeshes.Right.Num(), WingMeshes.GenericSide.Num(), WingMeshes.Top.Num());
    if ((WingMeshes.Left.IsEmpty() && WingMeshes.GenericSide.IsEmpty())
        || (WingMeshes.Right.IsEmpty() && WingMeshes.GenericSide.IsEmpty()))
    {
        OutReport = TEXT("The fixture needs role-compatible side meshes; no usable Left/Right or generic side palette was found.");
        return false;
    }

    UInfinityStageShowAsset* Show = LoadOrCreateAsset<UInfinityStageShowAsset>(
        TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"),
        TEXT("DA_InfinityStage_V1Show"));
    ULevelSequence* Master = LoadOrCreateSequence(TEXT("LS_InfinityStage_V1Master"));
    TArray<ULevelSequence*> SceneSequences;
    for (int32 SceneIndex = 0; SceneIndex < UE_ARRAY_COUNT(SourceMusic) - 1; ++SceneIndex)
    {
        SceneSequences.Add(LoadOrCreateSequence(FString::Printf(TEXT("LS_DevScene_%02d"), SceneIndex + 1)));
    }

    Show->Modify();
    Show->DisplayRate = FFrameRate(25, 1);
    Show->TickResolution = FFrameRate(24000, 1);
    Show->Cues.Reset();
    Show->PassageSettings.Reset();
    Show->MusicRails.Reset();
    Show->ManagedMasterSequence = Master;
    Show->WingLibrary = WingLibrary;

    const double CameraSpeed = 250.0;
    const double Spacing = 500.0;
    const double EntryClearance = 250.0;
    const double ExitClearance = 250.0;
    const int32 TickResolution = Show->TickResolution.Numerator;
    const int32 IntervalFrames = FMath::RoundToInt((Spacing / CameraSpeed) * TickResolution);
    const int32 LeadFrames = FMath::RoundToInt((EntryClearance / CameraSpeed) * TickResolution);

    TArray<FGuid> RailGuids;
    for (int32 PassageIndex = 0; PassageIndex < UE_ARRAY_COUNT(SourceMusic); ++PassageIndex)
    {
        const FSourceMusic& Source = SourceMusic[PassageIndex];
        FInfinityMusicRail& Rail = Show->MusicRails.AddDefaulted_GetRef();
        Rail.RailGuid = FGuid::NewGuid();
        Rail.Label = FText::FromString(FString::Printf(TEXT("Passage %d Music"), PassageIndex + 1));
        Rail.Sound = Sounds[PassageIndex];
        Rail.SourceInFrame = 0;
        Rail.SourceOutFrame = FFrameNumber(FMath::RoundToInt32(Source.DurationSeconds * TickResolution));
        Rail.FadeInFrames = TickResolution;
        Rail.FadeOutFrames = TickResolution;
        Rail.SourceFingerprint = LexToString(FMD5Hash::HashFile(*FPaths::Combine(MusicSourceDirectory, Source.Filename)));
        RailGuids.Add(Rail.RailGuid);

        const FInfinityPassageFitResult Fit = FInfinityStageCompiler::FitPassage({
            Source.DurationSeconds,
            CameraSpeed,
            Spacing,
            EntryClearance,
            ExitClearance });
        for (int32 WingIndex = 0; WingIndex < Fit.WingPairCount; ++WingIndex)
        {
            FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
            Cue.Type = EInfinityCueType::WingPair;
            Cue.CueGuid = FGuid::NewGuid();
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
            Cue.Label = FText::FromString(FString::Printf(TEXT("P%02d Wing %03d"), PassageIndex + 1, WingIndex + 1));
            Cue.WingPair.IntervalToNext = IntervalFrames;
            Cue.WingPair.GapToNextCm = Spacing;
            const int32 LeftMeshIndex = PassageIndex * FixtureSideVariantsPerHand
                + WingIndex % FixtureSideVariantsPerHand;
            const int32 RightMeshIndex = PassageIndex * FixtureSideVariantsPerHand
                + WingIndex % FixtureSideVariantsPerHand;
            Cue.WingPair.Left.Mesh = TSoftObjectPtr<UStaticMesh>(PickFixtureSideMesh(
                WingMeshes.Left, WingMeshes.GenericSide, LeftMeshIndex, 0));
            Cue.WingPair.Right.Mesh = TSoftObjectPtr<UStaticMesh>(PickFixtureSideMesh(
                WingMeshes.Right, WingMeshes.GenericSide, RightMeshIndex, FixtureSideVariantsPerHand));
            Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
            Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
            if (!WingMeshes.Top.IsEmpty() && WingIndex % 8 == 0)
            {
                Cue.WingPair.bHasTop = true;
                const int32 TopMeshIndex = PassageIndex * FixtureTopVariantsPerPassage
                    + (WingIndex / 8) % FixtureTopVariantsPerPassage;
                const FSoftObjectPath& TopMesh = WingMeshes.Top[TopMeshIndex % WingMeshes.Top.Num()];
                Cue.WingPair.Top.Mesh = TSoftObjectPtr<UStaticMesh>(TopMesh);
                Cue.WingPair.Top.LocalTransform = MakeFixtureTopTransform(TopMesh);
            }
            Cue.WingPair.Mechanism.PlaybackMode = EInfinityMotionPlaybackMode::ContinuousLoop;
            Cue.WingPair.Mechanism.CycleRateHz = 0.25;
            Cue.WingPair.Mechanism.PhaseOffsetCycles = (WingIndex % 8) / 8.0;
            Cue.WingPair.Mechanism.LeftNormalizedCurve.GetRichCurve()->AddKey(0.0f, 0.0f);
            Cue.WingPair.Mechanism.LeftNormalizedCurve.GetRichCurve()->AddKey(0.5f, 1.0f);
            Cue.WingPair.Mechanism.LeftNormalizedCurve.GetRichCurve()->AddKey(1.0f, 0.0f);
            Cue.WingPair.Mechanism.RightNormalizedCurve = Cue.WingPair.Mechanism.LeftNormalizedCurve;
        }

        if (PassageIndex + 1 < UE_ARRAY_COUNT(SourceMusic))
        {
            FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
            Scene.Type = EInfinityCueType::Scene;
            Scene.CueGuid = FGuid::NewGuid();
            Scene.Label = FText::FromString(FString::Printf(TEXT("Scene %d — Placeholder"), PassageIndex + 1));
            Scene.Scene.Sequence = SceneSequences[PassageIndex];
            Scene.Scene.DurationFrames = 15 * TickResolution;
            // These placeholders are silent, so declaring an unpausable external
            // clock only blocks seek, reverse and hold inside them for no reason.
            // Authored Scenes that really are driven from outside UE set this
            // themselves; the fixture must not assert it on their behalf.
            Scene.Scene.ExternalSound = EInfinityExternalSoundAuthority::None;
            Scene.Scene.Music.Mode = EInfinityMusicBindingMode::Silence;
        }
    }

    Show->EnsureStableIds();
    Show->ReconcilePassageSettings();
    for (int32 PassageIndex = 0; PassageIndex < Show->PassageSettings.Num(); ++PassageIndex)
    {
        FInfinityPassageSettings& Settings = Show->PassageSettings[PassageIndex];
        const double DurationSeconds = SourceMusic[PassageIndex].DurationSeconds;
        const int32 DurationFrames = FMath::RoundToInt(DurationSeconds * TickResolution);
        const FInfinityPassageFitResult Fit = FInfinityStageCompiler::FitPassage({
            DurationSeconds,
            CameraSpeed,
            Spacing,
            EntryClearance,
            ExitClearance });
        Settings.Label = FText::FromString(FString::Printf(TEXT("Passage %d"), PassageIndex + 1));
        Settings.LeadInFrames = LeadFrames;
        Settings.TailFrames = FMath::Max(1, DurationFrames - LeadFrames - (Fit.WingPairCount - 1) * IntervalFrames);
        Settings.LeadInDistanceCm = EntryClearance;
        Settings.TailDistanceCm = FMath::Max(0.01, DurationSeconds * CameraSpeed - EntryClearance - (Fit.WingPairCount - 1) * Spacing);
        Settings.PreferredCameraSpeedCmPerSecond = CameraSpeed;
        Settings.Music.Mode = EInfinityMusicBindingMode::Start;
        Settings.Music.PrimaryRailGuid = RailGuids[PassageIndex];
    }
    Show->MarkPackageDirty();
    PackagesToSave.AddUnique(Show->GetOutermost());

    FString BuildReport;
    if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, BuildReport))
    {
        OutReport = BuildReport;
        return false;
    }
    PackagesToSave.AddUnique(Master->GetOutermost());
    for (ULevelSequence* Scene : SceneSequences)
    {
        PackagesToSave.AddUnique(Scene->GetOutermost());
    }

    UWorld* World = UEditorLoadingAndSavingUtils::NewBlankMap(false);
    if (!World)
    {
        OutReport = TEXT("Could not create the V1 fixture map.");
        return false;
    }
    World->Modify();

    AInfinityStageShowRoot* ShowRoot = World->SpawnActor<AInfinityStageShowRoot>();
    ShowRoot->SetActorLabel(TEXT("Infinity Stage — One Master Authority"));
    ShowRoot->ShowAsset = Show;
    ShowRoot->MasterSequence = Master;

    // A single show-wide sky is evaluated by the same Master Passage sections
    // as the wings/cameras. The ordinary light/fog actors remain easy for an
    // artist to select and tune in the World Outliner.
    ASkyAtmosphere* Atmosphere = World->SpawnActor<ASkyAtmosphere>();
    Atmosphere->SetActorLabel(TEXT("Infinity Stage - Dusk Sky Atmosphere"));
    Atmosphere->SetFolderPath(TEXT("Infinity Stage/Environment - Celestial"));

    ADirectionalLight* Sun = World->SpawnActor<ADirectionalLight>();
    Sun->SetActorLabel(TEXT("Infinity Stage - Sun"));
    Sun->SetFolderPath(TEXT("Infinity Stage/Environment - Celestial"));
    Sun->Tags.Add(TEXT("InfinityStage.CelestialSun"));
    if (UDirectionalLightComponent* SunComponent = Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
    {
        SunComponent->SetMobility(EComponentMobility::Movable);
        SunComponent->SetAtmosphereSunLight(true);
        SunComponent->SetAtmosphereSunLightIndex(0);
    }

    ADirectionalLight* Moon = World->SpawnActor<ADirectionalLight>();
    Moon->SetActorLabel(TEXT("Infinity Stage - Moon"));
    Moon->SetFolderPath(TEXT("Infinity Stage/Environment - Celestial"));
    Moon->Tags.Add(TEXT("InfinityStage.CelestialMoon"));
    if (UDirectionalLightComponent* MoonComponent = Cast<UDirectionalLightComponent>(Moon->GetLightComponent()))
    {
        MoonComponent->SetMobility(EComponentMobility::Movable);
        MoonComponent->SetAtmosphereSunLight(true);
        MoonComponent->SetAtmosphereSunLightIndex(1);
    }

    ASkyLight* SkyLight = World->SpawnActor<ASkyLight>();
    SkyLight->SetActorLabel(TEXT("Infinity Stage - Celestial Skylight"));
    SkyLight->SetFolderPath(TEXT("Infinity Stage/Environment - Celestial"));
    SkyLight->Tags.Add(TEXT("InfinityStage.CelestialSkyLight"));
    SkyLight->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    SkyLight->GetLightComponent()->SetRealTimeCapture(true);

    AExponentialHeightFog* HeightFog = World->SpawnActor<AExponentialHeightFog>();
    HeightFog->SetActorLabel(TEXT("Infinity Stage - Celestial Height Fog"));
    HeightFog->SetFolderPath(TEXT("Infinity Stage/Environment - Celestial"));
    HeightFog->Tags.Add(TEXT("InfinityStage.CelestialFog"));
    HeightFog->GetComponent()->SetVolumetricFog(true);

    AInfinityStageCelestialRig* CelestialRig = World->SpawnActor<AInfinityStageCelestialRig>();
    CelestialRig->SetActorLabel(TEXT("Infinity Stage - Sun Moon Stars Cycle"));
    CelestialRig->SetFolderPath(TEXT("Infinity Stage/Environment - Celestial"));
    CelestialRig->SunLightActor = Sun;
    CelestialRig->MoonLightActor = Moon;
    CelestialRig->SkyLightActor = SkyLight;
    CelestialRig->HeightFogActor = HeightFog;
    CelestialRig->ApplyCyclePhase(CelestialRig->InitialPhaseCycles);

    for (int32 PassageIndex = 0; PassageIndex < Show->PassageSettings.Num(); ++PassageIndex)
    {
        const FVector BayOrigin(0.0, PassageIndex * 80000.0, 0.0);
        AInfinityStagePassageActor* PassageActor = World->SpawnActor<AInfinityStagePassageActor>(BayOrigin, FRotator::ZeroRotator);
        PassageActor->SetActorLabel(FString::Printf(TEXT("Passage %02d — Fixed Wings"), PassageIndex + 1));
        PassageActor->ShowAsset = Show;
        PassageActor->PassageGuid = Show->PassageSettings[PassageIndex].PassageGuid;
        // The fixture starts at 30 render keys but deliberately keeps editing headroom:
        // replacing one occurrence must not make the entire Passage invalid.
        PassageActor->ComponentBudget = FixtureComponentBudget;
        if (!PassageActor->MaterializePassage())
        {
            OutReport = FString::Printf(TEXT("Materialization failed for Passage %d."), PassageIndex + 1);
            return false;
        }

        AInfinityStageCameraRig* CameraRig = World->SpawnActor<AInfinityStageCameraRig>(BayOrigin, FRotator::ZeroRotator);
        CameraRig->SetActorLabel(FString::Printf(TEXT("Passage %02d — Camera + Shadow Figures"), PassageIndex + 1));
        CameraRig->PassageActor = PassageActor;
        CameraRig->CameraOffset = FVector(0.0, 0.0, 180.0);

        if (PassageIndex < SceneSequences.Num())
        {
            const FVector SceneOrigin(0.0, PassageIndex * 80000.0 + 40000.0, 180.0);
            ACineCameraActor* SceneCamera = World->SpawnActor<ACineCameraActor>(SceneOrigin, FRotator::ZeroRotator);
            SceneCamera->SetActorLabel(FString::Printf(TEXT("Scene %02d — Establishing / Exit Camera"), PassageIndex + 1));
            ConfigureSceneSequence(*SceneSequences[PassageIndex], *SceneCamera, *World, 15 * TickResolution);
        }
    }

    if (!UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, false))
    {
        OutReport = TEXT("Fixture assets were built, but one or more packages did not save.");
        return false;
    }
    if (!UEditorLoadingAndSavingUtils::SaveMap(World, TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice")))
    {
        OutReport = TEXT("Fixture assets saved, but the vertical-slice map did not save.");
        return false;
    }

    int32 WingPairCount = 0;
    for (const FInfinityShowCue& Cue : Show->Cues)
    {
        WingPairCount += Cue.Type == EInfinityCueType::WingPair ? 1 : 0;
    }
    OutReport = FString::Printf(
        TEXT("Created six music-led Passages, five external-sound Scenes, %d fixed Wing Pairs, %d distinct source meshes per Passage (%d currently available overall), one Master-driven sun/moon/stars cycle, one managed Master, and one saved map. %s"),
        WingPairCount,
        FixtureDistinctMeshesPerPassage,
        WingMeshes.Num(),
        *BuildReport);
    return true;
}

bool FInfinityStageDevFixtureBuilder::RepairCurrentWingPassages(FString& OutReport)
{
    OutReport.Reset();
    if (!GEditor)
    {
        OutReport = TEXT("Editor engine is unavailable.");
        return false;
    }

    UInfinityStageWingLibraryAsset* WingLibrary = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
    FInfinityWingAuditSummary AuditSummary;
    FString AuditError;
    if (!WingLibrary || !FInfinityStageWingAssetAuditor::Scan(*WingLibrary, AuditSummary, AuditError))
    {
        OutReport = AuditError.IsEmpty() ? TEXT("The Wing Library audit failed.") : AuditError;
        return false;
    }
    int32 RepairedLegacyRightMirrors = 0;
    if (!FInfinityStageWingAssetAuditor::RepairLegacyRightPhotographicMirrors(
        *WingLibrary, RepairedLegacyRightMirrors, AuditError))
    {
        OutReport = AuditError.IsEmpty()
            ? TEXT("The legacy right-wing mirror repair failed.")
            : AuditError;
        return false;
    }
    const FFixtureWingPalette Palette = FindWingMeshes(WingLibrary);
    if ((Palette.Left.IsEmpty() && Palette.GenericSide.IsEmpty())
        || (Palette.Right.IsEmpty() && Palette.GenericSide.IsEmpty()))
    {
        OutReport = TEXT("No role-approved replacement palette is available.");
        return false;
    }

    UInfinityStageShowAsset* Show = LoadObject<UInfinityStageShowAsset>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show.DA_InfinityStage_V1Show"));
    if (!Show)
    {
        OutReport = TEXT("The current Infinity Stage Show Asset could not be loaded.");
        return false;
    }

    const auto IsExcluded = [WingLibrary](const FInfinityPanelDesign& Panel)
    {
        const FInfinityWingAssetEntry* Entry = WingLibrary->FindEntry(Panel.Mesh.ToSoftObjectPath());
        return Entry && Entry->Role == EInfinityWingAssetRole::Excluded;
    };

    Show->Modify();
    int32 ReplacedPanels = 0;
    int32 WingOrdinal = 0;
    for (FInfinityShowCue& Cue : Show->Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        FInfinityWingOccurrence& Wing = Cue.WingPair;
        if (IsExcluded(Wing.Left))
        {
            Wing.Left.Mesh = TSoftObjectPtr<UStaticMesh>(PickFixtureSideMesh(
                Palette.Left, Palette.GenericSide, WingOrdinal, 0));
            ++ReplacedPanels;
        }
        if (IsExcluded(Wing.Right))
        {
            Wing.Right.Mesh = TSoftObjectPtr<UStaticMesh>(PickFixtureSideMesh(
                Palette.Right, Palette.GenericSide, WingOrdinal, FixtureSideVariantsPerHand));
            ++ReplacedPanels;
        }
        if (Wing.bHasTop && IsExcluded(Wing.Top))
        {
            if (Palette.Top.IsEmpty())
            {
                Wing.bHasTop = false;
                Wing.Top.Mesh.Reset();
            }
            else
            {
                Wing.Top.Mesh = TSoftObjectPtr<UStaticMesh>(Palette.Top[WingOrdinal % Palette.Top.Num()]);
            }
            ++ReplacedPanels;
        }
        ++WingOrdinal;
    }
    Show->MarkPackageDirty();
    if (!UEditorLoadingAndSavingUtils::SavePackages({ Show->GetOutermost() }, false))
    {
        OutReport = TEXT("The repaired Show Asset did not save.");
        return false;
    }

    UWorld* World = UEditorLoadingAndSavingUtils::LoadMap(
        TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"));
    if (!World)
    {
        OutReport = TEXT("The current Infinity Stage fixture map could not be loaded.");
        return false;
    }

    int32 RepairedPassages = 0;
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        AInfinityStagePassageActor* PassageActor = *It;
        if (PassageActor->ShowAsset != Show)
        {
            continue;
        }
        PassageActor->Modify();
        PassageActor->ComponentBudget = FMath::Max(PassageActor->ComponentBudget, FixtureComponentBudget);
        if (!PassageActor->MaterializePassage())
        {
            OutReport = FString::Printf(
                TEXT("%s could not be rematerialized; the previous valid instances were preserved."),
                *PassageActor->GetActorLabel());
            return false;
        }
        ++RepairedPassages;
    }
    if (!UEditorLoadingAndSavingUtils::SaveMap(
        World,
        TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice")))
    {
        OutReport = TEXT("The repaired fixture map did not save.");
        return false;
    }

    OutReport = FString::Printf(
        TEXT("Repaired %d legacy mirrored right-wing asset(s), replaced %d excluded Curtain panel assignment(s), preserved every other authored cue, raised editing headroom, and rematerialized %d Passage(s)."),
        RepairedLegacyRightMirrors,
        ReplacedPanels,
        RepairedPassages);
    return RepairedPassages > 0;
}
