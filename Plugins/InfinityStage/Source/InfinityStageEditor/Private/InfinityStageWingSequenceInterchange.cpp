#include "InfinityStageWingSequenceInterchange.h"

#include "Dom/JsonObject.h"
#include "InfinityStageShowAsset.h"
#include "JsonObjectConverter.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
constexpr TCHAR FormatName[] = TEXT("InfinityStageWingSequence");

TSharedRef<FJsonObject> FrameRateToJson(const FFrameRate& Rate)
{
    const TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
    Object->SetNumberField(TEXT("numerator"), Rate.Numerator);
    Object->SetNumberField(TEXT("denominator"), Rate.Denominator);
    return Object;
}

bool FrameRateFromJson(const TSharedPtr<FJsonObject>& Object, FFrameRate& OutRate)
{
    double Numerator = 0.0;
    double Denominator = 0.0;
    if (!Object.IsValid()
        || !Object->TryGetNumberField(TEXT("numerator"), Numerator)
        || !Object->TryGetNumberField(TEXT("denominator"), Denominator))
    {
        return false;
    }
    OutRate = FFrameRate(FMath::RoundToInt(Numerator), FMath::RoundToInt(Denominator));
    return OutRate.IsValid();
}

FFrameNumber ConvertFrame(
    const FFrameNumber SourceFrame,
    const FFrameRate SourceRate,
    const FFrameRate TargetRate)
{
    if (SourceRate == TargetRate)
    {
        return SourceFrame;
    }
    return FFrameRate::TransformTime(FFrameTime(SourceFrame), SourceRate, TargetRate).RoundToFrame();
}

TSharedRef<FJsonObject> EnvelopeToJson(const FInfinityPassageSettings& Passage)
{
    const TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
    Object->SetNumberField(TEXT("lead_in_frames"), Passage.LeadInFrames.Value);
    Object->SetNumberField(TEXT("tail_frames"), Passage.TailFrames.Value);
    Object->SetNumberField(TEXT("lead_in_distance_cm"), Passage.LeadInDistanceCm);
    Object->SetNumberField(TEXT("tail_distance_cm"), Passage.TailDistanceCm);
    Object->SetNumberField(TEXT("preferred_camera_speed_cm_per_second"), Passage.PreferredCameraSpeedCmPerSecond);
    Object->SetBoolField(TEXT("use_live_mechanism_phase_pattern"), Passage.bUseLiveMechanismPhasePattern);
    Object->SetNumberField(TEXT("mechanism_phase_step_cycles"), Passage.MechanismPhaseStepCycles);
    Object->SetNumberField(TEXT("mechanism_phase_offset_cycles"), Passage.MechanismPhaseOffsetCycles);
    Object->SetNumberField(TEXT("fit_mode"), static_cast<uint8>(Passage.FitMode));
    Object->SetNumberField(TEXT("preferred_spacing_cm"), Passage.PreferredSpacingCm);
    return Object;
}

bool EnvelopeFromJson(
    const TSharedPtr<FJsonObject>& Object,
    FInfinityWingSequencePassageEnvelope& OutEnvelope)
{
    if (!Object.IsValid())
    {
        return false;
    }
    double LeadFrames = 0.0;
    double TailFrames = 0.0;
    double FitMode = 0.0;
    if (!Object->TryGetNumberField(TEXT("lead_in_frames"), LeadFrames)
        || !Object->TryGetNumberField(TEXT("tail_frames"), TailFrames)
        || !Object->TryGetNumberField(TEXT("lead_in_distance_cm"), OutEnvelope.LeadInDistanceCm)
        || !Object->TryGetNumberField(TEXT("tail_distance_cm"), OutEnvelope.TailDistanceCm)
        || !Object->TryGetNumberField(TEXT("preferred_camera_speed_cm_per_second"), OutEnvelope.PreferredCameraSpeedCmPerSecond)
        || !Object->TryGetNumberField(TEXT("fit_mode"), FitMode)
        || !Object->TryGetNumberField(TEXT("preferred_spacing_cm"), OutEnvelope.PreferredSpacingCm))
    {
        return false;
    }
    OutEnvelope.LeadInFrames = FFrameNumber(static_cast<int32>(FMath::RoundToInt(LeadFrames)));
    OutEnvelope.TailFrames = FFrameNumber(static_cast<int32>(FMath::RoundToInt(TailFrames)));
    const int32 FitModeValue = FMath::RoundToInt(FitMode);
    if (FitModeValue < 0 || FitModeValue > static_cast<int32>(EInfinityPassageFitMode::ManualPassage))
    {
        return false;
    }
    OutEnvelope.FitMode = static_cast<EInfinityPassageFitMode>(FitModeValue);
    // Added compatibly to schema 1: older files simply retain the defaults.
    Object->TryGetBoolField(
        TEXT("use_live_mechanism_phase_pattern"), OutEnvelope.bUseLiveMechanismPhasePattern);
    Object->TryGetNumberField(
        TEXT("mechanism_phase_step_cycles"), OutEnvelope.MechanismPhaseStepCycles);
    Object->TryGetNumberField(
        TEXT("mechanism_phase_offset_cycles"), OutEnvelope.MechanismPhaseOffsetCycles);
    return OutEnvelope.LeadInFrames.Value >= 0
        && OutEnvelope.TailFrames.Value >= 0
        && OutEnvelope.LeadInDistanceCm >= 0.0
        && OutEnvelope.TailDistanceCm >= 0.0
        && OutEnvelope.PreferredCameraSpeedCmPerSecond > 0.0
        && OutEnvelope.PreferredSpacingCm > 0.0;
}

