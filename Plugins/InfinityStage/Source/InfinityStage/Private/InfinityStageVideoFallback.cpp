#include "InfinityStageVideoFallback.h"

#include "Dom/JsonObject.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStageCueSheet.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "LevelSequencePlayer.h"
#include "MediaPlayer.h"
#include "MediaSoundComponent.h"
#include "MediaTexture.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SOverlay.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageVideoFallback, Log, All);

namespace
{
TAutoConsoleVariable<FString> CVarFallbackRoot(
    TEXT("InfinityStage.VideoFallback.Root"),
    TEXT(""),
    TEXT("Folder holding current.json and the Scene fallback videos. Empty: <Project>/Renders/Fallbacks"));

TAutoConsoleVariable<int32> CVarWhiteFadeSchema(
    TEXT("InfinityStage.VideoFallback.WhiteFadeSchema"),
    1,
    TEXT("Read-only capability marker: current.json scenes may specify fade_from_white_seconds."),
    ECVF_ReadOnly);

/** Live overlay order: under the rehearsal bar (20), over the show. */
constexpr int32 OverlayZOrder = 5;
}

namespace InfinityStageVideoFallback
{
FString ResolveRoot()
{
    const FString Override = CVarFallbackRoot.GetValueOnGameThread();
    return Override.IsEmpty()
        ? FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("Renders/Fallbacks")))
        : Override;
}

TMap<int32, FInfinityFallbackClip> ParseRegistry(const FString& Json, const FString& FallbackRoot, TArray<FString>& OutWarnings)
{
    TMap<int32, FInfinityFallbackClip> Clips;
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutWarnings.Add(TEXT("current.json is not valid JSON"));
        return Clips;
    }
    const TSharedPtr<FJsonObject>* Scenes = nullptr;
    if (!Root->TryGetObjectField(TEXT("scenes"), Scenes) || !Scenes)
    {
        OutWarnings.Add(TEXT("current.json has no 'scenes' object"));
        return Clips;
    }
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Entry : (*Scenes)->Values)
    {
        const FString Key = Entry.Key.ToUpper();
        const int32 Ordinal = Key.StartsWith(TEXT("S")) ? FCString::Atoi(*Key.Mid(1)) : 0;
        const TSharedPtr<FJsonObject> Scene = Entry.Value.IsValid() ? Entry.Value->AsObject() : nullptr;
        if (Ordinal <= 0 || !Scene.IsValid())
        {
            OutWarnings.Add(FString::Printf(TEXT("scene entry '%s' skipped (expected S<n> with an object)"), *Entry.Key));
            continue;
        }
        FString Video;
        if (!Scene->TryGetStringField(TEXT("video"), Video) || Video.IsEmpty())
        {
            OutWarnings.Add(FString::Printf(TEXT("%s has no 'video'"), *Key));
            continue;
        }
        FInfinityFallbackClip Clip;
        Clip.VideoPath = FPaths::ConvertRelativePathToFull(FPaths::Combine(FallbackRoot, Video));
        FString Muxed;
        if (Scene->TryGetStringField(TEXT("muxed"), Muxed) && !Muxed.IsEmpty())
        {
            Clip.MuxedPath = FPaths::ConvertRelativePathToFull(FPaths::Combine(FallbackRoot, Muxed));
        }
        double Number = 0.0;
        if (Scene->TryGetNumberField(TEXT("frames"), Number))
        {
            Clip.Frames = static_cast<int32>(Number);
        }
        if (Scene->TryGetNumberField(TEXT("fps"), Number) && Number > 0.0)
        {
            Clip.Fps = Number;
        }
        if (Scene->TryGetNumberField(TEXT("fade_from_white_seconds"), Number))
        {
            if (Number < 0.0 || !FMath::IsFinite(Number))
            {
                OutWarnings.Add(FString::Printf(TEXT("%s has invalid fade_from_white_seconds; using 0"), *Key));
            }
            else
            {
                Clip.FadeFromWhiteSeconds = Number;
            }
        }
        Clips.Add(Ordinal, Clip);
    }
    return Clips;
}

