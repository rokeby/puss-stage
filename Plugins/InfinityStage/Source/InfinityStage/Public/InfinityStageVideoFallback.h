#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "InfinityStageVideoFallback.generated.h"

class AInfinityStageShowRoot;
class SImage;
class SWidget;
class UMediaPlayer;
class UMediaSoundComponent;
class UMediaTexture;
struct FSlateBrush;

/**
 * Cue Director CD4: play a pre-rendered video instead of a live Scene (Gary, 7-8 Oct: "scenes as
 * videos ready to trigger"; "add the use video checkbox"). Reworked from the held P15 bundle.
 *
 * - Files: the conductor's render contract, Renders/Fallbacks/current.json (schema 1):
 *   scenes.S<n> = { video, audio, frames, seconds, fps, ... } with paths relative to Renders/Fallbacks,
 *   plus an optional "muxed" (video + audio) used when UE plays the Scene's sound.
 * - Which Scenes: only those ticked "use video" in the Cue Director panel (cue_director.txt, use_video = S<n>).
 * - Clock: the Master playhead stays the only clock; the video follows it (rate included), so jumps,
 *   scrubs and fast-forward stay in step.
 * - While a video Scene shows: the live world is not rendered (saves the GPU), and the Master's own
 *   audio is muted (no double sound). If the video is missing or fails, the LIVE Scene plays instead.
 */
struct INFINITYSTAGE_API FInfinityFallbackClip
{
    FString VideoPath;    // absolute
    FString MuxedPath;    // absolute, may be empty
    int32 Frames = 0;
    double Fps = 25.0;
};

namespace InfinityStageVideoFallback
{
/** Parses current.json (schema 1). Paths are made absolute against FallbackRoot. Unknown or broken
 * entries are skipped with a warning; returns the Scene ordinals found (1-based, "S3" -> 3). */
INFINITYSTAGE_API TMap<int32, FInfinityFallbackClip> ParseRegistry(const FString& Json, const FString& FallbackRoot, TArray<FString>& OutWarnings);

/** E:\PussStage\Renders\Fallbacks (console InfinityStage.VideoFallback.Root overrides). */
INFINITYSTAGE_API FString ResolveRoot();

/** Seconds into the clip for a Master-relative Scene frame, clamped to the clip (no looping). */
INFINITYSTAGE_API double MediaSecondsForLocalFrame(int32 LocalFrame, double ShowTicksPerSecond, const FInfinityFallbackClip& Clip);
}

UCLASS()
class INFINITYSTAGE_API UInfinityStageVideoFallbackSubsystem final : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UInfinityStageVideoFallbackSubsystem, STATGROUP_Tickables); }

    /** Re-reads current.json (F5 reloads it with the cue sheet). */
    void ReloadRegistry();
    bool IsShowingVideo() const { return ActiveOrdinal != INDEX_NONE && bPictureUp; }

private:
    void EnsureOverlay();
    void Enter(int32 Ordinal);
    void Leave(const TCHAR* Why);
    void SetLiveSuppressed(bool bSuppressed);
    void Warn(const FString& Message);

    UFUNCTION()
    void HandleOpened(FString Url);
    UFUNCTION()
    void HandleOpenFailed(FString Url);

    UPROPERTY(Transient)
    TObjectPtr<UMediaPlayer> Player;
    UPROPERTY(Transient)
    TObjectPtr<UMediaTexture> Texture;
    UPROPERTY(Transient)
    TObjectPtr<UMediaSoundComponent> Sound;

    TMap<int32, FInfinityFallbackClip> Clips;
    TSharedPtr<SWidget> Overlay;
    TSharedPtr<SImage> Image;
    TSharedPtr<FSlateBrush> Brush;
    TWeakObjectPtr<AInfinityStageShowRoot> Root;
    int32 ActiveOrdinal = INDEX_NONE;
    int32 ActiveStartFrame = 0;
    int32 FailedOrdinal = INDEX_NONE;
    bool bOpen = false;
    bool bPictureUp = false;
    bool bLiveSuppressed = false;
    bool bOverlayAdded = false;
    double LastSeekRealSeconds = -1.0;
    TSet<FString> Warned;
};
