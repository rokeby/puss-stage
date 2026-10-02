#include "InfinityStageShowGameMode.h"

#include "GameFramework/PlayerController.h"
#include "Components/InputComponent.h"
#include "EngineUtils.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "InputCoreTypes.h"

namespace
{
UInfinityStageTransportController* FindShowTransport(UWorld* World)
{
    for (TActorIterator<AInfinityStageShowRoot> It(World); It; ++It)
    {
        if (It->Transport && It->SequencePlayer)
        {
            return It->Transport;
        }
    }
    return nullptr;
}

void ReportTransportResult(APlayerController* Controller, EInfinityTransportResult Result)
{
    UE_LOG(LogTemp, Display, TEXT("INFINITY_STAGE_VIEWPORT_TRANSPORT result=%d"), static_cast<int32>(Result));
    if (Result != EInfinityTransportResult::Succeeded)
    {
        Controller->ClientMessage(FString::Printf(TEXT("Show transport: %s"),
            *StaticEnum<EInfinityTransportResult>()->GetDisplayNameTextByValue(static_cast<int64>(Result)).ToString()));
    }
}
}

AInfinityStageShowPlayerController::AInfinityStageShowPlayerController()
{
    // Possessing a spectator must not replace the camera claimed by the Show.
    bAutoManageActiveCameraTarget = false;
}

void AInfinityStageShowPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    InputComponent->BindKey(EKeys::Right, IE_Pressed, this, &AInfinityStageShowPlayerController::BeginRightInput);
    InputComponent->BindKey(EKeys::Right, IE_Released, this, &AInfinityStageShowPlayerController::EndRightInput);
    InputComponent->BindKey(EKeys::Left, IE_Pressed, this, &AInfinityStageShowPlayerController::PreviousShowSegment);
    InputComponent->BindKey(EKeys::SpaceBar, IE_Pressed, this, &AInfinityStageShowPlayerController::ToggleShowPlayback);
}

void AInfinityStageShowPlayerController::PlayerTick(const float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    const float Threshold = Transport ? Transport->HoldThresholdSeconds : 0.30f;
    ApplyHoldRightAction(HoldRightState.Tick(DeltaTime, Threshold));
}

void AInfinityStageShowPlayerController::BeginRightInput()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    if (Transport && Transport->ReleaseActiveVamp())
    {
        // A vamp release is the whole RIGHT gesture. Its key-up must not also
        // become a tap advance or a fast-forward end.
        HoldRightState.Reset();
        return;
    }
    HoldRightState.Press(Transport && Transport->IsTransportPlaying());
}

void AInfinityStageShowPlayerController::EndRightInput()
{
    ApplyHoldRightAction(HoldRightState.Release());
}

void AInfinityStageShowPlayerController::ApplyHoldRightAction(const EInfinityHoldRightAction Action)
{
    if (Action == EInfinityHoldRightAction::None)
    {
        return;
    }
    if (Action == EInfinityHoldRightAction::Advance)
    {
        AdvanceShowSegment();
        return;
    }

    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    if (Action == EInfinityHoldRightAction::BeginFastForward)
    {
        const EInfinityTransportResult Result = Transport
            ? Transport->BeginFastForward()
            : EInfinityTransportResult::NoPlayer;
        HoldRightState.ResolveFastForwardStart(Result);
        ReportTransportResult(this, Result);
        return;
    }

    const bool bWasPlaying = Action == EInfinityHoldRightAction::EndFastForwardPlaying;
    ReportTransportResult(this, Transport
        ? Transport->EndFastForward(bWasPlaying)
        : EInfinityTransportResult::NoPlayer);
}

void AInfinityStageShowPlayerController::AdvanceShowSegment()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    ReportTransportResult(this, Transport ? Transport->AdvanceToNextSegment() : EInfinityTransportResult::NoPlayer);
}

void AInfinityStageShowPlayerController::PreviousShowSegment()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    ReportTransportResult(this, Transport ? Transport->JumpToPreviousSegment() : EInfinityTransportResult::NoPlayer);
}

void AInfinityStageShowPlayerController::ToggleShowPlayback()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    ReportTransportResult(this, Transport
        ? (Transport->IsTransportPlaying() ? Transport->PauseTransport() : Transport->PlayForwardToBoundary())
        : EInfinityTransportResult::NoPlayer);
}

AInfinityStageShowGameMode::AInfinityStageShowGameMode()
{
    // No pawn at all: the Show Root claims the Passage Camera Rig on Begin Play,
    // so a spawned pawn would only ever be visible scenery. Players start as
    // spectators so the PlayerController still exists for input and transport.
    DefaultPawnClass = nullptr;
    HUDClass = nullptr;
    bStartPlayersAsSpectators = true;
    PlayerControllerClass = AInfinityStageShowPlayerController::StaticClass();
}

void AInfinityStageShowGameMode::InitializeHUDForPlayer_Implementation(APlayerController* NewPlayer)
{
    // Intentionally no HUD for the projection-only show. The base implementation
    // forwards the null HUDClass to ClientSetHUD, which emits a no-class SpawnActor
    // warning even though the absence of a HUD is deliberate.
}