double MediaSecondsForLocalFrame(const int32 LocalFrame, const double ShowTicksPerSecond, const FInfinityFallbackClip& Clip)
{
    if (ShowTicksPerSecond <= 0.0)
    {
        return 0.0;
    }
    const double Seconds = FMath::Max(0, LocalFrame) / ShowTicksPerSecond;
    const double Length = Clip.Frames > 0 && Clip.Fps > 0.0 ? (Clip.Frames - 1) / Clip.Fps : Seconds;
    return FMath::Clamp(Seconds, 0.0, FMath::Max(0.0, Length));
}
}

bool UInfinityStageVideoFallbackSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UInfinityStageVideoFallbackSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    Player = NewObject<UMediaPlayer>(this, NAME_None, RF_Transient);
    Player->PlayOnOpen = false;
    Player->OnMediaOpened.AddDynamic(this, &UInfinityStageVideoFallbackSubsystem::HandleOpened);
    Player->OnMediaOpenFailed.AddDynamic(this, &UInfinityStageVideoFallbackSubsystem::HandleOpenFailed);
    Texture = NewObject<UMediaTexture>(this, NAME_None, RF_Transient);
    Texture->SetMediaPlayer(Player);
    Texture->UpdateResource();
    ReloadRegistry();
}

void UInfinityStageVideoFallbackSubsystem::Deinitialize()
{
    Leave(TEXT("deinitialize"));
    if (bOverlayAdded && Overlay.IsValid() && GetWorld() && GetWorld()->GetGameViewport())
    {
        GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(Overlay.ToSharedRef());
    }
    if (Sound)
    {
        Sound->UnregisterComponent();
    }
    Super::Deinitialize();
}

void UInfinityStageVideoFallbackSubsystem::ReloadRegistry()
{
    const FString FallbackRoot = InfinityStageVideoFallback::ResolveRoot();
    FString Text;
    Clips.Reset();
    FailedOrdinal = INDEX_NONE;
    if (FFileHelper::LoadFileToString(Text, *FPaths::Combine(FallbackRoot, TEXT("current.json"))))
    {
        TArray<FString> Warnings;
        Clips = InfinityStageVideoFallback::ParseRegistry(Text, FallbackRoot, Warnings);
        for (const FString& Warning : Warnings)
        {
            Warn(Warning);
        }
    }
    UE_LOG(LogInfinityStageVideoFallback, Log, TEXT("INFINITY_VIDEO_FALLBACK_REGISTRY clips=%d root=%s"), Clips.Num(), *FallbackRoot);
}

void UInfinityStageVideoFallbackSubsystem::Warn(const FString& Message)
{
    if (!Warned.Contains(Message))
    {
        Warned.Add(Message);
        UE_LOG(LogInfinityStageVideoFallback, Warning, TEXT("INFINITY_VIDEO_FALLBACK %s"), *Message);
    }
}

void UInfinityStageVideoFallbackSubsystem::EnsureOverlay()
{
    UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr;
    if (bOverlayAdded || !Viewport)
    {
        return;
    }
    Brush = MakeShared<FSlateBrush>();
    Brush->SetResourceObject(Texture);
    Brush->ImageSize = FVector2D(1920.0, 1080.0);
    Overlay = SNew(SOverlay)
        .Visibility(EVisibility::Collapsed)
        + SOverlay::Slot()[ SNew(SImage).ColorAndOpacity(FLinearColor::Black) ]
        + SOverlay::Slot()
        [
            SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
            [
                SAssignNew(Image, SImage).Image(Brush.Get())
            ]
        ]
        + SOverlay::Slot()
        [ SAssignNew(WhiteImage, SImage).ColorAndOpacity(FLinearColor::Transparent) ];
    Viewport->AddViewportWidgetContent(Overlay.ToSharedRef(), OverlayZOrder);
    bOverlayAdded = true;
}

