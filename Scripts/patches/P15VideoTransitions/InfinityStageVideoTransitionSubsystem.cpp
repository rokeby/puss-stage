#include "InfinityStageVideoTransitionSubsystem.h"

#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageTypes.h"
#include "Blueprint/UserWidget.h"
#include "Components/MediaSoundComponent.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "JsonObjectConverter.h"
#include "MediaPlayer.h"
#include "MediaTexture.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SOverlay.h"
#include "Widgets/Layout/SScaleBox.h"

DEFINE_LOG_CATEGORY_STATIC(LogP15Video, Log, All);

void UInfinityStageVideoTransitionSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    Player = NewObject<UMediaPlayer>(this);
    Texture = NewObject<UMediaTexture>(this);
    Texture->SetMediaPlayer(Player);
    Texture->UpdateResource();
    Player->PlayOnOpen = false;
    Player->OnMediaOpened.AddDynamic(this, &ThisClass::OnMediaOpened);
    Player->OnMediaOpenFailed.AddDynamic(this, &ThisClass::OnMediaOpenFailed);

    Sound = NewObject<UMediaSoundComponent>(GetWorld());
    Sound->SetMediaPlayer(Player);
    Sound->RegisterComponentWithWorld(GetWorld());

    Brush = MakeShared<FSlateBrush>();
    Brush->SetResourceObject(Texture);
    Brush->ImageSize = FVector2D(1920.0, 1080.0);
    SAssignNew(Overlay, SOverlay)
    + SOverlay::Slot()[SNew(SImage).ColorAndOpacity(FLinearColor::Black)]
    + SOverlay::Slot().HAlign(HAlign_Fill).VAlign(VAlign_Fill)
      [SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
       [SAssignNew(Image, SImage).Image(Brush.Get())]];
    Overlay->SetVisibility(EVisibility::Collapsed);
    if (GetWorld() && GetWorld()->GetGameViewport())
    {
        GetWorld()->GetGameViewport()->AddViewportWidgetContent(Overlay.ToSharedRef(), 10000);
    }
    LoadRegistry();
}

void UInfinityStageVideoTransitionSubsystem::Deinitialize()
{
    if (GetWorld() && GetWorld()->GetGameViewport() && Overlay.IsValid())
    {
        GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(Overlay.ToSharedRef());
    }
    if (Sound) { Sound->UnregisterComponent(); }
    if (Player) { Player->Close(); }
    Super::Deinitialize();
}

TStatId UInfinityStageVideoTransitionSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UInfinityStageVideoTransitionSubsystem, STATGROUP_Tickables);
}

bool UInfinityStageVideoTransitionSubsystem::LoadRegistry()
{
    const FString Registry = FPaths::ConvertRelativePathToFull(
        FPaths::ProjectDir() / TEXT("DerivedAssets/P15VideoTransitions/placeholder_current.json"));
    FString Text;
    TSharedPtr<FJsonObject> RootJson;
    if (!FFileHelper::LoadFileToString(Text, *Registry))
    {
        ShowBlack(TEXT("P15_VIDEO_REGISTRY_MISSING"), Registry);
        return false;
    }
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, RootJson) || !RootJson.IsValid())
    {
        ShowBlack(TEXT("P15_VIDEO_REGISTRY_BAD_JSON"), Registry);
        return false;
    }
    const TSharedPtr<FJsonObject>* SceneObject = nullptr;
    if (!RootJson->TryGetObjectField(TEXT("scenes"), SceneObject)) { return false; }
    for (int32 Ordinal = 1; Ordinal <= 6; ++Ordinal)
    {
        const TSharedPtr<FJsonObject>* Row = nullptr;
        if (!(*SceneObject)->TryGetObjectField(FString::Printf(TEXT("S%d"), Ordinal), Row)) { continue; }
        FSceneMedia Media;
        (*Row)->TryGetStringField(TEXT("playback_file"), Media.PlaybackFile);
        (*Row)->TryGetStringField(TEXT("audio_owner"), Media.AudioOwner);
        Media.Fps = (*Row)->GetIntegerField(TEXT("fps"));
        Media.MediaFrames = (*Row)->GetIntegerField(TEXT("media_frames"));
        Media.bLoop = (*Row)->GetBoolField(TEXT("loop"));
        Scenes.Add(Ordinal, Media);
    }
    return Scenes.Num() > 0;
}

AInfinityStageShowRoot* UInfinityStageVideoTransitionSubsystem::FindShowRoot() const
{
    for (TActorIterator<AInfinityStageShowRoot> It(GetWorld()); It; ++It) { return *It; }
    return nullptr;
}

bool UInfinityStageVideoTransitionSubsystem::ResolveScene(
    const int32 MasterFrame, int32& OutOrdinal, int32& OutStart) const
{
    if (!Root || !Root->Transport) { return false; }
    int32 Ordinal = 0;
    for (const FInfinityTransportSegment& Segment : Root->Transport->Segments)
    {
        if (Segment.Type != EInfinityCueType::Scene) { continue; }
        ++Ordinal;
        if (MasterFrame >= Segment.StartFrame.Value && MasterFrame < Segment.EndFrame.Value)
        {
            OutOrdinal = Ordinal;
            OutStart = Segment.StartFrame.Value;
            return true;
        }
    }
    return false;
}

