#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageShowGameMode.generated.h"

/** Keyboard transport for the focused game viewport, using the one Show player. */
UCLASS()
class INFINITYSTAGE_API AInfinityStageShowPlayerController : public APlayerController
{
    GENERATED_BODY()
public:
    AInfinityStageShowPlayerController();

    virtual void PlayerTick(float DeltaTime) override;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    void AdvanceShowSegment();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    void PreviousShowSegment();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    void ToggleShowPlayback();

    /** H: shows or hides the Director's bottom-row HUD (InfinityStage.DirectorHud). */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    void ToggleDirectorHud();
    void NextScriptLine();
    void PreviousScriptLine();
    void ReloadCueSheet();

protected:
    virtual void SetupInputComponent() override;

private:
    FInfinityHoldRightState HoldRightState;

    /** The same tap-or-hold machine for Left: tap = Previous, hold = rewind. */
    FInfinityHoldRightState HoldLeftState;

    void BeginRightInput();
    void EndRightInput();
    void ApplyHoldRightAction(EInfinityHoldRightAction Action);
    void BeginLeftInput();
    void EndLeftInput();
    void ApplyHoldLeftAction(EInfinityHoldRightAction Action);
};

/**
 * Game mode for show levels: spawns no default pawn and no HUD.
 *
 * The stage is viewed entirely through the Passage Camera Rigs that the Show
 * Root claims on Begin Play, so the engine's default floating pawn only ever
 * appears in shot. Set this as the level's GameMode Override in World Settings.
 */
UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageShowGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AInfinityStageShowGameMode();

    virtual void InitializeHUDForPlayer_Implementation(APlayerController* NewPlayer) override;
};
