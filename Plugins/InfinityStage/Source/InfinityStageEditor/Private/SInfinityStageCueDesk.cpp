#include "SInfinityStageCueDesk.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/AssetData.h"
#include "Components/AudioComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "CineCameraComponent.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Framework/Notifications/NotificationManager.h"
#include "Framework/Docking/TabManager.h"
#include "Framework/Application/SlateApplication.h"
#include "DragAndDrop/DecoratedDragDropOp.h"
#include "InfinityStageCameraPilot.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageCueProxy.h"
#include "InfinityStageMusicAnalysisImporter.h"
#include "InfinityStageMusicMapAsset.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStagePassageProxy.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCelestialRig.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageWingEditProxy.h"
#include "InfinityStageWingSequenceInterchange.h"
#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageSequencerBridge.h"
#include "LevelSequence.h"
#include "LevelSequencePlayer.h"
#include "LevelEditorViewport.h"
#include "PropertyCustomizationHelpers.h"
#include "PropertyEditorModule.h"
#include "Rendering/DrawElements.h"
#include "ScopedTransaction.h"
#include "HAL/PlatformTime.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/MessageDialog.h"
#include "Misc/Paths.h"
#include "Styling/AppStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SNumericEntryBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSplitter.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Text/SInlineEditableTextBlock.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Sound/SoundBase.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "MoviePipelineEditorBlueprintLibrary.h"
#include "MoviePipelineQueue.h"
#include "MoviePipelineQueueSubsystem.h"
#include "ObjectTools.h"
#include "Subsystems/EditorAssetSubsystem.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "DesktopPlatformModule.h"
#include "IDesktopPlatform.h"

namespace
{
class FInfinityCueDragDropOp final : public FDecoratedDragDropOp
{
public:
    DRAG_DROP_OPERATOR_TYPE(FInfinityCueDragDropOp, FDecoratedDragDropOp)

    TWeakObjectPtr<UInfinityStageShowAsset> Show;
    TArray<FGuid> OrderedCueGuids;

    static TSharedRef<FInfinityCueDragDropOp> New(
        UInfinityStageShowAsset* InShow,
        TArray<FGuid> InOrderedCueGuids)
    {
        TSharedRef<FInfinityCueDragDropOp> Operation = MakeShared<FInfinityCueDragDropOp>();
        Operation->Show = InShow;
        Operation->OrderedCueGuids = MoveTemp(InOrderedCueGuids);
        Operation->DefaultHoverText = FText::Format(
            NSLOCTEXT("InfinityStage", "MoveCueDragLabel", "Move {0} Wing cue(s)"),
            Operation->OrderedCueGuids.Num());
        Operation->CurrentIconBrush = FAppStyle::GetBrush(TEXT("Icons.DragAndDrop"));
        Operation->Construct();
        return Operation;
    }
};

DECLARE_DELEGATE_RetVal_OneParam(
    FReply,
    FOnInfinityCueDragDetected,
    TSharedPtr<FInfinityCueListItem>);
DECLARE_DELEGATE_RetVal_ThreeParams(
    TOptional<EItemDropZone>,
    FOnInfinityCueCanAcceptDrop,
    const FDragDropEvent&,
    EItemDropZone,
    TSharedPtr<FInfinityCueListItem>);
DECLARE_DELEGATE_RetVal_ThreeParams(
    FReply,
    FOnInfinityCueAcceptDrop,
    const FDragDropEvent&,
    EItemDropZone,
    TSharedPtr<FInfinityCueListItem>);

void NotifyCueDesk(const FString& Message, const SNotificationItem::ECompletionState State)
{
    FNotificationInfo Info(FText::FromString(Message));
    Info.ExpireDuration = State == SNotificationItem::CS_Fail ? 8.0f : 5.0f;
    Info.bUseLargeFont = false;
    const TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Info);
    if (Item)
    {
        Item->SetCompletionState(State);
    }
}

ULevelSequence* LoadOrCreateManagedRenderSequence(const UInfinityStageShowAsset& Show)
{
    FString ShowStem = Show.GetName();
    ShowStem.RemoveFromStart(TEXT("DA_"));
    const FString AssetName = ObjectTools::SanitizeObjectName(
        FString::Printf(TEXT("LS_%s_RenderSelection"), *ShowStem));
    const FString PackageName = FString::Printf(
        TEXT("/Game/InfinityStage/Generated/Renders/%s"),
        *AssetName);
    const FString ObjectPath = FString::Printf(TEXT("%s.%s"), *PackageName, *AssetName);
    if (ULevelSequence* Existing = LoadObject<ULevelSequence>(nullptr, *ObjectPath))
    {
        if (!Existing->GetMovieScene())
        {
            Existing->Initialize();
        }
        return Existing;
    }

    UPackage* Package = CreatePackage(*PackageName);
    ULevelSequence* Sequence = NewObject<ULevelSequence>(
        Package,
        *AssetName,
        RF_Public | RF_Standalone | RF_Transactional);
    Sequence->Initialize();
    FAssetRegistryModule::AssetCreated(Sequence);
    Package->MarkPackageDirty();
    return Sequence;
}

FText CueTypeText(const EInfinityCueType Type)
{
    switch (Type)
    {
    case EInfinityCueType::WingPair:
        return NSLOCTEXT("InfinityStage", "WingPairCueType", "WING");
    case EInfinityCueType::Scene:
        return NSLOCTEXT("InfinityStage", "SceneCueType", "SCENE");
    case EInfinityCueType::Sequence:
        return NSLOCTEXT("InfinityStage", "SequenceCueType", "SEQ");
    default:
        return FText::GetEmpty();
    }
}

FText NumberText(const double Value, const int32 MaximumFractionalDigits)
{
    FNumberFormattingOptions Options;
    Options.SetMaximumFractionalDigits(MaximumFractionalDigits);
    return FText::AsNumber(Value, &Options);
}

FText CameraChannelText(const EInfinityPassageCameraChannel Channel)
{
    switch (Channel)
    {
    case EInfinityPassageCameraChannel::SpeedMultiplier: return NSLOCTEXT("InfinityStage", "CurveSpeed", "Speed / Time Warp");
    case EInfinityPassageCameraChannel::LongitudinalOffsetCm: return NSLOCTEXT("InfinityStage", "CurveLongitudinal", "Camera Longitudinal");
    case EInfinityPassageCameraChannel::LateralOffsetCm: return NSLOCTEXT("InfinityStage", "CurveLateral", "Camera Lateral");
    case EInfinityPassageCameraChannel::HeightOffsetCm: return NSLOCTEXT("InfinityStage", "CurveHeight", "Camera Height");
    case EInfinityPassageCameraChannel::PitchDegrees: return NSLOCTEXT("InfinityStage", "CurvePitch", "Camera Pitch");
    case EInfinityPassageCameraChannel::YawDegrees: return NSLOCTEXT("InfinityStage", "CurveYaw", "Camera Yaw");
    case EInfinityPassageCameraChannel::RollDegrees: return NSLOCTEXT("InfinityStage", "CurveRoll", "Camera Roll");
    case EInfinityPassageCameraChannel::LookAheadDistanceCm: return NSLOCTEXT("InfinityStage", "CurveLookAhead", "Route Look Ahead");
    case EInfinityPassageCameraChannel::FocalLengthMm: return NSLOCTEXT("InfinityStage", "CurveFocal", "Focal Length");
    case EInfinityPassageCameraChannel::FocusDistanceCm: return NSLOCTEXT("InfinityStage", "CurveFocus", "Focus Distance");
    case EInfinityPassageCameraChannel::WingInwardTravelScale: return NSLOCTEXT("InfinityStage", "CurveWingTravel", "Wing Travel Scale");
    case EInfinityPassageCameraChannel::WingCycleRateScale: return NSLOCTEXT("InfinityStage", "CurveWingRate", "Wing Cycle Rate Scale");
    case EInfinityPassageCameraChannel::WingPhaseBiasCycles: return NSLOCTEXT("InfinityStage", "CurveWingPhase", "Wing Phase Bias");
    default: return FText::GetEmpty();
    }
}

/** Wing channels modulate authored mechanism values rather than the camera. */
bool IsWingMovementChannel(const EInfinityPassageCameraChannel Channel)
{
    return Channel == EInfinityPassageCameraChannel::WingInwardTravelScale
        || Channel == EInfinityPassageCameraChannel::WingCycleRateScale
        || Channel == EInfinityPassageCameraChannel::WingPhaseBiasCycles;
}

double CameraChannelDefault(const EInfinityPassageCameraChannel Channel)
{
    switch (Channel)
    {
    case EInfinityPassageCameraChannel::SpeedMultiplier: return 1.0;
    case EInfinityPassageCameraChannel::FocalLengthMm: return 35.0;
    case EInfinityPassageCameraChannel::FocusDistanceCm: return 100000.0;
    case EInfinityPassageCameraChannel::WingInwardTravelScale: return 1.0;
    case EInfinityPassageCameraChannel::WingCycleRateScale: return 1.0;
    case EInfinityPassageCameraChannel::WingPhaseBiasCycles: return 0.0;
    default: return 0.0;
    }
}

double ClampCameraChannelValue(const EInfinityPassageCameraChannel Channel, const double Value)
{
    switch (Channel)
    {
    case EInfinityPassageCameraChannel::SpeedMultiplier: return FMath::Max(0.0, Value);
    case EInfinityPassageCameraChannel::LookAheadDistanceCm: return FMath::Max(0.0, Value);
    case EInfinityPassageCameraChannel::FocalLengthMm: return FMath::Max(1.0, Value);
    case EInfinityPassageCameraChannel::FocusDistanceCm: return FMath::Max(0.0, Value);
    case EInfinityPassageCameraChannel::WingInwardTravelScale: return FMath::Max(0.0, Value);
    case EInfinityPassageCameraChannel::WingCycleRateScale: return FMath::Max(0.0, Value);
    default: return Value;
    }
}

DECLARE_DELEGATE_TwoParams(FOnInfinityMusicTimelineScrub, double, bool);
DECLARE_DELEGATE_TwoParams(FOnRenameInfinityPassage, FGuid, const FText&);

class SInfinityStageMusicTimeline final : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SInfinityStageMusicTimeline) {}
        SLATE_ATTRIBUTE(UInfinityStageShowAsset*, ShowAsset)
        SLATE_ATTRIBUTE(int32, SelectedCueIndex)
        SLATE_ATTRIBUTE(double, PlayheadPosition)
        SLATE_ATTRIBUTE(UMovieSceneInfinityPassageSection*, CameraSection)
        SLATE_ATTRIBUTE(EInfinityPassageCameraChannel, CameraChannel)
        SLATE_ATTRIBUTE(bool, SnapToMusicMarkers)
        SLATE_EVENT(FOnInfinityMusicTimelineScrub, OnScrub)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs)
    {
        ShowAssetAttribute = InArgs._ShowAsset;
        SelectedCueIndexAttribute = InArgs._SelectedCueIndex;
        PlayheadPositionAttribute = InArgs._PlayheadPosition;
        CameraSectionAttribute = InArgs._CameraSection;
        CameraChannelAttribute = InArgs._CameraChannel;
        SnapToMusicMarkersAttribute = InArgs._SnapToMusicMarkers;
        OnScrub = InArgs._OnScrub;
    }

    virtual FVector2D ComputeDesiredSize(float) const override
    {
        return FVector2D(600.0f, 150.0f);
    }

    virtual int32 OnPaint(
        const FPaintArgs& Args,
        const FGeometry& AllottedGeometry,
        const FSlateRect& MyCullingRect,
        FSlateWindowElementList& OutDrawElements,
        int32 LayerId,
        const FWidgetStyle& InWidgetStyle,
        bool bParentEnabled) const override
    {
        const FVector2D Size = AllottedGeometry.GetLocalSize();
        const FSlateBrush* WhiteBrush = FAppStyle::GetBrush(TEXT("WhiteBrush"));
        const FSlateFontInfo SmallFont = FAppStyle::GetFontStyle(TEXT("SmallFont"));
        const ESlateDrawEffect DrawEffects = bParentEnabled ? ESlateDrawEffect::None : ESlateDrawEffect::DisabledEffect;

        FSlateDrawElement::MakeBox(
            OutDrawElements,
            LayerId,
            AllottedGeometry.ToPaintGeometry(Size, FSlateLayoutTransform()),
            WhiteBrush,
            DrawEffects,
            FLinearColor(0.035f, 0.045f, 0.055f, 1.0f));

        UInfinityStageShowAsset* Show = ShowAssetAttribute.Get();
        if (!Show || Size.X < 80.0f || Size.Y < 34.0f)
        {
            FSlateDrawElement::MakeText(
                OutDrawElements,
                LayerId + 1,
                AllottedGeometry.ToOffsetPaintGeometry(FVector2f(10.0f, 8.0f)),
                Show ? TEXT("Expand Music Timeline to review the selected Passage") : TEXT("Select an Infinity Stage Show Asset"),
                SmallFont,
                DrawEffects,
                FLinearColor(0.62f, 0.68f, 0.74f));
            return LayerId + 2;
        }

        const int32 SelectedCueIndex = SelectedCueIndexAttribute.Get();
        const FInfinityPassageSettings* Passage = nullptr;
        int32 BestPreviousEnd = INDEX_NONE;
        for (const FInfinityPassageSettings& Candidate : Show->PassageSettings)
        {
            const int32 First = Show->FindCueIndex(Candidate.FirstCueGuid);
            const int32 Last = Show->FindCueIndex(Candidate.LastCueGuid);
            if (First == INDEX_NONE || Last == INDEX_NONE)
            {
                continue;
            }
            if (SelectedCueIndex >= First && SelectedCueIndex <= Last)
            {
                Passage = &Candidate;
                break;
            }
            if (Last < SelectedCueIndex && Last > BestPreviousEnd)
            {
                Passage = &Candidate;
                BestPreviousEnd = Last;
            }
        }
        if (!Passage && !Show->PassageSettings.IsEmpty())
        {
            Passage = &Show->PassageSettings[0];
        }

        const FInfinityMusicRail* Rail = Passage
            ? Show->MusicRails.FindByPredicate([Passage](const FInfinityMusicRail& Candidate)
            {
                return Candidate.RailGuid == Passage->Music.PrimaryRailGuid;
            })
            : nullptr;
        UInfinityStageMusicMapAsset* MusicMap = Rail ? Rail->AnalysisMap.LoadSynchronous() : nullptr;
        const double TickRate = Show->TickResolution.AsDecimal();
        const double UsedRailSeconds = Rail && TickRate > 0.0 && Rail->SourceOutFrame > Rail->SourceInFrame
            ? (Rail->SourceOutFrame - Rail->SourceInFrame).Value / TickRate
            : 0.0;
        const double SourceStartSeconds = Rail && TickRate > 0.0
            ? Rail->SourceInFrame.Value / TickRate
            : 0.0;
        if (!Passage || !Rail || (UsedRailSeconds <= 0.0 && (!MusicMap || MusicMap->DurationSeconds <= 0.0)))
        {
            FSlateDrawElement::MakeText(
                OutDrawElements,
                LayerId + 1,
                AllottedGeometry.ToOffsetPaintGeometry(FVector2f(10.0f, 8.0f)),
                TEXT("Selected Passage has no usable Music range"),
                SmallFont,
                DrawEffects,
                FLinearColor(0.75f, 0.55f, 0.35f));
            return LayerId + 2;
        }

        const double DurationSeconds = UsedRailSeconds > 0.0 ? UsedRailSeconds : MusicMap->DurationSeconds;
        const FString Tempo = !MusicMap || MusicMap->TempoCandidates.IsEmpty()
            ? TEXT("no stable tempo")
            : FString::Printf(TEXT("%.1f BPM proposal"), MusicMap->TempoCandidates[0].Bpm);
        const FString Title = FString::Printf(
            TEXT("%s  ·  %s  ·  %.1fs  ·  %s  ·  %d change proposals"),
            *Passage->Label.ToString(),
            *Rail->Label.ToString(),
            DurationSeconds,
            *Tempo,
            MusicMap ? MusicMap->MajorChangeProposals.Num() : 0);
        FSlateDrawElement::MakeText(
            OutDrawElements,
            LayerId + 1,
            AllottedGeometry.ToOffsetPaintGeometry(FVector2f(10.0f, 7.0f)),
            Title,
            SmallFont,
            DrawEffects,
            FLinearColor(0.86f, 0.89f, 0.93f));

        const float PlotLeft = 10.0f;
        const float PlotRight = FMath::Max(PlotLeft + 1.0f, Size.X - 10.0f);
        const float PlotTop = 28.0f;
        const float PlotBottom = FMath::Max(PlotTop + 1.0f, Size.Y - 22.0f);
        const float PlotWidth = PlotRight - PlotLeft;
        const float PlotHeight = PlotBottom - PlotTop;
        const float MidY = PlotTop + PlotHeight * 0.5f;

        FSlateDrawElement::MakeBox(
            OutDrawElements,
            LayerId + 1,
            AllottedGeometry.ToPaintGeometry(
                FVector2D(PlotWidth, PlotHeight),
                FSlateLayoutTransform(FVector2D(PlotLeft, PlotTop))),
            WhiteBrush,
            DrawEffects,
            FLinearColor(0.055f, 0.07f, 0.085f, 1.0f));

        if (TickRate > 0.0)
        {
            const float FadeInFraction = FMath::Clamp(
                static_cast<float>((Rail->FadeInFrames.Value / TickRate) / DurationSeconds), 0.0f, 1.0f);
            const float FadeOutFraction = FMath::Clamp(
                static_cast<float>((Rail->FadeOutFrames.Value / TickRate) / DurationSeconds), 0.0f, 1.0f);
            if (FadeInFraction > 0.0f)
            {
                FSlateDrawElement::MakeBox(
                    OutDrawElements,
                    LayerId + 2,
                    AllottedGeometry.ToPaintGeometry(
                        FVector2D(PlotWidth * FadeInFraction, PlotHeight),
                        FSlateLayoutTransform(FVector2D(PlotLeft, PlotTop))),
                    WhiteBrush,
                    DrawEffects,
                    FLinearColor(0.95f, 0.62f, 0.20f, 0.10f));
            }
            if (FadeOutFraction > 0.0f)
            {
                const float FadeWidth = PlotWidth * FadeOutFraction;
                FSlateDrawElement::MakeBox(
                    OutDrawElements,
                    LayerId + 2,
                    AllottedGeometry.ToPaintGeometry(
                        FVector2D(FadeWidth, PlotHeight),
                        FSlateLayoutTransform(FVector2D(PlotRight - FadeWidth, PlotTop))),
                    WhiteBrush,
                    DrawEffects,
                    FLinearColor(0.95f, 0.62f, 0.20f, 0.10f));
            }
        }

        if (MusicMap && MusicMap->WaveformBins.Num() > 1)
        {
            const int32 PointCount = FMath::Clamp(FMath::FloorToInt(PlotWidth), 2, MusicMap->WaveformBins.Num());
            TArray<FVector2D> Upper;
            TArray<FVector2D> Lower;
            Upper.Reserve(PointCount);
            Lower.Reserve(PointCount);
            for (int32 Point = 0; Point < PointCount; ++Point)
            {
                const int32 BinIndex = FMath::Min(
                    MusicMap->WaveformBins.Num() - 1,
                    FMath::FloorToInt(static_cast<double>(Point) * MusicMap->WaveformBins.Num() / PointCount));
                const FVector3f& Bin = MusicMap->WaveformBins[BinIndex];
                const float X = PlotLeft + PlotWidth * Point / FMath::Max(1, PointCount - 1);
                Upper.Add(FVector2D(X, MidY - FMath::Clamp(Bin.Y, -1.0f, 1.0f) * PlotHeight * 0.46f));
                Lower.Add(FVector2D(X, MidY - FMath::Clamp(Bin.X, -1.0f, 1.0f) * PlotHeight * 0.46f));
            }
            FSlateDrawElement::MakeLines(
                OutDrawElements, LayerId + 3, AllottedGeometry.ToPaintGeometry(), Upper,
                DrawEffects, FLinearColor(0.32f, 0.68f, 1.0f, 0.90f), true, 1.0f);
            FSlateDrawElement::MakeLines(
                OutDrawElements, LayerId + 3, AllottedGeometry.ToPaintGeometry(), Lower,
                DrawEffects, FLinearColor(0.32f, 0.68f, 1.0f, 0.90f), true, 1.0f);
        }

        if (MusicMap)
        {
            const auto MarkerX = [&](const FInfinityMusicAnalysisMarker& Marker)
            {
                return PlotLeft + PlotWidth * FMath::Clamp(
                    static_cast<float>((Marker.TimeSeconds - SourceStartSeconds) / DurationSeconds),
                    0.0f,
                    1.0f);
            };
            const auto MarkerInRange = [&](const FInfinityMusicAnalysisMarker& Marker)
            {
                const double RelativeSeconds = Marker.TimeSeconds - SourceStartSeconds;
                return RelativeSeconds >= 0.0 && RelativeSeconds <= DurationSeconds
                    && Marker.State != EInfinityMusicProposalState::Rejected;
            };

            for (const FInfinityMusicAnalysisMarker& Marker : MusicMap->BeatProposals)
            {
                if (!MarkerInRange(Marker))
                {
                    continue;
                }
                const float X = MarkerX(Marker);
                FSlateDrawElement::MakeBox(
                    OutDrawElements,
                    LayerId + 4,
                    AllottedGeometry.ToPaintGeometry(
                        FVector2D(1.0f, PlotHeight * 0.16f),
                        FSlateLayoutTransform(FVector2D(X, PlotBottom - PlotHeight * 0.16f))),
                    WhiteBrush,
                    DrawEffects,
                    Marker.State == EInfinityMusicProposalState::Confirmed
                        ? FLinearColor(0.35f, 0.92f, 1.0f, 0.85f)
                        : FLinearColor(0.35f, 0.70f, 0.92f, 0.42f));
            }
            for (const FInfinityMusicAnalysisMarker& Marker : MusicMap->OnsetProposals)
            {
                if (!MarkerInRange(Marker))
                {
                    continue;
                }
                const float X = MarkerX(Marker);
                const float Height = PlotHeight * FMath::Lerp(
                    0.10f,
                    0.42f,
                    FMath::Clamp(static_cast<float>(Marker.Strength), 0.0f, 1.0f));
                FSlateDrawElement::MakeBox(
                    OutDrawElements,
                    LayerId + 4,
                    AllottedGeometry.ToPaintGeometry(
                        FVector2D(1.0f, Height),
                        FSlateLayoutTransform(FVector2D(X, PlotTop))),
                    WhiteBrush,
                    DrawEffects,
                    Marker.State == EInfinityMusicProposalState::Confirmed
                        ? FLinearColor(1.0f, 0.82f, 0.30f, 0.90f)
                        : FLinearColor(0.90f, 0.68f, 0.24f, 0.42f));
            }
            for (const FInfinityMusicAnalysisMarker& Marker : MusicMap->MajorChangeProposals)
            {
                if (!MarkerInRange(Marker))
                {
                    continue;
                }
                const float X = MarkerX(Marker);
                FSlateDrawElement::MakeBox(
                    OutDrawElements,
                    LayerId + 4,
                    AllottedGeometry.ToPaintGeometry(
                        FVector2D(1.5f, PlotHeight),
                        FSlateLayoutTransform(FVector2D(X, PlotTop))),
                    WhiteBrush,
                    DrawEffects,
                    Marker.State == EInfinityMusicProposalState::Confirmed
                        ? FLinearColor(0.35f, 1.0f, 0.55f, 0.95f)
                        : FLinearColor(1.0f, 0.35f, 0.55f, 0.80f));
            }
        }

        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
        const FInfinityCompiledPassage* CompiledPassage = Compiled.Passages.FindByPredicate([Passage](const FInfinityCompiledPassage& Candidate)
        {
            return Passage && Candidate.PassageGuid == Passage->PassageGuid;
        });
        UMovieSceneInfinityPassageSection* CameraSection = CameraSectionAttribute.Get();
        const EInfinityPassageCameraChannel CameraChannelId = CameraChannelAttribute.Get(EInfinityPassageCameraChannel::SpeedMultiplier);
        const FMovieSceneDoubleChannel* CameraChannel = CameraSection
            ? CameraSection->GetCameraChannel(CameraChannelId)
            : nullptr;
        if (CompiledPassage && CameraChannel)
        {
            constexpr int32 CurveSamples = 128;
            TArray<double, TInlineAllocator<CurveSamples + 1>> Values;
            Values.Reserve(CurveSamples + 1);
            double Minimum = CameraChannelDefault(CameraChannelId);
            double Maximum = Minimum;
            const double StartFrame = CompiledPassage->SegmentStartFrame.Value;
            const double EndFrame = CompiledPassage->SegmentEndFrame.Value;
            for (int32 Sample = 0; Sample <= CurveSamples; ++Sample)
            {
                const double Frame = FMath::Lerp(StartFrame, EndFrame, static_cast<double>(Sample) / CurveSamples);
                double Value = CameraChannelDefault(CameraChannelId);
                CameraChannel->Evaluate(FFrameTime::FromDecimal(Frame), Value);
                Value = FMath::IsFinite(Value) ? Value : CameraChannelDefault(CameraChannelId);
                Values.Add(Value);
                Minimum = FMath::Min(Minimum, Value);
                Maximum = FMath::Max(Maximum, Value);
            }
            if (CameraChannelId == EInfinityPassageCameraChannel::SpeedMultiplier)
            {
                Minimum = FMath::Min(Minimum, 0.0);
                Maximum = FMath::Max(Maximum, 2.0);
            }
            else if (CameraChannelId == EInfinityPassageCameraChannel::FocalLengthMm)
            {
                Minimum = FMath::Min(Minimum, 10.0);
                Maximum = FMath::Max(Maximum, 100.0);
            }
            else if (CameraChannelId == EInfinityPassageCameraChannel::FocusDistanceCm)
            {
                Minimum = FMath::Min(Minimum, 0.0);
                Maximum = FMath::Max(Maximum, 1000.0);
            }
            else if (CameraChannelId == EInfinityPassageCameraChannel::LookAheadDistanceCm)
            {
                Minimum = FMath::Min(Minimum, 0.0);
                Maximum = FMath::Max(Maximum, 1000.0);
            }
            else if (CameraChannelId == EInfinityPassageCameraChannel::WingInwardTravelScale
                || CameraChannelId == EInfinityPassageCameraChannel::WingCycleRateScale)
            {
                // Unity is the neutral value, so keep it visible even when the
                // authored curve only ever reduces or only ever increases.
                Minimum = FMath::Min(Minimum, 0.0);
                Maximum = FMath::Max(Maximum, 2.0);
            }
            else if (CameraChannelId == EInfinityPassageCameraChannel::WingPhaseBiasCycles)
            {
                Minimum = FMath::Min(Minimum, -1.0);
                Maximum = FMath::Max(Maximum, 1.0);
            }
            else
            {
                const double MinimumSpan = CameraChannelId <= EInfinityPassageCameraChannel::HeightOffsetCm ? 200.0 : 20.0;
                const double Center = (Minimum + Maximum) * 0.5;
                const double HalfSpan = FMath::Max(MinimumSpan * 0.5, (Maximum - Minimum) * 0.6);
                Minimum = Center - HalfSpan;
                Maximum = Center + HalfSpan;
            }
            const double Range = FMath::Max(UE_DOUBLE_SMALL_NUMBER, Maximum - Minimum);
            TArray<FVector2D> CurvePoints;
            CurvePoints.Reserve(Values.Num());
            for (int32 Sample = 0; Sample < Values.Num(); ++Sample)
            {
                const float X = PlotLeft + PlotWidth * Sample / CurveSamples;
                const float Y = PlotBottom - PlotHeight * static_cast<float>((Values[Sample] - Minimum) / Range);
                CurvePoints.Add(FVector2D(X, Y));
            }
            FSlateDrawElement::MakeLines(
                OutDrawElements, LayerId + 5, AllottedGeometry.ToPaintGeometry(), CurvePoints,
                DrawEffects, FLinearColor(1.0f, 0.72f, 0.16f, 0.95f), true, 1.6f);

            const auto ChannelData = CameraChannel->GetData();
            const TArrayView<const FFrameNumber> KeyTimes = ChannelData.GetTimes();
            const TArrayView<const FMovieSceneDoubleValue> KeyValues = ChannelData.GetValues();
            for (int32 KeyIndex = 0; KeyIndex < KeyTimes.Num(); ++KeyIndex)
            {
                if (KeyTimes[KeyIndex].Value < StartFrame || KeyTimes[KeyIndex].Value > EndFrame)
                {
                    continue;
                }
                const float X = PlotLeft + PlotWidth * static_cast<float>((KeyTimes[KeyIndex].Value - StartFrame) / FMath::Max(1.0, EndFrame - StartFrame));
                const float Y = PlotBottom - PlotHeight * static_cast<float>((KeyValues[KeyIndex].Value - Minimum) / Range);
                FSlateDrawElement::MakeBox(
                    OutDrawElements, LayerId + 6,
                    AllottedGeometry.ToPaintGeometry(FVector2D(6.0f, 6.0f), FSlateLayoutTransform(FVector2D(X - 3.0f, Y - 3.0f))),
                    WhiteBrush, DrawEffects, FLinearColor(1.0f, 0.78f, 0.24f));
            }

            for (const FInfinityCompiledWing& Wing : CompiledPassage->Wings)
            {
                if (!CameraSection->PinnedWingCueGuids.Contains(Wing.CueGuid))
                {
                    continue;
                }
                const float X = PlotLeft + PlotWidth * static_cast<float>((Wing.PassFrame.Value - StartFrame) / FMath::Max(1.0, EndFrame - StartFrame));
                FSlateDrawElement::MakeBox(
                    OutDrawElements, LayerId + 4,
                    AllottedGeometry.ToPaintGeometry(FVector2D(1.0f, PlotHeight), FSlateLayoutTransform(FVector2D(X, PlotTop))),
                    WhiteBrush, DrawEffects, FLinearColor(0.35f, 1.0f, 0.62f, 0.75f));
            }
            for (const FFrameNumber RelativeFrame : CameraSection->PinnedPassageFrames)
            {
                const double AbsoluteFrame = StartFrame + RelativeFrame.Value;
                if (AbsoluteFrame <= StartFrame || AbsoluteFrame >= EndFrame)
                {
                    continue;
                }
                const float X = PlotLeft + PlotWidth * static_cast<float>((AbsoluteFrame - StartFrame) / FMath::Max(1.0, EndFrame - StartFrame));
                FSlateDrawElement::MakeBox(
                    OutDrawElements, LayerId + 4,
                    AllottedGeometry.ToPaintGeometry(FVector2D(1.0f, PlotHeight), FSlateLayoutTransform(FVector2D(X, PlotTop))),
                    WhiteBrush, DrawEffects, FLinearColor(0.20f, 0.92f, 1.0f, 0.82f));
            }
            FSlateDrawElement::MakeText(
                OutDrawElements, LayerId + 6,
                AllottedGeometry.ToPaintGeometry(FVector2D(220.0f, 16.0f), FSlateLayoutTransform(FVector2D(FMath::Max(PlotLeft, PlotRight - 220.0f), PlotTop + 3.0f))),
                CameraChannelText(CameraChannelId), SmallFont, DrawEffects, FLinearColor(1.0f, 0.78f, 0.24f));
        }

        const double ExternalPlayhead = PlayheadPositionAttribute.Get(-1.0);
        const double DisplayPlayhead = ExternalPlayhead >= 0.0 ? ExternalPlayhead : ScrubPosition;
        if (DisplayPlayhead >= 0.0)
        {
            const float ScrubX = PlotLeft + PlotWidth * static_cast<float>(DisplayPlayhead);
            FSlateDrawElement::MakeBox(
                OutDrawElements,
                LayerId + 6,
                AllottedGeometry.ToPaintGeometry(
                    FVector2D(2.0f, PlotHeight),
                    FSlateLayoutTransform(FVector2D(ScrubX, PlotTop))),
                WhiteBrush,
                DrawEffects,
                FLinearColor(1.0f, 0.82f, 0.22f, 0.95f));
        }

        FSlateDrawElement::MakeText(
            OutDrawElements,
            LayerId + 5,
            AllottedGeometry.ToOffsetPaintGeometry(FVector2f(PlotLeft, PlotBottom + 3.0f)),
            TEXT("0:00"),
            SmallFont,
            DrawEffects,
            FLinearColor(0.58f, 0.64f, 0.70f));
        const FString EndLabel = FString::Printf(TEXT("%.1fs"), DurationSeconds);
        FSlateDrawElement::MakeText(
            OutDrawElements,
            LayerId + 5,
            AllottedGeometry.ToPaintGeometry(
                FVector2D(70.0f, 16.0f),
                FSlateLayoutTransform(FVector2D(FMath::Max(PlotLeft, PlotRight - 70.0f), PlotBottom + 3.0f))),
            EndLabel,
            SmallFont,
            DrawEffects,
            FLinearColor(0.58f, 0.64f, 0.70f));

        return LayerId + 7;
    }

    virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (Event.GetEffectingButton() != EKeys::LeftMouseButton)
        {
            return FReply::Unhandled();
        }
        bScrubbing = true;
        ScrubAt(Geometry, Event, false);
        return FReply::Handled().CaptureMouse(AsShared());
    }

    virtual FReply OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (!bScrubbing || !HasMouseCapture())
        {
            return FReply::Unhandled();
        }
        ScrubAt(Geometry, Event, false);
        return FReply::Handled();
    }

    virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (!bScrubbing || Event.GetEffectingButton() != EKeys::LeftMouseButton)
        {
            return FReply::Unhandled();
        }
        ScrubAt(Geometry, Event, true);
        bScrubbing = false;
        return FReply::Handled().ReleaseMouseCapture();
    }

