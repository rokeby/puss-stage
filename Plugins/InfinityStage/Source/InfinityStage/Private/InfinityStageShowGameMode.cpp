#include "InfinityStageShowGameMode.h"

#include "GameFramework/PlayerController.h"
#include "Components/InputComponent.h"
#include "EngineUtils.h"
#include "InfinityStageDirectorHud.h"
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
    // Left is tap-or-hold like Right (Gary, 6 Oct): the tap's Previous now fires on
    // key-up, the hold rewinds.
    InputComponent->BindKey(EKeys::Left, IE_Pressed, this, &AInfinityStageShowPlayerController::BeginLeftInput);
    InputComponent->BindKey(EKeys::Left, IE_Released, this, &AInfinityStageShowPlayerController::EndLeftInput);
    InputComponent->BindKey(EKeys::SpaceBar, IE_Pressed, this, &AInfinityStageShowPlayerController::ToggleShowPlayback);
    InputComponent->BindKey(EKeys::H, IE_Pressed, this, &AInfinityStageShowPlayerController::ToggleDirectorHud);
}

void AInfinityStageShowPlayerController::ToggleDirectorHud()
{
    InfinityStageDirectorHud::Toggle(GetWorld());
    UE_LOG(LogTemp, Display, TEXT("INFINITY_DIRECTOR_HUD on=%d"),
        InfinityStageDirectorHud::IsEnabledForWorld(GetWorld()) ? 1 : 0);
}

void AInfinityStageShowPlayerController::PlayerTick(const float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    const float Threshold = Transport ? Transport->HoldThresholdSeconds : 0.30f;
    ApplyHoldRightAction(HoldRightState.Tick(DeltaTime, Threshold));
    ApplyHoldLeftAction(HoldLeftState.Tick(DeltaTime, Threshold));
}

void AInfinityStageShowPlayerController::BeginLeftInput()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    HoldLeftState.Press(Transport && Transport->IsTransportPlaying());
}

void AInfinityStageShowPlayerController::EndLeftInput()
{
    ApplyHoldLeftAction(HoldLeftState.Release());
}

void AInfinityStageShowPlayerController::ApplyHoldLeftAction(const EInfinityHoldRightAction Action)
{
    // The shared machine's names are Right's: Advance = the tap, FastForward = the hold.
    if (Action == EInfinityHoldRightAction::None)
    {
        return;
    }
    if (Action == EInfinityHoldRightAction::Advance)
    {
        PreviousShowSegment();
        return;
    }
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    if (Action == EInfinityHoldRightAction::BeginFastForward)
    {
        const EInfinityTransportResult Result = Transport
            ? Transport->BeginRewind()
            : EInfinityTransportResult::NoPlayer;
        // A refused rewind is still the whole gesture: its key-up does nothing.
        HoldLeftState.ResolveFastForwardStart(Result);
        ReportTransportResult(this, Result);
        return;
    }
    const bool bWasPlaying = Action == EInfinityHoldRightAction::EndFastForwardPlaying;
    ReportTransportResult(this, Transport
        ? Transport->EndRewind(bWasPlaying)
        : EInfinityTransportResult::NoPlayer);
}

void AInfinityStageShowPlayerController::BeginRightInput()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    if (Transport && (Transport->ReleaseActiveHold() || Transport->ReleaseActiveVamp()))
    {
        // A GO at a hold, or a vamp release, is the whole RIGHT gesture. Its key-up must not also
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
    ReportTransportResult(this, Transport ? Transport->StepShotForward() : EInfinityTransportResult::NoPlayer);
}

void AInfinityStageShowPlayerController::PreviousShowSegment()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    ReportTransportResult(this, Transport ? Transport->StepShotBack() : EInfinityTransportResult::NoPlayer);
}

void AInfinityStageShowPlayerController::ToggleShowPlayback()
{
    UInfinityStageTransportController* Transport = FindShowTransport(GetWorld());
    // Space is GO too (Gary, 4 Oct): at a hold it fires the cue and nothing else.
    if (Transport && Transport->ReleaseActiveHold())
    {
        return;
    }
    if (Transport && Transport->bSpaceNeverPauses && Transport->IsTransportPlaying())
    {
        UE_LOG(LogTemp, Display, TEXT("INFINITY_GO_SPACE_IGNORED playing, no hold: pause from the Cue Desk."));
        return;
    }
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