bool IsCueInsidePassage(
    const UInfinityStageShowAsset& Show,
    const FInfinityPassageSettings& Passage,
    const int32 CueIndex)
{
    const int32 First = Show.FindCueIndex(Passage.FirstCueGuid);
    const int32 Last = Show.FindCueIndex(Passage.LastCueGuid);
    return First != INDEX_NONE && Last != INDEX_NONE && CueIndex >= First && CueIndex <= Last;
}

void ApplyEnvelope(
    FInfinityPassageSettings& Target,
    const FInfinityWingSequencePassageEnvelope& Envelope,
    const FFrameRate SourceRate,
    const FFrameRate TargetRate)
{
    Target.LeadInFrames = FFrameNumber(FMath::Max(0,
        ConvertFrame(Envelope.LeadInFrames, SourceRate, TargetRate).Value));
    Target.TailFrames = FFrameNumber(FMath::Max(0,
        ConvertFrame(Envelope.TailFrames, SourceRate, TargetRate).Value));
    Target.LeadInDistanceCm = Envelope.LeadInDistanceCm;
    Target.TailDistanceCm = Envelope.TailDistanceCm;
    Target.PreferredCameraSpeedCmPerSecond = Envelope.PreferredCameraSpeedCmPerSecond;
    Target.bUseLiveMechanismPhasePattern = Envelope.bUseLiveMechanismPhasePattern;
    Target.MechanismPhaseStepCycles = Envelope.MechanismPhaseStepCycles;
    Target.MechanismPhaseOffsetCycles = Envelope.MechanismPhaseOffsetCycles;
    Target.FitMode = Envelope.FitMode;
    Target.PreferredSpacingCm = Envelope.PreferredSpacingCm;
}
}

bool FInfinityStageWingSequenceInterchange::ExportToJson(
    const UInfinityStageShowAsset& Show,
    const TArray<int32>& OrderedCueIndices,
    const FString& SequenceLabel,
    const FInfinityPassageSettings* CompletePassage,
    FString& OutJson,
    FString& OutReport)
{
    OutJson.Reset();
    OutReport.Reset();
    if (OrderedCueIndices.IsEmpty())
    {
        OutReport = TEXT("No Wing Pair cues were supplied for export.");
        return false;
    }

    const TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("format"), FormatName);
    Root->SetNumberField(TEXT("schema_version"), CurrentSchemaVersion);
    Root->SetStringField(TEXT("label"), SequenceLabel);
    Root->SetStringField(TEXT("source_show_path"), Show.GetPathName());
    Root->SetStringField(TEXT("source_show_guid"), Show.ShowGuid.ToString(EGuidFormats::DigitsWithHyphens));
    Root->SetObjectField(TEXT("source_display_rate"), FrameRateToJson(Show.DisplayRate));
    Root->SetObjectField(TEXT("source_tick_resolution"), FrameRateToJson(Show.TickResolution));

    TArray<TSharedPtr<FJsonValue>> CueValues;
    CueValues.Reserve(OrderedCueIndices.Num());
    TSet<int32> SeenIndices;
    for (const int32 CueIndex : OrderedCueIndices)
    {
        if (SeenIndices.Contains(CueIndex))
        {
            continue;
        }
        if (!Show.Cues.IsValidIndex(CueIndex) || Show.Cues[CueIndex].Type != EInfinityCueType::WingPair)
        {
            OutReport = FString::Printf(TEXT("Cue index %d is not a valid Wing Pair."), CueIndex);
            return false;
        }
        const TSharedPtr<FJsonObject> CueObject = FJsonObjectConverter::UStructToJsonObject(Show.Cues[CueIndex]);
        if (!CueObject.IsValid())
        {
            OutReport = FString::Printf(TEXT("Could not serialize Wing Pair cue %d."), CueIndex);
            return false;
        }
        CueValues.Add(MakeShared<FJsonValueObject>(CueObject));
        SeenIndices.Add(CueIndex);
    }
    Root->SetArrayField(TEXT("wing_cues"), CueValues);
    if (CompletePassage)
    {
        Root->SetObjectField(TEXT("passage_envelope"), EnvelopeToJson(*CompletePassage));
    }

    const TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> Writer =
        TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&OutJson);
    if (!FJsonSerializer::Serialize(Root, Writer))
    {
        OutReport = TEXT("Could not write the Infinity Stage Wing Sequence JSON document.");
        return false;
    }
    OutReport = FString::Printf(TEXT("Prepared %d Wing Pair(s) for export."), CueValues.Num());
    return true;
}