private:
    void ScrubAt(const FGeometry& Geometry, const FPointerEvent& Event, const bool bFinal)
    {
        const FVector2D Local = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition());
        const double Width = FMath::Max(1.0, static_cast<double>(Geometry.GetLocalSize().X) - 20.0);
        ScrubPosition = FMath::Clamp((Local.X - 10.0) / Width, 0.0, 1.0);
        if (SnapToMusicMarkersAttribute.Get(false) && !Event.IsAltDown())
        {
            UInfinityStageShowAsset* Show = ShowAssetAttribute.Get();
            const int32 SelectedCueIndex = SelectedCueIndexAttribute.Get();
            const FInfinityPassageSettings* Passage = nullptr;
            int32 BestPreviousEnd = INDEX_NONE;
            if (Show)
            {
                for (const FInfinityPassageSettings& Candidate : Show->PassageSettings)
                {
                    const int32 First = Show->FindCueIndex(Candidate.FirstCueGuid);
                    const int32 Last = Show->FindCueIndex(Candidate.LastCueGuid);
                    if (First == INDEX_NONE || Last == INDEX_NONE)
                    {
                        continue;
                    }
                    if (SelectedCueIndex >= First && SelectedCueIndex <= Last)
                    {
                        Passage = &Candidate;
                        break;
                    }
                    if (Last < SelectedCueIndex && Last > BestPreviousEnd)
                    {
                        Passage = &Candidate;
                        BestPreviousEnd = Last;
                    }
                }
                if (!Passage && !Show->PassageSettings.IsEmpty())
                {
                    Passage = &Show->PassageSettings[0];
                }
            }
            const FInfinityMusicRail* Rail = Show && Passage
                ? Show->MusicRails.FindByPredicate([Passage](const FInfinityMusicRail& Candidate)
                {
                    return Candidate.RailGuid == Passage->Music.PrimaryRailGuid;
                })
                : nullptr;
            const UInfinityStageMusicMapAsset* MusicMap = Rail
                ? Rail->AnalysisMap.LoadSynchronous()
                : nullptr;
            const double TickRate = Show ? Show->TickResolution.AsDecimal() : 0.0;
            const double SourceStartSeconds = Rail && TickRate > 0.0
                ? Rail->SourceInFrame.Value / TickRate
                : 0.0;
            const double UsedSeconds = Rail && TickRate > 0.0 && Rail->SourceOutFrame > Rail->SourceInFrame
                ? (Rail->SourceOutFrame - Rail->SourceInFrame).Value / TickRate
                : (MusicMap ? MusicMap->DurationSeconds : 0.0);
            if (MusicMap && UsedSeconds > UE_DOUBLE_SMALL_NUMBER)
            {
                double BestPosition = ScrubPosition;
                double BestDelta = 12.0 / Width;
                const auto ConsiderMarkers = [&](const TArray<FInfinityMusicAnalysisMarker>& Markers)
                {
                    for (const FInfinityMusicAnalysisMarker& Marker : Markers)
                    {
                        if (Marker.State == EInfinityMusicProposalState::Rejected)
                        {
                            continue;
                        }
                        const double Position = (Marker.TimeSeconds - SourceStartSeconds) / UsedSeconds;
                        if (Position < 0.0 || Position > 1.0)
                        {
                            continue;
                        }
                        const double Delta = FMath::Abs(Position - ScrubPosition);
                        if (Delta <= BestDelta)
                        {
                            BestDelta = Delta;
                            BestPosition = Position;
                        }
                    }
                };
                ConsiderMarkers(MusicMap->BeatProposals);
                ConsiderMarkers(MusicMap->OnsetProposals);
                ConsiderMarkers(MusicMap->MajorChangeProposals);
                ScrubPosition = BestPosition;
            }
        }
        OnScrub.ExecuteIfBound(ScrubPosition, bFinal);
        Invalidate(EInvalidateWidgetReason::Paint);
    }

    TAttribute<UInfinityStageShowAsset*> ShowAssetAttribute;
    TAttribute<int32> SelectedCueIndexAttribute;
    TAttribute<double> PlayheadPositionAttribute;
    TAttribute<UMovieSceneInfinityPassageSection*> CameraSectionAttribute;
    TAttribute<EInfinityPassageCameraChannel> CameraChannelAttribute;
    TAttribute<bool> SnapToMusicMarkersAttribute;
    FOnInfinityMusicTimelineScrub OnScrub;
    bool bScrubbing = false;
    double ScrubPosition = -1.0;
};

class SInfinityStageCueRow final : public SMultiColumnTableRow<TSharedPtr<FInfinityCueListItem>>
{
public:
    SLATE_BEGIN_ARGS(SInfinityStageCueRow) {}
        SLATE_ARGUMENT(TSharedPtr<FInfinityCueListItem>, Item)
        SLATE_ARGUMENT(TWeakObjectPtr<UInfinityStageShowAsset>, ShowAsset)
        SLATE_EVENT(FSimpleDelegate, OnTogglePassage)
        SLATE_EVENT(FOnRenameInfinityPassage, OnRenamePassage)
        SLATE_EVENT(FOnInfinityCueDragDetected, OnCueDragDetected)
        SLATE_EVENT(FOnInfinityCueCanAcceptDrop, OnCueCanAcceptDrop)
        SLATE_EVENT(FOnInfinityCueAcceptDrop, OnCueAcceptDrop)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& OwnerTable)
    {
        Item = InArgs._Item;
        ShowAsset = InArgs._ShowAsset;
        OnTogglePassage = InArgs._OnTogglePassage;
        OnRenamePassage = InArgs._OnRenamePassage;
        OnCueDragDetected = InArgs._OnCueDragDetected;
        OnCueCanAcceptDrop = InArgs._OnCueCanAcceptDrop;
        OnCueAcceptDrop = InArgs._OnCueAcceptDrop;
        SMultiColumnTableRow::Construct(
            FSuperRowType::FArguments()
                .Padding(FMargin(3.0f, 2.0f))
                .OnDragDetected(this, &SInfinityStageCueRow::HandleDragDetected)
                .OnCanAcceptDrop(this, &SInfinityStageCueRow::HandleCanAcceptDrop)
                .OnAcceptDrop(this, &SInfinityStageCueRow::HandleAcceptDrop),
            OwnerTable);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
    {
        if (Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::PassageHeader)
        {
            if (ColumnName == TEXT("Number"))
            {
                return SNew(SButton)
                    .ButtonStyle(FAppStyle::Get(), TEXT("SimpleButton"))
                    .ContentPadding(FMargin(2.0f, 0.0f))
                    .ToolTipText(Item->bPassageCollapsed
                        ? NSLOCTEXT("InfinityStage", "ExpandPassageTip", "Expand this Passage's Wing Pairs")
                        : NSLOCTEXT("InfinityStage", "CollapsePassageTip", "Collapse this Passage's Wing Pairs"))
                    .OnClicked_Lambda([this]()
                    {
                        OnTogglePassage.ExecuteIfBound();
                        return FReply::Handled();
                    })
                    [
                        SNew(STextBlock).Text(FText::FromString(
                            Item->bPassageCollapsed ? TEXT("▸") : TEXT("▾")))
                    ];
            }
            if (ColumnName == TEXT("Type"))
            {
                return SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "PassageNodeType", "PASS"));
            }
            if (ColumnName == TEXT("Name"))
            {
                return SNew(SHorizontalBox)
                    + SHorizontalBox::Slot()
                    .FillWidth(1.0f)
                    .VAlign(VAlign_Center)
                    [
                        SNew(SInlineEditableTextBlock)
                        .Text(Item->HeaderLabel)
                        .IsSelected(this, &SInfinityStageCueRow::IsSelectedExclusively)
                        .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")))
                        .ToolTipText(NSLOCTEXT(
                            "InfinityStage", "RenamePassageInlineTip",
                            "Double-click to rename this Passage. The Wing row names are independent."))
                        .OnTextCommitted_Lambda([this](const FText& NewText, ETextCommit::Type)
                        {
                            if (Item.IsValid())
                            {
                                OnRenamePassage.ExecuteIfBound(Item->PassageGuid, NewText);
                            }
                        })
                    ]
                    + SHorizontalBox::Slot()
                    .AutoWidth()
                    .Padding(6.0f, 0.0f)
                    .VAlign(VAlign_Center)
                    [
                        SNew(STextBlock)
                        .Text(FText::Format(
                            NSLOCTEXT("InfinityStage", "PassagePairCount", "{0} pairs"),
                            Item->ChildCount))
                    ];
            }
            return SNew(STextBlock).Text(FText::GetEmpty());
        }

        const UInfinityStageShowAsset* Asset = ShowAsset.Get();
        const FInfinityShowCue* Cue = Asset && Item.IsValid() && Asset->Cues.IsValidIndex(Item->CueIndex)
            ? &Asset->Cues[Item->CueIndex]
            : nullptr;
        if (!Cue)
        {
            return SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "MissingCue", "Missing"));
        }

        if (ColumnName == TEXT("Number"))
        {
            return SNew(STextBlock).Text(FText::AsNumber(Item->CueIndex + 1));
        }
        if (ColumnName == TEXT("Type"))
        {
            return SNew(STextBlock).Text(CueTypeText(Cue->Type));
        }
        if (ColumnName == TEXT("Name"))
        {
            return SNew(SBorder)
                .BorderImage(FAppStyle::GetBrush(TEXT("NoBorder")))
                .Padding(FMargin(Item->bNestedChild ? 14.0f : 0.0f, 0.0f))
                [
                    SNew(STextBlock).Text(Cue->Label.IsEmpty() ? NSLOCTEXT("InfinityStage", "UnnamedCue", "Untitled Cue") : Cue->Label)
                ];
        }
        if (ColumnName == TEXT("Timing"))
        {
            return SNew(STextBlock).Text(Cue->Type == EInfinityCueType::WingPair
                ? FText::Format(NSLOCTEXT("InfinityStage", "IntervalFrames", "{0} fr"), Cue->WingPair.IntervalToNext.Value)
                : FText::Format(NSLOCTEXT("InfinityStage", "DurationFrames", "{0} fr"), Cue->Scene.DurationFrames.Value));
        }
        if (ColumnName == TEXT("Spacing"))
        {
            return SNew(STextBlock).Text(Cue->Type == EInfinityCueType::WingPair
                ? FText::Format(NSLOCTEXT("InfinityStage", "SpacingMetres", "{0} m"), NumberText(Cue->WingPair.GapToNextCm / 100.0, 2))
                : FText::FromString(TEXT("—")));
        }
        return SNew(STextBlock).Text(Cue->bEnabled
            ? NSLOCTEXT("InfinityStage", "CueReady", "READY")
            : NSLOCTEXT("InfinityStage", "CueDisabled", "OFF"));
    }

private:
    FReply HandleDragDetected(const FGeometry&, const FPointerEvent&)
    {
        return OnCueDragDetected.IsBound()
            ? OnCueDragDetected.Execute(Item)
            : FReply::Unhandled();
    }

    TOptional<EItemDropZone> HandleCanAcceptDrop(
        const FDragDropEvent& DragDropEvent,
        const EItemDropZone DropZone,
        TSharedPtr<FInfinityCueListItem>)
    {
        return OnCueCanAcceptDrop.IsBound()
            ? OnCueCanAcceptDrop.Execute(DragDropEvent, DropZone, Item)
            : TOptional<EItemDropZone>();
    }

    FReply HandleAcceptDrop(
        const FDragDropEvent& DragDropEvent,
        const EItemDropZone DropZone,
        TSharedPtr<FInfinityCueListItem>)
    {
        return OnCueAcceptDrop.IsBound()
            ? OnCueAcceptDrop.Execute(DragDropEvent, DropZone, Item)
            : FReply::Unhandled();
    }

    TSharedPtr<FInfinityCueListItem> Item;
    TWeakObjectPtr<UInfinityStageShowAsset> ShowAsset;
    FSimpleDelegate OnTogglePassage;
    FOnRenameInfinityPassage OnRenamePassage;
    FOnInfinityCueDragDetected OnCueDragDetected;
    FOnInfinityCueCanAcceptDrop OnCueCanAcceptDrop;
    FOnInfinityCueAcceptDrop OnCueAcceptDrop;
};
}

void SInfinityStageCueDesk::Construct(const FArguments& InArgs)
{
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("FollowMusicScrubInViewport"),
        bFollowMusicScrubInViewport,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("FollowCueSelectionToPlayhead"),
        bFollowCueSelectionToPlayhead,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("NestedCueMode"),
        bNestedCueMode,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("MusicWorkspaceVisible"),
        bMusicWorkspaceVisible,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("SnapMusicScrubToMarkers"),
        bSnapMusicScrubToMarkers,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("RehearsalTransport"),
        bRehearsalTransport,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("PlayThroughBoundaries"),
        bPlayThroughBoundaries,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("SyncSequencerPlayhead"),
        bSyncSequencerPlayhead,
        GEditorPerProjectIni);
    GConfig->GetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("PieStartsAtPlayhead"),
        bPieStartsAtPlayhead,
        GEditorPerProjectIni);
    PostPieStartedHandle = FEditorDelegates::PostPIEStarted.AddSP(
        this, &SInfinityStageCueDesk::HandlePostPieStarted);
    GConfig->GetFloat(TEXT("InfinityStage.CueDesk"), TEXT("MainWorkspaceFraction"), MainWorkspaceFraction, GEditorPerProjectIni);
    GConfig->GetFloat(TEXT("InfinityStage.CueDesk"), TEXT("MusicWorkspaceFraction"), MusicWorkspaceFraction, GEditorPerProjectIni);
    GConfig->GetFloat(TEXT("InfinityStage.CueDesk"), TEXT("CueListFraction"), CueListFraction, GEditorPerProjectIni);
    GConfig->GetFloat(TEXT("InfinityStage.CueDesk"), TEXT("CueDetailsFraction"), CueDetailsFraction, GEditorPerProjectIni);
    GConfig->GetFloat(TEXT("InfinityStage.CueDesk"), TEXT("InspectorFraction"), InspectorFraction, GEditorPerProjectIni);
    // The vertical splitter normalizes these two against each other, so an
    // independently clamped pair can hand the music workspace a few percent of
    // the height — and because both are written back on every resize, that state
    // persists across restarts. Normalize the pair so a saved layout always
    // reopens usable.
    MainWorkspaceFraction = FMath::Clamp(MainWorkspaceFraction, 0.15f, 0.88f);
    MusicWorkspaceFraction = FMath::Clamp(MusicWorkspaceFraction, 0.12f, 0.85f);
    const float WorkspaceFractionTotal = MainWorkspaceFraction + MusicWorkspaceFraction;
    MainWorkspaceFraction /= WorkspaceFractionTotal;
    MusicWorkspaceFraction /= WorkspaceFractionTotal;
    CueListFraction = FMath::Clamp(CueListFraction, 0.10f, 0.80f);
    CueDetailsFraction = FMath::Clamp(CueDetailsFraction, 0.10f, 0.80f);
    InspectorFraction = FMath::Clamp(InspectorFraction, 0.10f, 0.80f);

    FPropertyEditorModule& PropertyEditor = FModuleManager::LoadModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
    FDetailsViewArgs DetailsArgs;
    DetailsArgs.bAllowSearch = true;
    DetailsArgs.bHideSelectionTip = true;
    DetailsArgs.NameAreaSettings = FDetailsViewArgs::HideNameArea;
    CueDetails = PropertyEditor.CreateDetailView(DetailsArgs);
    AssetDetails = PropertyEditor.CreateDetailView(DetailsArgs);
    PassageDetails = PropertyEditor.CreateDetailView(DetailsArgs);
    CueDetails->SetObject(nullptr);
    PassageDetails->SetObject(nullptr);

    ChildSlot
    [
        SNew(SVerticalBox)
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(4.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot()
            .FillWidth(1.0f)
            [
                SNew(SObjectPropertyEntryBox)
                .AllowedClass(UInfinityStageShowAsset::StaticClass())
                .ObjectPath(this, &SInfinityStageCueDesk::GetAssetPath)
                .OnObjectChanged(this, &SInfinityStageCueDesk::HandleAssetChanged)
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            .Padding(4.0f, 0.0f)
            [
                SNew(SComboButton)
                .ButtonContent()
                [
                    SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "AddMenu", "Add Cue"))
                ]
                .MenuContent()
                [
                    BuildAddMenu()
                ]
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            .Padding(0.0f, 0.0f, 4.0f, 0.0f)
            [
                SNew(SComboButton)
                .ButtonContent()
                [
                    SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "ViewMenu", "View"))
                ]
                .MenuContent()
                [
                    BuildViewMenu()
                ]
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            [
                SNew(SComboButton)
                .ButtonContent()
                [
                    SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "ActionsMenu", "Actions"))
                ]
                .MenuContent()
                [
                    BuildActionsMenu()
                ]
            ]
        ]
        + SVerticalBox::Slot()
        .FillHeight(1.0f)
        [
            SNew(SSplitter)
            .Orientation(Orient_Vertical)
            .PhysicalSplitterHandleSize(6.0f)
            .OnSplitterFinishedResizing_Lambda([this]() { SaveLayoutConfig(); })
            + SSplitter::Slot()
            .Value(MainWorkspaceFraction)
            // Keep the two minimums small enough to both fit a short docked
            // panel. If their sum exceeds the available height, neither slot can
            // give space away and the handle refuses every drag even though it
            // still shows a resize cursor.
            .MinSize(120.0f)
            .OnSlotResized_Lambda([this](const float Value) { MainWorkspaceFraction = Value; })
            [
                SNew(SSplitter)
                .PhysicalSplitterHandleSize(5.0f)
                .OnSplitterFinishedResizing_Lambda([this]() { SaveLayoutConfig(); })
                + SSplitter::Slot()
                .Value(CueListFraction)
                .MinSize(280.0f)
                .OnSlotResized_Lambda([this](const float Value) { CueListFraction = Value; })
                [
                    SAssignNew(CueList, SListView<FCueItem>)
                    .ListItemsSource(&CueItems)
                    .SelectionMode(ESelectionMode::Multi)
                    .OnGenerateRow(this, &SInfinityStageCueDesk::GenerateCueRow)
                    .OnSelectionChanged(this, &SInfinityStageCueDesk::HandleCueSelection)
                    .OnContextMenuOpening(this, &SInfinityStageCueDesk::BuildCueContextMenu)
                    .HeaderRow
                    (
                        SNew(SHeaderRow)
                        + SHeaderRow::Column(TEXT("Number")).DefaultLabel(NSLOCTEXT("InfinityStage", "NumberColumn", "#")).FixedWidth(42.0f)
                        + SHeaderRow::Column(TEXT("Type")).DefaultLabel(NSLOCTEXT("InfinityStage", "TypeColumn", "Type")).FixedWidth(68.0f)
                        + SHeaderRow::Column(TEXT("Name")).DefaultLabel(NSLOCTEXT("InfinityStage", "NameColumn", "Cue")).FillWidth(1.0f)
                        + SHeaderRow::Column(TEXT("Timing")).DefaultLabel(NSLOCTEXT("InfinityStage", "TimingColumn", "Timing")).FixedWidth(92.0f)
                        + SHeaderRow::Column(TEXT("Spacing")).DefaultLabel(NSLOCTEXT("InfinityStage", "SpacingColumn", "Spacing")).FixedWidth(78.0f)
                        + SHeaderRow::Column(TEXT("Status")).DefaultLabel(NSLOCTEXT("InfinityStage", "StatusColumn", "Status")).FixedWidth(70.0f)
                    )
                ]
                + SSplitter::Slot()
                .Value(CueDetailsFraction)
                .MinSize(260.0f)
                .OnSlotResized_Lambda([this](const float Value) { CueDetailsFraction = Value; })
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(6.0f, 4.0f)
                    [
                        SNew(STextBlock)
                        .Text(this, &SInfinityStageCueDesk::GetCueSelectionSummaryText)
                        .AutoWrapText(true)
                    ]
                    + SVerticalBox::Slot()
                    .FillHeight(1.0f)
                    [
                        CueDetails.ToSharedRef()
                    ]
                ]
                + SSplitter::Slot()
                .Value(InspectorFraction)
                .MinSize(320.0f)
                .OnSlotResized_Lambda([this](const float Value) { InspectorFraction = Value; })
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(6.0f, 4.0f)
                    [
                        SNew(STextBlock)
                        .Text(NSLOCTEXT("InfinityStage", "PassageMusicInspectorHeading", "Passage / Music"))
                        .Font(FAppStyle::GetFontStyle(TEXT("DetailsView.CategoryFontStyle")))
                    ]
                    + SVerticalBox::Slot()
                    .FillHeight(1.0f)
                    [
                        BuildMusicPanel()
                    ]
                ]
            ]
            + SSplitter::Slot()
            .Value(MusicWorkspaceFraction)
            // A zero minimum let the top slot drive this one to nothing, leaving
            // its 6 px handle pinned against the status bar. Collapsed slots are
            // skipped by SSplitter, so hiding the workspace still costs no height.
            .MinSize(90.0f)
            .OnSlotResized_Lambda([this](const float Value) { MusicWorkspaceFraction = Value; })
            [
                SNew(SBox)
                .Visibility_Lambda([this]()
                {
                    return bMusicWorkspaceVisible ? EVisibility::Visible : EVisibility::Collapsed;
                })
                [
                    BuildMusicWorkspace()
                ]
            ]
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            SNew(SBorder)
            .Padding(FMargin(8.0f, 4.0f))
            [
                SNew(STextBlock)
                .Text(this, &SInfinityStageCueDesk::GetStatusText)
            ]
        ]
    ];

    if (InArgs._InitialShowAsset)
    {
        ShowAsset = InArgs._InitialShowAsset;
        ShowAsset->EnsureStableIds();
        ShowAsset->ReconcilePassageSettings();
        AssetDetails->SetObject(ShowAsset.Get());
        RefreshFromAsset(false);
    }
}

SInfinityStageCueDesk::~SInfinityStageCueDesk()
{
    FEditorDelegates::PostPIEStarted.Remove(PostPieStartedHandle);
    StopEditorPreviewPlayback();
    StopMusicScrubPreview();
    FinishViewportEdit(false);
    ClearEditorWorldInstanceSelection();
}

TSharedRef<ITableRow> SInfinityStageCueDesk::GenerateCueRow(FCueItem Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SInfinityStageCueRow, OwnerTable)
        .Item(Item)
        .ShowAsset(ShowAsset)
        .OnTogglePassage(FSimpleDelegate::CreateSP(
            this,
            &SInfinityStageCueDesk::TogglePassageCollapsed,
            Item.IsValid() ? Item->PassageGuid : FGuid()))
        .OnRenamePassage(FOnRenameInfinityPassage::CreateSP(
            this, &SInfinityStageCueDesk::RenamePassage))
        .OnCueDragDetected(FOnInfinityCueDragDetected::CreateSP(
            this, &SInfinityStageCueDesk::HandleCueDragDetected))
        .OnCueCanAcceptDrop(FOnInfinityCueCanAcceptDrop::CreateSP(
            this, &SInfinityStageCueDesk::HandleCueCanAcceptDrop))
        .OnCueAcceptDrop(FOnInfinityCueAcceptDrop::CreateSP(
            this, &SInfinityStageCueDesk::HandleCueAcceptDrop));
}

FReply SInfinityStageCueDesk::HandleCueDragDetected(const FCueItem Item)
{
    if (!ShowAsset.IsValid() || !CueList.IsValid() || !Item.IsValid()
        || Item->NodeType != EInfinityCueListNodeType::Cue)
    {
        return FReply::Unhandled();
    }

    TArray<int32> OrderedIndices;
    for (const FCueItem& SelectedItem : CueList->GetSelectedItems())
    {
        if (!SelectedItem.IsValid() || SelectedItem->NodeType != EInfinityCueListNodeType::Cue
            || !ShowAsset->Cues.IsValidIndex(SelectedItem->CueIndex)
            || ShowAsset->Cues[SelectedItem->CueIndex].Type != EInfinityCueType::WingPair)
        {
            return FReply::Unhandled();
        }
        OrderedIndices.AddUnique(SelectedItem->CueIndex);
    }
    OrderedIndices.Sort();
    if (OrderedIndices.IsEmpty())
    {
        return FReply::Unhandled();
    }

    TArray<FGuid> OrderedCueGuids;
    OrderedCueGuids.Reserve(OrderedIndices.Num());
    for (const int32 CueIndex : OrderedIndices)
    {
        OrderedCueGuids.Add(ShowAsset->Cues[CueIndex].CueGuid);
    }
    return FReply::Handled().BeginDragDrop(
        FInfinityCueDragDropOp::New(ShowAsset.Get(), MoveTemp(OrderedCueGuids)));
}

TOptional<EItemDropZone> SInfinityStageCueDesk::HandleCueCanAcceptDrop(
    const FDragDropEvent& DragDropEvent,
    const EItemDropZone DropZone,
    const FCueItem TargetItem) const
{
    const TSharedPtr<FInfinityCueDragDropOp> Operation =
        DragDropEvent.GetOperationAs<FInfinityCueDragDropOp>();
    if (!Operation.IsValid() || Operation->Show.Get() != ShowAsset.Get()
        || Operation->OrderedCueGuids.IsEmpty() || !TargetItem.IsValid())
    {
        return TOptional<EItemDropZone>();
    }

    if (TargetItem->NodeType == EInfinityCueListNodeType::PassageHeader)
    {
        return EItemDropZone::OntoItem;
    }
    if (!ShowAsset->Cues.IsValidIndex(TargetItem->CueIndex))
    {
        return TOptional<EItemDropZone>();
    }
    if (Operation->OrderedCueGuids.Contains(ShowAsset->Cues[TargetItem->CueIndex].CueGuid))
    {
        return TOptional<EItemDropZone>();
    }
    return DropZone == EItemDropZone::OntoItem ? EItemDropZone::BelowItem : DropZone;
}

FReply SInfinityStageCueDesk::HandleCueAcceptDrop(
    const FDragDropEvent& DragDropEvent,
    const EItemDropZone DropZone,
    const FCueItem TargetItem)
{
    const TSharedPtr<FInfinityCueDragDropOp> Operation =
        DragDropEvent.GetOperationAs<FInfinityCueDragDropOp>();
    if (!Operation.IsValid() || Operation->Show.Get() != ShowAsset.Get()
        || !TargetItem.IsValid())
    {
        return FReply::Unhandled();
    }

    int32 RawInsertionIndex = INDEX_NONE;
    if (TargetItem->NodeType == EInfinityCueListNodeType::PassageHeader)
    {
        const FInfinityPassageSettings* TargetPassage = ShowAsset->PassageSettings.FindByPredicate(
            [TargetItem](const FInfinityPassageSettings& Passage)
            {
                return Passage.PassageGuid == TargetItem->PassageGuid;
            });
        RawInsertionIndex = TargetPassage
            ? ShowAsset->FindCueIndex(TargetPassage->LastCueGuid) + 1
            : INDEX_NONE;
    }
    else if (ShowAsset->Cues.IsValidIndex(TargetItem->CueIndex))
    {
        RawInsertionIndex = TargetItem->CueIndex
            + (DropZone == EItemDropZone::AboveItem ? 0 : 1);
    }
    if (RawInsertionIndex == INDEX_NONE)
    {
        return FReply::Unhandled();
    }

    const TArray<FGuid> MovedCueGuids = Operation->OrderedCueGuids;
    ApplyListMutation(
        NSLOCTEXT("InfinityStage", "DragMoveCueTransaction", "Reorder Infinity Stage Wing Cues"),
        [this, MovedCueGuids, RawInsertionIndex](TArray<int32>& NewSelection)
        {
            TArray<int32> SourceIndices;
            TArray<FInfinityShowCue> MovedCues;
            for (const FGuid& CueGuid : MovedCueGuids)
            {
                const int32 SourceIndex = ShowAsset->FindCueIndex(CueGuid);
                if (ShowAsset->Cues.IsValidIndex(SourceIndex)
                    && ShowAsset->Cues[SourceIndex].Type == EInfinityCueType::WingPair)
                {
                    SourceIndices.Add(SourceIndex);
                    MovedCues.Add(ShowAsset->Cues[SourceIndex]);
                }
            }
            SourceIndices.Sort();
            if (SourceIndices.IsEmpty())
            {
                return;
            }

            int32 AdjustedInsertionIndex = RawInsertionIndex;
            for (const int32 SourceIndex : SourceIndices)
            {
                if (SourceIndex < RawInsertionIndex)
                {
                    --AdjustedInsertionIndex;
                }
            }
            for (int32 Index = SourceIndices.Num() - 1; Index >= 0; --Index)
            {
                ShowAsset->Cues.RemoveAt(SourceIndices[Index]);
            }
            AdjustedInsertionIndex = FMath::Clamp(AdjustedInsertionIndex, 0, ShowAsset->Cues.Num());
            for (int32 Index = 0; Index < MovedCues.Num(); ++Index)
            {
                ShowAsset->Cues.Insert(MovedCues[Index], AdjustedInsertionIndex + Index);
                NewSelection.Add(AdjustedInsertionIndex + Index);
            }
        });
    return FReply::Handled();
}

void SInfinityStageCueDesk::HandleCueSelection(FCueItem Item, ESelectInfo::Type SelectInfo)
{
    StopEditorPreviewPlayback();
    EditorPreviewNormalizedPosition = -1.0;
    EditorPreviewPassageGuid.Invalidate();
    if (Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::PassageHeader)
    {
        FinishViewportEdit(false);
        CueProxies.Reset();
        SelectedPassageGuid = Item->PassageGuid;
        CueDetails->SetObject(nullptr, true);
        RefreshPassageInspector();
        LoadFitFromSelectedPassage();
        ClearEditorWorldInstanceSelection();
        if (bFollowCueSelectionToPlayhead && SelectInfo != ESelectInfo::Direct)
        {
            FollowCueSelectionToPlayhead(Item, true);
        }
        Invalidate(EInvalidateWidgetReason::Paint);
        return;
    }
    SelectedPassageGuid.Invalidate();
    FinishViewportEdit(false);
    CueProxies.Reset();

    if (!ShowAsset.IsValid() || !CueList.IsValid())
    {
        CueDetails->SetObject(nullptr, true);
        return;
    }

    TArray<FCueItem> SelectedItems = CueList->GetSelectedItems();
    if (SelectedItems.IsEmpty())
    {
        CueDetails->SetObject(nullptr, true);
        RefreshPassageInspector();
        ClearEditorWorldInstanceSelection();
        return;
    }

    const FCueItem PrimaryItem = Item.IsValid() && CueList->IsItemSelected(Item)
        ? Item
        : SelectedItems[0];
    if (!PrimaryItem.IsValid() || !ShowAsset->Cues.IsValidIndex(PrimaryItem->CueIndex))
    {
        CueDetails->SetObject(nullptr, true);
        return;
    }

    const EInfinityCueType PrimaryType = ShowAsset->Cues[PrimaryItem->CueIndex].Type;
    SelectedItems.Sort([](const FCueItem& A, const FCueItem& B)
    {
        return A.IsValid() && B.IsValid() ? A->CueIndex < B->CueIndex : A.IsValid();
    });

    TArray<UObject*> DetailObjects;
    for (const FCueItem& SelectedItem : SelectedItems)
    {
        if (!SelectedItem.IsValid() || !ShowAsset->Cues.IsValidIndex(SelectedItem->CueIndex)
            || ShowAsset->Cues[SelectedItem->CueIndex].Type != PrimaryType)
        {
            continue;
        }

        TStrongObjectPtr<UInfinityStageCueProxy> Proxy(
            NewObject<UInfinityStageCueProxy>(GetTransientPackage(), NAME_None, RF_Transactional));
        Proxy->Initialize(ShowAsset.Get(), SelectedItem->CueIndex);
        Proxy->OnChanged.BindSP(this, &SInfinityStageCueDesk::HandleCueProxyChanged);
        DetailObjects.Add(Proxy.Get());
        CueProxies.Add(MoveTemp(Proxy));
    }

    CueDetails->SetObjects(DetailObjects, true);
    RefreshPassageInspector();
    LoadFitFromSelectedPassage();
    // Selection highlighting and temporal navigation are deliberately separate.
    // Framing a complete pair also includes its optional Top panel and is useful
    // for inspection, but it is not the camera view at that occurrence's pass time.
    RefreshSelectedCuesInEditorWorld(false, false);
    if (bFollowCueSelectionToPlayhead && SelectInfo != ESelectInfo::Direct)
    {
        FollowCueSelectionToPlayhead(PrimaryItem, true);
    }
    Invalidate(EInvalidateWidgetReason::Paint);
}

void SInfinityStageCueDesk::HandleCueProxyChanged()
{
    if (CueList.IsValid())
    {
        CueList->RequestListRefresh();
    }
    if (!bWorldRefreshScheduled)
    {
        bWorldRefreshScheduled = true;
        RegisterActiveTimer(0.0f, FWidgetActiveTimerDelegate::CreateSP(
            this, &SInfinityStageCueDesk::HandleDeferredWorldRefresh));
    }
    RefreshPassageInspector();
    Invalidate(EInvalidateWidgetReason::Paint);
}

EActiveTimerReturnType SInfinityStageCueDesk::HandleDeferredWorldRefresh(double, float)
{
    bWorldRefreshScheduled = false;
    RefreshSelectedCuesInEditorWorld(true, false);
    return EActiveTimerReturnType::Stop;
}

void SInfinityStageCueDesk::ClearEditorWorldInstanceSelection() const
{
    if (!GEditor)
    {
        return;
    }
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        return;
    }
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        if (ShowAsset.IsValid() && It->ShowAsset != ShowAsset.Get())
        {
            continue;
        }
        for (UInstancedStaticMeshComponent* Component : It->ManagedComponents)
        {
            if (Component)
            {
                Component->ClearInstanceSelection();
                Component->MarkRenderStateDirty();
            }
        }
    }
}

