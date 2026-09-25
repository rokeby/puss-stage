#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InfinityStageTypes.h"
#include "InfinityStageTransportController.generated.h"

class UInfinityStageShowAsset;
class ULevelSequencePlayer;

UENUM(BlueprintType)
enum class EInfinityTransportResult : uint8
{
    Succeeded,
    NoPlayer,
    NoSegment,
    NotReady,
    UnsafeExternalClock
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityTransportSegment
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FGuid SegmentGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FText Label;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityCueType Type = EInfinityCueType::WingPair;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FFrameNumber StartFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FFrameNumber EndFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityExternalSoundAuthority ExternalSound = EInfinityExternalSoundAuthority::None;

    /** Re-claim the preceding segment camera instead of selecting a new view. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    bool bRetainPreviousCamera = false;

    /** Switch to the following Passage once this interstitial is fully covered. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    bool bRevealNextPassageWhenCovered = false;

    /** Absolute Master frame at which the covered handoff becomes active.
     * Sequence cues can author this with an InfinityStage.HiddenChangeover
     * marked frame; entry + hold timing is the fallback. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FFrameNumber CoveredHandoffFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bReady = true;
};

UCLASS(ClassGroup = "Infinity Stage", BlueprintType, meta = (BlueprintSpawnableComponent))
class INFINITYSTAGE_API UInfinityStageTransportController : public UActorComponent
{
    GENERATED_BODY()

public:
    UInfinityStageTransportController();

    /** Watches for the playhead crossing a segment boundary during playback. */
    virtual void TickComponent(
        float DeltaTime,
        ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    TArray<FInfinityTransportSegment> Segments;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bPerformanceMode = true;

    /** Continue a playing Passage into its immediately following cinematic Scene.
     * The Scene still holds at its end; this never starts the next Passage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bAutoPlaySceneAfterPassage = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    int32 SelectedSegmentIndex = INDEX_NONE;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityTransportResult LastResult = EInfinityTransportResult::NoPlayer;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    bool InitializeTransport(ULevelSequencePlayer* InPlayer, UInfinityStageShowAsset* InShowAsset);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PlayForwardToBoundary();

    /** Resolves the operator stop without moving or evaluating the player. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 GetForwardStopSegmentIndex(int32 FromSegmentIndex) const;

    /**
     * Plays forward through segment boundaries to the end of the Show, so a
     * Passage-to-Scene handover can be watched continuously. This bypasses all
     * operator stops, including the hold after a cinematic Scene.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PlayForwardThroughBoundaries();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PlayReverseToBoundary();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToCurrentStart();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToCurrentEnd();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToNextSegment();

    /** Operator advance: play a sequence/interstitial, or a Scene when automatic
     * Scene playback is enabled. A new Passage remains held at its first frame. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult AdvanceToNextSegment();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToPreviousSegment();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PauseTransport();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult ResumeForward();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult Shuttle(float Rate);

    /** Absolute-frame rehearsal/editor scrub on the one root Sequence Player.
     * Performance external-clock and readiness rules still apply. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult ScrubToMasterFrame(FFrameNumber TargetFrame);

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    FFrameNumber GetCurrentMasterFrame() const;

    /** True while the Master player is running, so a toggle can tell play from pause. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    bool IsTransportPlaying() const;

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 FindSegmentAtFrame(FFrameNumber Frame) const;

private:
    UPROPERTY(Transient)
    TObjectPtr<ULevelSequencePlayer> Player;

    UPROPERTY(Transient)
    TObjectPtr<UInfinityStageShowAsset> ShowAsset;

    bool bCoveredHandoffActive = false;

    EInfinityTransportResult JumpToSegment(int32 SegmentIndex, bool bToEnd);
    EInfinityTransportResult PlayToFrame(FFrameNumber TargetFrame);
    void ClaimSegmentCamera(const FInfinityTransportSegment& Segment, FFrameNumber MasterFrame) const;
    bool TryClaimSceneSequenceCamera(const FInfinityTransportSegment& Segment, FFrameNumber MasterFrame) const;
    bool IsCoveredHandoffActive(int32 SegmentIndex, FFrameNumber MasterFrame) const;
    bool IsUnsafeExternalMove(FFrameNumber TargetFrame) const;
    void RefreshSelectedSegment();
};