bool FInfinityStageWingSequenceInterchange::ImportFromJson(
    const FString& Json,
    FInfinityWingSequenceDocument& OutDocument,
    FString& OutReport)
{
    OutDocument = FInfinityWingSequenceDocument();
    OutReport.Reset();
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutReport = TEXT("The selected file is not valid JSON.");
        return false;
    }

    FString Format;
    double SchemaVersion = 0.0;
    if (!Root->TryGetStringField(TEXT("format"), Format) || Format != FormatName
        || !Root->TryGetNumberField(TEXT("schema_version"), SchemaVersion))
    {
        OutReport = TEXT("This is not an Infinity Stage Wing Sequence file.");
        return false;
    }
    if (FMath::RoundToInt(SchemaVersion) != CurrentSchemaVersion)
    {
        OutReport = FString::Printf(
            TEXT("Unsupported Wing Sequence schema %d; this plugin supports schema %d."),
            FMath::RoundToInt(SchemaVersion), CurrentSchemaVersion);
        return false;
    }
    if (!Root->HasTypedField<EJson::Object>(TEXT("source_tick_resolution"))
        || !Root->HasTypedField<EJson::Object>(TEXT("source_display_rate"))
        || !FrameRateFromJson(Root->GetObjectField(TEXT("source_tick_resolution")), OutDocument.SourceTickResolution)
        || !FrameRateFromJson(Root->GetObjectField(TEXT("source_display_rate")), OutDocument.SourceDisplayRate))
    {
        OutReport = TEXT("The Wing Sequence has an invalid source frame rate.");
        return false;
    }
    Root->TryGetStringField(TEXT("label"), OutDocument.Label);
    Root->TryGetStringField(TEXT("source_show_path"), OutDocument.SourceShowPath);
    FString SourceGuid;
    if (Root->TryGetStringField(TEXT("source_show_guid"), SourceGuid))
    {
        FGuid::Parse(SourceGuid, OutDocument.SourceShowGuid);
    }

    const TArray<TSharedPtr<FJsonValue>>* CueValues = nullptr;
    if (!Root->TryGetArrayField(TEXT("wing_cues"), CueValues) || !CueValues || CueValues->IsEmpty())
    {
        OutReport = TEXT("The Wing Sequence contains no Wing Pair cues.");
        return false;
    }
    OutDocument.Cues.Reserve(CueValues->Num());
    TSet<FGuid> SourceCueGuids;
    for (int32 Index = 0; Index < CueValues->Num(); ++Index)
    {
        if (!(*CueValues)[Index].IsValid() || (*CueValues)[Index]->Type != EJson::Object)
        {
            OutReport = FString::Printf(TEXT("Wing cue %d is not a JSON object."), Index + 1);
            return false;
        }
        const TSharedPtr<FJsonObject> CueObject = (*CueValues)[Index]->AsObject();
        FInfinityShowCue Cue;
        FText FailureReason;
        if (!CueObject.IsValid()
            || !FJsonObjectConverter::JsonObjectToUStruct(
                CueObject.ToSharedRef(), FInfinityShowCue::StaticStruct(), &Cue, 0, 0, false, &FailureReason))
        {
            OutReport = FString::Printf(TEXT("Wing cue %d could not be read: %s"), Index + 1, *FailureReason.ToString());
            return false;
        }
        if (Cue.Type != EInfinityCueType::WingPair)
        {
            OutReport = FString::Printf(TEXT("Entry %d is not a Wing Pair cue."), Index + 1);
            return false;
        }
        if (Cue.WingPair.IntervalToNext.Value < 1 || Cue.WingPair.GapToNextCm <= 0.0)
        {
            OutReport = FString::Printf(TEXT("Wing cue %d has invalid timing or spacing."), Index + 1);
            return false;
        }
        if (Cue.CueGuid.IsValid() && SourceCueGuids.Contains(Cue.CueGuid))
        {
            OutReport = FString::Printf(TEXT("Wing cue %d repeats a source Cue GUID."), Index + 1);
            return false;
        }
        SourceCueGuids.Add(Cue.CueGuid);
        OutDocument.Cues.Add(MoveTemp(Cue));
    }

    if (Root->HasTypedField<EJson::Object>(TEXT("passage_envelope")))
    {
        FInfinityWingSequencePassageEnvelope Envelope;
        if (!EnvelopeFromJson(Root->GetObjectField(TEXT("passage_envelope")), Envelope))
        {
            OutReport = TEXT("The complete-Passage envelope is invalid.");
            return false;
        }
        OutDocument.PassageEnvelope = Envelope;
    }
    OutReport = FString::Printf(TEXT("Read %d Wing Pair(s) from '%s'."),
        OutDocument.Cues.Num(), *OutDocument.Label);
    return true;
}

