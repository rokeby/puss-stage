#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Tickable.h"
#include "InfinityStageVideoTransitionSubsystem.generated.h"

class AInfinityStageShowRoot;
class UMediaPlayer;
class UMediaSoundComponent;
class UMediaTexture;
class SImage;
class SOverlay;
struct FSlateBrush;

/** Held P15 implementation: the Master/Transport playhead remains the sole clock. */
UCLASS()
class INFINITYSTAGE_API UInfinityStageVideoTransitionSubsystem final
    : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickableInEditor() const override { return false; }

private:
    struct FSceneMedia
    {
        FString PlaybackFile;
        FString AudioOwner;
        int32 Fps = 25;
        int32 MediaFrames = 0;
        bool bLoop = true;
    };

    bool LoadRegistry();
    AInfinityStageShowRoot* FindShowRoot() const;
    bool ResolveScene(int32 MasterFrame, int32& OutOrdinal, int32& OutStart) const;
    void EnterScene(int32 Ordinal, int32 LocalFrame);
    void SyncToFrame(int32 LocalFrame, bool bPlaying);
    void ShowBlack(const FString& Marker, const FString& Detail);
    void HideOverlay();

    UFUNCTION()
    void OnMediaOpened(FString OpenedUrl);

    UFUNCTION()
    void OnMediaOpenFailed(FString FailedUrl);

    UPROPERTY(Transient)
    TObjectPtr<UMediaPlayer> Player;

    UPROPERTY(Transient)
    TObjectPtr<UMediaTexture> Texture;

    UPROPERTY(Transient)
    TObjectPtr<UMediaSoundComponent> Sound;

    UPROPERTY(Transient)
    TObjectPtr<AInfinityStageShowRoot> Root;

    TMap<int32, FSceneMedia> Scenes;
    TSharedPtr<SOverlay> Overlay;
    TSharedPtr<SImage> Image;
    TSharedPtr<FSlateBrush> Brush;
    int32 ActiveOrdinal = INDEX_NONE;
    int32 ActiveSceneStart = 0;
    int32 LastRequestedFrame = INDEX_NONE;
    bool bOpen = false;
    bool bSeekPending = false;
    FString LastBlackKey;
};
