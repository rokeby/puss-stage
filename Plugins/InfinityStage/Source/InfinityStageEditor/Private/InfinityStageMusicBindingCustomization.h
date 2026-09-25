#pragma once

#include "CoreMinimal.h"
#include "IPropertyTypeCustomization.h"

class UInfinityStageShowAsset;

/**
 * Replaces the raw Rail GUID fields on a music binding with a picker.
 *
 * Music Rails live on the Show Asset and are referenced by GUID. That is the
 * right storage, but it left the only way to bind a Scene or Passage to a rail
 * as copying a GUID out of an array by hand — so a working data path had no
 * usable front door. This lists rails by label and writes the GUID behind the
 * scenes, and can create a rail from a Sound selected in the Content Browser.
 */
class FInfinityStageMusicBindingCustomization final : public IPropertyTypeCustomization
{
public:
    static TSharedRef<IPropertyTypeCustomization> MakeInstance();

    virtual void CustomizeHeader(
        TSharedRef<IPropertyHandle> PropertyHandle,
        FDetailWidgetRow& HeaderRow,
        IPropertyTypeCustomizationUtils& CustomizationUtils) override;

    virtual void CustomizeChildren(
        TSharedRef<IPropertyHandle> PropertyHandle,
        IDetailChildrenBuilder& ChildBuilder,
        IPropertyTypeCustomizationUtils& CustomizationUtils) override;

private:
    /** Resolves the Show that owns the edited binding, via its Details proxy. */
    UInfinityStageShowAsset* ResolveShow(const TSharedRef<IPropertyHandle>& Handle) const;

    TSharedRef<SWidget> BuildRailMenu(TSharedRef<IPropertyHandle> GuidHandle);
    FText GetRailLabel(TSharedRef<IPropertyHandle> GuidHandle) const;
    void SetRail(TSharedRef<IPropertyHandle> GuidHandle, FGuid RailGuid);
    /** Creates a Show-level rail from the Content Browser's selected Sound. */
    void CreateRailFromSelectedSound(TSharedRef<IPropertyHandle> GuidHandle);

    TSharedRef<SWidget> BuildRailRow(TSharedRef<IPropertyHandle> GuidHandle);
};