bool FInfinityStageWingSequenceInterchange::SaveToFile(
    const FString& Filename,
    const FString& Json,
    FString& OutReport)
{
    if (Filename.IsEmpty())
    {
        OutReport = TEXT("No export filename was selected.");
        return false;
    }
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true);
    if (!FFileHelper::SaveStringToFile(Json, *Filename, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        OutReport = FString::Printf(TEXT("Could not write '%s'."), *Filename);
        return false;
    }
    OutReport = FString::Printf(TEXT("Saved Infinity Stage Wing Sequence: %s"), *Filename);
    return true;
}

bool FInfinityStageWingSequenceInterchange::LoadFromFile(
    const FString& Filename,
    FInfinityWingSequenceDocument& OutDocument,
    FString& OutReport)
{
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *Filename))
    {
        OutReport = FString::Printf(TEXT("Could not read '%s'."), *Filename);
        return false;
    }
    if (!ImportFromJson(Json, OutDocument, OutReport))
    {
        OutReport = FString::Printf(TEXT("%s\nFile: %s"), *OutReport, *Filename);
        return false;
    }
    return true;
}

bool FInfinityStageWingSequenceInterchange::PrepareImportedCues(
    const FInfinityWingSequenceDocument& Document,
    const FFrameRate TargetTickResolution,
    TArray<FInfinityShowCue>& OutCues,
    FString& OutReport)
{
    OutCues.Reset();
    OutReport.Reset();
    if (!Document.SourceTickResolution.IsValid() || !TargetTickResolution.IsValid() || Document.Cues.IsEmpty())
    {
        OutReport = TEXT("The source or destination timing information is invalid.");
        return false;
    }

    TMap<FGuid, FGuid> CueGuidMap;
    OutCues = Document.Cues;
    for (FInfinityShowCue& Cue : OutCues)
    {
        const FGuid SourceCueGuid = Cue.CueGuid;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = FFrameNumber(FMath::Max(1,
            ConvertFrame(Cue.WingPair.IntervalToNext, Document.SourceTickResolution, TargetTickResolution).Value));
        Cue.WingPair.Mechanism.ExplicitOriginFrame = ConvertFrame(
            Cue.WingPair.Mechanism.ExplicitOriginFrame,
            Document.SourceTickResolution,
            TargetTickResolution);
        if (SourceCueGuid.IsValid())
        {
            CueGuidMap.Add(SourceCueGuid, Cue.CueGuid);
        }
    }
    for (FInfinityShowCue& Cue : OutCues)
    {
        FInfinityCameraGustSettings& Gust = Cue.WingPair.Mechanism.CameraGust;
        if (!Gust.GroupAnchorCueGuid.IsValid())
        {
            continue;
        }
        if (const FGuid* NewAnchor = CueGuidMap.Find(Gust.GroupAnchorCueGuid))
        {
            Gust.GroupAnchorCueGuid = *NewAnchor;
        }
        else
        {
            Gust.GroupAnchorCueGuid = Cue.CueGuid;
            Gust.GroupOrdinal = 0;
            Gust.GroupSize = 1;
        }
    }
    OutReport = FString::Printf(TEXT("Prepared %d imported Wing Pair(s) with fresh identities."), OutCues.Num());
    return true;
}

bool FInfinityStageWingSequenceInterchange::InsertAfter(
    UInfinityStageShowAsset& Show,
    const int32 AfterCueIndex,
    const FInfinityWingSequenceDocument& Document,
    TArray<int32>& OutInsertedIndices,
    FString& OutReport)
{
    TArray<FInfinityShowCue> ImportedCues;
    if (!PrepareImportedCues(Document, Show.TickResolution, ImportedCues, OutReport))
    {
        return false;
    }
    const int32 InsertIndex = FMath::Clamp(AfterCueIndex + 1, 0, Show.Cues.Num());
    Show.Cues.Insert(ImportedCues, InsertIndex);
    OutInsertedIndices.Reset();
    for (int32 Index = 0; Index < ImportedCues.Num(); ++Index)
    {
        OutInsertedIndices.Add(InsertIndex + Index);
    }
    Show.EnsureStableIds();
    Show.ReconcilePassageSettings();
    OutReport = FString::Printf(TEXT("Inserted %d Wing Pair(s)."), ImportedCues.Num());
    return true;
}