void UInfinityStageVideoTransitionSubsystem::EnterScene(const int32 Ordinal, const int32 LocalFrame)
{
    ActiveOrdinal = Ordinal;
    LastRequestedFrame = INDEX_NONE;
    bOpen = false;
    bSeekPending = false;
    Overlay->SetVisibility(EVisibility::Visible);
    Image->SetVisibility(EVisibility::Hidden);
    const FSceneMedia* Media = Scenes.Find(Ordinal);
    if (!Media)
    {
        ShowBlack(TEXT("P15_VIDEO_SCENE_UNREGISTERED"), FString::FromInt(Ordinal));
        return;
    }
    const FString FullPath = FPaths::ConvertRelativePathToFull(
        FPaths::ProjectDir() / TEXT("DerivedAssets/P15VideoTransitions") / Media->PlaybackFile);
    if (!IFileManager::Get().FileExists(*FullPath))
    {
        ShowBlack(TEXT("P15_VIDEO_FILE_MISSING"), FullPath);
        return;
    }
    if (!Media->AudioOwner.Equals(TEXT("ue_muxed")) && !Media->AudioOwner.Equals(TEXT("desk")))
    {
        ShowBlack(TEXT("P15_VIDEO_AUDIO_OWNER_BAD"), Media->AudioOwner);
        return;
    }
    const bool bUeOwnsAudio = Media->AudioOwner.Equals(TEXT("ue_muxed"));
    Sound->SetVolumeMultiplier(bUeOwnsAudio ? 1.0f : 0.0f);
    Player->SetLooping(Media->bLoop);
    ShowBlack(TEXT("P15_VIDEO_OPENING"), FullPath);
    Player->OpenFile(FullPath);
}

void UInfinityStageVideoTransitionSubsystem::OnMediaOpened(FString OpenedUrl)
{
    bOpen = true;
    bSeekPending = false;
    LastRequestedFrame = INDEX_NONE;
    UE_LOG(LogP15Video, Display, TEXT("P15_VIDEO_OPEN_OK|scene=S%d|url=%s"), ActiveOrdinal, *OpenedUrl);
}

void UInfinityStageVideoTransitionSubsystem::OnMediaOpenFailed(FString FailedUrl)
{
    bOpen = false;
    ShowBlack(TEXT("P15_VIDEO_OPEN_FAILED"), FailedUrl);
}

void UInfinityStageVideoTransitionSubsystem::SyncToFrame(const int32 LocalFrame, const bool bPlaying)
{
    const FSceneMedia* Media = Scenes.Find(ActiveOrdinal);
    if (!Media || !bOpen || Media->Fps <= 0 || Media->MediaFrames <= 0) { return; }
    const int32 WantedFrame = Media->bLoop ? LocalFrame % Media->MediaFrames : LocalFrame;
    if (WantedFrame < 0 || WantedFrame >= Media->MediaFrames)
    {
        ShowBlack(TEXT("P15_VIDEO_OUT_OF_RANGE"), FString::FromInt(WantedFrame));
        return;
    }
    const FTimespan Wanted = FTimespan::FromSeconds(double(WantedFrame) / Media->Fps);
    const double ErrorFrames = FMath::Abs((Player->GetTime() - Wanted).GetTotalSeconds() * Media->Fps);
    const bool bJump = LastRequestedFrame == INDEX_NONE || FMath::Abs(WantedFrame - LastRequestedFrame) > 1;
    if (bJump || (!bSeekPending && ErrorFrames > 0.5))
    {
        Image->SetVisibility(EVisibility::Hidden);
        if (!Player->Seek(Wanted))
        {
            ShowBlack(TEXT("P15_VIDEO_SEEK_FAILED"), FString::FromInt(WantedFrame));
            return;
        }
        bSeekPending = true;
    }
    LastRequestedFrame = WantedFrame;
    if (bPlaying) { Player->Play(); } else { Player->Pause(); }
    const double SettledError = FMath::Abs((Player->GetTime() - Wanted).GetTotalSeconds() * Media->Fps);
    if (SettledError <= 0.5)
    {
        bSeekPending = false;
        Image->SetVisibility(EVisibility::Visible);
    }
    else
    {
        Image->SetVisibility(EVisibility::Hidden);
    }
}

void UInfinityStageVideoTransitionSubsystem::Tick(float DeltaSeconds)
{
    if (!Root) { Root = FindShowRoot(); }
    if (!Root || !Root->Transport || !Root->SequencePlayer) { HideOverlay(); return; }
    const int32 MasterFrame = Root->Transport->GetCurrentMasterFrame().Value;
    int32 Ordinal = INDEX_NONE;
    int32 SceneStart = 0;
    if (!ResolveScene(MasterFrame, Ordinal, SceneStart)) { HideOverlay(); return; }
    if (Ordinal != ActiveOrdinal)
    {
        ActiveSceneStart = SceneStart;
        EnterScene(Ordinal, MasterFrame - SceneStart);
    }
    SyncToFrame(MasterFrame - ActiveSceneStart, Root->SequencePlayer->IsPlaying());
}

void UInfinityStageVideoTransitionSubsystem::ShowBlack(const FString& Marker, const FString& Detail)
{
    if (Overlay) { Overlay->SetVisibility(EVisibility::Visible); }
    if (Image) { Image->SetVisibility(EVisibility::Hidden); }
    const FString Key = Marker + Detail;
    if (Key != LastBlackKey)
    {
        UE_LOG(LogP15Video, Warning, TEXT("%s|%s"), *Marker, *Detail);
        LastBlackKey = Key;
    }
}

void UInfinityStageVideoTransitionSubsystem::HideOverlay()
{
    if (Overlay) { Overlay->SetVisibility(EVisibility::Collapsed); }
    if (Player && ActiveOrdinal != INDEX_NONE) { Player->Close(); }
    ActiveOrdinal = INDEX_NONE;
    LastRequestedFrame = INDEX_NONE;
    bOpen = false;
    bSeekPending = false;
}