void SInfinityStageCueDesk::RefreshSelectedCuesInEditorWorld(
    const bool bRematerialize,
    const bool bFrameViewport)
{
    ClearEditorWorldInstanceSelection();
    if (!GEditor || !ShowAsset.IsValid() || !CueList.IsValid())
    {
        return;
    }

    TSet<FGuid> SelectedCueGuids;
    TSet<FGuid> SelectedPassageGuids;
    for (const FCueItem& Item : CueList->GetSelectedItems())
    {
        if (!Item.IsValid() || !ShowAsset->Cues.IsValidIndex(Item->CueIndex))
        {
            continue;
        }
        const FInfinityShowCue& Cue = ShowAsset->Cues[Item->CueIndex];
        if (Cue.Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        SelectedCueGuids.Add(Cue.CueGuid);
        for (const FInfinityPassageSettings& Passage : ShowAsset->PassageSettings)
        {
            const int32 FirstIndex = ShowAsset->FindCueIndex(Passage.FirstCueGuid);
            const int32 LastIndex = ShowAsset->FindCueIndex(Passage.LastCueGuid);
            if (FirstIndex != INDEX_NONE && LastIndex != INDEX_NONE
                && Item->CueIndex >= FirstIndex && Item->CueIndex <= LastIndex)
            {
                SelectedPassageGuids.Add(Passage.PassageGuid);
                break;
            }
        }
    }
    if (SelectedCueGuids.IsEmpty())
    {
        return;
    }

    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        return;
    }

    FBox SelectionBounds(EForceInit::ForceInit);
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        AInfinityStagePassageActor* PassageActor = *It;
        if (PassageActor->ShowAsset != ShowAsset.Get()
            || !SelectedPassageGuids.Contains(PassageActor->PassageGuid))
        {
            continue;
        }
        if (bRematerialize && !PassageActor->MaterializePassage())
        {
            UE_LOG(LogTemp, Warning, TEXT("Infinity Stage could not refresh %s after a cue edit."), *PassageActor->GetActorLabel());
            continue;
        }
        for (const FInfinityMaterializedPanelRef& Ref : PassageActor->MaterializedPanels)
        {
            if (!SelectedCueGuids.Contains(Ref.CueGuid) || !Ref.Component
                || Ref.InstanceIndex < 0 || Ref.InstanceIndex >= Ref.Component->GetInstanceCount())
            {
                continue;
            }
            Ref.Component->SelectInstance(true, Ref.InstanceIndex);
            FTransform InstanceWorldTransform;
            if (Ref.Component->GetInstanceTransform(Ref.InstanceIndex, InstanceWorldTransform, true))
            {
                if (const UStaticMesh* Mesh = Ref.Component->GetStaticMesh())
                {
                    SelectionBounds += Mesh->GetBoundingBox().TransformBy(InstanceWorldTransform.ToMatrixWithScale());
                }
                else
                {
                    SelectionBounds += InstanceWorldTransform.GetLocation();
                }
            }
        }
    }

    if (bFrameViewport && SelectionBounds.IsValid)
    {
        SelectionBounds = SelectionBounds.ExpandBy(100.0);
        GEditor->MoveViewportCamerasToBox(SelectionBounds, true, 0.25f);
    }
}

UInfinityStageShowAsset* SInfinityStageCueDesk::FindEditorWorldShowAsset(bool& bOutMultipleShows) const
{
    bOutMultipleShows = false;
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World)
    {
        return nullptr;
    }

    TSet<UInfinityStageShowAsset*> LevelShows;
    for (TActorIterator<AInfinityStageShowRoot> It(World); It; ++It)
    {
        if (It->ShowAsset)
        {
            LevelShows.Add(It->ShowAsset);
        }
    }
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        if (It->ShowAsset)
        {
            LevelShows.Add(It->ShowAsset);
        }
    }

    bOutMultipleShows = LevelShows.Num() > 1;
    return LevelShows.Num() == 1 ? LevelShows.Array()[0] : nullptr;
}

bool SInfinityStageCueDesk::CanUseEditorWorldShowAsset() const
{
    bool bMultipleShows = false;
    UInfinityStageShowAsset* LevelShow = FindEditorWorldShowAsset(bMultipleShows);
    return LevelShow && LevelShow != ShowAsset.Get();
}

void SInfinityStageCueDesk::UseEditorWorldShowAsset()
{
    bool bMultipleShows = false;
    UInfinityStageShowAsset* LevelShow = FindEditorWorldShowAsset(bMultipleShows);
    if (!LevelShow)
    {
        NotifyCueDesk(
            bMultipleShows
                ? TEXT("The current level contains more than one Infinity Stage Show. Choose one explicitly in the Cue Desk asset picker.")
                : TEXT("The current level has no Infinity Stage Show Root or Passage Actor with an assigned Show."),
            SNotificationItem::CS_Fail);
        return;
    }

    StopEditorPreviewPlayback();
    StopMusicScrubPreview();
    ClearEditorWorldInstanceSelection();
    ShowAsset = LevelShow;
    ShowAsset->EnsureStableIds();
    ShowAsset->ReconcilePassageSettings();
    AssetDetails->SetObject(ShowAsset.Get());
    EditorPreviewNormalizedPosition = -1.0;
    EditorPreviewPassageGuid.Invalidate();
    RefreshFromAsset(false);
    NotifyCueDesk(
        FString::Printf(TEXT("Cue Desk now uses the current level Show: %s"), *ShowAsset->GetName()),
        SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::FollowCueSelectionToPlayhead(
    const FCueItem& Item,
    const bool bNotifyOnFailure)
{
    if (!ShowAsset.IsValid() || !Item.IsValid())
    {
        return;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = nullptr;
    FFrameNumber MasterFrame = 0;

    if (Item->NodeType == EInfinityCueListNodeType::PassageHeader)
    {
        Passage = Compiled.Passages.FindByPredicate([Item](const FInfinityCompiledPassage& Candidate)
        {
            return Candidate.PassageGuid == Item->PassageGuid;
        });
        if (!Passage)
        {
            return;
        }
        MasterFrame = Passage->SegmentStartFrame;
    }
    else if (ShowAsset->Cues.IsValidIndex(Item->CueIndex))
    {
        const FInfinityShowCue& Cue = ShowAsset->Cues[Item->CueIndex];
        if (Cue.Type == EInfinityCueType::WingPair)
        {
            for (const FInfinityCompiledPassage& Candidate : Compiled.Passages)
            {
                const FInfinityCompiledWing* Wing = Candidate.Wings.FindByPredicate([&Cue](const FInfinityCompiledWing& Entry)
                {
                    return Entry.CueGuid == Cue.CueGuid;
                });
                if (Wing)
                {
                    Passage = &Candidate;
                    MasterFrame = Wing->PassFrame;
                    break;
                }
            }
        }
        else
        {
            const FInfinityCompiledSegment* Segment = Compiled.Segments.FindByPredicate([&Cue](const FInfinityCompiledSegment& Candidate)
            {
                return Candidate.SegmentGuid == Cue.CueGuid;
            });
            if (Segment)
            {
                MasterFrame = Segment->StartFrame;
            }
        }
    }

    if (Passage)
    {
        EditorPreviewPassageGuid = Passage->PassageGuid;
        const int32 DurationFrames = FMath::Max(
            0,
            Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value);
        EditorPreviewNormalizedPosition = DurationFrames > 0
            ? FMath::Clamp(
                static_cast<double>(MasterFrame.Value - Passage->SegmentStartFrame.Value) / DurationFrames,
                0.0,
                1.0)
            : 0.0;
    }

    EvaluateMasterFrameForPreview(Passage, MasterFrame, bNotifyOnFailure);
}

bool SInfinityStageCueDesk::EvaluateMasterFrameForPreview(
    const FInfinityCompiledPassage* Passage,
    const FFrameNumber MasterFrame,
    const bool bNotifyOnFailure)
{
    // Sequencer follows the same absolute Master frame rather than keeping its
    // own idea of the playhead. Filtered by root sequence, so an unrelated open
    // Sequencer is never moved.
    if (bSyncSequencerPlayhead && ShowAsset.IsValid())
    {
        FInfinityStageSequencerBridge::PushRootFrame(
            ShowAsset->ManagedMasterSequence.LoadSynchronous(),
            FFrameTime(MasterFrame));
    }

    // Row selection and rail scrubbing honour the same visible rehearsal
    // preference as the transport buttons. Previously this path forgot to push
    // the preference, so a selected SEQ could still report UnsafeExternalClock.
    ApplyRehearsalTransportToLivePIE();
    bool bHasPieWorld = false;
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType != EWorldType::PIE || !Context.World())
        {
            continue;
        }
        bHasPieWorld = true;
        for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
        {
            if (It->ShowAsset == ShowAsset.Get() && It->Transport)
            {
                const EInfinityTransportResult Result = It->Transport->ScrubToMasterFrame(MasterFrame);
                if (Result == EInfinityTransportResult::Succeeded)
                {
                    return true;
                }
                if (bNotifyOnFailure)
                {
                    NotifyCueDesk(
                        FString::Printf(
                            TEXT("PIE transport could not move to frame %d (%s)."),
                            MasterFrame.Value,
                            *StaticEnum<EInfinityTransportResult>()->GetDisplayNameTextByValue(
                                static_cast<int64>(Result)).ToString()),
                        SNotificationItem::CS_Fail);
                }
                return false;
            }
        }
    }

    if (bHasPieWorld)
    {
        if (bNotifyOnFailure)
        {
            NotifyCueDesk(
                TEXT("The Cue Desk Show does not match the Show Root running in PIE. Use View > Use Current Level Show, then restart PIE."),
                SNotificationItem::CS_Fail);
        }
        return false;
    }

    if (Passage && EvaluateEditorPassageAtMasterFrame(*Passage, MasterFrame))
    {
        return true;
    }

    if (bNotifyOnFailure && Passage)
    {
        bool bMultipleShows = false;
        UInfinityStageShowAsset* LevelShow = FindEditorWorldShowAsset(bMultipleShows);
        if (LevelShow && LevelShow != ShowAsset.Get())
        {
            NotifyCueDesk(
                FString::Printf(
                    TEXT("Cue Desk uses %s, but the current level uses %s. Choose View > Use Current Level Show."),
                    *ShowAsset->GetName(),
                    *LevelShow->GetName()),
                SNotificationItem::CS_Fail);
        }
        else
        {
            NotifyCueDesk(
                TEXT("No matching materialized Passage camera rig was found in the current editor level."),
                SNotificationItem::CS_Fail);
        }
    }
    return false;
}

void SInfinityStageCueDesk::BeginViewportEdit(const EInfinityWingEditTarget Target)
{
    FinishViewportEdit(false);
    if (!GEditor || !ShowAsset.IsValid() || !CueList.IsValid() || CueList->GetNumItemsSelected() != 1)
    {
        return;
    }
    const int32 CueIndex = GetPrimarySelectedIndex();
    if (!ShowAsset->Cues.IsValidIndex(CueIndex) || ShowAsset->Cues[CueIndex].Type != EInfinityCueType::WingPair)
    {
        return;
    }
    const FGuid CueGuid = ShowAsset->Cues[CueIndex].CueGuid;
    UWorld* World = GEditor->GetEditorWorldContext().World();
    AInfinityStagePassageActor* PassageActor = nullptr;
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        if (It->ShowAsset != ShowAsset.Get())
        {
            continue;
        }
        if (It->MaterializedPanels.ContainsByPredicate([CueGuid](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == CueGuid; }))
        {
            PassageActor = *It;
            break;
        }
    }
    if (!PassageActor)
    {
        return;
    }

    FActorSpawnParameters SpawnParameters;
    SpawnParameters.ObjectFlags = RF_Transient | RF_Transactional;
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AInfinityStageWingEditProxy* Proxy = World->SpawnActor<AInfinityStageWingEditProxy>(
        FVector::ZeroVector,
        FRotator::ZeroRotator,
        SpawnParameters);
    if (!Proxy || !Proxy->InitializeEdit(ShowAsset.Get(), PassageActor, CueGuid, Target))
    {
        if (Proxy)
        {
            Proxy->Destroy();
        }
        return;
    }
    const FString TargetName = StaticEnum<EInfinityWingEditTarget>()->GetDisplayNameTextByValue(
        static_cast<int64>(Target)).ToString();
    Proxy->SetActorLabel(FString::Printf(TEXT("EDIT %s — %s"), *ShowAsset->Cues[CueIndex].Label.ToString(), *TargetName));
    ActiveEditProxy = Proxy;
    GEditor->SelectNone(false, true, false);
    GEditor->SelectActor(Proxy, true, true, true, true);
    GEditor->MoveViewportCamerasToBox(Proxy->GetComponentsBoundingBox(true).ExpandBy(100.0), true, 0.25f);
}

void SInfinityStageCueDesk::FinishViewportEdit(const bool bCancel)
{
    if (AInfinityStageWingEditProxy* Proxy = ActiveEditProxy.Get())
    {
        if (bCancel)
        {
            Proxy->CancelEditing();
        }
        else
        {
            Proxy->FinishEditing();
        }
    }
    ActiveEditProxy.Reset();
}

void SInfinityStageCueDesk::BuildViewportEditMenu(FMenuBuilder& MenuBuilder)
{
    auto AddTarget = [this, &MenuBuilder](const FText& Label, const FText& Tooltip, const EInfinityWingEditTarget Target)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            Tooltip,
            FSlateIcon(),
            FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::BeginViewportEdit, Target)));
    };
    AddTarget(
        NSLOCTEXT("InfinityStage", "EditPairViewport", "Edit Whole Pair"),
        NSLOCTEXT("InfinityStage", "EditPairViewportTip", "Use the standard Level viewport gizmo to offset this complete occurrence."),
        EInfinityWingEditTarget::Pair);
    AddTarget(NSLOCTEXT("InfinityStage", "EditLeftViewport", "Edit Left Panel"), FText::GetEmpty(), EInfinityWingEditTarget::Left);
    AddTarget(NSLOCTEXT("InfinityStage", "EditRightViewport", "Edit Right Panel"), FText::GetEmpty(), EInfinityWingEditTarget::Right);
    AddTarget(NSLOCTEXT("InfinityStage", "EditTopViewport", "Edit Top Panel"), FText::GetEmpty(), EInfinityWingEditTarget::Top);
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "FinishViewportEdit", "Finish Viewport Edit"),
        FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::FinishViewportEdit, false)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "CancelViewportEdit", "Cancel Viewport Edit"),
        FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::FinishViewportEdit, true)));
}

const FInfinityPanelDesign* SInfinityStageCueDesk::GetSelectedPanelDesign(
    const EInfinityWingEditTarget Target) const
{
    if (!ShowAsset.IsValid())
    {
        return nullptr;
    }
    const int32 CueIndex = GetPrimarySelectedIndex();
    if (!ShowAsset->Cues.IsValidIndex(CueIndex)
        || ShowAsset->Cues[CueIndex].Type != EInfinityCueType::WingPair)
    {
        return nullptr;
    }
    const FInfinityWingOccurrence& Wing = ShowAsset->Cues[CueIndex].WingPair;
    switch (Target)
    {
    case EInfinityWingEditTarget::Left: return &Wing.Left;
    case EInfinityWingEditTarget::Right: return &Wing.Right;
    case EInfinityWingEditTarget::Top: return Wing.bHasTop ? &Wing.Top : nullptr;
    default: return nullptr;
    }
}

FInfinityPanelDesign* SInfinityStageCueDesk::GetMutableSelectedPanelDesign(
    const EInfinityWingEditTarget Target)
{
    return const_cast<FInfinityPanelDesign*>(GetSelectedPanelDesign(Target));
}

bool SInfinityStageCueDesk::CanEditSelectedPanelImage(const EInfinityWingEditTarget Target) const
{
    const FInfinityPanelDesign* Panel = GetSelectedPanelDesign(Target);
    return Panel && !Panel->Mesh.IsNull();
}

bool SInfinityStageCueDesk::IsSelectedPanelImageFlipped(const EInfinityWingEditTarget Target) const
{
    const FInfinityPanelDesign* Panel = GetSelectedPanelDesign(Target);
    return Panel && Panel->bFlipImageHorizontally;
}

void SInfinityStageCueDesk::ToggleSelectedPanelImageFlip(const EInfinityWingEditTarget Target)
{
    FInfinityPanelDesign* Panel = GetMutableSelectedPanelDesign(Target);
    if (!Panel || !ShowAsset.IsValid())
    {
        return;
    }
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "TogglePanelImageFlipTransaction", "Flip Infinity Stage Panel Image"));
    ShowAsset->Modify();
    Panel->bFlipImageHorizontally = !Panel->bFlipImageHorizontally;
    ShowAsset->MarkPackageDirty();
    RefreshFromAsset(true);
    RefreshSelectedCuesInEditorWorld(true, false);
}

void SInfinityStageCueDesk::ApplySelectedPanelImageFlipToAllUses(
    const EInfinityWingEditTarget Target)
{
    const FInfinityPanelDesign* SelectedPanel = GetSelectedPanelDesign(Target);
    if (!SelectedPanel || SelectedPanel->Mesh.IsNull() || !ShowAsset.IsValid())
    {
        return;
    }
    const FSoftObjectPath MeshPath = SelectedPanel->Mesh.ToSoftObjectPath();
    const bool bFlipImage = SelectedPanel->bFlipImageHorizontally;
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ApplyPanelImageFlipToAllTransaction", "Apply Panel Image Orientation to All Uses"));
    ShowAsset->Modify();
    const int32 ChangedPanels = ShowAsset->ApplyImageFlipToAllUsesOfMesh(MeshPath, bFlipImage);
    if (ChangedPanels == 0)
    {
        return;
    }
    ShowAsset->MarkPackageDirty();
    RefreshFromAsset(true);
    RefreshAllPassagesInEditorWorld();
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage applied image orientation for %s to %d panel occurrence(s)."),
        *MeshPath.ToString(), ChangedPanels);
}

void SInfinityStageCueDesk::ApplySelectedPanelRelativeTransformToAllUses(
    const EInfinityWingEditTarget Target)
{
    const FInfinityPanelDesign* SelectedPanel = GetSelectedPanelDesign(Target);
    if (!SelectedPanel || SelectedPanel->Mesh.IsNull() || !ShowAsset.IsValid())
    {
        return;
    }
    const FSoftObjectPath MeshPath = SelectedPanel->Mesh.ToSoftObjectPath();
    const FTransform RelativeTransform = SelectedPanel->LocalTransform;
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ApplyPanelRelativeTransformToAllTransaction",
        "Apply Panel Relative Transform to All Uses"));
    ShowAsset->Modify();
    const int32 ChangedPanels = ShowAsset->ApplyRelativeTransformToAllUsesOfMesh(
        MeshPath, RelativeTransform);
    if (ChangedPanels == 0)
    {
        return;
    }
    ShowAsset->MarkPackageDirty();
    RefreshFromAsset(true);
    RefreshAllPassagesInEditorWorld();
    UE_LOG(LogTemp, Display,
        TEXT("Infinity Stage applied relative transform for %s to %d panel occurrence(s)."),
        *MeshPath.ToString(), ChangedPanels);
}

void SInfinityStageCueDesk::AddStageSpotsToSelection()
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const TArray<FGuid> Targets = GetMechanismTargetCueGuids(false);
    if (Targets.IsEmpty())
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "AddStageSpotsTransaction", "Add Infinity Stage Spots"));
    ShowAsset->Modify();

    int32 Added = 0;
    for (FInfinityShowCue& Cue : ShowAsset->Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair || !Targets.Contains(Cue.CueGuid))
        {
            continue;
        }
        // One native spot per physical side. Re-running this action fills only
        // missing panel slots and never accumulates duplicate fixtures.
        struct FSpotSpec
        {
            const TCHAR* Suffix;
            EInfinityAttachmentAnchor Anchor;
        };
        const FSpotSpec Specs[] = {
            { TEXT("Spot L"), EInfinityAttachmentAnchor::LeftPanel },
            { TEXT("Spot R"), EInfinityAttachmentAnchor::RightPanel },
        };
        for (const FSpotSpec& Spec : Specs)
        {
            const bool bAlreadyHasPanelLight = Cue.WingPair.Attachments.ContainsByPredicate(
                [&Spec](const FInfinityCueAttachment& Existing)
                {
                    return Existing.Kind == EInfinityAttachmentKind::Light
                        && Existing.Anchor == Spec.Anchor;
                });
            if (bAlreadyHasPanelLight)
            {
                continue;
            }

            FInfinityCueAttachment& Spot = Cue.WingPair.Attachments.AddDefaulted_GetRef();
            Spot.AttachmentGuid = FGuid::NewGuid();
            Spot.Kind = EInfinityAttachmentKind::Light;
            Spot.Anchor = Spec.Anchor;
            Spot.Lighting.Type = EInfinityStageLightType::Spot;
            Spot.Label = FText::FromString(FString::Printf(
                TEXT("%s %s"), *Cue.Label.ToString(), Spec.Suffix));
            // Above the panel, angled down into the opening. A starting point to
            // drag from, not a prescription.
            Spot.RelativeTransform.SetTranslation(FVector(0.0, 0.0, 900.0));
            Spot.RelativeTransform.SetRotation(FRotator(-55.0, 0.0, 0.0).Quaternion());
            ++Added;
        }
    }

    RefreshFromAsset();
    NotifyCueDesk(
        Added > 0
            ? FString::Printf(
                TEXT("Added %d native spot attachment(s) to %d Wing Pair(s). Adjust type and parameters in Stage, then materialize the selected Passage."),
                Added,
                Targets.Num())
            : TEXT("Every selected Wing Pair already has Left and Right panel lights."),
        SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::ReplicateStageLightingToSelection()
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const TArray<FGuid> Targets = GetMechanismTargetCueGuids(false);
    if (Targets.Num() < 2)
    {
        NotifyCueDesk(TEXT("Select at least two Wing Pairs; the earliest selected pair is the lighting template."),
            SNotificationItem::CS_Fail);
        return;
    }

    const int32 SourceIndex = ShowAsset->FindCueIndex(Targets[0]);
    if (!ShowAsset->Cues.IsValidIndex(SourceIndex))
    {
        return;
    }
    const FInfinityShowCue& SourceCue = ShowAsset->Cues[SourceIndex];
    int32 SourceLightCount = 0;
    for (const FInfinityCueAttachment& Attachment : SourceCue.WingPair.Attachments)
    {
        SourceLightCount += Attachment.Kind == EInfinityAttachmentKind::Light ? 1 : 0;
    }
    const FText SourceLabel = SourceCue.Label;
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ReplicateStageLightingTransaction", "Replicate Infinity Stage Lighting"));
    ShowAsset->Modify();
    const int32 ChangedTargets = ShowAsset->ReplicateLightAttachments(Targets[0], Targets);
    RefreshFromAsset();

    NotifyCueDesk(
        SourceLightCount == 0
            ? FString::Printf(
                TEXT("Removed replicated lights from %d selected Wing Pair(s), matching empty template %s. Materialize the selected Passage to preview the result."),
                ChangedTargets,
                *SourceLabel.ToString())
            : FString::Printf(
                TEXT("Copied %d light(s) from %s to %d selected Wing Pair(s). Materialize the selected Passage to preview them."),
                SourceLightCount,
                *SourceLabel.ToString(),
                ChangedTargets),
        SNotificationItem::CS_Success);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("INFINITY_STAGE_LIGHT_REPLICATION_OK source='%s' targets=%d lights_per_target=%d"),
        *SourceLabel.ToString(),
        ChangedTargets,
        SourceLightCount);
}

void SInfinityStageCueDesk::ReplicateStageLighting(const int32 Scope, const bool bWithVariation)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    // Scope 0: selection (earliest selected pair is the template).
    // Scope 1: the template's own Passage. Scope 2: every Wing Pair in the Show.
    const TArray<FGuid> Selected = GetMechanismTargetCueGuids(false);
    if (Selected.IsEmpty())
    {
        NotifyCueDesk(TEXT("Select the tuned Wing Pair first; it is the lighting template."), SNotificationItem::CS_Fail);
        return;
    }
    const FGuid Source = Selected[0];
    // The Passage is resolved from the template cue itself, never from the desk's remembered
    // passage-header selection, so the action always stays inside the tuned pair's Passage.
    const FGuid SourcePassageGuid = ShowAsset->FindPassageGuidForCue(Source);
    TArray<FGuid> Targets = Scope == 0 ? Selected
        : Scope == 1 ? ShowAsset->GetWingPairCueGuidsInPassage(SourcePassageGuid)
        : ShowAsset->GetAllWingPairCueGuids();
    Targets.Remove(Source);
    if (Targets.IsEmpty())
    {
        NotifyCueDesk(Scope == 1
            ? TEXT("The template Wing Pair's Passage has no other Wing Pairs to replicate to.")
            : TEXT("No other Wing Pairs to replicate to."), SNotificationItem::CS_Fail);
        return;
    }
    TSet<FGuid> AffectedPassageGuids;
    AffectedPassageGuids.Add(SourcePassageGuid);
    for (const FGuid& Target : Targets)
    {
        AffectedPassageGuids.Add(ShowAsset->FindPassageGuidForCue(Target));
    }
    AffectedPassageGuids.Remove(FGuid());
    const FInfinityPassageSettings* SourcePassage = ShowAsset->PassageSettings.FindByPredicate(
        [SourcePassageGuid](const FInfinityPassageSettings& Passage)
        {
            return Passage.PassageGuid == SourcePassageGuid;
        });
    const FString SourcePassageLabel = SourcePassage ? SourcePassage->Label.ToString() : TEXT("(no Passage)");
    const int32 SourceIndex = ShowAsset->FindCueIndex(Source);
    if (!ShowAsset->Cues.IsValidIndex(SourceIndex))
    {
        return;
    }
    int32 SourceLightCount = 0;
    for (const FInfinityCueAttachment& Attachment : ShowAsset->Cues[SourceIndex].WingPair.Attachments)
    {
        SourceLightCount += Attachment.Kind == EInfinityAttachmentKind::Light ? 1 : 0;
    }
    const FText SourceLabel = ShowAsset->Cues[SourceIndex].Label;

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ReplicateStageLightingScopedTransaction", "Replicate Infinity Stage Lighting"));
    ShowAsset->Modify();
    const int32 Changed = bWithVariation
        ? ShowAsset->ReplicateLightAttachmentsWithVariation(Source, Targets, FInfinityLightReplicationVariation())
        : ShowAsset->ReplicateLightAttachments(Source, Targets);
    RefreshFromAsset();
    // Replication can reach beyond the selection, so rematerialize every Passage
    // that received lights (and only those), then resync the selected cues.
    RefreshPassagesInEditorWorld(AffectedPassageGuids);
    RefreshSelectedCuesInEditorWorld(false, false);

    NotifyCueDesk(
        SourceLightCount == 0
            ? FString::Printf(
                TEXT("Removed replicated lights from %d other Wing Pair(s) in %s, matching empty template %s, and rematerialized. Save the Show and level intentionally."),
                Changed,
                Scope == 0 ? TEXT("the selection") : Scope == 1 ? *SourcePassageLabel : TEXT("the entire Show"),
                *SourceLabel.ToString())
            : FString::Printf(
                TEXT("Copied %d light(s) from %s to %d other Wing Pair(s) in %s%s and rematerialized. Save the Show and level intentionally."),
                SourceLightCount,
                *SourceLabel.ToString(),
                Changed,
                Scope == 0 ? TEXT("the selection") : Scope == 1 ? *SourcePassageLabel : TEXT("the entire Show"),
                bWithVariation ? TEXT(" with variation") : TEXT("")),
        SNotificationItem::CS_Success);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("INFINITY_STAGE_LIGHT_REPLICATION_OK source='%s' scope=%d variation=%d targets=%d lights_per_target=%d passage='%s' passages_rematerialized=%d"),
        *SourceLabel.ToString(),
        Scope,
        bWithVariation ? 1 : 0,
        Changed,
        SourceLightCount,
        *SourcePassageLabel,
        AffectedPassageGuids.Num());
}

void SInfinityStageCueDesk::MaterializeSelectedPassages()
{
    // Materializing is the step that re-places wings and cue-anchored content
    // after any structural change, so it belongs where the structure is edited
    // rather than only on the Passage Actor's Details panel.
    RefreshSelectedCuesInEditorWorld(true, false);
    NotifyCueDesk(
        TEXT("Materialized the selected Passage. The level is dirty; save it intentionally."),
        SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::RefreshAllPassagesInEditorWorld()
{
    if (!GEditor || !ShowAsset.IsValid())
    {
        return;
    }
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        return;
    }
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        if (It->ShowAsset == ShowAsset.Get() && !It->MaterializePassage())
        {
            UE_LOG(LogTemp, Warning, TEXT("Infinity Stage could not rematerialize %s after an authoring change."),
                *It->GetActorLabel());
        }
    }
    RefreshSelectedCuesInEditorWorld(false, false);
}

void SInfinityStageCueDesk::RefreshPassagesInEditorWorld(const TSet<FGuid>& PassageGuids)
{
    if (!GEditor || !ShowAsset.IsValid() || PassageGuids.IsEmpty())
    {
        return;
    }
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        return;
    }
    for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
    {
        if (It->ShowAsset == ShowAsset.Get() && PassageGuids.Contains(It->PassageGuid)
            && !It->MaterializePassage())
        {
            UE_LOG(LogTemp, Warning, TEXT("Infinity Stage could not rematerialize %s after an authoring change."),
                *It->GetActorLabel());
        }
    }
}

void SInfinityStageCueDesk::BuildImageOrientationMenu(FMenuBuilder& MenuBuilder)
{
    const auto AddFlipEntry = [this, &MenuBuilder](
        const FText& Label,
        const EInfinityWingEditTarget Target)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            NSLOCTEXT("InfinityStage", "FlipImageThisOccurrenceTip",
                "Mirror the photograph only for this panel occurrence. The source mesh and texture are not modified."),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ToggleSelectedPanelImageFlip, Target),
                FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::CanEditSelectedPanelImage, Target),
                FIsActionChecked::CreateSP(this, &SInfinityStageCueDesk::IsSelectedPanelImageFlipped, Target)),
            NAME_None,
            EUserInterfaceActionType::ToggleButton);
    };
    AddFlipEntry(NSLOCTEXT("InfinityStage", "FlipLeftImageThis", "Flip Left Image — This Occurrence"),
        EInfinityWingEditTarget::Left);
    AddFlipEntry(NSLOCTEXT("InfinityStage", "FlipRightImageThis", "Flip Right Image — This Occurrence"),
        EInfinityWingEditTarget::Right);
    AddFlipEntry(NSLOCTEXT("InfinityStage", "FlipTopImageThis", "Flip Top Image — This Occurrence"),
        EInfinityWingEditTarget::Top);

    MenuBuilder.AddSeparator();
    const auto AddAllUsesEntry = [this, &MenuBuilder](
        const FText& Label,
        const EInfinityWingEditTarget Target)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            NSLOCTEXT("InfinityStage", "ApplyImageStateAllUsesTip",
                "Copy this panel's checked or unchecked Flip Image Horizontally state to every Left, Right or Top occurrence using the same mesh."),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ApplySelectedPanelImageFlipToAllUses, Target),
                FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::CanEditSelectedPanelImage, Target)));
    };
    AddAllUsesEntry(NSLOCTEXT("InfinityStage", "ApplyLeftImageAllUses", "Apply Left Image State to Every Use of This Mesh"),
        EInfinityWingEditTarget::Left);
    AddAllUsesEntry(NSLOCTEXT("InfinityStage", "ApplyRightImageAllUses", "Apply Right Image State to Every Use of This Mesh"),
        EInfinityWingEditTarget::Right);
    AddAllUsesEntry(NSLOCTEXT("InfinityStage", "ApplyTopImageAllUses", "Apply Top Image State to Every Use of This Mesh"),
        EInfinityWingEditTarget::Top);
}

void SInfinityStageCueDesk::BuildRelativeTransformMenu(FMenuBuilder& MenuBuilder)
{
    const auto AddAllUsesEntry = [this, &MenuBuilder](
        const FText& Label,
        const EInfinityWingEditTarget Target)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            NSLOCTEXT("InfinityStage", "ApplyRelativeTransformAllUsesTip",
                "Copy this panel occurrence's complete Relative Transform (location, rotation and scale) to every Left, Right or Top occurrence using the same mesh."),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(
                    this, &SInfinityStageCueDesk::ApplySelectedPanelRelativeTransformToAllUses, Target),
                FCanExecuteAction::CreateSP(
                    this, &SInfinityStageCueDesk::CanEditSelectedPanelImage, Target)));
    };
    AddAllUsesEntry(
        NSLOCTEXT("InfinityStage", "ApplyLeftTransformAllUses",
            "Apply Left Relative Transform to Every Use of This Mesh"),
        EInfinityWingEditTarget::Left);
    AddAllUsesEntry(
        NSLOCTEXT("InfinityStage", "ApplyRightTransformAllUses",
            "Apply Right Relative Transform to Every Use of This Mesh"),
        EInfinityWingEditTarget::Right);
    AddAllUsesEntry(
        NSLOCTEXT("InfinityStage", "ApplyTopTransformAllUses",
            "Apply Top Relative Transform to Every Use of This Mesh"),
        EInfinityWingEditTarget::Top);
}

TArray<FGuid> SInfinityStageCueDesk::GetMechanismTargetCueGuids(const bool bWholePassage) const
{
    TArray<FGuid> Result;
    if (!ShowAsset.IsValid())
    {
        return Result;
    }

    if (bWholePassage)
    {
        const int32 SelectedIndex = GetPrimarySelectedIndex();
        if (!ShowAsset->Cues.IsValidIndex(SelectedIndex)
            || ShowAsset->Cues[SelectedIndex].Type != EInfinityCueType::WingPair)
        {
            return Result;
        }
        // The selected cue's own Passage, not the desk's remembered passage-header
        // selection, which can be stale after navigation or a rename.
        return ShowAsset->GetWingPairCueGuidsInPassage(
            ShowAsset->FindPassageGuidForCue(ShowAsset->Cues[SelectedIndex].CueGuid));
    }

    if (!CueList.IsValid())
    {
        return Result;
    }
    TArray<FCueItem> SelectedItems = CueList->GetSelectedItems();
    SelectedItems.Sort([](const FCueItem& A, const FCueItem& B)
    {
        return A.IsValid() && B.IsValid() ? A->CueIndex < B->CueIndex : A.IsValid();
    });
    for (const FCueItem& Item : SelectedItems)
    {
        if (Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::Cue
            && ShowAsset->Cues.IsValidIndex(Item->CueIndex)
            && ShowAsset->Cues[Item->CueIndex].Type == EInfinityCueType::WingPair)
        {
            Result.AddUnique(ShowAsset->Cues[Item->CueIndex].CueGuid);
        }
    }
    return Result;
}

bool SInfinityStageCueDesk::HasMechanismTargets(const bool bWholePassage) const
{
    return !GetMechanismTargetCueGuids(bWholePassage).IsEmpty();
}

void SInfinityStageCueDesk::ApplyUndulationPreset(
    const bool bWholePassage,
    const double PhaseStepCycles)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const TArray<FGuid> TargetGuids = GetMechanismTargetCueGuids(bWholePassage);
    if (TargetGuids.IsEmpty())
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ApplyUndulationTransaction", "Apply Infinity Stage Wing Undulation"));
    ShowAsset->Modify();
    const int32 ChangedCues = ShowAsset->ApplyTravelingUndulation(
        TargetGuids,
        0.18,  // one gentle breath every 5.56 seconds
        75.0,  // each side moves 75 cm inward at the crest
        PhaseStepCycles,
        bWholePassage);
    if (ChangedCues == 0)
    {
        return;
    }
    ShowAsset->MarkPackageDirty();
    RefreshFromAsset(true);
    RefreshSelectedCuesInEditorWorld(false, false);
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage applied a smooth undulation to %d Wing Pair cue(s)."), ChangedCues);
}