bool FInfinityStageWingSequenceInterchange::ReplacePassage(
    UInfinityStageShowAsset& Show,
    const FGuid TargetPassageGuid,
    const FInfinityWingSequenceDocument& Document,
    TArray<int32>& OutInsertedIndices,
    FString& OutReport)
{
    const FInfinityPassageSettings* Existing = Show.PassageSettings.FindByPredicate(
        [TargetPassageGuid](const FInfinityPassageSettings& Passage)
        {
            return Passage.PassageGuid == TargetPassageGuid;
        });
    if (!Existing)
    {
        OutReport = TEXT("Select a valid Passage heading or one of its Wing Pair cues before replacing.");
        return false;
    }
    const int32 FirstIndex = Show.FindCueIndex(Existing->FirstCueGuid);
    const int32 LastIndex = Show.FindCueIndex(Existing->LastCueGuid);
    if (FirstIndex == INDEX_NONE || LastIndex < FirstIndex)
    {
        OutReport = TEXT("The selected Passage range is invalid.");
        return false;
    }

    const FInfinityPassageSettings PreservedSettings = *Existing;
    TArray<FInfinityShowCue> ImportedCues;
    if (!PrepareImportedCues(Document, Show.TickResolution, ImportedCues, OutReport))
    {
        return false;
    }
    if (!ImportedCues.ContainsByPredicate([](const FInfinityShowCue& Cue) { return Cue.bEnabled; }))
    {
        OutReport = TEXT("A Passage replacement needs at least one enabled Wing Pair.");
        return false;
    }
    if (ImportedCues.ContainsByPredicate([](const FInfinityShowCue& Cue) { return !Cue.bEnabled; }))
    {
        OutReport = TEXT("A Passage replacement requires every imported Wing Pair to be enabled. Use Insert for a block containing disabled rows.");
        return false;
    }

    Show.Cues.RemoveAt(FirstIndex, LastIndex - FirstIndex + 1);
    Show.Cues.Insert(ImportedCues, FirstIndex);
    OutInsertedIndices.Reset();
    for (int32 Index = 0; Index < ImportedCues.Num(); ++Index)
    {
        OutInsertedIndices.Add(FirstIndex + Index);
    }
    Show.EnsureStableIds();
    Show.ReconcilePassageSettings();

    FInfinityPassageSettings* Replacement = Show.PassageSettings.FindByPredicate(
        [&Show, FirstIndex](const FInfinityPassageSettings& Passage)
        {
            return IsCueInsidePassage(Show, Passage, FirstIndex);
        });
    if (!Replacement)
    {
        OutReport = TEXT("The imported rows did not produce a valid enabled Passage.");
        return false;
    }
    const FGuid DerivedGuid = Replacement->PassageGuid;
    const FGuid FirstCueGuid = Replacement->FirstCueGuid;
    const FGuid LastCueGuid = Replacement->LastCueGuid;
    *Replacement = PreservedSettings;
    Replacement->PassageGuid = TargetPassageGuid;
    Replacement->FirstCueGuid = FirstCueGuid;
    Replacement->LastCueGuid = LastCueGuid;
    if (Document.PassageEnvelope.IsSet())
    {
        ApplyEnvelope(*Replacement, Document.PassageEnvelope.GetValue(),
            Document.SourceTickResolution, Show.TickResolution);
    }
    for (FInfinityPassageSettings& Passage : Show.PassageSettings)
    {
        if (&Passage != Replacement && Passage.PassageGuid == TargetPassageGuid)
        {
            Passage.PassageGuid = DerivedGuid.IsValid() && DerivedGuid != TargetPassageGuid
                ? DerivedGuid
                : FGuid::NewGuid();
        }
    }
    OutReport = FString::Printf(
        TEXT("Replaced Passage '%s' with %d Wing Pair(s); Passage identity, music and temporality were preserved."),
        *PreservedSettings.Label.ToString(), ImportedCues.Num());
    return true;
}