void UInfinityStageVideoFallbackSubsystem::SetLiveSuppressed(const bool bSuppressed)
{
    if (bLiveSuppressed == bSuppressed)
    {
        return;
    }
    bLiveSuppressed = bSuppressed;
    if (UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr)
    {
        // Nothing of the live Scene is seen under the video: do not pay to render it.
        Viewport->bDisableWorldRendering = bSuppressed;
    }
    if (AInfinityStageShowRoot* ShowRoot = Root.Get())
    {
        if (ShowRoot->Transport)
        {
            ShowRoot->Transport->SetVideoAudioMuted(bSuppressed);
        }
    }
    if (Overlay.IsValid())
    {
        Overlay->SetVisibility(bSuppressed ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
    }
    UE_LOG(LogInfinityStageVideoFallback, Display, TEXT("INFINITY_VIDEO_FALLBACK_LIVE_%s scene=S%d"),
        bSuppressed ? TEXT("OFF") : TEXT("ON"), ActiveOrdinal);
}

void UInfinityStageVideoFallbackSubsystem::Enter(const int32 Ordinal)
{
    Leave(TEXT("switch"));
    const FInfinityFallbackClip* Clip = Clips.Find(Ordinal);
    if (!Clip)
    {
        return;
    }
    FString VideoAudio = TEXT("ue");
    if (UInfinityStageCueDirectorSubsystem* Director = GetWorld()->GetSubsystem<UInfinityStageCueDirectorSubsystem>())
    {
        VideoAudio = Director->GetSettings().VideoAudio;
    }
    const bool bUeSound = !VideoAudio.Equals(TEXT("desk"), ESearchCase::IgnoreCase);
    FString Path = Clip->VideoPath;
    if (bUeSound && !Clip->MuxedPath.IsEmpty() && IFileManager::Get().FileExists(*Clip->MuxedPath))
    {
        Path = Clip->MuxedPath;
    }
    else if (bUeSound)
    {
        Warn(FString::Printf(TEXT("S%d: video_audio=ue but no muxed file; the video plays silent (desk WAV needed)"), Ordinal));
    }
    if (!IFileManager::Get().FileExists(*Path))
    {
        Warn(FString::Printf(TEXT("S%d: file missing %s; playing the LIVE Scene"), Ordinal, *Path));
        FailedOrdinal = Ordinal;
        return;
    }
    if (!Sound)
    {
        Sound = NewObject<UMediaSoundComponent>(this, NAME_None, RF_Transient);
        Sound->SetMediaPlayer(Player);
        Sound->RegisterComponentWithWorld(GetWorld());
    }
    Sound->SetVolumeMultiplier(Path == Clip->MuxedPath ? 1.0f : 0.0f);
    ActiveOrdinal = Ordinal;
    bOpen = false;
    bPictureUp = false;
    if (WhiteImage.IsValid())
    {
        WhiteImage->SetColorAndOpacity(Clip->FadeFromWhiteSeconds > 0.0
            ? FLinearColor::White : FLinearColor::Transparent);
    }
    Player->SetLooping(false);
    Player->OpenFile(Path);
    UE_LOG(LogInfinityStageVideoFallback, Display,
        TEXT("INFINITY_VIDEO_FALLBACK_OPEN scene=S%d file=%s ue_sound=%d fade_from_white_s=%.3f"),
        Ordinal, *Path, Path == Clip->MuxedPath ? 1 : 0, Clip->FadeFromWhiteSeconds);
}

void UInfinityStageVideoFallbackSubsystem::Leave(const TCHAR* Why)
{
    if (ActiveOrdinal == INDEX_NONE && !bLiveSuppressed)
    {
        return;
    }
    SetLiveSuppressed(false);
    if (WhiteImage.IsValid())
    {
        WhiteImage->SetColorAndOpacity(FLinearColor::Transparent);
    }
    if (Player)
    {
        Player->Close();
    }
    UE_LOG(LogInfinityStageVideoFallback, Log, TEXT("INFINITY_VIDEO_FALLBACK_LEAVE scene=S%d why=%s"), ActiveOrdinal, Why);
    ActiveOrdinal = INDEX_NONE;
    bOpen = false;
    bPictureUp = false;
}

void UInfinityStageVideoFallbackSubsystem::HandleOpened(FString Url)
{
    bOpen = true;
}

void UInfinityStageVideoFallbackSubsystem::HandleOpenFailed(FString Url)
{
    Warn(FString::Printf(TEXT("S%d: could not open %s; playing the LIVE Scene"), ActiveOrdinal, *Url));
    FailedOrdinal = ActiveOrdinal;
    Leave(TEXT("open failed"));
}

void UInfinityStageVideoFallbackSubsystem::Tick(const float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (!Root.IsValid())
    {
        for (TActorIterator<AInfinityStageShowRoot> It(GetWorld()); It; ++It)
        {
            Root = *It;
            break;
        }
    }
    AInfinityStageShowRoot* ShowRoot = Root.Get();
    UInfinityStageCueDirectorSubsystem* Director = GetWorld()->GetSubsystem<UInfinityStageCueDirectorSubsystem>();
    if (!ShowRoot || !ShowRoot->Transport || !ShowRoot->SequencePlayer || !ShowRoot->ShowAsset || !Director || Clips.IsEmpty())
    {
        Leave(TEXT("no show or no clips"));
        return;
    }
    EnsureOverlay();

    // Which Scene (1-based, Scene segments only) is under the Master playhead?
    const UInfinityStageTransportController& Transport = *ShowRoot->Transport;
    const int32 Frame = Transport.GetCurrentMasterFrame().Value;
    int32 Ordinal = 0;
    int32 Found = INDEX_NONE;
    int32 Start = 0;
    for (const FInfinityTransportSegment& Segment : Transport.Segments)
    {
        if (Segment.Type != EInfinityCueType::Scene)
        {
            continue;
        }
        ++Ordinal;
        if (Frame >= Segment.StartFrame.Value && Frame < Segment.EndFrame.Value)
        {
            Found = Ordinal;
            Start = Segment.StartFrame.Value;
            break;
        }
    }
    const bool bWanted = Found != INDEX_NONE && Found != FailedOrdinal && Clips.Contains(Found)
        && Director->GetSettings().UseVideoScenes.Contains(FString::Printf(TEXT("S%d"), Found));
    if (!bWanted)
    {
        Leave(TEXT("live"));
        if (Found == INDEX_NONE)
        {
            FailedOrdinal = INDEX_NONE;   // a failure is retried next time the Scene is entered
        }
        return;
    }
    if (Found != ActiveOrdinal)
    {
        ActiveStartFrame = Start;
        Enter(Found);
        return;
    }
    if (!bOpen)
    {
        return;   // still opening: the live Scene stays up, never a black gap
    }

    // Follow the Master: its rate while playing (fast-forward included), its frame while paused.
    const double Ticks = ShowRoot->ShowAsset->TickResolution.AsDecimal();
    const double Wanted = InfinityStageVideoFallback::MediaSecondsForLocalFrame(Frame - ActiveStartFrame, Ticks, Clips[Found]);
    if (WhiteImage.IsValid())
    {
        const double Duration = Clips[Found].FadeFromWhiteSeconds;
        const float Alpha = Duration > 0.0 ? static_cast<float>(FMath::Clamp(1.0 - Wanted / Duration, 0.0, 1.0)) : 0.0f;
        WhiteImage->SetColorAndOpacity(FLinearColor(1.0f, 1.0f, 1.0f, Alpha));
    }
    const double Now = FPlatformTime::Seconds();
    const bool bPlaying = ShowRoot->SequencePlayer->IsPlaying() && !ShowRoot->SequencePlayer->IsReversed();
    const float Rate = bPlaying ? ShowRoot->SequencePlayer->GetPlayRate() : 0.0f;
    if (!FMath::IsNearlyEqual(Player->GetRate(), Rate, 0.01f))
    {
        Player->SetRate(Rate);
    }
    const double Error = FMath::Abs(Player->GetTime().GetTotalSeconds() - Wanted);
    const double Tolerance = bPlaying ? FMath::Max(0.25, 0.1 * Rate) : 0.5 / FMath::Max(1.0, Clips[Found].Fps);
    if (Error > Tolerance && Now - LastSeekRealSeconds > 0.3)
    {
        Player->Seek(FTimespan::FromSeconds(Wanted));
        LastSeekRealSeconds = Now;
    }
    if (!bPictureUp)
    {
        bPictureUp = true;
        SetLiveSuppressed(true);
    }
}
