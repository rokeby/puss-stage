#pragma once

#include "CoreMinimal.h"
#include "IDetailCustomization.h"

class AInfinityStagePassageActor;
class IDetailLayoutBuilder;

/**
 * Adds the guided route-editing workflow to the Passage Actor Details panel.
 *
 * The three route hazards are otherwise silent: Auto Fit replaces a hand-edited
 * curve on the next materialization, a route shorter than the compiled Passage
 * makes materialization refuse, and a changed endpoint leaves Scene camera
 * handoffs stale. This customization surfaces all three before they bite.
 *
 * It lives in the editor module because Scene camera matching is editor-only and
 * the runtime Passage Actor cannot reach it.
 */
class FInfinityStagePassageActorDetails final : public IDetailCustomization
{
public:
    static TSharedRef<IDetailCustomization> MakeInstance();

    virtual void CustomizeDetails(IDetailLayoutBuilder& DetailBuilder) override;

private:
    AInfinityStagePassageActor* GetSelectedActor() const;

    /** Disables Auto Fit and selects the Route spline for immediate editing. */
    FReply BeginRouteEdit();
    FReply ExtendRoute();
    /** Materializes, then offers Scene handoff matching rather than assuming it. */
    FReply FinishRouteEdit();

    FText GetRouteStatusText() const;
    FSlateColor GetRouteStatusColor() const;
    bool IsRouteShort() const;
    bool IsAutoFitEnabled() const;

    TArray<TWeakObjectPtr<AInfinityStagePassageActor>> SelectedActors;
};