void SInfinityStageCueDesk::ApplyCameraGustPreset(
    const bool bWholePassage,
    const int32 Preset)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const TArray<FGuid> TargetGuids = GetMechanismTargetCueGuids(bWholePassage);
    if (TargetGuids.IsEmpty())
    {
        return;
    }

    FInfinityCameraGustSettings Settings;
    if (Preset == 0) // Tight Snap
    {
        Settings.FanDepthPairs = 3;
        Settings.OpeningSpanPairs = 0.10;
    }
    else if (Preset == 2) // Broad Gust
    {
        Settings.FanDepthPairs = 10;
        Settings.OpeningSpanPairs = 0.75;
    }
    else if (Preset == 3) // Custom: reuse the primary occurrence's visible fields.
    {
        const int32 PrimaryIndex = GetPrimarySelectedIndex();
        if (ShowAsset->Cues.IsValidIndex(PrimaryIndex)
            && ShowAsset->Cues[PrimaryIndex].Type == EInfinityCueType::WingPair
            && ShowAsset->Cues[PrimaryIndex].WingPair.Mechanism.PlaybackMode == EInfinityMotionPlaybackMode::CameraGust)
        {
            Settings = ShowAsset->Cues[PrimaryIndex].WingPair.Mechanism.CameraGust;
        }
    }
    // Preset 1 and a Custom operation without an existing gust intentionally use
    // the camera-led defaults declared by FInfinityCameraGustSettings.

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ApplyCameraGustTransaction", "Apply Infinity Stage Camera Gust Fan Reveal"));
    ShowAsset->Modify();
    const int32 ChangedCues = ShowAsset->ApplyCameraGust(TargetGuids, Settings, bWholePassage);
    if (ChangedCues == 0)
    {
        return;
    }
    ShowAsset->MarkPackageDirty();
    RefreshFromAsset(true);
    RefreshSelectedCuesInEditorWorld(false, false);
}

void SInfinityStageCueDesk::BuildCameraGustPresetMenu(
    FMenuBuilder& MenuBuilder,
    const bool bWholePassage)
{
    const FCanExecuteAction CanApply = FCanExecuteAction::CreateSP(
        this, &SInfinityStageCueDesk::HasMechanismTargets, bWholePassage);
    const auto AddPreset = [this, &MenuBuilder, bWholePassage, CanApply](
        const FText& Label,
        const FText& Tooltip,
        const int32 Preset)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            Tooltip,
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(
                    this, &SInfinityStageCueDesk::ApplyCameraGustPreset, bWholePassage, Preset),
                CanApply));
    };
    AddPreset(
        NSLOCTEXT("InfinityStage", "CameraGustTightSnap", "Tight Snap"),
        NSLOCTEXT("InfinityStage", "CameraGustTightSnapTip",
            "Keep three pairs revealed ahead of the camera with a very crisp 0.10-pair opening edge."),
        0);
    AddPreset(
        NSLOCTEXT("InfinityStage", "CameraGustOneSecond", "Camera-led Reveal (Default)"),
        NSLOCTEXT("InfinityStage", "CameraGustOneSecondTip",
            "Keep six pairs revealed ahead. Wing motion follows the evaluated music-driven camera position, with a 0.25-pair opening edge."),
        1);
    AddPreset(
        NSLOCTEXT("InfinityStage", "CameraGustBroad", "Broad Gust"),
        NSLOCTEXT("InfinityStage", "CameraGustBroadTip",
            "Keep ten pairs revealed ahead with a broad 0.75-pair opening edge."),
        2);
    MenuBuilder.AddSeparator();
    AddPreset(
        NSLOCTEXT("InfinityStage", "CameraGustCustom", "Custom / Reapply Current Settings"),
        NSLOCTEXT("InfinityStage", "CameraGustCustomTip",
            "Use the primary Wing Pair's visible reveal settings for the ordered selection or whole Passage. If it has no reveal yet, start from the camera-led defaults."),
        3);
}

void SInfinityStageCueDesk::SetSelectedMechanismsStatic(const bool bWholePassage)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const TArray<FGuid> TargetGuids = GetMechanismTargetCueGuids(bWholePassage);
    if (TargetGuids.IsEmpty())
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "HoldMechanismsStaticTransaction", "Hold Infinity Stage Wings Static"));
    ShowAsset->Modify();
    const int32 ChangedCues = ShowAsset->SetMechanismsStatic(TargetGuids);
    if (ChangedCues == 0)
    {
        return;
    }
    ShowAsset->MarkPackageDirty();
    RefreshFromAsset(true);
    RefreshSelectedCuesInEditorWorld(false, false);
}

void SInfinityStageCueDesk::BuildWingMovementScopeMenu(
    FMenuBuilder& MenuBuilder,
    const bool bWholePassage)
{
    const FCanExecuteAction CanApply = FCanExecuteAction::CreateSP(
        this, &SInfinityStageCueDesk::HasMechanismTargets, bWholePassage);
    const auto AddWave = [this, &MenuBuilder, bWholePassage, CanApply](
        const FText& Label,
        const FText& Tooltip,
        const double PhaseStepCycles)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            Tooltip,
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(
                    this, &SInfinityStageCueDesk::ApplyUndulationPreset, bWholePassage, PhaseStepCycles),
                CanApply));
    };
    AddWave(
        NSLOCTEXT("InfinityStage", "GentleWaveAlongPassage", "Gentle Wave Along Passage"),
        NSLOCTEXT("InfinityStage", "GentleWaveAlongPassageTip",
            "Apply a smooth 5.56-second in/out loop with successive pairs delayed so the crest travels in the camera's forward direction. Whole-Passage mode stays live when rows are reordered."),
        -0.10);
    AddWave(
        NSLOCTEXT("InfinityStage", "GentleWaveTowardCamera", "Gentle Wave Toward Camera"),
        NSLOCTEXT("InfinityStage", "GentleWaveTowardCameraTip",
            "Apply the same smooth loop with the phase order reversed, so the crest travels back toward the camera. Whole-Passage mode stays live when rows are reordered."),
        0.10);
    AddWave(
        NSLOCTEXT("InfinityStage", "GentleBreatheTogether", "Breathe Together"),
        NSLOCTEXT("InfinityStage", "GentleBreatheTogetherTip",
            "Apply the same smooth in/out loop to every target with no phase delay between pairs."),
        0.0);
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "PhasedBreathe", "Phased Breathe"),
        NSLOCTEXT("InfinityStage", "PhasedBreatheTip",
            "Repeat the same breathing gesture across consecutive pairs in two, three or four evenly spaced phases."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildPhasedBreathePresetMenu, bWholePassage));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "CameraGustFanReveal", "Camera Gust / Fan Reveal"),
        NSLOCTEXT("InfinityStage", "CameraGustFanRevealTip",
            "Reveal a fixed number of closed pairs ahead of the evaluated camera. The music rail drives camera travel, so the wing opening pace follows automatically."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildCameraGustPresetMenu, bWholePassage));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "HoldWingMovementStatic", "Hold Static"),
        NSLOCTEXT("InfinityStage", "HoldWingMovementStaticTip",
            "Stop at the authored phase without deleting the motion curves, rate or travel settings."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(
                this, &SInfinityStageCueDesk::SetSelectedMechanismsStatic, bWholePassage),
            CanApply));
}

void SInfinityStageCueDesk::BuildPhasedBreathePresetMenu(
    FMenuBuilder& MenuBuilder,
    const bool bWholePassage)
{
    const FCanExecuteAction CanApply = FCanExecuteAction::CreateSP(
        this, &SInfinityStageCueDesk::HasMechanismTargets, bWholePassage);
    const auto AddPhasePreset = [this, &MenuBuilder, bWholePassage, CanApply](
        const FText& Label,
        const FText& Tooltip,
        const int32 PhaseCount)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            Tooltip,
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(
                    this,
                    &SInfinityStageCueDesk::ApplyUndulationPreset,
                    bWholePassage,
                    1.0 / static_cast<double>(PhaseCount)),
                CanApply));
    };

    AddPhasePreset(
        NSLOCTEXT("InfinityStage", "PhasedBreatheTwo", "2 Phases — Alternate"),
        NSLOCTEXT("InfinityStage", "PhasedBreatheTwoTip",
            "Repeat 1–2 across consecutive pairs. When one pair is fully inward, the next is fully outward, and they swap every half-cycle."),
        2);
    AddPhasePreset(
        NSLOCTEXT("InfinityStage", "PhasedBreatheThree", "3 Phases — 1–2–3"),
        NSLOCTEXT("InfinityStage", "PhasedBreatheThreeTip",
            "Repeat three evenly spaced breathing phases across consecutive pairs: 1–2–3, then 1–2–3 again."),
        3);
    AddPhasePreset(
        NSLOCTEXT("InfinityStage", "PhasedBreatheFour", "4 Phases — 1–2–3–4"),
        NSLOCTEXT("InfinityStage", "PhasedBreatheFourTip",
            "Repeat four evenly spaced breathing phases across consecutive pairs: 1–2–3–4, then begin again."),
        4);
}

void SInfinityStageCueDesk::BuildWingMovementMenu(FMenuBuilder& MenuBuilder)
{
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "WingMovementSelection", "Selected Wing Pairs"),
        NSLOCTEXT("InfinityStage", "WingMovementSelectionTip",
            "Apply a preset only to Wing Pair rows in the current multi-selection; Scene and Sequence rows are ignored."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildWingMovementScopeMenu, false));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "WingMovementPassage", "Whole Current Passage"),
        NSLOCTEXT("InfinityStage", "WingMovementPassageTip",
            "Apply a preset to every Wing Pair in the Passage containing the primary selection."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildWingMovementScopeMenu, true));
}

void SInfinityStageCueDesk::BuildSceneHandoffMenu(FMenuBuilder& MenuBuilder)
{
    const auto CanMatchSelected = [this]()
    {
        const int32 Index = GetPrimarySelectedIndex();
        return ShowAsset.IsValid() && ShowAsset->Cues.IsValidIndex(Index)
            && ShowAsset->Cues[Index].Type == EInfinityCueType::Scene;
    };
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "MatchSelectedSceneHandoff", "Match Selected Scene"),
        NSLOCTEXT("InfinityStage", "MatchSelectedSceneHandoffTip",
            "Match the first Scene camera to the incoming Passage endpoint. A normal final camera matches the outgoing Passage; when the next cue retains camera, it holds the final designed Scene shot. Missing boundary cameras/cuts are provisioned and internal artist cuts are preserved."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::MatchSceneCameraHandoffs, false),
            FCanExecuteAction::CreateLambda(CanMatchSelected)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "MatchAllSceneHandoffs", "Match All Scenes"),
        NSLOCTEXT("InfinityStage", "MatchAllSceneHandoffsTip",
            "Refresh every Scene boundary in the current Show, including retained-camera post-scene interstitials."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::MatchSceneCameraHandoffs, true)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "CheckSceneHandoffs", "Check All Scenes (read-only)"),
        NSLOCTEXT(
            "InfinityStage",
            "CheckSceneHandoffsTip",
            "Compare every Scene's handoff cameras against the current evaluated Passage endpoints and report any that no longer match. "
            "Handoff cameras are a snapshot, so changing a Passage route or camera curve — a focal length key especially — leaves them stale "
            "and produces a jump at the boundary. This writes nothing."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::CheckSceneCameraHandoffs)));
}

void SInfinityStageCueDesk::CheckSceneCameraHandoffs()
{
    if (!ShowAsset.IsValid() || !GEditor)
    {
        return;
    }
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        return;
    }
    TArray<FGuid> StaleScenes;
    FString Report;
    const bool bChecked = FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(
        *ShowAsset.Get(), *World, TArray<FGuid>(), StaleScenes, Report);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("INFINITY_STAGE_HANDOFF_CHECK ok=%d stale=%d report=%s"),
        bChecked ? 1 : 0,
        StaleScenes.Num(),
        *Report);
    NotifyCueDesk(
        Report,
        (bChecked && StaleScenes.IsEmpty()) ? SNotificationItem::CS_Success : SNotificationItem::CS_Fail);
}

void SInfinityStageCueDesk::MatchSceneCameraHandoffs(const bool bAllScenes)
{
    if (!ShowAsset.IsValid() || !GEditor)
    {
        return;
    }
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World)
    {
        return;
    }
    TArray<FGuid> Targets;
    if (!bAllScenes)
    {
        const int32 Index = GetPrimarySelectedIndex();
        if (!ShowAsset->Cues.IsValidIndex(Index) || ShowAsset->Cues[Index].Type != EInfinityCueType::Scene)
        {
            return;
        }
        Targets.Add(ShowAsset->Cues[Index].CueGuid);
    }
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "MatchSceneHandoffsTransaction", "Match Infinity Stage Scene Camera Handoffs"));
    FString Report;
    if (!FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(
        *ShowAsset.Get(), *World, Targets, Report))
    {
        UE_LOG(LogTemp, Error, TEXT("Infinity Stage camera handoff: %s"), *Report);
        return;
    }
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage camera handoff: %s"), *Report);
    Invalidate(EInvalidateWidgetReason::Paint);
}

bool SInfinityStageCueDesk::CanOpenSelectedSceneSequence() const
{
    if (!ShowAsset.IsValid())
    {
        return false;
    }
    const int32 CueIndex = GetPrimarySelectedIndex();
    return ShowAsset->Cues.IsValidIndex(CueIndex)
        && ShowAsset->Cues[CueIndex].Type != EInfinityCueType::WingPair
        && !ShowAsset->Cues[CueIndex].Scene.Sequence.IsNull();
}

void SInfinityStageCueDesk::OpenSelectedSceneSequence()
{
    if (!CanOpenSelectedSceneSequence() || !GEditor)
    {
        return;
    }
    const int32 CueIndex = GetPrimarySelectedIndex();
    if (ULevelSequence* Sequence = ShowAsset->Cues[CueIndex].Scene.Sequence.LoadSynchronous())
    {
        GEditor->GetEditorSubsystem<UAssetEditorSubsystem>()->OpenEditorForAsset(Sequence);
    }
}

TSharedPtr<SWidget> SInfinityStageCueDesk::BuildCueContextMenu()
{
    return BuildActionsMenu();
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildAddMenu()
{
    FMenuBuilder MenuBuilder(true, nullptr);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "AddWingPair", "Wing Pair"),
        NSLOCTEXT("InfinityStage", "AddWingPairTooltip", "Insert a finite Wing Pair occurrence."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::AddCue, EInfinityCueType::WingPair)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "AddScene", "Scene"),
        NSLOCTEXT("InfinityStage", "AddSceneTooltip", "Insert a Scene handoff cue."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::AddCue, EInfinityCueType::Scene)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "AddSequence", "Sequence"),
        NSLOCTEXT("InfinityStage", "AddSequenceTooltip", "Insert an authored sequence cue."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::AddCue, EInfinityCueType::Sequence)));
    return MenuBuilder.MakeWidget();
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildViewMenu()
{
    FMenuBuilder MenuBuilder(true, nullptr);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "NestedCueMode", "Nested Passage View"),
        NSLOCTEXT("InfinityStage", "NestedCueModeTip", "Show Wing Pair rows nested below their derived Passage Sections."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetNestedCueMode, true),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bNestedCueMode; })),
        NAME_None,
        EUserInterfaceActionType::RadioButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "FlatCueMode", "Flat Cue View"),
        NSLOCTEXT("InfinityStage", "FlatCueModeTip", "Show only the authoritative chronological Cue rows."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetNestedCueMode, false),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return !bNestedCueMode; })),
        NAME_None,
        EUserInterfaceActionType::RadioButton);
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "UseEditorWorldShow", "Use Current Level Show"),
        NSLOCTEXT(
            "InfinityStage",
            "UseEditorWorldShowTip",
            "Switch the Cue Desk to the single Show Asset referenced by the current level's Show Root and Passage Actors."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::UseEditorWorldShowAsset),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::CanUseEditorWorldShowAsset)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "FollowMusicScrub", "Follow Music Scrub in Level Viewport"),
        NSLOCTEXT("InfinityStage", "FollowMusicScrubTip", "Move the editor viewport with the Passage camera while dragging the Music timeline."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]() { SetMusicScrubCameraFollow(!bFollowMusicScrubInViewport); }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bFollowMusicScrubInViewport; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "AudibleMusicScrub", "Audible Music Scrub"),
        NSLOCTEXT("InfinityStage", "AudibleMusicScrubTip",
            "Audition the selected Passage music at its exact source position while dragging the Music Timeline. Audio stops when the drag ends."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bAudibleMusicScrub = !bAudibleMusicScrub;
                if (!bAudibleMusicScrub)
                {
                    StopMusicScrubPreview();
                }
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bAudibleMusicScrub; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "LiveCameraOwner", "Live Camera Owner"),
        NSLOCTEXT(
            "InfinityStage",
            "LiveCameraOwnerTip",
            "Override who drives the camera in a running PIE session, without editing the Show. Authored per-Passage and "
            "per-Scene ownership resumes when set back to Follow Show."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildLiveCameraOwnerMenu));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "PieStartsAtPlayhead", "PIE Starts At Playhead"),
        NSLOCTEXT(
            "InfinityStage",
            "PieStartsAtPlayheadTip",
            "Begin Play In Editor at the Cue Desk playhead instead of the start of the Show, so a Passage or Scene can be "
            "rehearsed without scrubbing back to it every time. Turn off for a full run-through from the top."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bPieStartsAtPlayhead = !bPieStartsAtPlayhead;
                GConfig->SetBool(
                    TEXT("InfinityStage.CueDesk"),
                    TEXT("PieStartsAtPlayhead"),
                    bPieStartsAtPlayhead,
                    GEditorPerProjectIni);
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bPieStartsAtPlayhead; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SyncSequencerPlayhead", "Sync Sequencer Playhead"),
        NSLOCTEXT(
            "InfinityStage",
            "SyncSequencerPlayheadTip",
            "Move any open Sequencer showing this Show's managed Master to the Cue Desk playhead. PIE already follows the same "
            "absolute Master frame, so this brings the third view into line. Sequencers with a different sequence open are untouched."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bSyncSequencerPlayhead = !bSyncSequencerPlayhead;
                GConfig->SetBool(
                    TEXT("InfinityStage.CueDesk"),
                    TEXT("SyncSequencerPlayhead"),
                    bSyncSequencerPlayhead,
                    GEditorPerProjectIni);
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bSyncSequencerPlayhead; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "PlayThroughBoundaries", "Play Through Boundaries"),
        NSLOCTEXT(
            "InfinityStage",
            "PlayThroughBoundariesTip",
            "Forward play runs continuously to the end of the Show, bypassing operator holds. "
            "When disabled, the Show Root's automatic Scene playback setting can continue a Passage into its Scene, then hold."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bPlayThroughBoundaries = !bPlayThroughBoundaries;
                GConfig->SetBool(
                    TEXT("InfinityStage.CueDesk"),
                    TEXT("PlayThroughBoundaries"),
                    bPlayThroughBoundaries,
                    GEditorPerProjectIni);
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bPlayThroughBoundaries; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "RehearsalTransport", "Rehearsal Transport (ignore external sound locks)"),
        NSLOCTEXT(
            "InfinityStage",
            "RehearsalTransportTip",
            "Allow seek, reverse and hold while the playhead sits inside a Scene that declares externally controlled sound. "
            "Performance mode refuses those moves so a live show cannot desynchronize from an external clock; rehearsal "
            "deliberately ignores that. Applies to every running PIE Show Root for this Show."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ToggleRehearsalTransport),
            FCanExecuteAction(),
            FIsActionChecked::CreateSP(this, &SInfinityStageCueDesk::IsRehearsalTransportEnabled)),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ShowMusicWorkspace", "Show Music Timeline Workspace"),
        NSLOCTEXT(
            "InfinityStage",
            "ShowMusicWorkspaceTip",
            "Show or completely collapse the resizable horizontal waveform, transport and camera-curve workspace."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bMusicWorkspaceVisible = !bMusicWorkspaceVisible;
                SaveLayoutConfig();
                Invalidate(EInvalidateWidgetReason::Layout);
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bMusicWorkspaceVisible; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SnapMusicMarkers", "Snap Scrub to Music Markers"),
        NSLOCTEXT(
            "InfinityStage",
            "SnapMusicMarkersTip",
            "Snap within twelve pixels of non-rejected beat, onset and major-change proposals. Hold Option while dragging to bypass snapping."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bSnapMusicScrubToMarkers = !bSnapMusicScrubToMarkers;
                SaveLayoutConfig();
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bSnapMusicScrubToMarkers; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddSeparator();
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "EditorLightingSubmenu", "Editor Lighting"),
        NSLOCTEXT(
            "InfinityStage",
            "EditorLightingSubmenuTip",
            "Choose a stable working light for level editing, or deliberately follow the Master time of day while scrubbing. PIE and renders always follow the Master."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildEditorLightingMenu));
    return MenuBuilder.MakeWidget();
}

void SInfinityStageCueDesk::BuildEditorLightingMenu(FMenuBuilder& MenuBuilder)
{
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "EditorLightingManual", "Manual Editing Light"),
        NSLOCTEXT(
            "InfinityStage",
            "EditorLightingManualTip",
            "Protect the editor viewport from timeline day/night evaluation and use the Celestial Rig's Editor Preview Time. This does not affect PIE or rendering."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetEditorLightingFollowMaster, false),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return !IsEditorLightingFollowingMaster(); })),
        NAME_None,
        EUserInterfaceActionType::RadioButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "EditorLightingFollowMaster", "Follow Master While Editing"),
        NSLOCTEXT(
            "InfinityStage",
            "EditorLightingFollowMasterTip",
            "Let Cue Desk and Sequencer scrubbing show the production day/night phase in the editor world."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetEditorLightingFollowMaster, true),
            FCanExecuteAction(),
            FIsActionChecked::CreateSP(this, &SInfinityStageCueDesk::IsEditorLightingFollowingMaster)),
        NAME_None,
        EUserInterfaceActionType::RadioButton);
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "EditorLightingBright", "Bright Work Light — 12:00"),
        NSLOCTEXT("InfinityStage", "EditorLightingBrightTip", "Switch to manual editor lighting at noon."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetEditorLightingHour, 12.0)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "EditorLightingMorning", "Soft Morning — 09:00"),
        NSLOCTEXT("InfinityStage", "EditorLightingMorningTip", "Switch to manual editor lighting at nine in the morning."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetEditorLightingHour, 9.0)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "EditorLightingDusk", "Dusk — 18:00"),
        NSLOCTEXT("InfinityStage", "EditorLightingDuskTip", "Switch to manual editor lighting at sunset."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetEditorLightingHour, 18.0)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "EditorLightingNight", "Night — 00:00"),
        NSLOCTEXT("InfinityStage", "EditorLightingNightTip", "Switch to manual editor lighting at midnight."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetEditorLightingHour, 0.0)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SelectCelestialRig", "Select Celestial Rig for Detailed Controls"),
        NSLOCTEXT(
            "InfinityStage",
            "SelectCelestialRigTip",
            "Select the show-wide Celestial Rig in the Level Editor. Its Details panel exposes exact editor time, sun/moon strength, skylight, fog colors, stars and bindings."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SelectCelestialRigInEditor)));
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildScrubViewMenu()
{
    FMenuBuilder MenuBuilder(true, nullptr);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ScrubCameraView", "Camera View"),
        NSLOCTEXT("InfinityStage", "ScrubCameraViewTip", "Move the editor viewport with the evaluated Passage camera while scrubbing."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetMusicScrubCameraFollow, true),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bFollowMusicScrubInViewport; })),
        NAME_None,
        EUserInterfaceActionType::RadioButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ScrubOverview", "Overview"),
        NSLOCTEXT("InfinityStage", "ScrubOverviewTip", "Evaluate wings and the camera rig while leaving the editor viewport free at your chosen overview."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetMusicScrubCameraFollow, false),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return !bFollowMusicScrubInViewport; })),
        NAME_None,
        EUserInterfaceActionType::RadioButton);
    return MenuBuilder.MakeWidget();
}


/**
 * Ramer-Douglas-Peucker index selection.
 *
 * A sampled envelope becomes an editable Sequencer curve only if it is reduced
 * to the points that carry its shape; keeping every sample would produce a
 * curve no artist can adjust afterwards. Tolerance is in output units, and the
 * budget is a hard ceiling reached by relaxing tolerance.
 */
TArray<int32> DecimateCurveIndices(const TArray<double>& Samples, const double Tolerance, const int32 MaxKeys)
{
    const int32 Count = Samples.Num();
    if (Count <= 2 || MaxKeys <= 2)
    {
        TArray<int32> Ends;
        for (int32 Index = 0; Index < Count; ++Index)
        {
            Ends.Add(Index);
        }
        return Ends;
    }

    auto Simplify = [&Samples, Count](const double UseTolerance)
    {
        TArray<bool> Keep;
        Keep.Init(false, Count);
        Keep[0] = true;
        Keep[Count - 1] = true;
        TArray<TPair<int32, int32>> Stack;
        Stack.Emplace(0, Count - 1);
        while (!Stack.IsEmpty())
        {
            const TPair<int32, int32> Span = Stack.Pop();
            const int32 First = Span.Key;
            const int32 Last = Span.Value;
            if (Last <= First + 1)
            {
                continue;
            }
            const double Slope = (Samples[Last] - Samples[First]) / static_cast<double>(Last - First);
            double WorstError = 0.0;
            int32 WorstIndex = INDEX_NONE;
            for (int32 Index = First + 1; Index < Last; ++Index)
            {
                const double Predicted = Samples[First] + Slope * (Index - First);
                const double Error = FMath::Abs(Samples[Index] - Predicted);
                if (Error > WorstError)
                {
                    WorstError = Error;
                    WorstIndex = Index;
                }
            }
            if (WorstIndex != INDEX_NONE && WorstError > UseTolerance)
            {
                Keep[WorstIndex] = true;
                Stack.Emplace(First, WorstIndex);
                Stack.Emplace(WorstIndex, Last);
            }
        }
        TArray<int32> Indices;
        for (int32 Index = 0; Index < Count; ++Index)
        {
            if (Keep[Index])
            {
                Indices.Add(Index);
            }
        }
        return Indices;
    };

    double UseTolerance = FMath::Max(Tolerance, UE_DOUBLE_SMALL_NUMBER);
    TArray<int32> Indices = Simplify(UseTolerance);
    // Relax rather than truncate: dropping keys from the tail would silently
    // flatten the end of the Passage.
    for (int32 Attempt = 0; Attempt < 12 && Indices.Num() > MaxKeys; ++Attempt)
    {
        UseTolerance *= 1.6;
        Indices = Simplify(UseTolerance);
    }
    return Indices;
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildCameraCurveMenu()
{
    FMenuBuilder MenuBuilder(true, nullptr);
    MenuBuilder.BeginSection(
        TEXT("InfinityStageCameraChannels"),
        NSLOCTEXT("InfinityStage", "CameraChannelSection", "Camera"));
    for (uint8 RawChannel = static_cast<uint8>(InfinityFirstPassageChannel);
        RawChannel <= static_cast<uint8>(InfinityLastPassageChannel);
        ++RawChannel)
    {
        const EInfinityPassageCameraChannel Channel = static_cast<EInfinityPassageCameraChannel>(RawChannel);
        if (Channel == EInfinityPassageCameraChannel::WingInwardTravelScale)
        {
            MenuBuilder.EndSection();
            MenuBuilder.BeginSection(
                TEXT("InfinityStageWingChannels"),
                NSLOCTEXT("InfinityStage", "WingChannelSection", "Wing Movement"));
        }
        MenuBuilder.AddMenuEntry(
            CameraChannelText(Channel),
            FText::GetEmpty(),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateLambda([this, Channel]()
                {
                    ActiveCameraChannel = Channel;
                    Invalidate(EInvalidateWidgetReason::Paint);
                }),
                FCanExecuteAction(),
                FIsActionChecked::CreateLambda([this, Channel]() { return ActiveCameraChannel == Channel; })),
            NAME_None,
            EUserInterfaceActionType::RadioButton);
    }
    MenuBuilder.EndSection();
    return MenuBuilder.MakeWidget();
}

void SInfinityStageCueDesk::BuildAnalysisCurveMenu(FMenuBuilder& MenuBuilder)
{
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    const FInfinityMusicRail* Rail = (ShowAsset.IsValid() && Settings)
        ? ShowAsset->MusicRails.FindByPredicate([Settings](const FInfinityMusicRail& Candidate)
            { return Candidate.RailGuid == Settings->Music.PrimaryRailGuid; })
        : nullptr;
    UInfinityStageMusicMapAsset* Map = Rail ? Rail->AnalysisMap.LoadSynchronous() : nullptr;
    if (!Map || Map->FeatureCurves.IsEmpty())
    {
        MenuBuilder.AddWidget(
            SNew(STextBlock)
            .Text(NSLOCTEXT(
                "InfinityStage",
                "NoAnalysisCurves",
                "No analysis curves. Re-run music analysis (provider 0.3.0 or newer) and import its map."))
            .AutoWrapText(true),
            FText::GetEmpty());
        return;
    }

    for (const FInfinityAnalysisCurve& Curve : Map->FeatureCurves)
    {
        const FName CurveName = Curve.Name;
        MenuBuilder.AddMenuEntry(
            FText::FromName(CurveName),
            FText::Format(
                NSLOCTEXT(
                    "InfinityStage",
                    "AnalysisCurveEntryTip",
                    "Write {0} across this Passage as keys on the active channel. Existing keys on that channel are replaced."),
                FText::FromName(CurveName)),
            FSlateIcon(),
            FUIAction(FExecuteAction::CreateSP(
                this,
                &SInfinityStageCueDesk::ApplyAnalysisCurveToActiveChannel,
                CurveName)));
    }
}

