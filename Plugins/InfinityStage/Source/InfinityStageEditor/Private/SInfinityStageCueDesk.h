#pragma once

#include "CoreMinimal.h"
#include "InfinityStageCueProxy.h"
#include "InfinityStagePassageProxy.h"
#include "InfinityStageTypes.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "UObject/StrongObjectPtr.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Views/SListView.h"

class IDetailsView;
class AInfinityStageWingEditProxy;
class FMenuBuilder;
class UAudioComponent;
class UInfinityStageShowAsset;
struct FInfinityCompileResult;
enum class EInfinityWingEditTarget : uint8;

enum class EInfinityWingSequenceImportMode : uint8
{
    ApplyArrangement,
    InsertRows,
    ReplaceCompleteRows
};

enum class EInfinityCueListNodeType : uint8
{
    Cue,
    PassageHeader
};

struct FInfinityCueListItem
{
    EInfinityCueListNodeType NodeType = EInfinityCueListNodeType::Cue;
    int32 CueIndex = INDEX_NONE;
    FGuid PassageGuid;
    FText HeaderLabel;
    int32 ChildCount = 0;
    bool bNestedChild = false;
    bool bPassageCollapsed = false;
};

enum class EInfinityCueDeskPostPieAction : uint8
{
    None,
    ApplyTransportPreference,
    ApplyTransportPreferenceAndSeek
};

class SInfinityStageCueDesk final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SInfinityStageCueDesk)
        : _InitialShowAsset(nullptr)
    {}
        SLATE_ARGUMENT(UInfinityStageShowAsset*, InitialShowAsset)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);
    virtual ~SInfinityStageCueDesk() override;

    /** Lets the desk itself hold focus so transport keys work after a background click. */
    virtual bool SupportsKeyboardFocus() const override { return true; }

    /** Space toggles the playhead. Child widgets that legitimately consume Space —
     * text entry, the cue list — handle it first, so this only fires when nothing
     * more specific wanted it. */
    virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& KeyEvent) override;

    /** Pure plan for PostPIEStarted. The rehearsal preference is independent of
     * the optional start-at-playhead seek, so a normal PIE start must still push it. */
    static EInfinityCueDeskPostPieAction ResolvePostPieAction(
        bool bIsSimulating, bool bHasShow, bool bHasEngine, bool bStartsAtPlayhead);