bool FInfinityStageWingSequenceInterchange::ApplyArrangementToPassage(
    UInfinityStageShowAsset& Show,
    const FGuid TargetPassageGuid,
    const FInfinityWingSequenceDocument& Document,
    TArray<int32>& OutAffectedIndices,
    FString& OutReport)
{
    const FInfinityPassageSettings* Passage = Show.PassageSettings.FindByPredicate(
        [TargetPassageGuid](const FInfinityPassageSettings& Candidate)
        {
            return Candidate.PassageGuid == TargetPassageGuid;
        });
    if (!Passage)
    {
        OutReport = TEXT("Select a valid Passage before applying a Wing arrangement.");
        return false;
    }
    const int32 FirstIndex = Show.FindCueIndex(Passage->FirstCueGuid);
    const int32 LastIndex = Show.FindCueIndex(Passage->LastCueGuid);
    if (FirstIndex == INDEX_NONE || LastIndex < FirstIndex)
    {
        OutReport = TEXT("The selected Passage range is invalid.");
        return false;
    }

    TArray<FInfinityShowCue> Pattern;
    if (!PrepareImportedCues(Document, Show.TickResolution, Pattern, OutReport))
    {
        return false;
    }
    if (Pattern.IsEmpty())
    {
        OutReport = TEXT("The saved Wing arrangement contains no Wing Pairs.");
        return false;
    }

    TMap<FGuid, int32> PatternIndexByGuid;
    for (int32 PatternIndex = 0; PatternIndex < Pattern.Num(); ++PatternIndex)
    {
        PatternIndexByGuid.Add(Pattern[PatternIndex].CueGuid, PatternIndex);
    }

    OutAffectedIndices.Reset();
    const int32 TargetCount = LastIndex - FirstIndex + 1;
    for (int32 TargetOrdinal = 0; TargetOrdinal < TargetCount; ++TargetOrdinal)
    {
        const int32 TargetIndex = FirstIndex + TargetOrdinal;
        FInfinityShowCue& Target = Show.Cues[TargetIndex];
        if (Target.Type != EInfinityCueType::WingPair)
        {
            OutReport = TEXT("The selected Passage contains a non-Wing cue.");
            return false;
        }

        const FInfinityShowCue& Source = Pattern[TargetOrdinal % Pattern.Num()];
        const FGuid StableCueGuid = Target.CueGuid;
        const FGuid StableOccurrenceGuid = Target.WingPair.OccurrenceGuid;
        const FFrameNumber StableInterval = Target.WingPair.IntervalToNext;
        const double StableGap = Target.WingPair.GapToNextCm;
        const int32 StableLayoutOverrides = Target.WingPair.LocalOverrideMask
            & (static_cast<int32>(EInfinityLocalOverride::IntervalToNext)
                | static_cast<int32>(EInfinityLocalOverride::GapToNext));

        Target.WingPair = Source.WingPair;
        Target.CueGuid = StableCueGuid;
        Target.WingPair.OccurrenceGuid = StableOccurrenceGuid;
        Target.WingPair.IntervalToNext = StableInterval;
        Target.WingPair.GapToNextCm = StableGap;
        Target.WingPair.LocalOverrideMask =
            (Target.WingPair.LocalOverrideMask
                & ~(static_cast<int32>(EInfinityLocalOverride::IntervalToNext)
                    | static_cast<int32>(EInfinityLocalOverride::GapToNext)))
            | StableLayoutOverrides;

        FInfinityCameraGustSettings& Gust = Target.WingPair.Mechanism.CameraGust;
        if (Gust.GroupAnchorCueGuid.IsValid())
        {
            const int32* SourceAnchorOrdinal = PatternIndexByGuid.Find(Gust.GroupAnchorCueGuid);
            const int32 CycleStart = TargetOrdinal - (TargetOrdinal % Pattern.Num());
            const int32 TargetAnchorOrdinal = SourceAnchorOrdinal
                ? CycleStart + *SourceAnchorOrdinal
                : INDEX_NONE;
            Gust.GroupAnchorCueGuid = TargetAnchorOrdinal >= 0 && TargetAnchorOrdinal < TargetCount
                ? Show.Cues[FirstIndex + TargetAnchorOrdinal].CueGuid
                : StableCueGuid;
        }
        OutAffectedIndices.Add(TargetIndex);
    }

    // Repeated or tail-trimmed source groups must describe the actual imported
    // target group rather than retaining the source file's group size.
    TMap<FGuid, TArray<int32>> GustGroups;
    TArray<int32> CameraLedGustRows;
    for (const int32 TargetIndex : OutAffectedIndices)
    {
        FInfinityShowCue& Cue = Show.Cues[TargetIndex];
        if (Cue.WingPair.Mechanism.PlaybackMode == EInfinityMotionPlaybackMode::CameraGust
            && Cue.WingPair.Mechanism.CameraGust.GroupAnchorCueGuid.IsValid())
        {
            if (Cue.WingPair.Mechanism.CameraGust.TimingMode
                == EInfinityCameraGustTimingMode::CameraTravelWindow)
            {
                CameraLedGustRows.Add(TargetIndex);
            }
            else
            {
                GustGroups.FindOrAdd(Cue.WingPair.Mechanism.CameraGust.GroupAnchorCueGuid).Add(TargetIndex);
            }
        }
    }
    if (!CameraLedGustRows.IsEmpty())
    {
        const FGuid AnchorGuid = Show.Cues[CameraLedGustRows[0]].CueGuid;
        for (int32 Ordinal = 0; Ordinal < CameraLedGustRows.Num(); ++Ordinal)
        {
            FInfinityCameraGustSettings& Gust =
                Show.Cues[CameraLedGustRows[Ordinal]].WingPair.Mechanism.CameraGust;
            Gust.GroupAnchorCueGuid = AnchorGuid;
            Gust.GroupOrdinal = Ordinal;
            Gust.GroupSize = CameraLedGustRows.Num();
        }
    }
    for (const TPair<FGuid, TArray<int32>>& Group : GustGroups)
    {
        for (int32 Ordinal = 0; Ordinal < Group.Value.Num(); ++Ordinal)
        {
            FInfinityCameraGustSettings& Gust =
                Show.Cues[Group.Value[Ordinal]].WingPair.Mechanism.CameraGust;
            Gust.GroupOrdinal = Ordinal;
            Gust.GroupSize = Group.Value.Num();
        }
    }

    Show.EnsureStableIds();
    const FString FillDescription = TargetCount == Pattern.Num()
        ? TEXT("one-to-one")
        : (TargetCount > Pattern.Num() ? TEXT("repeated") : TEXT("trimmed"));
    OutReport = FString::Printf(
        TEXT("Applied '%s' across %d existing Wing Pair(s) (%s from %d saved rows); target names, timing, spacing and Passage settings were preserved."),
        *Document.Label, TargetCount, *FillDescription, Pattern.Num());
    return true;
}