void SInfinityStageCueDesk::ApplyAnalysisCurveToActiveChannel(const FName CurveName)
{
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    if (!ShowAsset.IsValid() || !Settings || !Section)
    {
        return;
    }
    const FInfinityMusicRail* Rail = ShowAsset->MusicRails.FindByPredicate(
        [Settings](const FInfinityMusicRail& Candidate)
        { return Candidate.RailGuid == Settings->Music.PrimaryRailGuid; });
    UInfinityStageMusicMapAsset* Map = Rail ? Rail->AnalysisMap.LoadSynchronous() : nullptr;
    const FInfinityAnalysisCurve* Curve = Map ? Map->FindCurve(CurveName) : nullptr;
    FMovieSceneDoubleChannel* Channel = Section->GetCameraChannel(ActiveCameraChannel);
    if (!Curve || Curve->Values.IsEmpty() || !Channel)
    {
        return;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
        [Settings](const FInfinityCompiledPassage& Candidate)
        { return Candidate.PassageGuid == Settings->PassageGuid; });
    if (!Passage || !ShowAsset->TickResolution.IsValid())
    {
        return;
    }

    // The curve is unit-range; map it onto something sensible for the channel so
    // the first application is musically legible rather than arbitrary.
    double OutputMinimum = 0.0;
    double OutputMaximum = 1.0;
    switch (ActiveCameraChannel)
    {
    case EInfinityPassageCameraChannel::WingInwardTravelScale:
    case EInfinityPassageCameraChannel::WingCycleRateScale:
    case EInfinityPassageCameraChannel::SpeedMultiplier:
        OutputMinimum = 0.5;
        OutputMaximum = 1.5;
        break;
    case EInfinityPassageCameraChannel::WingPhaseBiasCycles:
        OutputMinimum = -0.25;
        OutputMaximum = 0.25;
        break;
    default:
        OutputMinimum = CameraChannelDefault(ActiveCameraChannel);
        OutputMaximum = CameraChannelDefault(ActiveCameraChannel);
        break;
    }
    if (FMath::IsNearlyEqual(OutputMinimum, OutputMaximum))
    {
        NotifyCueDesk(
            TEXT("Select a Wing Movement or Speed channel before applying an analysis curve; other channels have no meaningful unit mapping yet."),
            SNotificationItem::CS_Fail);
        return;
    }

    // Sample the curve at the Passage's music position, then decimate: a
    // three-minute Passage is thousands of samples and nobody can hand-edit
    // thousands of keys.
    const double TickRate = ShowAsset->TickResolution.AsDecimal();
    const double StartFrame = Passage->SegmentStartFrame.Value;
    const double EndFrame = Passage->SegmentEndFrame.Value;
    const double SpanFrames = EndFrame - StartFrame;
    if (SpanFrames <= 0.0)
    {
        return;
    }
    const double RailOffsetSeconds =
        (Rail->SourceInFrame.Value + Settings->Music.RailOffsetFrames.Value) / TickRate;

    constexpr int32 SampleCount = 512;
    TArray<double> Samples;
    Samples.Reserve(SampleCount);
    for (int32 Index = 0; Index < SampleCount; ++Index)
    {
        const double Alpha = static_cast<double>(Index) / (SampleCount - 1);
        const double MusicSeconds = RailOffsetSeconds + (Alpha * SpanFrames) / TickRate;
        const double Unit = FMath::Clamp(static_cast<double>(Curve->Sample(MusicSeconds)), 0.0, 1.0);
        Samples.Add(FMath::Lerp(OutputMinimum, OutputMaximum, Unit));
    }

    const TArray<int32> KeyIndices = DecimateCurveIndices(Samples, 0.02, 96);

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ApplyAnalysisCurveTransaction", "Apply Music Analysis Curve"));
    Section->Modify();
    Channel->Reset();
    for (const int32 Index : KeyIndices)
    {
        const double Alpha = static_cast<double>(Index) / (SampleCount - 1);
        const FFrameNumber Frame(static_cast<int32>(FMath::RoundToInt(StartFrame + Alpha * SpanFrames)));
        Channel->AddLinearKey(Frame, Samples[Index]);
    }
    Section->MarkPackageDirty();

    NotifyCueDesk(
        FString::Printf(
            TEXT("Applied '%s' to %s across %s: %d keys from %d samples. Review, then save the Master intentionally."),
            *CurveName.ToString(),
            *CameraChannelText(ActiveCameraChannel).ToString(),
            *Settings->Label.ToString(),
            KeyIndices.Num(),
            SampleCount),
        SNotificationItem::CS_Success);
    Invalidate(EInvalidateWidgetReason::Paint);
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildCameraCurveActionsMenu()
{
    FMenuBuilder MenuBuilder(true, nullptr);
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "ApplyAnalysisCurve", "Apply Music Analysis Curve"),
        NSLOCTEXT(
            "InfinityStage",
            "ApplyAnalysisCurveTip",
            "Write an expressive envelope from this Passage's analysis map onto the active channel as decimated keys. "
            "Intensity onto Wing Travel Scale makes the wings open with the music; rhythmic density onto Cycle Rate Scale makes them breathe with it."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildAnalysisCurveMenu));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "CameraSpeedEnvelopeSubmenu", "Add Speed Envelope"),
        NSLOCTEXT("InfinityStage", "CameraSpeedEnvelopeSubmenuTip", "Add a smooth, constraint-normalized 30-second acceleration or slowdown to the authoritative Speed / Time Warp channel."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildCameraSpeedPresetMenu));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "RemoveCameraKey", "Remove Key at Playhead"),
        NSLOCTEXT("InfinityStage", "RemoveCameraKeyTip", "Remove the active camera-channel key exactly at the Music Timeline playhead."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::RemoveCameraCurveKey)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ResetCameraCurve", "Reset Active Curve"),
        NSLOCTEXT("InfinityStage", "ResetCameraCurveTip", "Remove all keys from this channel and restore its production-safe default."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ResetCameraCurve)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "PinWingCameraAnchor", "Pin Selected Wing as Timing Anchor"),
        NSLOCTEXT("InfinityStage", "PinWingCameraAnchorTip", "Keep the camera at this Wing's exact authored pass-distance and Master time while normalizing speed curves on either side."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ToggleSelectedWingCameraAnchor),
            FCanExecuteAction::CreateLambda([this]()
            {
                const int32 Index = GetPrimarySelectedIndex();
                return ShowAsset.IsValid() && ShowAsset->Cues.IsValidIndex(Index)
                    && ShowAsset->Cues[Index].Type == EInfinityCueType::WingPair
                    && GetSelectedPassageCameraSection() != nullptr;
            }),
            FIsActionChecked::CreateSP(this, &SInfinityStageCueDesk::IsSelectedWingCameraAnchorPinned)),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "PinMusicCameraAnchor", "Pin Playhead as Music Anchor"),
        NSLOCTEXT("InfinityStage", "PinMusicCameraAnchorTip", "Keep the current music/Master time at its exact camera distance. Stored passage-relative so earlier Show edits do not orphan it."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::TogglePlayheadMusicCameraAnchor),
            FCanExecuteAction::CreateLambda([this]() { return GetSelectedPassageCameraSection() != nullptr; }),
            FIsActionChecked::CreateSP(this, &SInfinityStageCueDesk::IsPlayheadMusicCameraAnchorPinned)),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "PinConfirmedMusicMarkers", "Pin Confirmed Music Markers as Anchors"),
        NSLOCTEXT(
            "InfinityStage",
            "PinConfirmedMusicMarkersTip",
            "Add every confirmed beat, onset and major-change proposal in this Passage's source range as a camera timing anchor. Suggested markers remain non-authoritative."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::PinConfirmedMusicMarkersAsCameraAnchors)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ClearPassageFrameAnchors", "Clear Music / Passage-frame Anchors"),
        NSLOCTEXT(
            "InfinityStage",
            "ClearPassageFrameAnchorsTip",
            "Remove passage-relative timing anchors. Wing anchors remain pinned."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ClearPassageFrameCameraAnchors)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "PilotCameraSubmenu", "Pilot Camera from Viewport"),
        NSLOCTEXT(
            "InfinityStage",
            "PilotCameraSubmenuTip",
            "Look through the Passage camera at the playhead, fly it in the Level Viewport, and key the view you chose back onto the camera channels."),
        FNewMenuDelegate::CreateLambda([this](FMenuBuilder& SubMenuBuilder)
        {
            const FInfinityPassageSettings* Passage = GetSelectedPassage();
            FInfinityStageCameraPilot::BuildMenu(
                SubMenuBuilder,
                ShowAsset.Get(),
                Passage ? Passage->PassageGuid : FGuid(),
                GetCameraCurveEditFrame());
        }));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "OpenMasterCameraCurves", "Open Master in Sequencer"),
        NSLOCTEXT("InfinityStage", "OpenMasterCameraCurvesTip", "Open the managed Master and use Sequencer's native curve editor for full tangent and multi-key editing."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateLambda([this]()
        {
            if (GEditor && ShowAsset.IsValid())
            {
                if (ULevelSequence* Master = ShowAsset->ManagedMasterSequence.LoadSynchronous())
                {
                    GEditor->GetEditorSubsystem<UAssetEditorSubsystem>()->OpenEditorForAsset(Master);
                }
            }
        })));
    return MenuBuilder.MakeWidget();
}

void SInfinityStageCueDesk::BuildCameraSpeedPresetMenu(FMenuBuilder& MenuBuilder)
{
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SpeedEnvelopeAccelerate", "Accelerate over First 30 Seconds"),
        NSLOCTEXT("InfinityStage", "SpeedEnvelopeAccelerateTip", "Ease from 0.25x to 1x during the first 30 seconds; pinned endpoints and Wings remain exact."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ApplyCameraSpeedPreset, 0)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SpeedEnvelopeSlowEnd", "Slow over Last 30 Seconds"),
        NSLOCTEXT("InfinityStage", "SpeedEnvelopeSlowEndTip", "Ease from 1x to 0.25x during the last 30 seconds; compensation stays within each unlocked anchor span."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ApplyCameraSpeedPreset, 1)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SpeedEnvelopeSlowPlayhead", "30-Second Slowdown at Playhead"),
        NSLOCTEXT("InfinityStage", "SpeedEnvelopeSlowPlayheadTip", "Create a smooth 1x → 0.35x → 1x valley centred on the current Music Timeline playhead."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ApplyCameraSpeedPreset, 2)));
}

void SInfinityStageCueDesk::SetMusicScrubCameraFollow(const bool bEnabled)
{
    bFollowMusicScrubInViewport = bEnabled;
    GConfig->SetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("FollowMusicScrubInViewport"),
        bFollowMusicScrubInViewport,
        GEditorPerProjectIni);
    GConfig->Flush(false, GEditorPerProjectIni);

    if (!bEnabled && GCurrentLevelEditingViewportClient)
    {
        // Overview is a genuinely unpiloted editor view. The evaluated camera rig still moves,
        // but the viewport remains free for orbiting and inspecting the whole Passage.
        GCurrentLevelEditingViewportClient->SetActorLock(nullptr);
        if (SavedOverviewViewFOV.IsSet())
        {
            GCurrentLevelEditingViewportClient->ViewFOV = SavedOverviewViewFOV.GetValue();
            GCurrentLevelEditingViewportClient->FOVAngle = SavedOverviewFOVAngle.Get(
                SavedOverviewViewFOV.GetValue());
            GCurrentLevelEditingViewportClient->AspectRatio = SavedOverviewAspectRatio.Get(
                GCurrentLevelEditingViewportClient->AspectRatio);
            SavedOverviewViewFOV.Reset();
            SavedOverviewFOVAngle.Reset();
            SavedOverviewAspectRatio.Reset();
        }
        GCurrentLevelEditingViewportClient->Invalidate();
    }
}

bool SInfinityStageCueDesk::IsEditorLightingFollowingMaster() const
{
    UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!EditorWorld)
    {
        return false;
    }
    TActorIterator<AInfinityStageCelestialRig> It(EditorWorld);
    if (It)
    {
        return !It->bUseManualEditorLighting;
    }
    return false;
}

void SInfinityStageCueDesk::SetEditorLightingFollowMaster(const bool bFollowMaster)
{
    UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!EditorWorld)
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "EditorLightingModeTransaction", "Change Infinity Stage Editor Lighting Mode"));
    TArray<AInfinityStageCelestialRig*> Rigs;
    for (TActorIterator<AInfinityStageCelestialRig> It(EditorWorld); It; ++It)
    {
        AInfinityStageCelestialRig* Rig = *It;
        Rig->Modify();
        Rig->SetUseManualEditorLighting(!bFollowMaster);
        Rig->MarkPackageDirty();
        Rigs.Add(Rig);
    }

    if (bFollowMaster && ShowAsset.IsValid() && !Rigs.IsEmpty())
    {
        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
        const FInfinityPassageSettings* SelectedSettings = GetSelectedPassage();
        const FInfinityCompiledPassage* Passage = SelectedSettings
            ? Compiled.Passages.FindByPredicate([SelectedSettings](const FInfinityCompiledPassage& Candidate)
            {
                return Candidate.PassageGuid == SelectedSettings->PassageGuid;
            })
            : nullptr;
        if (Passage)
        {
            const double NormalizedPosition = EditorPreviewNormalizedPosition >= 0.0
                ? FMath::Clamp(EditorPreviewNormalizedPosition, 0.0, 1.0)
                : 0.0;
            const int32 DurationFrames = FMath::Max(
                0,
                Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value);
            const FFrameNumber Frame(Passage->SegmentStartFrame.Value
                + FMath::RoundToInt32(NormalizedPosition * DurationFrames));
            for (AInfinityStageCelestialRig* Rig : Rigs)
            {
                Rig->EvaluateAtMasterFrame(ShowAsset.Get(), Passage->PassageGuid, Frame);
            }
        }
    }

    if (GCurrentLevelEditingViewportClient)
    {
        GCurrentLevelEditingViewportClient->Invalidate();
    }
}

void SInfinityStageCueDesk::SetEditorLightingHour(const double TimeHours)
{
    UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!EditorWorld)
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "EditorLightingTimeTransaction", "Set Infinity Stage Editor Lighting Time"));
    for (TActorIterator<AInfinityStageCelestialRig> It(EditorWorld); It; ++It)
    {
        It->Modify();
        It->bUseManualEditorLighting = true;
        It->SetEditorPreviewTimeHours(TimeHours);
        It->MarkPackageDirty();
    }
    if (GCurrentLevelEditingViewportClient)
    {
        GCurrentLevelEditingViewportClient->Invalidate();
    }
}

void SInfinityStageCueDesk::SelectCelestialRigInEditor()
{
    UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!GEditor || !EditorWorld)
    {
        return;
    }

    GEditor->SelectNone(false, true, false);
    int32 SelectedCount = 0;
    for (TActorIterator<AInfinityStageCelestialRig> It(EditorWorld); It; ++It)
    {
        GEditor->SelectActor(*It, true, false, true);
        ++SelectedCount;
    }
    if (SelectedCount > 0)
    {
        GEditor->NoteSelectionChange();
    }
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildActionsMenu()
{
    FMenuBuilder MenuBuilder(true, nullptr);
    MenuBuilder.BeginSection(TEXT("Materialize"), NSLOCTEXT("InfinityStage", "MaterializeSection", "Materialize"));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "MaterializeSelectedPassage", "Materialize Selected Passage"),
        NSLOCTEXT(
            "InfinityStage",
            "MaterializeSelectedPassageTip",
            "Rebuild the selected Passage's Wings and cue-anchored stage content from the Show. Run this after changing "
            "wing count, spacing, meshes or attachments. The level is left dirty for an intentional save."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::MaterializeSelectedPassages),
            FCanExecuteAction::CreateLambda([this]() { return ShowAsset.IsValid(); })));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "MaterializeAllPassages", "Materialize All Passages"),
        NSLOCTEXT(
            "InfinityStage",
            "MaterializeAllPassagesTip",
            "Rebuild every Passage Actor bound to this Show. Use after a change that affects the whole Show, such as "
            "re-fitting wing counts from new music."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::RefreshAllPassagesInEditorWorld),
            FCanExecuteAction::CreateLambda([this]() { return ShowAsset.IsValid(); })));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "RefitSelectedPassageFromMusic", "Refit Selected Passage from Music"),
        NSLOCTEXT(
            "InfinityStage",
            "RefitSelectedPassageFromMusicTip",
            "Derive the selected Passage's Wing count from its linked Music Rail duration and its saved camera speed, spacing and entry/exit clearances. Existing Wing designs remain in order and repeat or trim as needed."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::RefitSelectedPassageFromMusic),
            FCanExecuteAction::CreateLambda([this]()
            {
                return ShowAsset.IsValid() && GetSelectedPassage() != nullptr;
            })));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "AddStageSpots", "Add Missing Stage Lights to Selection"),
        NSLOCTEXT(
            "InfinityStage",
            "AddStageSpotsTip",
            "Ensure every selected Wing Pair has one native light on its Left panel and one on its Right panel. "
            "They default to spots, can be changed to Rect or Point in the Stage inspector, and retain their full "
            "parameters and relative offsets when the Passage is re-spaced."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::AddStageSpotsToSelection),
            FCanExecuteAction::CreateLambda([this]() { return HasMechanismTargets(false); })));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "ReplicateStageLightingMenu", "Replicate First Pair's Lighting"),
        NSLOCTEXT(
            "InfinityStage",
            "ReplicateStageLightingMenuTip",
            "Tune one Wing Pair's lights in the level (moving a light writes its offset back to the Show), then use that "
            "pair as the template. Replaces only Light attachments on the targets with complete copies; props, sounds and "
            "triggers are preserved. 'With Variation' jitters each copy's offset, aim and intensity so the rig reads as "
            "hand-hung. Affected Passages are rematerialized."),
        FNewMenuDelegate::CreateLambda([this](FMenuBuilder& Sub)
        {
            struct FEntry { const TCHAR* Key; const TCHAR* Label; int32 Scope; bool bVariation; };
            const FEntry Entries[] = {
                { TEXT("SelExact"), TEXT("Across Selection — Exact"), 0, false },
                { TEXT("SelVar"), TEXT("Across Selection — With Variation"), 0, true },
                { TEXT("PassExact"), TEXT("Whole Passage — Exact"), 1, false },
                { TEXT("PassVar"), TEXT("Whole Passage — With Variation"), 1, true },
                { TEXT("ShowExact"), TEXT("Entire Show — Exact"), 2, false },
                { TEXT("ShowVar"), TEXT("Entire Show — With Variation"), 2, true },
            };
            for (const FEntry& Entry : Entries)
            {
                const int32 Scope = Entry.Scope;
                const bool bVariation = Entry.bVariation;
                Sub.AddMenuEntry(
                    FText::FromString(Entry.Label),
                    FText::FromString(Scope == 0
                        ? TEXT("Template: earliest selected Wing Pair. Targets: the other selected pairs.")
                        : Scope == 1
                            ? TEXT("Template: the selected Wing Pair. Targets: every other pair in that pair's own Passage "
                                   "(e.g. select P02 Wing 001 to relight Passage 02 only).")
                            : TEXT("Template: the selected Wing Pair. Targets: every other Wing Pair in the Show.")),
                    FSlateIcon(),
                    FUIAction(
                        FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ReplicateStageLighting, Scope, bVariation),
                        FCanExecuteAction::CreateLambda([this, Scope]()
                        {
                            return Scope == 0 ? GetMechanismTargetCueGuids(false).Num() > 1
                                : Scope == 1 ? GetMechanismTargetCueGuids(true).Num() > 1
                                : HasMechanismTargets(false);
                        })));
            }
        }));
    MenuBuilder.EndSection();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "OpenSelectedSceneSequence", "Open Scene Sequence"),
        NSLOCTEXT("InfinityStage", "OpenSelectedSceneSequenceTip", "Open the Level Sequence assigned to the selected Scene or Sequence cue."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::OpenSelectedSceneSequence),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::CanOpenSelectedSceneSequence)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "FollowSelectionInViewport", "Follow Cue Playhead in Level Viewport"),
        NSLOCTEXT(
            "InfinityStage",
            "FollowSelectionInViewportTooltip",
            "Selecting a Passage or Wing cue moves the one Master playhead to its exact frame. Camera View follows the evaluated Cine Camera; Overview leaves the viewport free."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([this]()
            {
                bFollowCueSelectionToPlayhead = !bFollowCueSelectionToPlayhead;
                GConfig->SetBool(
                    TEXT("InfinityStage.CueDesk"),
                    TEXT("FollowCueSelectionToPlayhead"),
                    bFollowCueSelectionToPlayhead,
                    GEditorPerProjectIni);
                GConfig->Flush(false, GEditorPerProjectIni);
            }),
            FCanExecuteAction(),
            FIsActionChecked::CreateLambda([this]() { return bFollowCueSelectionToPlayhead; })),
        NAME_None,
        EUserInterfaceActionType::ToggleButton);
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "FrameSelectedWings", "Frame Selected Wing Pair(s)"),
        NSLOCTEXT("InfinityStage", "FrameSelectedWingsTooltip", "Move the active Level viewport to the currently selected Wing Pair cues."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::RefreshSelectedCuesInEditorWorld, false, true)));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "ViewportEditSubmenu", "Edit Selected Wing in Level Viewport"),
        NSLOCTEXT("InfinityStage", "ViewportEditSubmenuTip", "Open an authoritative transient gizmo proxy; finishing writes the transform back to the Cue."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildViewportEditMenu));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "ImageOrientationSubmenu", "Image Orientation"),
        NSLOCTEXT("InfinityStage", "ImageOrientationSubmenuTip",
            "Mirror a selected photograph for this occurrence, or copy that explicit state to every use of the same mesh."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildImageOrientationMenu));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "RelativeTransformSubmenu", "Relative Transform"),
        NSLOCTEXT("InfinityStage", "RelativeTransformSubmenuTip",
            "Copy the selected Left, Right or Top panel's saved location, rotation and scale to every use of the same mesh."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildRelativeTransformMenu));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "WingMovementSubmenu", "Wing Movement"),
        NSLOCTEXT("InfinityStage", "WingMovementSubmenuTip",
            "Apply deterministic in/out motion presets. Scrub the Music Timeline or play the Master to preview the result."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildWingMovementMenu));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "WingSequenceFilesSubmenu", "Wing Sequence Files"),
        NSLOCTEXT("InfinityStage", "WingSequenceFilesSubmenuTip",
            "Save or restore lossless, versioned .infinitywings.json blocks. Imported rows receive fresh identities while preserving their authored design."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildWingSequenceFileMenu));
    MenuBuilder.AddSubMenu(
        NSLOCTEXT("InfinityStage", "SceneHandoffSubmenu", "Scene Camera Handoff"),
        NSLOCTEXT("InfinityStage", "SceneHandoffSubmenuTip",
            "Create or refresh exact Scene boundary cameras, preserving the final designed shot when a retained-camera interstitial follows."),
        FNewMenuDelegate::CreateSP(this, &SInfinityStageCueDesk::BuildSceneHandoffMenu));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "DuplicateSelection", "Duplicate Selection"),
        FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::DuplicateSelected)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "MoveSelectionUp", "Move Up"),
        FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::MoveSelected, -1)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "MoveSelectionDown", "Move Down"),
        FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::MoveSelected, 1)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ReimportMusicAnalysis", "Link / Reimport Music Analysis"),
        NSLOCTEXT("InfinityStage", "ReimportMusicAnalysisTooltip", "Link the latest non-destructive waveform, tempo and musical-change review maps from Saved/InfinityStage/MusicAnalysis. Cue timing is not changed."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ReimportMusicAnalysis)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "AnalyzeSelectionMusic", "Analyze Music for Selection"),
        NSLOCTEXT(
            "InfinityStage",
            "AnalyzeSelectionMusicTooltip",
            "Analyse the sound bound to the selected Passage's Music Rail: exports the imported audio, runs the analyzer and "
            "links the resulting review map, including the expressive curves used by Apply Music Analysis Curve. "
            "Cue timing is not changed."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::AnalyzeSelectionMusic)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "RebuildManagedMaster", "Rebuild Managed Master Sequence"),
        NSLOCTEXT("InfinityStage", "RebuildManagedMasterTooltip", "Refresh only the plugin-owned Passage, Scene and music tracks; artist tracks are preserved."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::RebuildManagedMaster)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "RenderSelectedRange", "Render Selected Range…"),
        NSLOCTEXT(
            "InfinityStage",
            "RenderSelectedRangeTooltip",
            "Build a managed render wrapper for the selected Cue span or whole selected Passage, expose Passage cameras through a standard Camera Cut Track, and open Movie Render Queue."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::RenderSelectedRange),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::CanRenderSelectedRange)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "DeleteSelection", "Delete Selection"),
        FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::DeleteSelected)));
    return MenuBuilder.MakeWidget();
}

void SInfinityStageCueDesk::BuildWingSequenceFileMenu(FMenuBuilder& MenuBuilder)
{
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ExportSelectedWingSequence", "Export Selected Wing Pair(s)…"),
        NSLOCTEXT("InfinityStage", "ExportSelectedWingSequenceTip",
            "Save the selected Wing Pair rows in their Show order as a reusable external JSON sequence."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ExportWingSequence, false),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::HasWingSequenceExportTargets, false)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ExportWholePassageWingSequence", "Export Whole Current Passage…"),
        NSLOCTEXT("InfinityStage", "ExportWholePassageWingSequenceTip",
            "Save every Wing Pair in the current Passage plus its lead/tail, fit, spacing and preferred camera-speed envelope. Music and sky settings are not exported."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::ExportWingSequence, true),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::HasWingSequenceExportTargets, true)));
    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ImportApplyWingArrangement", "Apply Saved Arrangement to Current Passage…"),
        NSLOCTEXT("InfinityStage", "ImportApplyWingArrangementTip",
            "Apply only the saved ordered Wing designs to the selected Passage's existing rows. The pattern repeats or trims to fit; Passage name, row names, count, music timing, spacing and stable identities are preserved."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(
                this, &SInfinityStageCueDesk::ImportWingSequence,
                EInfinityWingSequenceImportMode::ApplyArrangement),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::HasPassageReplacementTarget)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ImportInsertWingSequence", "Import and Insert After Selection…"),
        NSLOCTEXT("InfinityStage", "ImportInsertWingSequenceTip",
            "Insert a reusable Wing Sequence after the last selected cue. Passage-wide values in the file do not overwrite the surrounding Passage."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(
            this, &SInfinityStageCueDesk::ImportWingSequence,
            EInfinityWingSequenceImportMode::InsertRows)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "ImportReplaceWingSequence", "Advanced: Replace Complete Passage Rows…"),
        NSLOCTEXT("InfinityStage", "ImportReplaceWingSequenceTip",
            "Replace the selected Passage's row count, row labels, timing, spacing and layout defaults from the file. Passage identity/name, music rail, temporality and scene/camera handovers are preserved."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateSP(
                this, &SInfinityStageCueDesk::ImportWingSequence,
                EInfinityWingSequenceImportMode::ReplaceCompleteRows),
            FCanExecuteAction::CreateSP(this, &SInfinityStageCueDesk::HasPassageReplacementTarget)));
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildMusicPanel()
{
    return SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(6.0f)
        [
            SNew(STextBlock)
            .Text(NSLOCTEXT("InfinityStage", "MusicPanelHelp", "Selected Passage and its one Master-owned Music Rail. Source In/Out and fades edit here; the horizontal timeline below remains visible with Cue details. Passage world position never starts music."))
            .AutoWrapText(true)
        ]
        + SVerticalBox::Slot().FillHeight(1.0f)[PassageDetails.ToSharedRef()];
}

TSharedRef<SWidget> SInfinityStageCueDesk::BuildMusicWorkspace()
{
    return SNew(SBorder)
        .Padding(2.0f)
        .ToolTipText(NSLOCTEXT("InfinityStage", "MusicTimelineTooltip", "Drag the divider above this panel to resize it. Drag the waveform to scrub the selected Passage's visuals and audition its music."))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot()
            .AutoHeight()
            .Padding(4.0f, 2.0f)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text_Lambda([this]()
                    {
                        const FInfinityPassageSettings* Passage = GetSelectedPassage();
                        return Passage
                            ? FText::Format(NSLOCTEXT("InfinityStage", "SelectedPassageTimeline", "{0} · music/visual Master-frame preview"), Passage->Label)
                            : NSLOCTEXT("InfinityStage", "NoPassageTimeline", "Select a Passage cue");
                    })
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f)
                [
                    SNew(SComboButton)
                    .ToolTipText(NSLOCTEXT("InfinityStage", "ScrubViewModeTip", "Choose whether Music Timeline scrubbing follows the Passage camera or leaves the Level viewport at a free overview."))
                    .ButtonContent()
                    [
                        SNew(STextBlock)
                        .Text_Lambda([this]()
                        {
                            return bFollowMusicScrubInViewport
                                ? NSLOCTEXT("InfinityStage", "ScrubViewCameraLabel", "Scrub View: Camera")
                                : NSLOCTEXT("InfinityStage", "ScrubViewOverviewLabel", "Scrub View: Overview");
                        })
                    ]
                    .MenuContent()
                    [
                        BuildScrubViewMenu()
                    ]
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f).VAlign(VAlign_Center)
                [
                    SNew(SCheckBox)
                    .ToolTipText(NSLOCTEXT(
                        "InfinityStage",
                        "VisibleRehearsalTransportTip",
                        "Allow Cue Desk selection and scrubbing to seek across externally clocked Scenes while rehearsing in PIE. Turn this off for performance-safe transport."))
                    .IsChecked_Lambda([this]()
                    {
                        return bRehearsalTransport
                            ? ECheckBoxState::Checked
                            : ECheckBoxState::Unchecked;
                    })
                    .OnCheckStateChanged_Lambda([this](const ECheckBoxState NewState)
                    {
                        const bool bEnabled = NewState == ECheckBoxState::Checked;
                        if (bEnabled != bRehearsalTransport)
                        {
                            ToggleRehearsalTransport();
                        }
                    })
                    [
                        SNew(STextBlock)
                        .Text(NSLOCTEXT("InfinityStage", "VisibleRehearsalTransportLabel", "Rehearsal"))
                    ]
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [
                    SNew(SButton)
                    .Text(NSLOCTEXT("InfinityStage", "CueAndPlaySelectedLabel", "Play Selected"))
                    .ToolTipText(NSLOCTEXT(
                        "InfinityStage",
                        "CueAndPlaySelectedTip",
                        "In PIE, cue the selected Scene or SEQ at its exact first frame, enable rehearsal transport, and play only that segment to its boundary."))
                    .IsEnabled_Lambda([this]() { return CanCueAndPlaySelectedSegment(); })
                    .OnClicked_Lambda([this]()
                    {
                        CueAndPlaySelectedSegment();
                        return FReply::Handled();
                    })
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("⇤"))).ToolTipText(NSLOCTEXT("InfinityStage", "PreviousSegmentTip", "Jump to the previous Master segment (previous Passage or Scene). In PIE this uses the live operator transport and its readiness/external-clock safety rules.")).OnClicked_Lambda([this](){ RunTransportCommand(5); return FReply::Handled(); })]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("|◀"))).ToolTipText(NSLOCTEXT("InfinityStage", "PassageStartTip", "Jump to the start of the current Passage")).OnClicked_Lambda([this](){ RunTransportCommand(0); return FReply::Handled(); })]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("◀"))).ToolTipText(NSLOCTEXT("InfinityStage", "ReverseBoundaryTip", "Play backward to the Passage start. Editor preview reverses visuals; production music is not played backward.")).OnClicked_Lambda([this](){ RunTransportCommand(1); return FReply::Handled(); })]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("■"))).ToolTipText(NSLOCTEXT("InfinityStage", "StopPreviewTip", "Stop / hold at the current frame")).OnClicked_Lambda([this](){ RunTransportCommand(2); return FReply::Handled(); })]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("▶"))).ToolTipText(NSLOCTEXT("InfinityStage", "PlayPreviewTip", "Play forward with music to the Passage end")).OnClicked_Lambda([this](){ RunTransportCommand(3); return FReply::Handled(); })]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("▶|"))).ToolTipText(NSLOCTEXT("InfinityStage", "PassageEndTip", "Jump to the end of the current Passage")).OnClicked_Lambda([this](){ RunTransportCommand(4); return FReply::Handled(); })]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [SNew(SButton).Text(FText::FromString(TEXT("⇥"))).ToolTipText(NSLOCTEXT("InfinityStage", "NextSegmentTip", "Advance to the next Master segment. Sequence/interstitial cues play automatically to their boundary; Passage and Scene cues hold at their exact start.")).OnClicked_Lambda([this](){ RunTransportCommand(6); return FReply::Handled(); })]
            ]
            + SVerticalBox::Slot()
            .AutoHeight()
            .Padding(4.0f, 0.0f, 4.0f, 3.0f)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                [SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "CameraCurveRailLabel", "Camera curve"))]
                + SHorizontalBox::Slot().AutoWidth().Padding(5.0f, 0.0f)
                [
                    SNew(SComboButton)
                    .ToolTipText(NSLOCTEXT("InfinityStage", "CameraCurveChooserTip", "Choose the managed Passage camera channel painted over the music rail."))
                    .ButtonContent()[SNew(STextBlock).Text(this, &SInfinityStageCueDesk::GetCameraCurveLabel)]
                    .MenuContent()[BuildCameraCurveMenu()]
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [
                    SNew(SBox).WidthOverride(118.0f)
                    [
                        SNew(SNumericEntryBox<double>)
                        .ToolTipText(NSLOCTEXT("InfinityStage", "CameraCurveValueTip", "Value at the playhead. Committing creates or updates one native Sequencer key."))
                        .Value(this, &SInfinityStageCueDesk::GetCameraCurveValue)
                        .OnValueCommitted(this, &SInfinityStageCueDesk::SetCameraCurveValue)
                    ]
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f, 0.0f)
                [
                    SNew(SComboButton)
                    .ButtonContent()[SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "CameraCurveActions", "Curve Actions"))]
                    .MenuContent()[BuildCameraCurveActionsMenu()]
                ]
                + SHorizontalBox::Slot().FillWidth(1.0f).Padding(8.0f, 0.0f).VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text(this, &SInfinityStageCueDesk::GetCameraCurveStatusText)
                    .Justification(ETextJustify::Right)
                    .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                ]
            ]
            + SVerticalBox::Slot()
            .FillHeight(1.0f)
            [
                SNew(SInfinityStageMusicTimeline)
                .ShowAsset_Lambda([this]() -> UInfinityStageShowAsset* { return ShowAsset.Get(); })
                .SelectedCueIndex_Lambda([this]() { return GetTimelineSelectedCueIndex(); })
                .PlayheadPosition_Lambda([this]() { return EditorPreviewNormalizedPosition; })
                .CameraSection_Lambda([this]() { return GetSelectedPassageCameraSection(); })
                .CameraChannel_Lambda([this]() { return ActiveCameraChannel; })
                .SnapToMusicMarkers_Lambda([this]() { return bSnapMusicScrubToMarkers; })
                .OnScrub(FOnInfinityMusicTimelineScrub::CreateSP(this, &SInfinityStageCueDesk::HandleMusicScrub))
            ]
        ];
}

void SInfinityStageCueDesk::SaveLayoutConfig() const
{
    GConfig->SetBool(TEXT("InfinityStage.CueDesk"), TEXT("NestedCueMode"), bNestedCueMode, GEditorPerProjectIni);
    GConfig->SetBool(TEXT("InfinityStage.CueDesk"), TEXT("MusicWorkspaceVisible"), bMusicWorkspaceVisible, GEditorPerProjectIni);
    GConfig->SetBool(TEXT("InfinityStage.CueDesk"), TEXT("SnapMusicScrubToMarkers"), bSnapMusicScrubToMarkers, GEditorPerProjectIni);
    GConfig->SetFloat(TEXT("InfinityStage.CueDesk"), TEXT("MainWorkspaceFraction"), MainWorkspaceFraction, GEditorPerProjectIni);
    GConfig->SetFloat(TEXT("InfinityStage.CueDesk"), TEXT("MusicWorkspaceFraction"), MusicWorkspaceFraction, GEditorPerProjectIni);
    GConfig->SetFloat(TEXT("InfinityStage.CueDesk"), TEXT("CueListFraction"), CueListFraction, GEditorPerProjectIni);
    GConfig->SetFloat(TEXT("InfinityStage.CueDesk"), TEXT("CueDetailsFraction"), CueDetailsFraction, GEditorPerProjectIni);
    GConfig->SetFloat(TEXT("InfinityStage.CueDesk"), TEXT("InspectorFraction"), InspectorFraction, GEditorPerProjectIni);
    GConfig->Flush(false, GEditorPerProjectIni);
}

FString SInfinityStageCueDesk::GetAssetPath() const
{
    return ShowAsset.IsValid() ? ShowAsset->GetPathName() : FString();
}

void SInfinityStageCueDesk::HandleAssetChanged(const FAssetData& AssetData)
{
    StopEditorPreviewPlayback();
    EditorPreviewNormalizedPosition = -1.0;
    EditorPreviewPassageGuid.Invalidate();
    ClearEditorWorldInstanceSelection();
    ShowAsset = Cast<UInfinityStageShowAsset>(AssetData.GetAsset());
    if (ShowAsset.IsValid())
    {
        ShowAsset->EnsureStableIds();
        ShowAsset->ReconcilePassageSettings();
        AssetDetails->SetObject(ShowAsset.Get());
    }
    else
    {
        AssetDetails->SetObject(nullptr);
    }
    RefreshFromAsset(false);
}