private:
    using FCueItem = TSharedPtr<FInfinityCueListItem>;

    TSharedRef<ITableRow> GenerateCueRow(FCueItem Item, const TSharedRef<STableViewBase>& OwnerTable);
    void HandleCueSelection(FCueItem Item, ESelectInfo::Type SelectInfo);
    FReply HandleCueDragDetected(FCueItem Item);
    TOptional<EItemDropZone> HandleCueCanAcceptDrop(
        const FDragDropEvent& DragDropEvent,
        EItemDropZone DropZone,
        FCueItem TargetItem) const;
    FReply HandleCueAcceptDrop(
        const FDragDropEvent& DragDropEvent,
        EItemDropZone DropZone,
        FCueItem TargetItem);
    void HandleCueProxyChanged();
    void RefreshSelectedCuesInEditorWorld(bool bRematerialize, bool bFrameViewport);
    void ClearEditorWorldInstanceSelection() const;
    void FollowCueSelectionToPlayhead(const FCueItem& Item, bool bNotifyOnFailure);
    bool EvaluateMasterFrameForPreview(
        const struct FInfinityCompiledPassage* Passage,
        FFrameNumber MasterFrame,
        bool bNotifyOnFailure);
    UInfinityStageShowAsset* FindEditorWorldShowAsset(bool& bOutMultipleShows) const;
    void UseEditorWorldShowAsset();
    bool CanUseEditorWorldShowAsset() const;
    EActiveTimerReturnType HandleDeferredWorldRefresh(double CurrentTime, float DeltaTime);
    void BeginViewportEdit(EInfinityWingEditTarget Target);
    void FinishViewportEdit(bool bCancel);
    void BuildViewportEditMenu(FMenuBuilder& MenuBuilder);
    void BuildImageOrientationMenu(FMenuBuilder& MenuBuilder);
    void BuildRelativeTransformMenu(FMenuBuilder& MenuBuilder);
    void BuildWingMovementMenu(FMenuBuilder& MenuBuilder);
    void BuildWingSequenceFileMenu(FMenuBuilder& MenuBuilder);
    void BuildWingMovementScopeMenu(FMenuBuilder& MenuBuilder, bool bWholePassage);
    void BuildPhasedBreathePresetMenu(FMenuBuilder& MenuBuilder, bool bWholePassage);
    void BuildCameraGustPresetMenu(FMenuBuilder& MenuBuilder, bool bWholePassage);
    void BuildSceneHandoffMenu(FMenuBuilder& MenuBuilder);
    void MatchSceneCameraHandoffs(bool bAllScenes);
    bool CanOpenSelectedSceneSequence() const;
    void OpenSelectedSceneSequence();
    TArray<FGuid> GetMechanismTargetCueGuids(bool bWholePassage) const;
    bool HasMechanismTargets(bool bWholePassage) const;
    void ApplyUndulationPreset(bool bWholePassage, double PhaseStepCycles);
    void ApplyCameraGustPreset(bool bWholePassage, int32 Preset);
    void SetSelectedMechanismsStatic(bool bWholePassage);
    const FInfinityPanelDesign* GetSelectedPanelDesign(EInfinityWingEditTarget Target) const;
    FInfinityPanelDesign* GetMutableSelectedPanelDesign(EInfinityWingEditTarget Target);
    bool CanEditSelectedPanelImage(EInfinityWingEditTarget Target) const;
    bool IsSelectedPanelImageFlipped(EInfinityWingEditTarget Target) const;
    void ToggleSelectedPanelImageFlip(EInfinityWingEditTarget Target);
    void ApplySelectedPanelImageFlipToAllUses(EInfinityWingEditTarget Target);
    void ApplySelectedPanelRelativeTransformToAllUses(EInfinityWingEditTarget Target);
    void RefreshAllPassagesInEditorWorld();
    /** Rebuild the selected Passage's wings and attachments from the Show. */
    void MaterializeSelectedPassages();
    /** Generate any missing default top-left/right spots on selected Wing Pairs. */
    void AddStageSpotsToSelection();
    /** Copy the first selected pair's complete Light attachments across the rest. */
    void ReplicateStageLightingToSelection();
    /** Scope 0 selection, 1 whole Passage, 2 entire Show; optionally with seeded variation. Rematerializes. */
    void ReplicateStageLighting(int32 Scope, bool bWithVariation);
    TSharedPtr<SWidget> BuildCueContextMenu();
    TSharedRef<SWidget> BuildAddMenu();
    TSharedRef<SWidget> BuildActionsMenu();
    TSharedRef<SWidget> BuildViewMenu();
    void BuildEditorLightingMenu(FMenuBuilder& MenuBuilder);
    TSharedRef<SWidget> BuildScrubViewMenu();
    TSharedRef<SWidget> BuildCameraCurveMenu();
    TSharedRef<SWidget> BuildCameraCurveActionsMenu();
    void BuildAnalysisCurveMenu(FMenuBuilder& MenuBuilder);
    /** Writes an analysis envelope onto the active channel as decimated keys. */
    void ApplyAnalysisCurveToActiveChannel(FName CurveName);
    void BuildCameraSpeedPresetMenu(FMenuBuilder& MenuBuilder);
    TSharedRef<SWidget> BuildMusicPanel();
    TSharedRef<SWidget> BuildMusicWorkspace();
    void SaveLayoutConfig() const;

    FString GetAssetPath() const;
    void HandleAssetChanged(const FAssetData& AssetData);
    void RefreshFromAsset(bool bPreserveSelection = true);
    void RefreshPassageInspector();
    void LoadFitFromSelectedPassage();
    const FInfinityPassageSettings* GetSelectedPassage() const;
    UMovieSceneInfinityPassageSection* GetSelectedPassageCameraSection() const;
    FFrameNumber GetCameraCurveEditFrame() const;
    TOptional<double> GetCameraCurveValue() const;
    void SetCameraCurveValue(double NewValue, ETextCommit::Type CommitType);
    void RemoveCameraCurveKey();
    void ResetCameraCurve();
    void ApplyCameraSpeedPreset(int32 Preset);
    void ToggleSelectedWingCameraAnchor();
    bool IsSelectedWingCameraAnchorPinned() const;
    void TogglePlayheadMusicCameraAnchor();
    bool IsPlayheadMusicCameraAnchorPinned() const;
    void PinConfirmedMusicMarkersAsCameraAnchors();
    void ClearPassageFrameCameraAnchors();
    FText GetCameraCurveLabel() const;
    FText GetCameraCurveStatusText() const;
    void HandleMusicScrub(double NormalizedPosition, bool bFinal);
    bool EvaluateEditorPassageAtMasterFrame(
        const struct FInfinityCompiledPassage& Passage,
        FFrameNumber MasterFrame);
    void PreviewMusicAtScrub(
        const FInfinityPassageSettings& Settings,
        const struct FInfinityCompiledPassage& Passage,
        double NormalizedPosition,
        bool bFinal);
    float GetMusicPreviewVolume(
        const FInfinityMusicRail& Rail,
        const struct FInfinityCompiledPassage& Passage,
        double NormalizedPosition) const;
    void StopMusicScrubPreview();
    void StartEditorPreviewPlayback(int32 Direction);
    void StopEditorPreviewPlayback();
    EActiveTimerReturnType HandleEditorPreviewPlayback(double CurrentTime, float DeltaTime);
    void SetNestedCueMode(bool bEnabled);
    void SetMusicScrubCameraFollow(bool bEnabled);
    void SetEditorLightingFollowMaster(bool bFollowMaster);
    bool IsEditorLightingFollowingMaster() const;
    void SetEditorLightingHour(double TimeHours);
    void SelectCelestialRigInEditor();
    void TogglePassageCollapsed(FGuid PassageGuid);
    void RenamePassage(FGuid PassageGuid, const FText& NewLabel);
    /** True while either the editor preview or the PIE transport is running. */
    bool IsPlaybackRunning() const;

    /** Read-only staleness report for every Scene's handoff cameras. */
    void CheckSceneCameraHandoffs();

    /** "PIE ▶ Passage 03 · wing 7/21" style readout for the status rail. */
    FText GetNowPlayingText(const FInfinityCompileResult& Compiled) const;

    /** Rehearsal transport ignores declared external sound locks so seeking works. */
    /** Resolves the operator-visible playhead frame: timeline position, else selection. */
    bool GetCueDeskPlayheadFrame(FFrameNumber& OutFrame) const;
    void HandlePostPieStarted(bool bIsSimulating);

    void BuildLiveCameraOwnerMenu(FMenuBuilder& MenuBuilder);
    void SetLiveCameraOwner(bool bOverride, EInfinityCameraOwner Owner);
    bool IsLiveCameraOwner(bool bOverride, EInfinityCameraOwner Owner) const;

    void ToggleRehearsalTransport();
    bool IsRehearsalTransportEnabled() const;
    /** Pushes the preference onto every live PIE transport; returns how many. */
    int32 ApplyRehearsalTransportToLivePIE() const;
    bool CanCueAndPlaySelectedSegment() const;
    /** Explicit rehearsal action: cue the selected Scene/SEQ exactly and play to its boundary. */
    void CueAndPlaySelectedSegment();

    void RunTransportCommand(int32 Command);
    void JumpEditorPreviewToAdjacentSegment(int32 Direction);
    void AddCue(EInfinityCueType Type);
    void DuplicateSelected();
    void DeleteSelected();
    void MoveSelected(int32 Delta);
    void RefitSelectedPassageFromMusic();
    void ReimportMusicAnalysis();
    /** Export the selected Passage's rail sound, analyse it and link the result. */
    void AnalyzeSelectionMusic();
    void RebuildManagedMaster();
    void ExportWingSequence(bool bWholePassage);
    void ImportWingSequence(EInfinityWingSequenceImportMode ImportMode);
    bool HasWingSequenceExportTargets(bool bWholePassage) const;
    bool HasPassageReplacementTarget() const;
    TArray<int32> GetSelectedWingCueIndices() const;
    FGuid GetExplicitSelectedPassageGuid() const;
    void RefreshPassagesInEditorWorld(const TSet<FGuid>& PassageGuids);
    bool CanRenderSelectedRange() const;
    void RenderSelectedRange();
    void ApplyListMutation(const FText& TransactionLabel, TFunctionRef<void(TArray<int32>&)> Mutation);
    void RenumberDefaultLabels();
    int32 GetPrimarySelectedIndex() const;
    int32 GetTimelineSelectedCueIndex() const;
    FText GetStatusText() const;
    FText GetCueSelectionSummaryText() const;
    FText GetMusicAnalysisSummaryText() const;

    TWeakObjectPtr<UInfinityStageShowAsset> ShowAsset;
    TArray<TStrongObjectPtr<UInfinityStageCueProxy>> CueProxies;
    TStrongObjectPtr<UInfinityStagePassageProxy> PassageProxy;
    TArray<FCueItem> CueItems;
    TSharedPtr<SListView<FCueItem>> CueList;
    TSharedPtr<IDetailsView> CueDetails;
    TSharedPtr<IDetailsView> AssetDetails;
    TSharedPtr<IDetailsView> PassageDetails;
    bool bNestedCueMode = true;
    bool bMusicWorkspaceVisible = true;
    /** View menu panel toggles (Gary, 8 Oct): each panel can be hidden; persisted. */
    bool bCueListVisible = true;
    bool bCueDetailsVisible = true;
    bool bInspectorVisible = true;
    /** Rehearsal bar along the bottom (follows PIE). */
    bool bRehearsalBarVisible = true;
    /** Cue list columns hidden from the header's right-click menu; persisted. */
    TArray<FName> HiddenCueColumns;
    TSharedPtr<class SHeaderRow> CueHeaderRow;
    float MainWorkspaceFraction = 0.80f;
    float MusicWorkspaceFraction = 0.20f;
    float CueListFraction = 0.28f;
    float CueDetailsFraction = 0.30f;
    float InspectorFraction = 0.42f;
    bool bFollowMusicScrubInViewport = true;
    bool bFollowCueSelectionToPlayhead = true;
    bool bAudibleMusicScrub = true;
    /** Editor preference; performance mode stays the runtime default. */
    bool bRehearsalTransport = false;
    /** Forward play runs to the Show end instead of stopping at each boundary. */
    bool bPlayThroughBoundaries = false;
    /** Push the Cue Desk playhead onto any open Sequencer showing this Master. */
    bool bSyncSequencerPlayhead = false;
    /** Begin PIE at the Cue Desk playhead rather than the start of the Show. */
    bool bPieStartsAtPlayhead = true;
    FDelegateHandle PostPieStartedHandle;
    bool LiveCameraOwnerOverride = false;
    EInfinityCameraOwner LiveCameraOwner = EInfinityCameraOwner::Timeline;
    bool bSnapMusicScrubToMarkers = false;
    TOptional<float> SavedOverviewViewFOV;
    TOptional<float> SavedOverviewFOVAngle;
    TOptional<float> SavedOverviewAspectRatio;
    TSet<FGuid> CollapsedPassages;
    FGuid SelectedPassageGuid;
    bool bWorldRefreshScheduled = false;
    TWeakObjectPtr<AInfinityStageWingEditProxy> ActiveEditProxy;
    TWeakObjectPtr<UAudioComponent> MusicScrubPreviewComponent;
    FGuid MusicScrubPreviewRailGuid;
    double LastMusicScrubPreviewWallSeconds = -1.0;
    double LastMusicScrubPreviewSourceSeconds = -1.0;
    FGuid EditorPreviewPassageGuid;
    FFrameNumber EditorPreviewStartMasterFrame = 0;
    double EditorPreviewStartWallSeconds = 0.0;
    double EditorPreviewNormalizedPosition = -1.0;
    int32 EditorPreviewDirection = 0;
    bool bEditorPreviewTimerRegistered = false;
    EInfinityPassageCameraChannel ActiveCameraChannel = EInfinityPassageCameraChannel::SpeedMultiplier;

    double FitDurationSeconds = 240.0;
    double FitCameraSpeedCmPerSecond = 250.0;
    double FitSpacingCm = 500.0;
    double FitEntryClearanceCm = 250.0;
    double FitExitClearanceCm = 250.0;
};