bool FInfinityStageWingSequenceInterchange::ResizePassageToCountPreservingPattern(
    UInfinityStageShowAsset& Show,
    const FGuid TargetPassageGuid,
    const int32 DesiredWingPairCount,
    const FFrameNumber IntervalToNext,
    const double GapToNextCm,
    TArray<int32>& OutAffectedIndices,
    FString& OutReport)
{
    if (DesiredWingPairCount < 1 || IntervalToNext.Value < 1 || GapToNextCm <= 0.0)
    {
        OutReport = TEXT("The fitted Wing count, interval or spacing is invalid.");
        return false;
    }
    const FInfinityPassageSettings* Existing = Show.PassageSettings.FindByPredicate(
        [TargetPassageGuid](const FInfinityPassageSettings& Candidate)
        {
            return Candidate.PassageGuid == TargetPassageGuid;
        });
    if (!Existing)
    {
        OutReport = TEXT("Select a Passage before resetting its Wing count.");
        return false;
    }
    const int32 FirstIndex = Show.FindCueIndex(Existing->FirstCueGuid);
    const int32 LastIndex = Show.FindCueIndex(Existing->LastCueGuid);
    if (FirstIndex == INDEX_NONE || LastIndex < FirstIndex)
    {
        OutReport = TEXT("The selected Passage range is invalid.");
        return false;
    }

    const FInfinityPassageSettings PreservedSettings = *Existing;
    const int32 ExistingCount = LastIndex - FirstIndex + 1;
    TArray<FInfinityShowCue> Pattern;
    Pattern.Reserve(ExistingCount);
    for (int32 Index = FirstIndex; Index <= LastIndex; ++Index)
    {
        if (Show.Cues[Index].Type != EInfinityCueType::WingPair)
        {
            OutReport = TEXT("The selected Passage contains a non-Wing cue.");
            return false;
        }
        Pattern.Add(Show.Cues[Index]);
    }

    if (DesiredWingPairCount < ExistingCount)
    {
        Show.Cues.RemoveAt(FirstIndex + DesiredWingPairCount, ExistingCount - DesiredWingPairCount);
    }
    else if (DesiredWingPairCount > ExistingCount)
    {
        for (int32 Ordinal = ExistingCount; Ordinal < DesiredWingPairCount; ++Ordinal)
        {
            FInfinityShowCue Copy = Pattern[Ordinal % Pattern.Num()];
            Copy.CueGuid = FGuid::NewGuid();
            Copy.WingPair.OccurrenceGuid = FGuid::NewGuid();
            Copy.Label = FText::Format(
                NSLOCTEXT("InfinityStage", "MusicFitAddedWingLabel", "{0} / Wing {1}"),
                PreservedSettings.Label,
                FText::AsNumber(Ordinal + 1));
            Show.Cues.Insert(Copy, FirstIndex + Ordinal);
        }
    }

    OutAffectedIndices.Reset();
    const int32 LayoutOverrideMask = static_cast<int32>(EInfinityLocalOverride::IntervalToNext)
        | static_cast<int32>(EInfinityLocalOverride::GapToNext);
    TMap<FGuid, int32> PatternIndexByGuid;
    for (int32 PatternIndex = 0; PatternIndex < Pattern.Num(); ++PatternIndex)
    {
        PatternIndexByGuid.Add(Pattern[PatternIndex].CueGuid, PatternIndex);
    }
    for (int32 Ordinal = 0; Ordinal < DesiredWingPairCount; ++Ordinal)
    {
        FInfinityShowCue& Cue = Show.Cues[FirstIndex + Ordinal];
        Cue.WingPair.IntervalToNext = IntervalToNext;
        Cue.WingPair.GapToNextCm = GapToNextCm;
        Cue.WingPair.LocalOverrideMask &= ~LayoutOverrideMask;
        FInfinityCameraGustSettings& Gust = Cue.WingPair.Mechanism.CameraGust;
        if (Gust.GroupAnchorCueGuid.IsValid())
        {
            const int32 SourceOrdinal = Ordinal % Pattern.Num();
            const int32* SourceAnchorOrdinal = PatternIndexByGuid.Find(
                Pattern[SourceOrdinal].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid);
            const int32 CycleStart = Ordinal - SourceOrdinal;
            const int32 TargetAnchorOrdinal = SourceAnchorOrdinal
                ? CycleStart + *SourceAnchorOrdinal
                : INDEX_NONE;
            Gust.GroupAnchorCueGuid = TargetAnchorOrdinal >= 0
                    && TargetAnchorOrdinal < DesiredWingPairCount
                ? Show.Cues[FirstIndex + TargetAnchorOrdinal].CueGuid
                : Cue.CueGuid;
        }
        OutAffectedIndices.Add(FirstIndex + Ordinal);
    }

    TMap<FGuid, TArray<int32>> GustGroups;
    TArray<int32> CameraLedGustRows;
    for (const int32 TargetIndex : OutAffectedIndices)
    {
        FInfinityShowCue& Cue = Show.Cues[TargetIndex];
        if (Cue.WingPair.Mechanism.PlaybackMode == EInfinityMotionPlaybackMode::CameraGust
            && Cue.WingPair.Mechanism.CameraGust.GroupAnchorCueGuid.IsValid())
        {
            if (Cue.WingPair.Mechanism.CameraGust.TimingMode
                == EInfinityCameraGustTimingMode::CameraTravelWindow)
            {
                CameraLedGustRows.Add(TargetIndex);
            }
            else
            {
                GustGroups.FindOrAdd(Cue.WingPair.Mechanism.CameraGust.GroupAnchorCueGuid).Add(TargetIndex);
            }
        }
    }
    if (!CameraLedGustRows.IsEmpty())
    {
        const FGuid AnchorGuid = Show.Cues[CameraLedGustRows[0]].CueGuid;
        for (int32 Ordinal = 0; Ordinal < CameraLedGustRows.Num(); ++Ordinal)
        {
            FInfinityCameraGustSettings& Gust =
                Show.Cues[CameraLedGustRows[Ordinal]].WingPair.Mechanism.CameraGust;
            Gust.GroupAnchorCueGuid = AnchorGuid;
            Gust.GroupOrdinal = Ordinal;
            Gust.GroupSize = CameraLedGustRows.Num();
        }
    }
    for (const TPair<FGuid, TArray<int32>>& Group : GustGroups)
    {
        for (int32 Ordinal = 0; Ordinal < Group.Value.Num(); ++Ordinal)
        {
            FInfinityCameraGustSettings& Gust =
                Show.Cues[Group.Value[Ordinal]].WingPair.Mechanism.CameraGust;
            Gust.GroupOrdinal = Ordinal;
            Gust.GroupSize = Group.Value.Num();
        }
    }

    Show.EnsureStableIds();
    Show.ReconcilePassageSettings();
    FInfinityPassageSettings* Resized = Show.PassageSettings.FindByPredicate(
        [&Show, FirstIndex](const FInfinityPassageSettings& Candidate)
        {
            return IsCueInsidePassage(Show, Candidate, FirstIndex);
        });
    if (!Resized)
    {
        OutReport = TEXT("The resized rows did not produce a valid Passage.");
        return false;
    }
    const FGuid FirstCueGuid = Resized->FirstCueGuid;
    const FGuid LastCueGuid = Resized->LastCueGuid;
    *Resized = PreservedSettings;
    Resized->PassageGuid = TargetPassageGuid;
    Resized->FirstCueGuid = FirstCueGuid;
    Resized->LastCueGuid = LastCueGuid;

    OutReport = FString::Printf(
        TEXT("Reset '%s' from %d to %d Wing Pair(s); the existing ordered arrangement was used as the repeat pattern."),
        *PreservedSettings.Label.ToString(), ExistingCount, DesiredWingPairCount);
    return true;
}