void SInfinityStageCueDesk::RefreshFromAsset(const bool bPreserveSelection)
{
    const int32 PreviousIndex = bPreserveSelection ? GetPrimarySelectedIndex() : INDEX_NONE;
    const FGuid PreviousPassageGuid = bPreserveSelection ? SelectedPassageGuid : FGuid();
    if (!bPreserveSelection)
    {
        SelectedPassageGuid.Invalidate();
    }
    CueItems.Reset();
    if (ShowAsset.IsValid())
    {
        for (int32 Index = 0; Index < ShowAsset->Cues.Num();)
        {
            const FInfinityShowCue& Cue = ShowAsset->Cues[Index];
            if (bNestedCueMode && Cue.Type == EInfinityCueType::WingPair && Cue.bEnabled)
            {
                const FInfinityPassageSettings* Passage = ShowAsset->PassageSettings.FindByPredicate(
                    [this, Index](const FInfinityPassageSettings& Candidate)
                    {
                        const int32 First = ShowAsset->FindCueIndex(Candidate.FirstCueGuid);
                        return First == Index;
                    });
                if (Passage)
                {
                    const int32 Last = ShowAsset->FindCueIndex(Passage->LastCueGuid);
                    FCueItem Header = MakeShared<FInfinityCueListItem>();
                    Header->NodeType = EInfinityCueListNodeType::PassageHeader;
                    Header->PassageGuid = Passage->PassageGuid;
                    Header->HeaderLabel = Passage->Label;
                    Header->ChildCount = FMath::Max(0, Last - Index + 1);
                    Header->bPassageCollapsed = CollapsedPassages.Contains(Passage->PassageGuid);
                    CueItems.Add(Header);
                    if (!CollapsedPassages.Contains(Passage->PassageGuid))
                    {
                        for (int32 ChildIndex = Index; ChildIndex <= Last; ++ChildIndex)
                        {
                            FCueItem Child = MakeShared<FInfinityCueListItem>();
                            Child->CueIndex = ChildIndex;
                            Child->PassageGuid = Passage->PassageGuid;
                            Child->bNestedChild = true;
                            CueItems.Add(Child);
                        }
                    }
                    Index = Last + 1;
                    continue;
                }
            }

            FCueItem Item = MakeShared<FInfinityCueListItem>();
            Item->CueIndex = Index++;
            CueItems.Add(Item);
        }
    }
    if (CueList.IsValid())
    {
        CueList->RequestListRefresh();
        if (PreviousPassageGuid.IsValid())
        {
            const FCueItem* PreviousPassageItem = CueItems.FindByPredicate(
                [PreviousPassageGuid](const FCueItem& Candidate)
                {
                    return Candidate.IsValid()
                        && Candidate->NodeType == EInfinityCueListNodeType::PassageHeader
                        && Candidate->PassageGuid == PreviousPassageGuid;
                });
            if (PreviousPassageItem)
            {
                CueList->SetSelection(*PreviousPassageItem);
            }
        }
        else if (PreviousIndex != INDEX_NONE)
        {
            const FCueItem* PreviousItem = CueItems.FindByPredicate([PreviousIndex](const FCueItem& Candidate)
            {
                return Candidate.IsValid() && Candidate->NodeType == EInfinityCueListNodeType::Cue
                    && Candidate->CueIndex == PreviousIndex;
            });
            if (PreviousItem)
            {
                CueList->SetSelection(*PreviousItem);
            }
        }
    }
    RefreshPassageInspector();
    LoadFitFromSelectedPassage();
}

void SInfinityStageCueDesk::SetNestedCueMode(const bool bEnabled)
{
    if (bNestedCueMode != bEnabled)
    {
        bNestedCueMode = bEnabled;
        SaveLayoutConfig();
        RefreshFromAsset(true);
    }
}

void SInfinityStageCueDesk::TogglePassageCollapsed(const FGuid PassageGuid)
{
    if (CollapsedPassages.Contains(PassageGuid))
    {
        CollapsedPassages.Remove(PassageGuid);
    }
    else
    {
        CollapsedPassages.Add(PassageGuid);
    }
    RefreshFromAsset(true);
}

void SInfinityStageCueDesk::RenamePassage(const FGuid PassageGuid, const FText& NewLabel)
{
    if (!ShowAsset.IsValid() || !PassageGuid.IsValid())
    {
        return;
    }
    const FString TrimmedLabel = NewLabel.ToString().TrimStartAndEnd();
    if (TrimmedLabel.IsEmpty())
    {
        NotifyCueDesk(TEXT("A Passage name cannot be empty."), SNotificationItem::CS_Fail);
        RefreshFromAsset(true);
        return;
    }
    FInfinityPassageSettings* Passage = ShowAsset->PassageSettings.FindByPredicate(
        [PassageGuid](const FInfinityPassageSettings& Candidate)
        {
            return Candidate.PassageGuid == PassageGuid;
        });
    if (!Passage || Passage->Label.ToString().Equals(TrimmedLabel, ESearchCase::CaseSensitive))
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "RenamePassageTransaction", "Rename Infinity Stage Passage"));
    ShowAsset->Modify();
    Passage->Label = FText::FromString(TrimmedLabel);
    ShowAsset->MarkPackageDirty();
    SelectedPassageGuid = PassageGuid;
    RefreshFromAsset(true);

    if (!ShowAsset->ManagedMasterSequence.IsNull())
    {
        FString MasterReport;
        if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(
            ShowAsset.Get(), ShowAsset->ManagedMasterSequence.LoadSynchronous(), MasterReport))
        {
            UE_LOG(LogTemp, Error, TEXT("Passage renamed, but managed Master rebuild failed: %s"), *MasterReport);
        }
    }
    UE_LOG(LogTemp, Display, TEXT("INFINITY_STAGE_PASSAGE_RENAME_OK passage=%s label='%s'"),
        *PassageGuid.ToString(), *TrimmedLabel);
}

const FInfinityPassageSettings* SInfinityStageCueDesk::GetSelectedPassage() const
{
    if (!ShowAsset.IsValid())
    {
        return nullptr;
    }
    if (ShowAsset.IsValid() && SelectedPassageGuid.IsValid())
    {
        if (const FInfinityPassageSettings* ExplicitPassage = ShowAsset->PassageSettings.FindByPredicate(
            [this](const FInfinityPassageSettings& Passage)
            {
                return Passage.PassageGuid == SelectedPassageGuid;
            }))
        {
            return ExplicitPassage;
        }
    }

    const int32 SelectedIndex = GetPrimarySelectedIndex();
    const FInfinityPassageSettings* BestPrevious = nullptr;
    int32 BestPreviousEnd = INDEX_NONE;
    for (const FInfinityPassageSettings& Passage : ShowAsset->PassageSettings)
    {
        const int32 First = ShowAsset->FindCueIndex(Passage.FirstCueGuid);
        const int32 Last = ShowAsset->FindCueIndex(Passage.LastCueGuid);
        if (SelectedIndex >= First && SelectedIndex <= Last)
        {
            return &Passage;
        }
        if (Last < SelectedIndex && Last > BestPreviousEnd)
        {
            BestPrevious = &Passage;
            BestPreviousEnd = Last;
        }
    }
    return BestPrevious ? BestPrevious : (ShowAsset->PassageSettings.IsEmpty() ? nullptr : &ShowAsset->PassageSettings[0]);
}

UMovieSceneInfinityPassageSection* SInfinityStageCueDesk::GetSelectedPassageCameraSection() const
{
    const FInfinityPassageSettings* Passage = GetSelectedPassage();
    ULevelSequence* Master = ShowAsset.IsValid()
        ? ShowAsset->ManagedMasterSequence.LoadSynchronous()
        : nullptr;
    UMovieScene* MovieScene = Master ? Master->GetMovieScene() : nullptr;
    UMovieSceneInfinityPassageTrack* Track = MovieScene
        ? MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>()
        : nullptr;
    if (!Passage || !Track)
    {
        return nullptr;
    }
    for (UMovieSceneSection* RawSection : Track->GetAllSections())
    {
        UMovieSceneInfinityPassageSection* Section = Cast<UMovieSceneInfinityPassageSection>(RawSection);
        if (Section && Section->PassageGuid == Passage->PassageGuid)
        {
            return Section;
        }
    }
    return nullptr;
}

FFrameNumber SInfinityStageCueDesk::GetCameraCurveEditFrame() const
{
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!ShowAsset.IsValid() || !Settings)
    {
        return 0;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    if (!Passage)
    {
        return 0;
    }
    const double Normalized = EditorPreviewNormalizedPosition >= 0.0
        ? FMath::Clamp(EditorPreviewNormalizedPosition, 0.0, 1.0)
        : 0.0;
    return FFrameNumber(FMath::RoundToInt32(FMath::Lerp(
        static_cast<double>(Passage->SegmentStartFrame.Value),
        static_cast<double>(Passage->SegmentEndFrame.Value),
        Normalized)));
}

TOptional<double> SInfinityStageCueDesk::GetCameraCurveValue() const
{
    const UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    const FMovieSceneDoubleChannel* Channel = Section ? Section->GetCameraChannel(ActiveCameraChannel) : nullptr;
    if (!Channel)
    {
        return TOptional<double>();
    }
    double Value = CameraChannelDefault(ActiveCameraChannel);
    Channel->Evaluate(FFrameTime(GetCameraCurveEditFrame()), Value);
    return FMath::IsFinite(Value) ? TOptional<double>(Value) : TOptional<double>();
}

void SInfinityStageCueDesk::SetCameraCurveValue(const double NewValue, ETextCommit::Type)
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    FMovieSceneDoubleChannel* Channel = Section ? Section->GetCameraChannel(ActiveCameraChannel) : nullptr;
    if (!Section || !Channel || !FMath::IsFinite(NewValue))
    {
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "SetCameraCurveKeyTransaction", "Set Passage Camera Key"));
    Section->Modify();
    Channel->GetData().UpdateOrAddKey(
        GetCameraCurveEditFrame(),
        FMovieSceneDoubleValue(ClampCameraChannelValue(ActiveCameraChannel, NewValue)));
    Channel->AutoSetTangents();
    Channel->PostEditChange();
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);

    if (ShowAsset.IsValid())
    {
        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
        const FInfinityPassageSettings* Settings = GetSelectedPassage();
        const FInfinityCompiledPassage* Passage = Settings
            ? Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
            {
                return Candidate.PassageGuid == Settings->PassageGuid;
            })
            : nullptr;
        if (Passage)
        {
            EvaluateEditorPassageAtMasterFrame(*Passage, GetCameraCurveEditFrame());
        }
    }
}

void SInfinityStageCueDesk::RemoveCameraCurveKey()
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    FMovieSceneDoubleChannel* Channel = Section ? Section->GetCameraChannel(ActiveCameraChannel) : nullptr;
    if (!Section || !Channel)
    {
        return;
    }
    auto Data = Channel->GetData();
    const int32 KeyIndex = Data.FindKey(GetCameraCurveEditFrame());
    if (KeyIndex == INDEX_NONE)
    {
        return;
    }
    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "RemoveCameraCurveKeyTransaction", "Remove Passage Camera Key"));
    Section->Modify();
    Data.RemoveKey(KeyIndex);
    Channel->AutoSetTangents();
    Channel->PostEditChange();
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);
}

void SInfinityStageCueDesk::ResetCameraCurve()
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    FMovieSceneDoubleChannel* Channel = Section ? Section->GetCameraChannel(ActiveCameraChannel) : nullptr;
    if (!Section || !Channel)
    {
        return;
    }
    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "ResetCameraCurveTransaction", "Reset Passage Camera Curve"));
    Section->Modify();
    Channel->Reset();
    Channel->SetDefault(CameraChannelDefault(ActiveCameraChannel));
    Channel->PostEditChange();
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);
}

void SInfinityStageCueDesk::ApplyCameraSpeedPreset(const int32 Preset)
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    FMovieSceneDoubleChannel* Speed = Section
        ? Section->GetCameraChannel(EInfinityPassageCameraChannel::SpeedMultiplier)
        : nullptr;
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Section || !Speed || !Settings || !ShowAsset.IsValid())
    {
        return;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    if (!Passage)
    {
        return;
    }

    const int32 ThirtySeconds = FMath::Max(1, FMath::RoundToInt32(ShowAsset->TickResolution.AsDecimal() * 30.0));
    const int32 HalfWindow = ThirtySeconds / 2;
    const int32 Start = Passage->SegmentStartFrame.Value;
    const int32 End = Passage->SegmentEndFrame.Value;
    TArray<TPair<FFrameNumber, double>, TInlineAllocator<3>> Keys;
    if (Preset == 0)
    {
        Keys.Emplace(FFrameNumber(Start), 0.25);
        Keys.Emplace(FFrameNumber(FMath::Min(End, Start + ThirtySeconds / 2)), 0.65);
        Keys.Emplace(FFrameNumber(FMath::Min(End, Start + ThirtySeconds)), 1.0);
    }
    else if (Preset == 1)
    {
        Keys.Emplace(FFrameNumber(FMath::Max(Start, End - ThirtySeconds)), 1.0);
        Keys.Emplace(FFrameNumber(FMath::Max(Start, End - ThirtySeconds / 2)), 0.65);
        Keys.Emplace(FFrameNumber(End), 0.25);
    }
    else
    {
        const int32 Centre = GetCameraCurveEditFrame().Value;
        Keys.Emplace(FFrameNumber(FMath::Max(Start, Centre - HalfWindow)), 1.0);
        Keys.Emplace(FFrameNumber(FMath::Clamp(Centre, Start, End)), 0.35);
        Keys.Emplace(FFrameNumber(FMath::Min(End, Centre + HalfWindow)), 1.0);
    }

    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "ApplyCameraSpeedEnvelopeTransaction", "Add Passage Camera Speed Envelope"));
    Section->Modify();
    for (const TPair<FFrameNumber, double>& Key : Keys)
    {
        Speed->GetData().UpdateOrAddKey(Key.Key, FMovieSceneDoubleValue(Key.Value));
    }
    Speed->AutoSetTangents();
    Speed->PostEditChange();
    Section->MarkPackageDirty();
    ActiveCameraChannel = EInfinityPassageCameraChannel::SpeedMultiplier;
    Invalidate(EInvalidateWidgetReason::Paint);
}

bool SInfinityStageCueDesk::IsSelectedWingCameraAnchorPinned() const
{
    const int32 CueIndex = GetPrimarySelectedIndex();
    const UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    return Section && ShowAsset.IsValid() && ShowAsset->Cues.IsValidIndex(CueIndex)
        && Section->PinnedWingCueGuids.Contains(ShowAsset->Cues[CueIndex].CueGuid);
}

void SInfinityStageCueDesk::ToggleSelectedWingCameraAnchor()
{
    const int32 CueIndex = GetPrimarySelectedIndex();
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    if (!Section || !ShowAsset.IsValid() || !ShowAsset->Cues.IsValidIndex(CueIndex)
        || ShowAsset->Cues[CueIndex].Type != EInfinityCueType::WingPair)
    {
        return;
    }
    const FGuid CueGuid = ShowAsset->Cues[CueIndex].CueGuid;
    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "ToggleCameraAnchorTransaction", "Toggle Passage Camera Timing Anchor"));
    Section->Modify();
    if (Section->PinnedWingCueGuids.Contains(CueGuid))
    {
        Section->PinnedWingCueGuids.Remove(CueGuid);
    }
    else
    {
        Section->PinnedWingCueGuids.Add(CueGuid);
    }
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);
}

bool SInfinityStageCueDesk::IsPlayheadMusicCameraAnchorPinned() const
{
    const UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Section || !Settings || !ShowAsset.IsValid())
    {
        return false;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    return Passage && Section->PinnedPassageFrames.Contains(
        GetCameraCurveEditFrame() - Passage->SegmentStartFrame);
}

void SInfinityStageCueDesk::TogglePlayheadMusicCameraAnchor()
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Section || !Settings || !ShowAsset.IsValid())
    {
        return;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    if (!Passage)
    {
        return;
    }
    const FFrameNumber RelativeFrame = GetCameraCurveEditFrame() - Passage->SegmentStartFrame;
    const int32 Duration = Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value;
    if (RelativeFrame.Value <= 0 || RelativeFrame.Value >= Duration)
    {
        return; // Start and end are already implicit anchors.
    }
    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "ToggleMusicCameraAnchorTransaction", "Toggle Music Camera Timing Anchor"));
    Section->Modify();
    if (Section->PinnedPassageFrames.Contains(RelativeFrame))
    {
        Section->PinnedPassageFrames.Remove(RelativeFrame);
    }
    else
    {
        Section->PinnedPassageFrames.Add(RelativeFrame);
        Section->PinnedPassageFrames.Sort();
    }
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);
}

void SInfinityStageCueDesk::PinConfirmedMusicMarkersAsCameraAnchors()
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Section || !Settings || !ShowAsset.IsValid())
    {
        NotifyCueDesk(TEXT("Select a Passage and rebuild its managed Master camera section first."),
            SNotificationItem::CS_Fail);
        return;
    }
    const FInfinityMusicRail* Rail = ShowAsset->MusicRails.FindByPredicate([Settings](const FInfinityMusicRail& Candidate)
    {
        return Candidate.RailGuid == Settings->Music.PrimaryRailGuid;
    });
    const UInfinityStageMusicMapAsset* MusicMap = Rail ? Rail->AnalysisMap.LoadSynchronous() : nullptr;
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    if (!Rail || !MusicMap || !Passage)
    {
        NotifyCueDesk(TEXT("The selected Passage has no reviewable Music Map."), SNotificationItem::CS_Fail);
        return;
    }

    const double TickRate = ShowAsset->TickResolution.AsDecimal();
    const double SourceStartSeconds = TickRate > 0.0 ? Rail->SourceInFrame.Value / TickRate : 0.0;
    const double UsedSeconds = TickRate > 0.0 && Rail->SourceOutFrame > Rail->SourceInFrame
        ? (Rail->SourceOutFrame - Rail->SourceInFrame).Value / TickRate
        : MusicMap->DurationSeconds;
    const int32 PassageDurationFrames = Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value;
    if (UsedSeconds <= UE_DOUBLE_SMALL_NUMBER || PassageDurationFrames <= 0)
    {
        NotifyCueDesk(TEXT("The selected Passage music range has no usable duration."), SNotificationItem::CS_Fail);
        return;
    }

    TArray<FFrameNumber> ProposedFrames;
    const auto GatherConfirmed = [&](const TArray<FInfinityMusicAnalysisMarker>& Markers)
    {
        for (const FInfinityMusicAnalysisMarker& Marker : Markers)
        {
            if (Marker.State != EInfinityMusicProposalState::Confirmed)
            {
                continue;
            }
            const double Normalized = (Marker.TimeSeconds - SourceStartSeconds) / UsedSeconds;
            if (Normalized <= 0.0 || Normalized >= 1.0)
            {
                continue;
            }
            ProposedFrames.AddUnique(FFrameNumber(FMath::RoundToInt32(Normalized * PassageDurationFrames)));
        }
    };
    GatherConfirmed(MusicMap->BeatProposals);
    GatherConfirmed(MusicMap->OnsetProposals);
    GatherConfirmed(MusicMap->MajorChangeProposals);
    if (ProposedFrames.IsEmpty())
    {
        NotifyCueDesk(
            TEXT("No confirmed beat, onset or major-change markers fall inside this Passage's source range."),
            SNotificationItem::CS_Fail);
        return;
    }

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "PinConfirmedMusicMarkersTransaction", "Pin Confirmed Music Camera Anchors"));
    Section->Modify();
    int32 AddedCount = 0;
    for (const FFrameNumber RelativeFrame : ProposedFrames)
    {
        if (!Section->PinnedPassageFrames.Contains(RelativeFrame))
        {
            Section->PinnedPassageFrames.Add(RelativeFrame);
            ++AddedCount;
        }
    }
    Section->PinnedPassageFrames.Sort();
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);
    NotifyCueDesk(
        FString::Printf(TEXT("Pinned %d confirmed music marker(s) as camera timing anchors."), AddedCount),
        SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::ClearPassageFrameCameraAnchors()
{
    UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    if (!Section || Section->PinnedPassageFrames.IsEmpty())
    {
        return;
    }
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ClearPassageFrameAnchorsTransaction", "Clear Passage Camera Frame Anchors"));
    Section->Modify();
    Section->PinnedPassageFrames.Reset();
    Section->MarkPackageDirty();
    Invalidate(EInvalidateWidgetReason::Paint);
}

FText SInfinityStageCueDesk::GetCameraCurveLabel() const
{
    return CameraChannelText(ActiveCameraChannel);
}

FText SInfinityStageCueDesk::GetCameraCurveStatusText() const
{
    const UMovieSceneInfinityPassageSection* Section = GetSelectedPassageCameraSection();
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Section || !Settings || !ShowAsset.IsValid())
    {
        return NSLOCTEXT("InfinityStage", "NoManagedCameraSection", "Rebuild Master to create managed camera curves");
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    const double TickRate = ShowAsset->TickResolution.AsDecimal();
    if (!Passage || TickRate <= 0.0)
    {
        return NSLOCTEXT("InfinityStage", "InvalidCameraCurvePassage", "Camera curve unavailable");
    }

    const double DurationSeconds = (Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value) / TickRate;
    const double AverageMetresPerSecond = DurationSeconds > 0.0
        ? Passage->TotalDistanceCm / DurationSeconds / 100.0
        : 0.0;
    const double DeltaFrames = FMath::Max(1.0, TickRate * 0.05);
    // Read the speed the Passage camera actually travels, including its
    // crossing settle, from the rig that drives this Passage in the editor world.
    double SettleFrames = 0.0;
    if (UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr)
    {
        for (TActorIterator<AInfinityStageCameraRig> It(EditorWorld); It; ++It)
        {
            if (It->PassageActor && It->PassageActor->ShowAsset == ShowAsset.Get()
                && It->PassageActor->PassageGuid == Passage->PassageGuid)
            {
                SettleFrames = It->GetCrossingSettleFrames();
                break;
            }
        }
    }
    auto SpeedAt = [Section, Passage, TickRate, DeltaFrames, SettleFrames](const double Frame, bool& bFallback)
    {
        const double AFrame = FMath::Max(static_cast<double>(Passage->SegmentStartFrame.Value), Frame - DeltaFrames);
        const double BFrame = FMath::Min(static_cast<double>(Passage->SegmentEndFrame.Value), Frame + DeltaFrames);
        if (BFrame <= AFrame)
        {
            return 0.0;
        }
        FInfinityPassageCameraEvaluation A;
        FInfinityPassageCameraEvaluation B;
        if (!Section->EvaluateCamera(*Passage, FFrameTime::FromDecimal(AFrame), A, SettleFrames)
            || !Section->EvaluateCamera(*Passage, FFrameTime::FromDecimal(BFrame), B, SettleFrames))
        {
            return 0.0;
        }
        bFallback |= A.bUsedInvalidSpeedFallback || B.bUsedInvalidSpeedFallback;
        const double DistanceA = FInfinityStageCompiler::EvaluateDistanceAtFrame(*Passage, A.DistanceMasterFrame);
        const double DistanceB = FInfinityStageCompiler::EvaluateDistanceAtFrame(*Passage, B.DistanceMasterFrame);
        return FMath::Abs(DistanceB - DistanceA) / ((BFrame - AFrame) / TickRate) / 100.0;
    };

    bool bFallback = false;
    bool bNegativeRate = false;
    const FMovieSceneDoubleChannel* SpeedChannel = Section->GetCameraChannel(
        EInfinityPassageCameraChannel::SpeedMultiplier);
    const double CurrentSpeed = SpeedAt(GetCameraCurveEditFrame().Value, bFallback);
    double PeakSpeed = CurrentSpeed;
    constexpr int32 PeakSamples = 32;
    for (int32 Sample = 0; Sample <= PeakSamples; ++Sample)
    {
        const double Frame = FMath::Lerp(
            static_cast<double>(Passage->SegmentStartFrame.Value),
            static_cast<double>(Passage->SegmentEndFrame.Value),
            static_cast<double>(Sample) / PeakSamples);
        PeakSpeed = FMath::Max(PeakSpeed, SpeedAt(Frame, bFallback));
        double RawRate = 1.0;
        if (SpeedChannel)
        {
            SpeedChannel->Evaluate(FFrameTime::FromDecimal(Frame), RawRate);
            bNegativeRate |= RawRate < 0.0;
        }
    }

    FString ConstraintWarning;
    if (bFallback)
    {
        ConstraintWarning = TEXT("  ·  INVALID ZERO-RATE SPAN (linear fallback)");
    }
    else if (bNegativeRate)
    {
        ConstraintWarning = TEXT("  ·  negative rate clamped to zero");
    }

    return FText::FromString(FString::Printf(
        TEXT("actual %.2f m/s  ·  avg %.2f  ·  peak %.2f  ·  %d anchors%s"),
        CurrentSpeed,
        AverageMetresPerSecond,
        PeakSpeed,
        Section->PinnedWingCueGuids.Num() + Section->PinnedPassageFrames.Num() + 2,
        *ConstraintWarning));
}

void SInfinityStageCueDesk::RefreshPassageInspector()
{
    PassageProxy.Reset();
    if (!PassageDetails.IsValid())
    {
        return;
    }
    const FInfinityPassageSettings* Passage = GetSelectedPassage();
    if (!Passage || !ShowAsset.IsValid())
    {
        PassageDetails->SetObject(nullptr, true);
        if (SelectedPassageGuid.IsValid())
        {
            CueDetails->SetObject(nullptr, true);
        }
        return;
    }

    PassageProxy = TStrongObjectPtr<UInfinityStagePassageProxy>(
        NewObject<UInfinityStagePassageProxy>(GetTransientPackage(), NAME_None, RF_Transactional));
    PassageProxy->Initialize(ShowAsset.Get(), Passage->PassageGuid);
    PassageProxy->OnChanged.BindSP(this, &SInfinityStageCueDesk::HandleCueProxyChanged);
    PassageDetails->SetObject(PassageProxy.Get(), true);
    if (SelectedPassageGuid.IsValid())
    {
        // PASS is a first-class selection. Its passage-wide settings occupy the
        // ordinary selection inspector, while the right-hand Music/Fit/Route
        // workspace remains available for the same Passage.
        CueDetails->SetObject(PassageProxy.Get(), true);
    }
}

void SInfinityStageCueDesk::LoadFitFromSelectedPassage()
{
    const FInfinityPassageSettings* Passage = GetSelectedPassage();
    if (!Passage || !ShowAsset.IsValid())
    {
        return;
    }
    FitCameraSpeedCmPerSecond = Passage->PreferredCameraSpeedCmPerSecond;
    FitSpacingCm = Passage->PreferredSpacingCm;
    FitEntryClearanceCm = Passage->LeadInDistanceCm;
    FitExitClearanceCm = Passage->TailDistanceCm;
    if (const FInfinityMusicRail* Rail = ShowAsset->MusicRails.FindByPredicate([Passage](const FInfinityMusicRail& Candidate)
        { return Candidate.RailGuid == Passage->Music.PrimaryRailGuid; }))
    {
        const double TickRate = ShowAsset->TickResolution.AsDecimal();
        if (TickRate > 0.0 && Rail->SourceOutFrame > Rail->SourceInFrame)
        {
            FitDurationSeconds = (Rail->SourceOutFrame - Rail->SourceInFrame).Value / TickRate;
        }
        else if (const UInfinityStageMusicMapAsset* Map = Rail->AnalysisMap.LoadSynchronous())
        {
            FitDurationSeconds = Map->DurationSeconds;
        }
    }
}

void SInfinityStageCueDesk::HandleMusicScrub(const double NormalizedPosition, const bool bFinal)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Settings)
    {
        return;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    if (!Passage)
    {
        return;
    }
    if (EditorPreviewDirection != 0)
    {
        StopEditorPreviewPlayback();
    }
    EditorPreviewPassageGuid = Passage->PassageGuid;
    EditorPreviewNormalizedPosition = FMath::Clamp(NormalizedPosition, 0.0, 1.0);
    Invalidate(EInvalidateWidgetReason::Paint);
    PreviewMusicAtScrub(*Settings, *Passage, NormalizedPosition, bFinal);
    const int32 DurationFrames = FMath::Max(0, Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value);
    const FFrameNumber MasterFrame(static_cast<int32>(Passage->SegmentStartFrame.Value
        + FMath::RoundToInt(FMath::Clamp(NormalizedPosition, 0.0, 1.0) * DurationFrames)));

    EvaluateMasterFrameForPreview(Passage, MasterFrame, bFinal);
}

bool SInfinityStageCueDesk::EvaluateEditorPassageAtMasterFrame(
    const FInfinityCompiledPassage& Passage,
    const FFrameNumber MasterFrame)
{
    UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!EditorWorld)
    {
        return false;
    }
    AInfinityStageCameraRig* EvaluatedRig = nullptr;
    bool bFoundPassageActor = false;
    for (TActorIterator<AInfinityStageCameraRig> It(EditorWorld); It; ++It)
    {
        if (It->PassageActor && It->PassageActor->ShowAsset == ShowAsset.Get()
            && It->PassageActor->PassageGuid == Passage.PassageGuid
            && It->EvaluateAtMasterFrame(MasterFrame))
        {
            EvaluatedRig = *It;
            break;
        }
    }
    if (!EvaluatedRig)
    {
        for (TActorIterator<AInfinityStagePassageActor> It(EditorWorld); It; ++It)
        {
            if (It->ShowAsset == ShowAsset.Get() && It->PassageGuid == Passage.PassageGuid)
            {
                bFoundPassageActor = true;
                It->EvaluateMechanismsAtMasterFrame(MasterFrame);
                break;
            }
        }
    }
    if (ShowAsset.IsValid())
    {
        for (TActorIterator<AInfinityStageCelestialRig> It(EditorWorld); It; ++It)
        {
            It->EvaluateAtMasterFrame(ShowAsset.Get(), Passage.PassageGuid, MasterFrame);
        }
    }
    if (EvaluatedRig && bFollowMusicScrubInViewport)
    {
        FLevelEditorViewportClient* ViewportClient = GCurrentLevelEditingViewportClient;
        if (!ViewportClient && GEditor)
        {
            for (FLevelEditorViewportClient* Candidate : GEditor->GetLevelViewportClients())
            {
                if (Candidate && Candidate->IsPerspective())
                {
                    ViewportClient = Candidate;
                    break;
                }
            }
        }

        if (ViewportClient)
        {
            FMinimalViewInfo CameraView;
            if (EvaluatedRig->Camera)
            {
                EvaluatedRig->Camera->GetCameraView(0.0f, CameraView);
            }
            else
            {
                CameraView.Location = EvaluatedRig->GetActorLocation();
                CameraView.Rotation = EvaluatedRig->GetActorRotation();
                CameraView.FOV = ViewportClient->ViewFOV;
                CameraView.AspectRatio = ViewportClient->AspectRatio;
            }

            if (!SavedOverviewViewFOV.IsSet())
            {
                SavedOverviewViewFOV = ViewportClient->ViewFOV;
                SavedOverviewFOVAngle = ViewportClient->FOVAngle;
                SavedOverviewAspectRatio = ViewportClient->AspectRatio;
            }

            // This is deliberately an accurate but unpiloted camera match. The editor
            // viewport inherits the real Cine Camera component's view (including any
            // component-relative offset, filmback-derived FOV and aspect ratio) without
            // locking the artist into the camera actor.
            ViewportClient->SetActorLock(nullptr);
            ViewportClient->SetViewLocation(CameraView.Location);
            ViewportClient->SetViewRotation(CameraView.Rotation);
            ViewportClient->ViewFOV = CameraView.FOV;
            ViewportClient->FOVAngle = CameraView.FOV;
            if (CameraView.AspectRatio > 0.0f)
            {
                ViewportClient->AspectRatio = CameraView.AspectRatio;
            }
            ViewportClient->SetIsCameraCut();
            ViewportClient->Invalidate();
        }
    }
    return EvaluatedRig != nullptr || (!bFollowMusicScrubInViewport && bFoundPassageActor);
}

float SInfinityStageCueDesk::GetMusicPreviewVolume(
    const FInfinityMusicRail& Rail,
    const FInfinityCompiledPassage& Passage,
    const double NormalizedPosition) const
{
    const int32 PassageDurationFrames = FMath::Max(
        0,
        Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value);
    const int32 ElapsedFrames = FMath::RoundToInt(
        FMath::Clamp(NormalizedPosition, 0.0, 1.0) * PassageDurationFrames);
    float Volume = 1.0f;
    if (Rail.FadeInFrames.Value > 0 && ElapsedFrames < Rail.FadeInFrames.Value)
    {
        Volume *= FMath::Clamp(
            static_cast<float>(ElapsedFrames) / Rail.FadeInFrames.Value,
            0.0f,
            1.0f);
    }
    const int32 RemainingFrames = PassageDurationFrames - ElapsedFrames;
    if (Rail.FadeOutFrames.Value > 0 && RemainingFrames < Rail.FadeOutFrames.Value)
    {
        Volume *= FMath::Clamp(
            static_cast<float>(RemainingFrames) / Rail.FadeOutFrames.Value,
            0.0f,
            1.0f);
    }
    return Volume;
}

void SInfinityStageCueDesk::PreviewMusicAtScrub(
    const FInfinityPassageSettings& Settings,
    const FInfinityCompiledPassage& Passage,
    const double NormalizedPosition,
    const bool bFinal)
{
    if (bFinal || !bAudibleMusicScrub || !GEditor || !ShowAsset.IsValid())
    {
        StopMusicScrubPreview();
        return;
    }

    const FInfinityMusicRail* Rail = ShowAsset->MusicRails.FindByPredicate([&Settings](const FInfinityMusicRail& Candidate)
    {
        return Candidate.RailGuid == Settings.Music.PrimaryRailGuid;
    });
    USoundBase* Sound = Rail ? Rail->Sound.LoadSynchronous() : nullptr;
    const double TickRate = ShowAsset->TickResolution.AsDecimal();
    if (!Rail || !Sound || TickRate <= 0.0)
    {
        StopMusicScrubPreview();
        return;
    }

    const int32 PassageDurationFrames = FMath::Max(
        0,
        Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value);
    const int32 ElapsedFrames = FMath::RoundToInt(
        FMath::Clamp(NormalizedPosition, 0.0, 1.0) * PassageDurationFrames);
    const int32 SourceFrame = Rail->SourceInFrame.Value
        + Settings.Music.RailOffsetFrames.Value
        + ElapsedFrames;
    if ((Rail->SourceOutFrame.Value > Rail->SourceInFrame.Value && SourceFrame >= Rail->SourceOutFrame.Value)
        || SourceFrame < 0)
    {
        StopMusicScrubPreview();
        return;
    }

    const double SourceSeconds = SourceFrame / TickRate;
    const double Now = FPlatformTime::Seconds();
    const bool bDifferentRail = MusicScrubPreviewRailGuid != Rail->RailGuid;
    const bool bCursorMoved = FMath::Abs(SourceSeconds - LastMusicScrubPreviewSourceSeconds) >= 0.035;
    const bool bRestartDue = LastMusicScrubPreviewWallSeconds < 0.0
        || Now - LastMusicScrubPreviewWallSeconds >= 0.075;
    if (!bDifferentRail && MusicScrubPreviewComponent.IsValid() && (!bCursorMoved || !bRestartDue))
    {
        return;
    }

    UAudioComponent* Preview = GEditor->ResetPreviewAudioComponent(Sound);
    if (!Preview)
    {
        StopMusicScrubPreview();
        return;
    }
    Preview->SetVolumeMultiplier(GetMusicPreviewVolume(*Rail, Passage, NormalizedPosition));
    Preview->Play(static_cast<float>(SourceSeconds));
    MusicScrubPreviewComponent = Preview;
    MusicScrubPreviewRailGuid = Rail->RailGuid;
    LastMusicScrubPreviewWallSeconds = Now;
    LastMusicScrubPreviewSourceSeconds = SourceSeconds;
}

void SInfinityStageCueDesk::StopMusicScrubPreview()
{
    if (MusicScrubPreviewComponent.IsValid())
    {
        MusicScrubPreviewComponent->Stop();
    }
    MusicScrubPreviewComponent.Reset();
    MusicScrubPreviewRailGuid.Invalidate();
    LastMusicScrubPreviewWallSeconds = -1.0;
    LastMusicScrubPreviewSourceSeconds = -1.0;
}

void SInfinityStageCueDesk::StartEditorPreviewPlayback(const int32 Direction)
{
    if (!ShowAsset.IsValid() || Direction == 0)
    {
        return;
    }
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Settings)
    {
        return;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([Settings](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == Settings->PassageGuid;
    });
    if (!Passage)
    {
        return;
    }

    if (EditorPreviewPassageGuid != Passage->PassageGuid || EditorPreviewNormalizedPosition < 0.0)
    {
        EditorPreviewNormalizedPosition = Direction > 0 ? 0.0 : 1.0;
    }
    else if (Direction > 0 && EditorPreviewNormalizedPosition >= 1.0)
    {
        EditorPreviewNormalizedPosition = 0.0;
    }
    else if (Direction < 0 && EditorPreviewNormalizedPosition <= 0.0)
    {
        EditorPreviewNormalizedPosition = 1.0;
    }

    const int32 DurationFrames = FMath::Max(
        0,
        Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value);
    EditorPreviewPassageGuid = Passage->PassageGuid;
    EditorPreviewStartMasterFrame = FFrameNumber(static_cast<int32>(
        Passage->SegmentStartFrame.Value
        + FMath::RoundToInt(EditorPreviewNormalizedPosition * DurationFrames)));
    EditorPreviewStartWallSeconds = FPlatformTime::Seconds();
    EditorPreviewDirection = Direction > 0 ? 1 : -1;
    StopMusicScrubPreview();
    if (EditorPreviewDirection > 0 && bAudibleMusicScrub)
    {
        PreviewMusicAtScrub(*Settings, *Passage, EditorPreviewNormalizedPosition, false);
    }
    EvaluateEditorPassageAtMasterFrame(*Passage, EditorPreviewStartMasterFrame);

    if (!bEditorPreviewTimerRegistered)
    {
        bEditorPreviewTimerRegistered = true;
        RegisterActiveTimer(0.0f, FWidgetActiveTimerDelegate::CreateSP(
            this,
            &SInfinityStageCueDesk::HandleEditorPreviewPlayback));
    }
    Invalidate(EInvalidateWidgetReason::Paint);
}

void SInfinityStageCueDesk::StopEditorPreviewPlayback()
{
    EditorPreviewDirection = 0;
    StopMusicScrubPreview();
    Invalidate(EInvalidateWidgetReason::Paint);
}

EActiveTimerReturnType SInfinityStageCueDesk::HandleEditorPreviewPlayback(double, float)
{
    if (EditorPreviewDirection == 0 || !ShowAsset.IsValid())
    {
        bEditorPreviewTimerRegistered = false;
        return EActiveTimerReturnType::Stop;
    }
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!Settings || Settings->PassageGuid != EditorPreviewPassageGuid)
    {
        StopEditorPreviewPlayback();
        bEditorPreviewTimerRegistered = false;
        return EActiveTimerReturnType::Stop;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([this](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == EditorPreviewPassageGuid;
    });
    const double TickRate = ShowAsset->TickResolution.AsDecimal();
    if (!Passage || TickRate <= 0.0)
    {
        StopEditorPreviewPlayback();
        bEditorPreviewTimerRegistered = false;
        return EActiveTimerReturnType::Stop;
    }

    const int32 ElapsedFrames = FMath::RoundToInt(
        (FPlatformTime::Seconds() - EditorPreviewStartWallSeconds) * TickRate);
    const int32 UnclampedFrame = EditorPreviewStartMasterFrame.Value
        + EditorPreviewDirection * ElapsedFrames;
    const int32 CurrentFrame = FMath::Clamp(
        UnclampedFrame,
        Passage->SegmentStartFrame.Value,
        Passage->SegmentEndFrame.Value);
    const int32 DurationFrames = FMath::Max(
        1,
        Passage->SegmentEndFrame.Value - Passage->SegmentStartFrame.Value);
    EditorPreviewNormalizedPosition = static_cast<double>(
        CurrentFrame - Passage->SegmentStartFrame.Value) / DurationFrames;
    EvaluateEditorPassageAtMasterFrame(*Passage, FFrameNumber(CurrentFrame));

    if (EditorPreviewDirection > 0 && MusicScrubPreviewComponent.IsValid())
    {
        if (const FInfinityMusicRail* Rail = ShowAsset->MusicRails.FindByPredicate([Settings](const FInfinityMusicRail& Candidate)
            { return Candidate.RailGuid == Settings->Music.PrimaryRailGuid; }))
        {
            MusicScrubPreviewComponent->SetVolumeMultiplier(
                GetMusicPreviewVolume(*Rail, *Passage, EditorPreviewNormalizedPosition));
        }
    }
    Invalidate(EInvalidateWidgetReason::Paint);

    const bool bAtBoundary = EditorPreviewDirection > 0
        ? CurrentFrame >= Passage->SegmentEndFrame.Value
        : CurrentFrame <= Passage->SegmentStartFrame.Value;
    if (bAtBoundary)
    {
        StopEditorPreviewPlayback();
        bEditorPreviewTimerRegistered = false;
        return EActiveTimerReturnType::Stop;
    }
    return EActiveTimerReturnType::Continue;
}

FReply SInfinityStageCueDesk::OnKeyDown(const FGeometry& Geometry, const FKeyEvent& KeyEvent)
{
    // Bare Space only. Modified chords stay available for other bindings.
    if (KeyEvent.GetKey() == EKeys::SpaceBar
        && !KeyEvent.IsControlDown()
        && !KeyEvent.IsCommandDown()
        && !KeyEvent.IsAltDown()
        && !KeyEvent.IsShiftDown()
        && !KeyEvent.IsRepeat())
    {
        // Route through the transport command so PIE performance constraints,
        // such as an externally unpausable Scene, still reject the pause.
        RunTransportCommand(IsPlaybackRunning() ? 2 : 3);
        return FReply::Handled();
    }

    // Left/Right step whole segments — Passage to Scene to Passage — rather than
    // individual wings, which is the granularity an operator rehearses at.
    if ((KeyEvent.GetKey() == EKeys::Left || KeyEvent.GetKey() == EKeys::Right)
        && !KeyEvent.IsControlDown()
        && !KeyEvent.IsCommandDown()
        && !KeyEvent.IsAltDown()
        && !KeyEvent.IsShiftDown())
    {
        RunTransportCommand(KeyEvent.GetKey() == EKeys::Left ? 5 : 6);
        return FReply::Handled();
    }
    return SCompoundWidget::OnKeyDown(Geometry, KeyEvent);
}

bool SInfinityStageCueDesk::IsPlaybackRunning() const
{
    if (EditorPreviewDirection != 0)
    {
        return true;
    }
    if (!ShowAsset.IsValid() || !GEngine)
    {
        return false;
    }
    // During PIE the Show Root owns playback, so the editor preview direction
    // stays zero and the real player has to be asked.
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType != EWorldType::PIE || !Context.World())
        {
            continue;
        }
        for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
        {
            if (It->ShowAsset == ShowAsset.Get() && It->Transport && It->Transport->IsTransportPlaying())
            {
                return true;
            }
        }
    }
    return false;
}

bool SInfinityStageCueDesk::GetCueDeskPlayheadFrame(FFrameNumber& OutFrame) const
{
    if (!ShowAsset.IsValid())
    {
        return false;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);

    // Prefer the music-timeline position, which is what the operator is looking
    // at; fall back to the selected row's segment start.
    if (EditorPreviewNormalizedPosition >= 0.0 && EditorPreviewPassageGuid.IsValid())
    {
        if (const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
            [this](const FInfinityCompiledPassage& Candidate)
            { return Candidate.PassageGuid == EditorPreviewPassageGuid; }))
        {
            OutFrame = FFrameNumber(static_cast<int32>(FMath::RoundToInt(FMath::Lerp(
                static_cast<double>(Passage->SegmentStartFrame.Value),
                static_cast<double>(Passage->SegmentEndFrame.Value),
                FMath::Clamp(EditorPreviewNormalizedPosition, 0.0, 1.0)))));
            return true;
        }
    }

    const int32 SelectedIndex = GetPrimarySelectedIndex();
    if (ShowAsset->Cues.IsValidIndex(SelectedIndex))
    {
        const FGuid SelectedGuid = ShowAsset->Cues[SelectedIndex].CueGuid;
        for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
        {
            if (Segment.SegmentGuid == SelectedGuid
                || (SelectedIndex >= Segment.FirstCueIndex && SelectedIndex <= Segment.LastCueIndex))
            {
                OutFrame = Segment.StartFrame;
                return true;
            }
        }
    }
    return false;
}

void SInfinityStageCueDesk::HandlePostPieStarted(const bool bIsSimulating)
{
    if (!bPieStartsAtPlayhead || bIsSimulating || !ShowAsset.IsValid() || !GEngine)
    {
        return;
    }
    FFrameNumber StartFrame;
    if (!GetCueDeskPlayheadFrame(StartFrame) || StartFrame.Value <= 0)
    {
        return;
    }

    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType != EWorldType::PIE || !Context.World())
        {
            continue;
        }
        for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
        {
            // Only when PIE is running the same Show the desk is editing;
            // otherwise the frame means nothing in that Show's timeline.
            if (It->ShowAsset != ShowAsset.Get() || !It->Transport)
            {
                continue;
            }
            ApplyRehearsalTransportToLivePIE();
            EInfinityTransportResult Result = It->Transport->ScrubToMasterFrame(StartFrame);
            // Starting at the rehearsal playhead must respect the Show's
            // autoplay preference; ScrubToMasterFrame deliberately pauses.
            if (Result == EInfinityTransportResult::Succeeded && It->PlaybackSettings.bAutoPlay)
            {
                Result = bPlayThroughBoundaries
                    ? It->Transport->PlayForwardThroughBoundaries()
                    : It->Transport->PlayForwardToBoundary();
            }
            UE_LOG(
                LogTemp,
                Display,
                TEXT("INFINITY_STAGE_PIE_START_AT_PLAYHEAD frame=%d result=%d"),
                StartFrame.Value,
                static_cast<int32>(Result));
            if (Result != EInfinityTransportResult::Succeeded)
            {
                NotifyCueDesk(
                    TEXT("PIE could not start at the Cue Desk playhead; it began at the Show start instead."),
                    SNotificationItem::CS_Fail);
            }
            return;
        }
    }
}

void SInfinityStageCueDesk::BuildLiveCameraOwnerMenu(FMenuBuilder& MenuBuilder)
{
    auto AddEntry = [this, &MenuBuilder](const FText& Label, const FText& Tip, const bool bOverride, const EInfinityCameraOwner Owner)
    {
        MenuBuilder.AddMenuEntry(
            Label,
            Tip,
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateSP(this, &SInfinityStageCueDesk::SetLiveCameraOwner, bOverride, Owner),
                FCanExecuteAction(),
                FIsActionChecked::CreateSP(this, &SInfinityStageCueDesk::IsLiveCameraOwner, bOverride, Owner)),
            NAME_None,
            EUserInterfaceActionType::RadioButton);
    };
    AddEntry(
        NSLOCTEXT("InfinityStage", "OwnerFollowShow", "Follow Show"),
        NSLOCTEXT("InfinityStage", "OwnerFollowShowTip", "Use each Passage's and Scene's authored Camera Owner."),
        false,
        EInfinityCameraOwner::Timeline);
    MenuBuilder.AddSeparator();
    AddEntry(
        NSLOCTEXT("InfinityStage", "OwnerForceTimeline", "Force Timeline"),
        NSLOCTEXT("InfinityStage", "OwnerForceTimelineTip", "Take the camera back from external telemetry for the rest of this session."),
        true,
        EInfinityCameraOwner::Timeline);
    AddEntry(
        NSLOCTEXT("InfinityStage", "OwnerForceDog", "Force Dog"),
        NSLOCTEXT("InfinityStage", "OwnerForceDogTip", "Give look control to external telemetry for rehearsal, everywhere except Sequence cues (the Opening, the Interactions, the Closing), which stay on their authored owner so the camera cannot swing behind the curtain while the dog is walked."),
        true,
        EInfinityCameraOwner::DogFreeLook);
    AddEntry(
        NSLOCTEXT("InfinityStage", "OwnerForceGaze", "Force Dog (Gaze Only)"),
        NSLOCTEXT("InfinityStage", "OwnerForceGazeTip", "External look within the authored gaze limits only. Like Force Dog, it does not apply inside Sequence cues."),
        true,
        EInfinityCameraOwner::DogGazeOnly);
}

void SInfinityStageCueDesk::SetLiveCameraOwner(const bool bOverride, const EInfinityCameraOwner Owner)
{
    int32 Applied = 0;
    if (GEngine && ShowAsset.IsValid())
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            if (Context.WorldType != EWorldType::PIE || !Context.World())
            {
                continue;
            }
            for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
            {
                if (It->ShowAsset != ShowAsset.Get())
                {
                    continue;
                }
                It->bOverrideCameraOwner = bOverride;
                It->CameraOwnerOverride = Owner;
                ++Applied;
            }
        }
    }
    LiveCameraOwnerOverride = bOverride;
    LiveCameraOwner = Owner;
    NotifyCueDesk(
        bOverride
            ? FString::Printf(TEXT("Live camera owner overridden (%d Show Root(s)). The Show is unchanged."), Applied)
            : FString::Printf(TEXT("Following authored camera ownership again (%d Show Root(s))."), Applied),
        SNotificationItem::CS_Success);
}

bool SInfinityStageCueDesk::IsLiveCameraOwner(const bool bOverride, const EInfinityCameraOwner Owner) const
{
    return bOverride ? (LiveCameraOwnerOverride && LiveCameraOwner == Owner) : !LiveCameraOwnerOverride;
}

bool SInfinityStageCueDesk::IsRehearsalTransportEnabled() const
{
    return bRehearsalTransport;
}

void SInfinityStageCueDesk::ToggleRehearsalTransport()
{
    bRehearsalTransport = !bRehearsalTransport;
    GConfig->SetBool(
        TEXT("InfinityStage.CueDesk"),
        TEXT("RehearsalTransport"),
        bRehearsalTransport,
        GEditorPerProjectIni);
    GConfig->Flush(false, GEditorPerProjectIni);
    const int32 Applied = ApplyRehearsalTransportToLivePIE();
    NotifyCueDesk(
        bRehearsalTransport
            ? FString::Printf(
                TEXT("Rehearsal transport enabled; external sound locks ignored (%d live transport(s) updated)."),
                Applied)
            : FString::Printf(
                TEXT("Performance transport restored; declared external sound locks apply again (%d live transport(s) updated)."),
                Applied),
        SNotificationItem::CS_Success);
    Invalidate(EInvalidateWidgetReason::Paint);
}

int32 SInfinityStageCueDesk::ApplyRehearsalTransportToLivePIE() const
{
    if (!ShowAsset.IsValid() || !GEngine)
    {
        return 0;
    }
    // PIE creates a fresh transport per session, so the preference is pushed
    // whenever it changes and again before every transport command.
    int32 Applied = 0;
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType != EWorldType::PIE || !Context.World())
        {
            continue;
        }
        for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
        {
            if (It->ShowAsset == ShowAsset.Get() && It->Transport)
            {
                It->Transport->bPerformanceMode = !bRehearsalTransport;
                ++Applied;
            }
        }
    }
    return Applied;
}

bool SInfinityStageCueDesk::CanCueAndPlaySelectedSegment() const
{
    if (!ShowAsset.IsValid())
    {
        return false;
    }
    const int32 CueIndex = GetPrimarySelectedIndex();
    return ShowAsset->Cues.IsValidIndex(CueIndex)
        && ShowAsset->Cues[CueIndex].Type != EInfinityCueType::WingPair
        && !ShowAsset->Cues[CueIndex].Scene.Sequence.IsNull();
}

void SInfinityStageCueDesk::CueAndPlaySelectedSegment()
{
    if (!CanCueAndPlaySelectedSegment() || !GEngine)
    {
        NotifyCueDesk(
            TEXT("Select one Scene or SEQ row before using Play Selected."),
            SNotificationItem::CS_Fail);
        return;
    }

    const int32 CueIndex = GetPrimarySelectedIndex();
    const FInfinityShowCue& Cue = ShowAsset->Cues[CueIndex];
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledSegment* Segment = Compiled.Segments.FindByPredicate(
        [&Cue](const FInfinityCompiledSegment& Candidate)
        {
            return Candidate.SegmentGuid == Cue.CueGuid;
        });
    if (!Segment)
    {
        NotifyCueDesk(
            TEXT("The selected Scene/SEQ has no compiled Master segment."),
            SNotificationItem::CS_Fail);
        return;
    }

    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType != EWorldType::PIE || !Context.World())
        {
            continue;
        }
        for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
        {
            if (It->ShowAsset != ShowAsset.Get() || !It->Transport)
            {
                continue;
            }

            // This button is an explicit rehearsal action. Make the state
            // visible and persistent so subsequent cue selection/scrubbing
            // remains reliable until the operator turns Rehearsal off.
            if (!bRehearsalTransport)
            {
                bRehearsalTransport = true;
                GConfig->SetBool(
                    TEXT("InfinityStage.CueDesk"),
                    TEXT("RehearsalTransport"),
                    true,
                    GEditorPerProjectIni);
                GConfig->Flush(false, GEditorPerProjectIni);
            }
            ApplyRehearsalTransportToLivePIE();
            StopEditorPreviewPlayback();

            EInfinityTransportResult Result =
                It->Transport->ScrubToMasterFrame(Segment->StartFrame);
            if (Result == EInfinityTransportResult::Succeeded)
            {
                Result = It->Transport->PlayForwardToBoundary();
            }
            if (Result != EInfinityTransportResult::Succeeded)
            {
                NotifyCueDesk(
                    FString::Printf(
                        TEXT("Play Selected failed for %s: %s"),
                        *Cue.Label.ToString(),
                        *StaticEnum<EInfinityTransportResult>()->GetDisplayNameTextByValue(
                            static_cast<int64>(Result)).ToString()),
                    SNotificationItem::CS_Fail);
                return;
            }

            NotifyCueDesk(
                FString::Printf(
                    TEXT("Rehearsing %s from its exact start to its boundary."),
                    *Cue.Label.ToString()),
                SNotificationItem::CS_Success);
            Invalidate(EInvalidateWidgetReason::Paint);
            return;
        }
    }

    NotifyCueDesk(
        TEXT("Play Selected requires PIE running the same Show as the Cue Desk."),
        SNotificationItem::CS_Fail);
}

void SInfinityStageCueDesk::RunTransportCommand(const int32 Command)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    ApplyRehearsalTransportToLivePIE();
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.WorldType != EWorldType::PIE || !Context.World())
        {
            continue;
        }
        for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
        {
            if (It->ShowAsset != ShowAsset.Get() || !It->Transport)
            {
                continue;
            }
            StopEditorPreviewPlayback();
            EInfinityTransportResult Result = EInfinityTransportResult::Succeeded;
            switch (Command)
            {
            case 0: Result = It->Transport->JumpToCurrentStart(); break;
            case 1: Result = It->Transport->PlayReverseToBoundary(); break;
            case 2: Result = It->Transport->PauseTransport(); break;
            case 3:
                Result = bPlayThroughBoundaries
                    ? It->Transport->PlayForwardThroughBoundaries()
                    : It->Transport->PlayForwardToBoundary();
                break;
            case 4: Result = It->Transport->JumpToCurrentEnd(); break;
            case 5: Result = It->Transport->JumpToPreviousSegment(); break;
            case 6: Result = It->Transport->AdvanceToNextSegment(); break;
            default: break;
            }
            if (Result != EInfinityTransportResult::Succeeded)
            {
                NotifyCueDesk(
                    FString::Printf(TEXT("Operator transport did not move: %s"),
                        *StaticEnum<EInfinityTransportResult>()->GetDisplayNameTextByValue(
                            static_cast<int64>(Result)).ToString()),
                    SNotificationItem::CS_Fail);
            }
            return;
        }
    }
    switch (Command)
    {
    case 0:
        StopEditorPreviewPlayback();
        EditorPreviewNormalizedPosition = 0.0;
        HandleMusicScrub(0.0, true);
        break;
    case 1: StartEditorPreviewPlayback(-1); break;
    case 2: StopEditorPreviewPlayback(); break;
    case 3: StartEditorPreviewPlayback(1); break;
    case 4:
        StopEditorPreviewPlayback();
        EditorPreviewNormalizedPosition = 1.0;
        HandleMusicScrub(1.0, true);
        break;
    case 5: JumpEditorPreviewToAdjacentSegment(-1); break;
    case 6: JumpEditorPreviewToAdjacentSegment(1); break;
    default: break;
    }
}

void SInfinityStageCueDesk::JumpEditorPreviewToAdjacentSegment(const int32 Direction)
{
    if (!ShowAsset.IsValid() || Direction == 0)
    {
        return;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    if (Compiled.Segments.IsEmpty())
    {
        return;
    }

    int32 CurrentSegmentIndex = INDEX_NONE;
    if (SelectedPassageGuid.IsValid())
    {
        CurrentSegmentIndex = Compiled.Segments.IndexOfByPredicate([this](const FInfinityCompiledSegment& Segment)
        {
            return Segment.SegmentGuid == SelectedPassageGuid;
        });
    }
    if (CurrentSegmentIndex == INDEX_NONE)
    {
        const int32 CueIndex = GetPrimarySelectedIndex();
        if (ShowAsset->Cues.IsValidIndex(CueIndex))
        {
            const FGuid CueGuid = ShowAsset->Cues[CueIndex].CueGuid;
            CurrentSegmentIndex = Compiled.Segments.IndexOfByPredicate([CueGuid](const FInfinityCompiledSegment& Segment)
            {
                return Segment.Type != EInfinityCueType::WingPair
                    && Segment.SegmentGuid == CueGuid;
            });
            if (ShowAsset->Cues[CueIndex].Type == EInfinityCueType::WingPair)
            {
                CurrentSegmentIndex = Compiled.Segments.IndexOfByPredicate([CueIndex](const FInfinityCompiledSegment& Segment)
                {
                    return Segment.Type == EInfinityCueType::WingPair
                        && CueIndex >= Segment.FirstCueIndex && CueIndex <= Segment.LastCueIndex;
                });
            }
        }
    }

    const int32 TargetIndex = FMath::Clamp(
        (CurrentSegmentIndex == INDEX_NONE ? (Direction > 0 ? -1 : Compiled.Segments.Num()) : CurrentSegmentIndex)
            + FMath::Sign(Direction),
        0,
        Compiled.Segments.Num() - 1);
    if (TargetIndex == CurrentSegmentIndex || !Compiled.Segments.IsValidIndex(TargetIndex))
    {
        return;
    }

    StopEditorPreviewPlayback();
    const FInfinityCompiledSegment& Target = Compiled.Segments[TargetIndex];
    SelectedPassageGuid = Target.Type == EInfinityCueType::WingPair ? Target.SegmentGuid : FGuid();
    RefreshFromAsset(true);

    FCueItem TargetItem;
    if (Target.Type == EInfinityCueType::WingPair)
    {
        if (bNestedCueMode)
        {
            if (const FCueItem* Header = CueItems.FindByPredicate([&Target](const FCueItem& Item)
                { return Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::PassageHeader
                    && Item->PassageGuid == Target.SegmentGuid; }))
            {
                TargetItem = *Header;
            }
        }
        if (!TargetItem.IsValid())
        {
            if (const FCueItem* FirstCue = CueItems.FindByPredicate([&Target](const FCueItem& Item)
                { return Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::Cue
                    && Item->CueIndex == Target.FirstCueIndex; }))
            {
                TargetItem = *FirstCue;
            }
        }
    }
    else if (const FCueItem* SceneItem = CueItems.FindByPredicate([&Target](const FCueItem& Item)
        { return Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::Cue
            && Item->CueIndex == Target.FirstCueIndex; }))
    {
        TargetItem = *SceneItem;
    }

    if (TargetItem.IsValid() && CueList.IsValid())
    {
        CueList->SetSelection(TargetItem, ESelectInfo::Direct);
        CueList->RequestScrollIntoView(TargetItem);
    }
    if (Target.Type == EInfinityCueType::WingPair)
    {
        const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([&Target](const FInfinityCompiledPassage& Candidate)
        {
            return Candidate.PassageGuid == Target.SegmentGuid;
        });
        EditorPreviewNormalizedPosition = 0.0;
        EditorPreviewPassageGuid = Target.SegmentGuid;
        EvaluateMasterFrameForPreview(Passage, Target.StartFrame, true);
    }
    else
    {
        EditorPreviewNormalizedPosition = -1.0;
        EditorPreviewPassageGuid.Invalidate();
        NotifyCueDesk(TEXT("Scene selected. In PIE the operator transport claims its Camera Cut; in editor, open its purple Scene block or use Open Scene Sequence."), SNotificationItem::CS_Success);
    }
}

void SInfinityStageCueDesk::AddCue(const EInfinityCueType Type)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    ApplyListMutation(NSLOCTEXT("InfinityStage", "AddCueTransaction", "Add Infinity Stage Cue"), [this, Type](TArray<int32>& NewSelection)
    {
        const int32 Selected = GetPrimarySelectedIndex();
        const int32 InsertIndex = Selected == INDEX_NONE ? ShowAsset->Cues.Num() : Selected + 1;
        FInfinityShowCue Cue;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Type = Type;
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        ShowAsset->Cues.Insert(Cue, InsertIndex);
        NewSelection.Add(InsertIndex);
    });
}

void SInfinityStageCueDesk::DuplicateSelected()
{
    ApplyListMutation(NSLOCTEXT("InfinityStage", "DuplicateCueTransaction", "Duplicate Infinity Stage Cues"), [this](TArray<int32>& NewSelection)
    {
        TArray<int32> Selected;
        for (const FCueItem& Item : CueList->GetSelectedItems())
        {
            if (Item.IsValid() && ShowAsset->Cues.IsValidIndex(Item->CueIndex))
            {
                Selected.Add(Item->CueIndex);
            }
        }
        Selected.Sort();
        if (Selected.IsEmpty())
        {
            return;
        }
        int32 InsertIndex = Selected.Last() + 1;
        for (const int32 SourceIndex : Selected)
        {
            FInfinityShowCue Copy = ShowAsset->Cues[SourceIndex];
            Copy.CueGuid = FGuid::NewGuid();
            if (Copy.Type == EInfinityCueType::WingPair)
            {
                Copy.WingPair.OccurrenceGuid = FGuid::NewGuid();
            }
            ShowAsset->Cues.Insert(Copy, InsertIndex);
            NewSelection.Add(InsertIndex++);
        }
    });
}

void SInfinityStageCueDesk::DeleteSelected()
{
    ApplyListMutation(NSLOCTEXT("InfinityStage", "DeleteCueTransaction", "Delete Infinity Stage Cues"), [this](TArray<int32>& NewSelection)
    {
        TArray<int32> Selected;
        for (const FCueItem& Item : CueList->GetSelectedItems())
        {
            if (Item.IsValid() && ShowAsset->Cues.IsValidIndex(Item->CueIndex))
            {
                Selected.Add(Item->CueIndex);
            }
        }
        Selected.Sort(TGreater<int32>());
        for (const int32 Index : Selected)
        {
            ShowAsset->Cues.RemoveAt(Index);
        }
        if (!ShowAsset->Cues.IsEmpty())
        {
            NewSelection.Add(FMath::Clamp(Selected.IsEmpty() ? 0 : Selected.Last(), 0, ShowAsset->Cues.Num() - 1));
        }
    });
}

void SInfinityStageCueDesk::MoveSelected(const int32 Delta)
{
    ApplyListMutation(NSLOCTEXT("InfinityStage", "MoveCueTransaction", "Move Infinity Stage Cue"), [this, Delta](TArray<int32>& NewSelection)
    {
        const int32 Source = GetPrimarySelectedIndex();
        const int32 Target = Source + Delta;
        if (!ShowAsset->Cues.IsValidIndex(Source) || !ShowAsset->Cues.IsValidIndex(Target))
        {
            return;
        }
        ShowAsset->Cues.Swap(Source, Target);
        NewSelection.Add(Target);
    });
}

void SInfinityStageCueDesk::RefitSelectedPassageFromMusic()
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    // The former Fit tab kept editable shadow values. The Passage/Music
    // inspector is now the single authoring surface, so always re-read those
    // authoritative saved values immediately before deriving the count.
    LoadFitFromSelectedPassage();
    const FInfinityPassageFitResult Fit = FInfinityStageCompiler::FitPassage({
        FitDurationSeconds,
        FitCameraSpeedCmPerSecond,
        FitSpacingCm,
        FitEntryClearanceCm,
        FitExitClearanceCm});
    if (!Fit.bValid)
    {
        NotifyCueDesk(Fit.Error, SNotificationItem::CS_Fail);
        return;
    }
    const FInfinityPassageSettings* SelectedPassage = GetSelectedPassage();
    if (!SelectedPassage)
    {
        NotifyCueDesk(TEXT("Select a Passage heading or one of its Wing Pair rows first."),
            SNotificationItem::CS_Fail);
        return;
    }
    const FGuid PassageGuid = SelectedPassage->PassageGuid;
    const int32 IntervalFrames = FMath::Max(1, FMath::RoundToInt(
        (FitSpacingCm / FitCameraSpeedCmPerSecond) * ShowAsset->TickResolution.AsDecimal()));

    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "RefitPassageTransaction", "Refit Passage From Music"));
    ShowAsset->Modify();
    TArray<int32> AffectedIndices;
    FString Report;
    if (!FInfinityStageWingSequenceInterchange::ResizePassageToCountPreservingPattern(
        *ShowAsset,
        PassageGuid,
        Fit.WingPairCount,
        FFrameNumber(IntervalFrames),
        FitSpacingCm,
        AffectedIndices,
        Report))
    {
        NotifyCueDesk(Report, SNotificationItem::CS_Fail);
        return;
    }

    if (FInfinityPassageSettings* Settings = ShowAsset->PassageSettings.FindByPredicate(
        [PassageGuid](const FInfinityPassageSettings& Candidate)
        {
            return Candidate.PassageGuid == PassageGuid;
        }))
    {
        Settings->FitMode = EInfinityPassageFitMode::MusicLockedDeriveCount;
        Settings->PreferredCameraSpeedCmPerSecond = FitCameraSpeedCmPerSecond;
        Settings->PreferredSpacingCm = FitSpacingCm;
        Settings->LeadInDistanceCm = FitEntryClearanceCm;
        Settings->TailDistanceCm = FitExitClearanceCm;
        Settings->LeadInFrames = FFrameNumber(static_cast<int32>(FMath::Max<int64>(0, FMath::RoundToInt(
            (FitEntryClearanceCm / FitCameraSpeedCmPerSecond) * ShowAsset->TickResolution.AsDecimal()))));
        Settings->TailFrames = FFrameNumber(static_cast<int32>(FMath::Max<int64>(0, FMath::RoundToInt(
            (FitExitClearanceCm / FitCameraSpeedCmPerSecond) * ShowAsset->TickResolution.AsDecimal()))));
    }
    RenumberDefaultLabels();
    ShowAsset->MarkPackageDirty();

    RefreshPassagesInEditorWorld({ PassageGuid });
    if (!ShowAsset->ManagedMasterSequence.IsNull())
    {
        FString MasterReport;
        if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(
            ShowAsset.Get(), ShowAsset->ManagedMasterSequence.LoadSynchronous(), MasterReport))
        {
            UE_LOG(LogTemp, Error, TEXT("Music-fit count reset succeeded, but managed Master rebuild failed: %s"), *MasterReport);
            NotifyCueDesk(TEXT("Wing count reset, but the managed Master rebuild failed. See Output Log."),
                SNotificationItem::CS_Fail);
        }
    }

    SelectedPassageGuid = PassageGuid;
    RefreshFromAsset(true);
    UE_LOG(LogTemp, Display,
        TEXT("INFINITY_STAGE_MUSIC_FIT_COUNT_OK passage=%s count=%d interval_frames=%d spacing_cm=%.3f report='%s'"),
        *PassageGuid.ToString(), Fit.WingPairCount, IntervalFrames, FitSpacingCm, *Report);
    NotifyCueDesk(Report, SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::RebuildManagedMaster()
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    ULevelSequence* Master = ShowAsset->ManagedMasterSequence.LoadSynchronous();
    FString Report;
    if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(ShowAsset.Get(), Master, Report))
    {
        UE_LOG(LogTemp, Error, TEXT("Infinity Stage Master rebuild failed: %s"), *Report);
        return;
    }
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage Master: %s"), *Report);
}

bool SInfinityStageCueDesk::CanRenderSelectedRange() const
{
    if (!ShowAsset.IsValid() || ShowAsset->ManagedMasterSequence.IsNull())
    {
        return false;
    }
    if (SelectedPassageGuid.IsValid())
    {
        return true;
    }
    if (!CueList.IsValid())
    {
        return false;
    }
    return CueList->GetSelectedItems().ContainsByPredicate([](const FCueItem& Item)
    {
        return Item.IsValid()
            && Item->NodeType == EInfinityCueListNodeType::Cue
            && Item->CueIndex != INDEX_NONE;
    });
}

void SInfinityStageCueDesk::RenderSelectedRange()
{
    if (!CanRenderSelectedRange() || !GEditor)
    {
        NotifyCueDesk(TEXT("Select one or more Cues, or a Passage heading, before rendering."), SNotificationItem::CS_Fail);
        return;
    }

    UInfinityStageShowAsset* Show = ShowAsset.Get();
    ULevelSequence* Master = Show->ManagedMasterSequence.LoadSynchronous();
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!Master || !World || World->GetOutermost()->GetName().StartsWith(TEXT("/Temp/Untitled")))
    {
        NotifyCueDesk(TEXT("A saved Master Sequence and saved current level are required for Movie Render Queue."), SNotificationItem::CS_Fail);
        return;
    }

    TArray<FGuid> SelectedCueGuids;
    if (CueList.IsValid())
    {
        for (const FCueItem& Item : CueList->GetSelectedItems())
        {
            if (Item.IsValid()
                && Item->NodeType == EInfinityCueListNodeType::Cue
                && Show->Cues.IsValidIndex(Item->CueIndex))
            {
                SelectedCueGuids.AddUnique(Show->Cues[Item->CueIndex].CueGuid);
            }
        }
    }

    FString MasterReport;
    if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, MasterReport))
    {
        UE_LOG(LogTemp, Error, TEXT("Infinity Stage render preparation failed: %s"), *MasterReport);
        NotifyCueDesk(MasterReport, SNotificationItem::CS_Fail);
        return;
    }

    ULevelSequence* RenderSequence = LoadOrCreateManagedRenderSequence(*Show);
    FFrameNumber StartFrame;
    FFrameNumber EndFrame;
    FString RenderReport;
    if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
        Show,
        Master,
        RenderSequence,
        World,
        SelectedCueGuids,
        SelectedPassageGuid,
        StartFrame,
        EndFrame,
        RenderReport))
    {
        UE_LOG(LogTemp, Error, TEXT("Infinity Stage render wrapper failed: %s"), *RenderReport);
        NotifyCueDesk(RenderReport, SNotificationItem::CS_Fail);
        return;
    }

    UEditorAssetSubsystem* AssetSubsystem = GEditor->GetEditorSubsystem<UEditorAssetSubsystem>();
    if (!AssetSubsystem || !AssetSubsystem->SaveLoadedAssets({ Show, Master, RenderSequence }, false))
    {
        NotifyCueDesk(TEXT("Render wrapper was built, but the Show/Master/wrapper assets could not all be saved."), SNotificationItem::CS_Fail);
        return;
    }

    UMoviePipelineQueueSubsystem* QueueSubsystem = GEditor->GetEditorSubsystem<UMoviePipelineQueueSubsystem>();
    UMoviePipelineQueue* Queue = QueueSubsystem ? QueueSubsystem->GetQueue() : nullptr;
    if (!Queue)
    {
        NotifyCueDesk(TEXT("Movie Render Queue is unavailable. Check that the Movie Render Queue plugin is enabled."), SNotificationItem::CS_Fail);
        return;
    }

    Queue->Modify();
    const FString ManagedJobKey = FString::Printf(
        TEXT("InfinityStage.RenderSelection.%s"),
        *Show->ShowGuid.ToString(EGuidFormats::Digits));
    UMoviePipelineExecutorJob* Job = nullptr;
    for (UMoviePipelineExecutorJob* Candidate : Queue->GetJobs())
    {
        if (Candidate && Candidate->UserData == ManagedJobKey)
        {
            Job = Candidate;
            break;
        }
    }
    const bool bCreatedJob = Job == nullptr;
    if (bCreatedJob)
    {
        Job = UMoviePipelineEditorBlueprintLibrary::CreateJobFromSequence(Queue, RenderSequence);
    }
    if (!Job)
    {
        NotifyCueDesk(TEXT("Movie Render Queue could not allocate the managed render job."), SNotificationItem::CS_Fail);
        return;
    }

    Job->Modify();
    Job->UserData = ManagedJobKey;
    Job->JobName = FString::Printf(
        TEXT("%s — Infinity Stage frames %d-%d"),
        *Show->GetName(),
        StartFrame.Value,
        EndFrame.Value - 1);
    Job->Comment = FString::Printf(
        TEXT("Managed by Infinity Stage. %s"),
        *RenderReport);
    Job->Map = FSoftObjectPath(World);
    Job->SetSequence(FSoftObjectPath(RenderSequence));
    Job->SetConsumed(false);
    Job->SetIsEnabled(true);
    if (bCreatedJob)
    {
        UMoviePipelineEditorBlueprintLibrary::ApplyDefaultConfigurationTypeToJob(Job);
        UMoviePipelineEditorBlueprintLibrary::EnsureJobHasDefaultSettings(Job);
    }

    if (UAssetEditorSubsystem* AssetEditors = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>())
    {
        AssetEditors->OpenEditorForAsset(RenderSequence);
    }
    // The queue tab's public static name is not exported by every UE 5.8 Mac linkage
    // configuration, although the tab itself is public and stable.
    FGlobalTabmanager::Get()->TryInvokeTab(FName(TEXT("MoviePipelineQueue")));

    FString Notice = FString::Printf(TEXT("Movie Render Queue prepared. %s"), *RenderReport);
    if (World->GetOutermost()->IsDirty())
    {
        Notice += TEXT(" The current level is dirty; save it before Render (Remote). ");
    }
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage render selection: %s"), *Notice);
    NotifyCueDesk(Notice, SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::AnalyzeSelectionMusic()
{
    const FInfinityPassageSettings* Settings = GetSelectedPassage();
    if (!ShowAsset.IsValid() || !Settings)
    {
        NotifyCueDesk(TEXT("Select a Passage first."), SNotificationItem::CS_Fail);
        return;
    }
    const FInfinityMusicRail* Rail = ShowAsset->MusicRails.FindByPredicate(
        [Settings](const FInfinityMusicRail& Candidate)
        { return Candidate.RailGuid == Settings->Music.PrimaryRailGuid; });
    USoundBase* Sound = Rail ? Rail->Sound.LoadSynchronous() : nullptr;
    if (!Sound)
    {
        NotifyCueDesk(
            TEXT("This Passage has no Music Rail sound. Bind one with the rail picker first."),
            SNotificationItem::CS_Fail);
        return;
    }

    // The analyzer keys a Passage from the exported filename prefix, so pass the
    // rail's index rather than letting filename order decide.
    const int32 PassageNumber = ShowAsset->MusicRails.IndexOfByPredicate(
        [Rail](const FInfinityMusicRail& Candidate) { return Candidate.RailGuid == Rail->RailGuid; }) + 1;

    FString Report;
    const bool bAnalyzed = FInfinityStageMusicAnalysisImporter::AnalyzeSound(Sound, PassageNumber, Report);
    UE_LOG(LogTemp, Display, TEXT("INFINITY_STAGE_ANALYZE_SOUND ok=%d %s"), bAnalyzed ? 1 : 0, *Report);
    if (!bAnalyzed)
    {
        NotifyCueDesk(Report, SNotificationItem::CS_Fail);
        return;
    }
    NotifyCueDesk(Report, SNotificationItem::CS_Success);
    ReimportMusicAnalysis();
}

void SInfinityStageCueDesk::ReimportMusicAnalysis()
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "ReimportMusicAnalysisTransaction", "Link Infinity Stage Music Analysis"));
    FString Report;
    const FString AnalysisDirectory = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("InfinityStage/MusicAnalysis"));
    if (!FInfinityStageMusicAnalysisImporter::ImportDirectory(AnalysisDirectory, ShowAsset.Get(), Report))
    {
        UE_LOG(LogTemp, Error, TEXT("Infinity Stage music analysis import failed: %s"), *Report);
        return;
    }
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage music analysis: %s"), *Report);
    RefreshPassageInspector();
    LoadFitFromSelectedPassage();
    Invalidate(EInvalidateWidgetReason::Paint);
}

TArray<int32> SInfinityStageCueDesk::GetSelectedWingCueIndices() const
{
    TArray<int32> Indices;
    if (!ShowAsset.IsValid() || !CueList.IsValid())
    {
        return Indices;
    }
    for (const FCueItem& Item : CueList->GetSelectedItems())
    {
        if (Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::Cue
            && ShowAsset->Cues.IsValidIndex(Item->CueIndex)
            && ShowAsset->Cues[Item->CueIndex].Type == EInfinityCueType::WingPair)
        {
            Indices.AddUnique(Item->CueIndex);
        }
    }
    Indices.Sort();
    return Indices;
}

FGuid SInfinityStageCueDesk::GetExplicitSelectedPassageGuid() const
{
    if (!ShowAsset.IsValid())
    {
        return FGuid();
    }
    if (SelectedPassageGuid.IsValid())
    {
        return SelectedPassageGuid;
    }
    const int32 CueIndex = GetPrimarySelectedIndex();
    if (!ShowAsset->Cues.IsValidIndex(CueIndex)
        || ShowAsset->Cues[CueIndex].Type != EInfinityCueType::WingPair)
    {
        return FGuid();
    }
    for (const FInfinityPassageSettings& Passage : ShowAsset->PassageSettings)
    {
        const int32 First = ShowAsset->FindCueIndex(Passage.FirstCueGuid);
        const int32 Last = ShowAsset->FindCueIndex(Passage.LastCueGuid);
        if (First != INDEX_NONE && Last != INDEX_NONE && CueIndex >= First && CueIndex <= Last)
        {
            return Passage.PassageGuid;
        }
    }
    return FGuid();
}

bool SInfinityStageCueDesk::HasWingSequenceExportTargets(const bool bWholePassage) const
{
    if (bWholePassage)
    {
        return GetExplicitSelectedPassageGuid().IsValid();
    }
    return !GetSelectedWingCueIndices().IsEmpty();
}

bool SInfinityStageCueDesk::HasPassageReplacementTarget() const
{
    return GetExplicitSelectedPassageGuid().IsValid();
}

void SInfinityStageCueDesk::ExportWingSequence(const bool bWholePassage)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }

    TArray<int32> CueIndices;
    const FInfinityPassageSettings* CompletePassage = nullptr;
    FString SequenceLabel;
    if (bWholePassage)
    {
        const FGuid PassageGuid = GetExplicitSelectedPassageGuid();
        CompletePassage = ShowAsset->PassageSettings.FindByPredicate(
            [PassageGuid](const FInfinityPassageSettings& Passage)
            {
                return Passage.PassageGuid == PassageGuid;
            });
        if (CompletePassage)
        {
            const int32 First = ShowAsset->FindCueIndex(CompletePassage->FirstCueGuid);
            const int32 Last = ShowAsset->FindCueIndex(CompletePassage->LastCueGuid);
            for (int32 Index = First; Index != INDEX_NONE && Index <= Last; ++Index)
            {
                if (ShowAsset->Cues.IsValidIndex(Index)
                    && ShowAsset->Cues[Index].Type == EInfinityCueType::WingPair)
                {
                    CueIndices.Add(Index);
                }
            }
            SequenceLabel = CompletePassage->Label.ToString();
        }
    }
    else
    {
        CueIndices = GetSelectedWingCueIndices();
        if (CueIndices.Num() == 1)
        {
            SequenceLabel = ShowAsset->Cues[CueIndices[0]].Label.ToString();
        }
        else
        {
            SequenceLabel = FString::Printf(TEXT("%s — %d selected wings"),
                *ShowAsset->GetName(), CueIndices.Num());
        }
    }
    if (CueIndices.IsEmpty())
    {
        NotifyCueDesk(TEXT("Select Wing Pair rows or a Passage heading before exporting."),
            SNotificationItem::CS_Fail);
        return;
    }

    FString Json;
    FString Report;
    if (!FInfinityStageWingSequenceInterchange::ExportToJson(
        *ShowAsset, CueIndices, SequenceLabel, CompletePassage, Json, Report))
    {
        NotifyCueDesk(Report, SNotificationItem::CS_Fail);
        return;
    }

    IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
    if (!DesktopPlatform)
    {
        NotifyCueDesk(TEXT("The native file dialog is unavailable."), SNotificationItem::CS_Fail);
        return;
    }
    const FString DefaultDirectory = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("InfinityStage/WingSequences"));
    IFileManager::Get().MakeDirectory(*DefaultDirectory, true);
    FString FilenameStem = SequenceLabel.IsEmpty() ? TEXT("WingSequence") : SequenceLabel;
    FilenameStem = FPaths::MakeValidFileName(FilenameStem, static_cast<TCHAR>('_'));
    TArray<FString> Filenames;
    const void* ParentWindow = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr);
    if (!DesktopPlatform->SaveFileDialog(
        ParentWindow,
        TEXT("Export Infinity Stage Wing Sequence"),
        DefaultDirectory,
        FilenameStem + TEXT(".infinitywings.json"),
        TEXT("Infinity Stage Wing Sequence (*.infinitywings.json)|*.infinitywings.json|JSON (*.json)|*.json"),
        EFileDialogFlags::None,
        Filenames)
        || Filenames.IsEmpty())
    {
        return;
    }
    FString Filename = Filenames[0];
    if (FPaths::GetExtension(Filename).IsEmpty())
    {
        Filename += TEXT(".infinitywings.json");
    }
    if (!FInfinityStageWingSequenceInterchange::SaveToFile(Filename, Json, Report))
    {
        NotifyCueDesk(Report, SNotificationItem::CS_Fail);
        return;
    }
    UE_LOG(LogTemp, Display, TEXT("Infinity Stage Wing Sequence export: %s"), *Report);
    NotifyCueDesk(FString::Printf(TEXT("Exported %d Wing Pair(s) to %s"),
        CueIndices.Num(), *FPaths::GetCleanFilename(Filename)), SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::ImportWingSequence(const EInfinityWingSequenceImportMode ImportMode)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
    if (!DesktopPlatform)
    {
        NotifyCueDesk(TEXT("The native file dialog is unavailable."), SNotificationItem::CS_Fail);
        return;
    }
    const FString DefaultDirectory = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("InfinityStage/WingSequences"));
    IFileManager::Get().MakeDirectory(*DefaultDirectory, true);
    TArray<FString> Filenames;
    const void* ParentWindow = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr);
    if (!DesktopPlatform->OpenFileDialog(
        ParentWindow,
        TEXT("Import Infinity Stage Wing Sequence"),
        DefaultDirectory,
        FString(),
        TEXT("Infinity Stage Wing Sequence (*.infinitywings.json)|*.infinitywings.json|JSON (*.json)|*.json"),
        EFileDialogFlags::None,
        Filenames)
        || Filenames.IsEmpty())
    {
        return;
    }

    FInfinityWingSequenceDocument Document;
    FString Report;
    if (!FInfinityStageWingSequenceInterchange::LoadFromFile(Filenames[0], Document, Report))
    {
        NotifyCueDesk(Report, SNotificationItem::CS_Fail);
        return;
    }

    const bool bApplyArrangement = ImportMode == EInfinityWingSequenceImportMode::ApplyArrangement;
    const bool bReplaceCompleteRows = ImportMode == EInfinityWingSequenceImportMode::ReplaceCompleteRows;
    const bool bTargetsPassage = bApplyArrangement || bReplaceCompleteRows;
    const FGuid TargetPassageGuid = bTargetsPassage
        ? GetExplicitSelectedPassageGuid()
        : FGuid();
    if (bTargetsPassage && !TargetPassageGuid.IsValid())
    {
        NotifyCueDesk(TEXT("Select a Passage heading or one of its Wing Pair rows first."),
            SNotificationItem::CS_Fail);
        return;
    }
    if (bTargetsPassage)
    {
        const FInfinityPassageSettings* TargetPassage = ShowAsset->PassageSettings.FindByPredicate(
            [TargetPassageGuid](const FInfinityPassageSettings& Passage)
            {
                return Passage.PassageGuid == TargetPassageGuid;
            });
        const FString TargetLabel = TargetPassage ? TargetPassage->Label.ToString() : TEXT("current Passage");
        const int32 TargetCount = TargetPassage
            ? FMath::Max(0,
                ShowAsset->FindCueIndex(TargetPassage->LastCueGuid)
                - ShowAsset->FindCueIndex(TargetPassage->FirstCueGuid) + 1)
            : 0;
        const FText Confirmation = bApplyArrangement
            ? FText::Format(
                NSLOCTEXT("InfinityStage", "ConfirmApplyWingArrangement",
                    "Apply the ordered Wing arrangement '{0}' across the {1} existing rows in '{2}'?\n\n"
                    "The saved pattern will repeat or trim as needed. Passage and row names, Wing count, music timing, spacing and stable identities will remain unchanged. This action supports Undo."),
                FText::FromString(Document.Label),
                FText::AsNumber(TargetCount),
                FText::FromString(TargetLabel))
            : FText::Format(
                NSLOCTEXT("InfinityStage", "ConfirmReplaceWingSequence",
                    "Replace all complete Wing rows in '{0}' with the {1} row(s) from '{2}'?\n\n"
                    "This advanced mode changes row count, row names, timing, spacing and saved layout defaults. The target Passage name, identity, music, sky and camera/Scene handovers remain unchanged. This action supports Undo."),
                FText::FromString(TargetLabel),
                FText::AsNumber(Document.Cues.Num()),
                FText::FromString(Document.Label));
        if (FMessageDialog::Open(EAppMsgType::YesNo, Confirmation) != EAppReturnType::Yes)
        {
            return;
        }
    }

    int32 AfterCueIndex = ShowAsset->Cues.Num() - 1;
    if (ImportMode == EInfinityWingSequenceImportMode::InsertRows)
    {
        if (SelectedPassageGuid.IsValid())
        {
            if (const FInfinityPassageSettings* SelectedPassage = ShowAsset->PassageSettings.FindByPredicate(
                [this](const FInfinityPassageSettings& Passage)
                {
                    return Passage.PassageGuid == SelectedPassageGuid;
                }))
            {
                AfterCueIndex = ShowAsset->FindCueIndex(SelectedPassage->LastCueGuid);
            }
        }
        else if (CueList.IsValid())
        {
            int32 LastSelectedCueIndex = INDEX_NONE;
            for (const FCueItem& Item : CueList->GetSelectedItems())
            {
                if (Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::Cue)
                {
                    LastSelectedCueIndex = FMath::Max(LastSelectedCueIndex, Item->CueIndex);
                }
            }
            if (LastSelectedCueIndex != INDEX_NONE)
            {
                AfterCueIndex = LastSelectedCueIndex;
            }
        }
    }

    const FText TransactionLabel = bApplyArrangement
        ? NSLOCTEXT("InfinityStage", "ApplyWingArrangementTransaction", "Apply Infinity Stage Wing Arrangement")
        : (bReplaceCompleteRows
            ? NSLOCTEXT("InfinityStage", "ReplaceWingSequenceTransaction", "Replace Infinity Stage Wing Sequence")
            : NSLOCTEXT("InfinityStage", "InsertWingSequenceTransaction", "Import Infinity Stage Wing Sequence"));
    const FScopedTransaction Transaction(TransactionLabel);
    ShowAsset->Modify();
    TArray<int32> InsertedIndices;
    const bool bApplied = bApplyArrangement
        ? FInfinityStageWingSequenceInterchange::ApplyArrangementToPassage(
            *ShowAsset, TargetPassageGuid, Document, InsertedIndices, Report)
        : (bReplaceCompleteRows
            ? FInfinityStageWingSequenceInterchange::ReplacePassage(
                *ShowAsset, TargetPassageGuid, Document, InsertedIndices, Report)
            : FInfinityStageWingSequenceInterchange::InsertAfter(
                *ShowAsset, AfterCueIndex, Document, InsertedIndices, Report));
    if (!bApplied)
    {
        NotifyCueDesk(Report, SNotificationItem::CS_Fail);
        return;
    }
    RenumberDefaultLabels();
    ShowAsset->MarkPackageDirty();

    TSet<FGuid> AffectedPassages;
    for (const int32 InsertedIndex : InsertedIndices)
    {
        for (const FInfinityPassageSettings& Passage : ShowAsset->PassageSettings)
        {
            const int32 First = ShowAsset->FindCueIndex(Passage.FirstCueGuid);
            const int32 Last = ShowAsset->FindCueIndex(Passage.LastCueGuid);
            if (First != INDEX_NONE && Last != INDEX_NONE
                && InsertedIndex >= First && InsertedIndex <= Last)
            {
                AffectedPassages.Add(Passage.PassageGuid);
            }
        }
    }
    RefreshPassagesInEditorWorld(AffectedPassages);

    if (!ShowAsset->ManagedMasterSequence.IsNull())
    {
        FString MasterReport;
        if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(
            ShowAsset.Get(), ShowAsset->ManagedMasterSequence.LoadSynchronous(), MasterReport))
        {
            UE_LOG(LogTemp, Error, TEXT("Wing Sequence imported, but managed Master rebuild failed: %s"), *MasterReport);
            NotifyCueDesk(TEXT("Wing Sequence imported, but the managed Master rebuild failed. See Output Log."),
                SNotificationItem::CS_Fail);
        }
    }

    for (const FGuid& PassageGuid : AffectedPassages)
    {
        CollapsedPassages.Remove(PassageGuid);
    }
    RefreshFromAsset(false);
    for (const int32 Index : InsertedIndices)
    {
        const FCueItem* Item = CueItems.FindByPredicate([Index](const FCueItem& Candidate)
        {
            return Candidate.IsValid()
                && Candidate->NodeType == EInfinityCueListNodeType::Cue
                && Candidate->CueIndex == Index;
        });
        if (Item && CueList.IsValid())
        {
            CueList->SetItemSelection(*Item, true);
        }
    }
    UE_LOG(LogTemp, Display,
        TEXT("INFINITY_STAGE_WING_SEQUENCE_IMPORT_OK file='%s' count=%d mode=%s report='%s'"),
        *Filenames[0], InsertedIndices.Num(),
        bApplyArrangement ? TEXT("arrangement") : (bReplaceCompleteRows ? TEXT("replace") : TEXT("insert")),
        *Report);
    NotifyCueDesk(Report, SNotificationItem::CS_Success);
}

void SInfinityStageCueDesk::ApplyListMutation(const FText& TransactionLabel, TFunctionRef<void(TArray<int32>&)> Mutation)
{
    if (!ShowAsset.IsValid())
    {
        return;
    }
    const FScopedTransaction Transaction(TransactionLabel);
    ShowAsset->Modify();
    TArray<int32> NewSelection;
    Mutation(NewSelection);
    ShowAsset->EnsureStableIds();
    ShowAsset->ReconcilePassageSettings();
    RenumberDefaultLabels();
    ShowAsset->MarkPackageDirty();
    if (!ShowAsset->ManagedMasterSequence.IsNull())
    {
        FString MasterReport;
        if (!UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(
            ShowAsset.Get(), ShowAsset->ManagedMasterSequence.LoadSynchronous(), MasterReport))
        {
            UE_LOG(LogTemp, Error, TEXT("Infinity Stage list mutation could not rebuild the managed Master: %s"),
                *MasterReport);
            NotifyCueDesk(
                TEXT("Cue order changed, but the managed Master rebuild failed. See Output Log."),
                SNotificationItem::CS_Fail);
        }
    }
    RefreshAllPassagesInEditorWorld();
    RefreshFromAsset(false);
    for (const int32 Index : NewSelection)
    {
        const FCueItem* Item = CueItems.FindByPredicate([Index](const FCueItem& Candidate)
        {
            return Candidate.IsValid()
                && Candidate->NodeType == EInfinityCueListNodeType::Cue
                && Candidate->CueIndex == Index;
        });
        if (Item)
        {
            CueList->SetItemSelection(*Item, true);
        }
    }
}

void SInfinityStageCueDesk::RenumberDefaultLabels()
{
    int32 WingNumber = 0;
    int32 SceneNumber = 0;
    for (FInfinityShowCue& Cue : ShowAsset->Cues)
    {
        if (!Cue.Label.IsEmpty())
        {
            continue;
        }
        if (Cue.Type == EInfinityCueType::WingPair)
        {
            Cue.Label = FText::Format(NSLOCTEXT("InfinityStage", "DefaultWingLabel", "Wing Pair {0}"), ++WingNumber);
        }
        else
        {
            Cue.Label = FText::Format(NSLOCTEXT("InfinityStage", "DefaultSceneLabel", "Scene {0}"), ++SceneNumber);
        }
    }
}

int32 SInfinityStageCueDesk::GetPrimarySelectedIndex() const
{
    if (CueList.IsValid())
    {
        const TArray<FCueItem> Selected = CueList->GetSelectedItems();
        for (const FCueItem& Item : Selected)
        {
            if (Item.IsValid() && Item->NodeType == EInfinityCueListNodeType::Cue && Item->CueIndex != INDEX_NONE)
            {
                return Item->CueIndex;
            }
        }
    }
    return INDEX_NONE;
}

int32 SInfinityStageCueDesk::GetTimelineSelectedCueIndex() const
{
    if (ShowAsset.IsValid() && SelectedPassageGuid.IsValid())
    {
        if (const FInfinityPassageSettings* Passage = ShowAsset->PassageSettings.FindByPredicate(
            [this](const FInfinityPassageSettings& Candidate)
            {
                return Candidate.PassageGuid == SelectedPassageGuid;
            }))
        {
            return ShowAsset->FindCueIndex(Passage->FirstCueGuid);
        }
    }
    return GetPrimarySelectedIndex();
}

FText SInfinityStageCueDesk::GetStatusText() const
{
    if (!ShowAsset.IsValid())
    {
        return NSLOCTEXT("InfinityStage", "NoShowSelected", "Select or create an Infinity Stage Show Asset");
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    int32 WingCount = 0;
    double DistanceCm = 0.0;
    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        WingCount += Passage.Wings.Num();
        DistanceCm += Passage.TotalDistanceCm;
    }
    const double DurationSeconds = ShowAsset->TickResolution.AsDecimal() > 0.0
        ? Compiled.ShowEndFrame.Value / ShowAsset->TickResolution.AsDecimal()
        : 0.0;
    const double AverageSpeed = DurationSeconds > 0.0 ? DistanceCm / DurationSeconds : 0.0;
    bool bMultipleLevelShows = false;
    UInfinityStageShowAsset* LevelShow = FindEditorWorldShowAsset(bMultipleLevelShows);
    FText State = Compiled.HasErrors()
        ? NSLOCTEXT("InfinityStage", "StatusErrors", "ERRORS")
        : NSLOCTEXT("InfinityStage", "StatusReady", "READY");
    if (bMultipleLevelShows)
    {
        State = NSLOCTEXT("InfinityStage", "StatusMultipleShows", "LEVEL HAS MULTIPLE SHOWS");
    }
    else if (LevelShow && LevelShow != ShowAsset.Get())
    {
        State = FText::Format(
            NSLOCTEXT("InfinityStage", "StatusShowMismatch", "SHOW MISMATCH: level uses {0}"),
            FText::FromString(LevelShow->GetName()));
    }
    return FText::Format(
        NSLOCTEXT("InfinityStage", "StatusRail", "{6}  |  Show {0}s  |  Camera avg {1}m/s  |  Route {2}m  |  {3} wing pairs  |  {4} passages  |  {5}"),
        NumberText(DurationSeconds, 1),
        NumberText(AverageSpeed / 100.0, 2),
        NumberText(DistanceCm / 100.0, 1),
        WingCount,
        Compiled.Passages.Num(),
        State,
        GetNowPlayingText(Compiled));
}

FText SInfinityStageCueDesk::GetNowPlayingText(const FInfinityCompileResult& Compiled) const
{
    if (!ShowAsset.IsValid())
    {
        return NSLOCTEXT("InfinityStage", "NowIdle", "—");
    }

    // Prefer the live PIE clock; fall back to the editor preview playhead so the
    // readout is meaningful while scrubbing without PIE.
    FFrameNumber CurrentFrame = 0;
    const TCHAR* Source = TEXT("PREVIEW");
    bool bHasFrame = false;
    if (GEngine)
    {
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            if (Context.WorldType != EWorldType::PIE || !Context.World())
            {
                continue;
            }
            for (TActorIterator<AInfinityStageShowRoot> It(Context.World()); It; ++It)
            {
                if (It->ShowAsset == ShowAsset.Get() && It->Transport)
                {
                    CurrentFrame = It->Transport->GetCurrentMasterFrame();
                    Source = It->Transport->IsTransportPlaying() ? TEXT("PIE ▶") : TEXT("PIE ❙❙");
                    bHasFrame = true;
                    break;
                }
            }
            if (bHasFrame)
            {
                break;
            }
        }
    }
    if (!bHasFrame && EditorPreviewNormalizedPosition >= 0.0)
    {
        if (const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
            [this](const FInfinityCompiledPassage& Candidate)
            {
                return Candidate.PassageGuid == EditorPreviewPassageGuid;
            }))
        {
            CurrentFrame = FFrameNumber(static_cast<int32>(FMath::RoundToInt(FMath::Lerp(
                static_cast<double>(Passage->SegmentStartFrame.Value),
                static_cast<double>(Passage->SegmentEndFrame.Value),
                EditorPreviewNormalizedPosition))));
            bHasFrame = true;
        }
    }
    if (!bHasFrame)
    {
        return NSLOCTEXT("InfinityStage", "NowIdle", "—");
    }

    // Wing Pair segments report the exact cue whose pass frame the playhead has
    // most recently reached, which is what an operator watches for.
    for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
    {
        if (CurrentFrame < Segment.StartFrame || CurrentFrame > Segment.EndFrame)
        {
            continue;
        }
        if (Segment.Type != EInfinityCueType::WingPair)
        {
            const FText Label = ShowAsset->Cues.IsValidIndex(Segment.FirstCueIndex)
                ? ShowAsset->Cues[Segment.FirstCueIndex].Label
                : NSLOCTEXT("InfinityStage", "NowSceneFallback", "Scene");
            return FText::Format(
                NSLOCTEXT("InfinityStage", "NowScene", "{0}  SCENE · {1}"),
                FText::FromString(Source),
                Label);
        }

        const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
            [&Segment](const FInfinityCompiledPassage& Candidate)
            {
                return Candidate.PassageGuid == Segment.SegmentGuid;
            });
        const FInfinityPassageSettings* Settings = ShowAsset->PassageSettings.FindByPredicate(
            [&Segment](const FInfinityPassageSettings& Candidate)
            {
                return Candidate.PassageGuid == Segment.SegmentGuid;
            });
        FText WingLabel = NSLOCTEXT("InfinityStage", "NowApproaching", "approaching first wing");
        if (Passage)
        {
            int32 Ordinal = INDEX_NONE;
            for (int32 Index = 0; Index < Passage->Wings.Num(); ++Index)
            {
                if (Passage->Wings[Index].PassFrame <= CurrentFrame)
                {
                    Ordinal = Index;
                }
            }
            if (Passage->Wings.IsValidIndex(Ordinal))
            {
                const int32 CueIndex = ShowAsset->FindCueIndex(Passage->Wings[Ordinal].CueGuid);
                const FText CueLabel = ShowAsset->Cues.IsValidIndex(CueIndex)
                    ? ShowAsset->Cues[CueIndex].Label
                    : FText::GetEmpty();
                WingLabel = CueLabel.IsEmpty()
                    ? FText::Format(
                        NSLOCTEXT("InfinityStage", "NowWingOrdinal", "wing {0}/{1}"),
                        Ordinal + 1,
                        Passage->Wings.Num())
                    : FText::Format(
                        NSLOCTEXT("InfinityStage", "NowWingNamed", "wing {0}/{1} · {2}"),
                        Ordinal + 1,
                        Passage->Wings.Num(),
                        CueLabel);
            }
        }
        return FText::Format(
            NSLOCTEXT("InfinityStage", "NowPassage", "{0}  {1} · {2}"),
            FText::FromString(Source),
            Settings ? Settings->Label : NSLOCTEXT("InfinityStage", "NowPassageFallback", "Passage"),
            WingLabel);
    }
    return NSLOCTEXT("InfinityStage", "NowIdle", "—");
}

FText SInfinityStageCueDesk::GetCueSelectionSummaryText() const
{
    if (ShowAsset.IsValid() && SelectedPassageGuid.IsValid())
    {
        if (const FInfinityPassageSettings* Passage = GetSelectedPassage())
        {
            const int32 First = ShowAsset->FindCueIndex(Passage->FirstCueGuid);
            const int32 Last = ShowAsset->FindCueIndex(Passage->LastCueGuid);
            return FText::Format(
                NSLOCTEXT("InfinityStage", "PassageSelectionSummary", "{0} selected · passage-wide settings for {1} Wing Pairs"),
                Passage->Label,
                FMath::Max(0, Last - First + 1));
        }
    }
    if (!CueList.IsValid() || CueList->GetNumItemsSelected() == 0)
    {
        return NSLOCTEXT("InfinityStage", "NoCueSelection", "Select one or more cues to edit.");
    }

    const int32 EditedCount = CueProxies.Num();
    const int32 ExcludedCount = CueList->GetNumItemsSelected() - EditedCount;
    if (EditedCount <= 1)
    {
        return NSLOCTEXT("InfinityStage", "SingleCueSelection", "1 cue selected");
    }

    const FText CueType = CueProxies.IsEmpty()
        ? NSLOCTEXT("InfinityStage", "GenericCueSelectionType", "cue")
        : CueTypeText(CueProxies[0]->Cue.Type);
    if (ExcludedCount > 0)
    {
        return FText::Format(
            NSLOCTEXT("InfinityStage", "MultiCueSelectionMixed", "{0} {1} rows selected · shared edits apply to all · {2} other rows excluded"),
            EditedCount,
            CueType,
            ExcludedCount);
    }

    return FText::Format(
        NSLOCTEXT("InfinityStage", "MultiCueSelection", "{0} {1} rows selected · shared edits apply to all"),
        EditedCount,
        CueType);
}

FText SInfinityStageCueDesk::GetMusicAnalysisSummaryText() const
{
    if (!ShowAsset.IsValid() || ShowAsset->MusicRails.IsEmpty())
    {
        return NSLOCTEXT("InfinityStage", "NoMusicRails", "No Passage music rails are configured.");
    }

    TArray<FString> Lines;
    Lines.Add(TEXT("ANALYSIS REVIEW — proposals only; never applied to cues automatically"));
    for (int32 Index = 0; Index < ShowAsset->MusicRails.Num(); ++Index)
    {
        const FInfinityMusicRail& Rail = ShowAsset->MusicRails[Index];
        const UInfinityStageMusicMapAsset* Map = Rail.AnalysisMap.LoadSynchronous();
        if (!Map)
        {
            Lines.Add(FString::Printf(TEXT("P%02d  No Music Map"), Index + 1));
            continue;
        }
        const FString Tempo = Map->TempoCandidates.IsEmpty()
            ? TEXT("no stable tempo")
            : FString::Printf(TEXT("%.1f BPM candidate (%.0f%%)"), Map->TempoCandidates[0].Bpm, Map->TempoCandidates[0].Confidence * 100.0);
        Lines.Add(FString::Printf(
            TEXT("P%02d  %.1fs  ·  %s  ·  %d change suggestions  ·  %s %s"),
            Index + 1,
            Map->DurationSeconds,
            *Tempo,
            Map->MajorChangeProposals.Num(),
            *Map->ProviderName,
            *Map->ProviderVersion));
    }
    return FText::FromString(FString::Join(Lines, TEXT("\n")));
}
