#include "InfinityStageMusicAnalysisImporter.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "FileHelpers.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "InfinityStageMusicMapAsset.h"
#include "InfinityStageShowAsset.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundBase.h"

namespace
{
FGuid StableMarkerGuid(const FString& SourceFingerprint, const FString& Kind, const double TimeSeconds)
{
    const FString Key = FString::Printf(TEXT("%s|%s|%.6f"), *SourceFingerprint, *Kind, TimeSeconds);
    FTCHARToUTF8 Utf8(*Key);
    FMD5 Md5;
    Md5.Update(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
    uint8 Bytes[16];
    Md5.Final(Bytes);
    uint32 Parts[4];
    FMemory::Memcpy(Parts, Bytes, sizeof(Parts));
    return FGuid(Parts[0], Parts[1], Parts[2], Parts[3]);
}

UInfinityStageMusicMapAsset* LoadOrCreateMap(const int32 Passage)
{
    const FString AssetName = FString::Printf(TEXT("MM_P%02d_Analysis"), Passage);
    const FString PackageName = FString::Printf(TEXT("/Game/InfinityStage/MusicMaps/%s"), *AssetName);
    const FString ObjectPath = FString::Printf(TEXT("%s.%s"), *PackageName, *AssetName);
    if (UInfinityStageMusicMapAsset* Existing = LoadObject<UInfinityStageMusicMapAsset>(nullptr, *ObjectPath))
    {
        return Existing;
    }
    UPackage* Package = CreatePackage(*PackageName);
    UInfinityStageMusicMapAsset* Asset = NewObject<UInfinityStageMusicMapAsset>(
        Package,
        *AssetName,
        RF_Public | RF_Standalone | RF_Transactional);
    Asset->MusicMapGuid = FGuid::NewGuid();
    FAssetRegistryModule::AssetCreated(Asset);
    Package->MarkPackageDirty();
    return Asset;
}

void ReadMarkers(
    const TSharedPtr<FJsonObject>& Root,
    const TCHAR* Field,
    const FString& Kind,
    const FString& Fingerprint,
    const FText& DefaultLabel,
    TArray<FInfinityMusicAnalysisMarker>& OutMarkers)
{
    TMap<FGuid, EInfinityMusicProposalState> ExistingStates;
    for (const FInfinityMusicAnalysisMarker& Marker : OutMarkers)
    {
        ExistingStates.Add(Marker.MarkerGuid, Marker.State);
    }
    OutMarkers.Reset();

    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Root->TryGetArrayField(Field, Values) || !Values)
    {
        return;
    }
    for (const TSharedPtr<FJsonValue>& Value : *Values)
    {
        const TSharedPtr<FJsonObject> Object = Value->AsObject();
        if (!Object)
        {
            continue;
        }
        FInfinityMusicAnalysisMarker& Marker = OutMarkers.AddDefaulted_GetRef();
        Marker.TimeSeconds = Object->GetNumberField(TEXT("timeSeconds"));
        if (!Object->TryGetNumberField(TEXT("strength"), Marker.Strength))
        {
            Object->TryGetNumberField(TEXT("confidence"), Marker.Strength);
        }
        Marker.MarkerGuid = StableMarkerGuid(Fingerprint, Kind, Marker.TimeSeconds);
        FString Label;
        Marker.Label = Object->TryGetStringField(TEXT("label"), Label) ? FText::FromString(Label) : DefaultLabel;
        Marker.State = ExistingStates.FindRef(Marker.MarkerGuid);
        if (!ExistingStates.Contains(Marker.MarkerGuid))
        {
            Marker.State = EInfinityMusicProposalState::Suggested;
        }
    }
}
}

bool FInfinityStageMusicAnalysisImporter::ImportDirectory(
    const FString& AnalysisDirectory,
    UInfinityStageShowAsset* Show,
    FString& OutReport)
{
    OutReport.Reset();
    if (!Show)
    {
        OutReport = TEXT("A Show Asset is required.");
        return false;
    }

    TArray<FString> Files;
    IFileManager::Get().FindFiles(Files, *FPaths::Combine(AnalysisDirectory, TEXT("*.analysis.json")), true, false);
    Files.Sort();
    if (Files.IsEmpty())
    {
        OutReport = FString::Printf(TEXT("No analysis JSON files were found in %s."), *AnalysisDirectory);
        return false;
    }

    TArray<UPackage*> PackagesToSave;
    int32 Imported = 0;
    Show->Modify();
    for (const FString& Filename : Files)
    {
        FString JsonText;
        if (!FFileHelper::LoadFileToString(JsonText, *FPaths::Combine(AnalysisDirectory, Filename)))
        {
            OutReport = FString::Printf(TEXT("Could not read %s."), *Filename);
            return false;
        }
        TSharedPtr<FJsonObject> Root;
        if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root)
        {
            OutReport = FString::Printf(TEXT("Invalid JSON in %s."), *Filename);
            return false;
        }
        const TSharedPtr<FJsonObject> Safety = Root->GetObjectField(TEXT("safety"));
        if (!Safety || Safety->GetBoolField(TEXT("cueScoreMutated")))
        {
            OutReport = FString::Printf(TEXT("Unsafe analysis record refused: %s."), *Filename);
            return false;
        }

        const int32 Passage = FMath::RoundToInt(Root->GetNumberField(TEXT("passage")));
        if (!Show->MusicRails.IsValidIndex(Passage - 1))
        {
            OutReport = FString::Printf(TEXT("%s targets missing Passage %d."), *Filename, Passage);
            return false;
        }
        const TSharedPtr<FJsonObject> Source = Root->GetObjectField(TEXT("source"));
        const TSharedPtr<FJsonObject> Analyzer = Root->GetObjectField(TEXT("analyzer"));
        if (!Source || !Analyzer)
        {
            OutReport = FString::Printf(TEXT("%s has no source/provider record."), *Filename);
            return false;
        }

        UInfinityStageMusicMapAsset* Map = LoadOrCreateMap(Passage);
        Map->Modify();
        if (!Map->MusicMapGuid.IsValid())
        {
            Map->MusicMapGuid = FGuid::NewGuid();
        }
        Map->SourceFilename = Source->GetStringField(TEXT("filename"));
        Map->SourceSha256 = Source->GetStringField(TEXT("sha256"));
        Map->SourceMd5 = Source->GetStringField(TEXT("md5"));
        Map->DurationSeconds = Source->GetNumberField(TEXT("sourceDurationSeconds"));
        Map->ProviderName = Analyzer->GetStringField(TEXT("name"));
        Map->ProviderVersion = Analyzer->GetStringField(TEXT("version"));
        Map->GeneratedAtUtc = Root->GetStringField(TEXT("generatedAtUtc"));
        Map->bCueScoreMutatedByAnalysis = false;
        Map->bRequiresArtistApproval = true;
        Map->Sound = TSoftObjectPtr<USoundBase>(FSoftObjectPath(Source->GetStringField(TEXT("unrealSoundPath"))));

        TMap<int32, EInfinityMusicProposalState> TempoStates;
        for (const FInfinityTempoCandidate& Candidate : Map->TempoCandidates)
        {
            TempoStates.Add(FMath::RoundToInt(Candidate.Bpm * 100.0), Candidate.State);
        }
        Map->TempoCandidates.Reset();
        const TArray<TSharedPtr<FJsonValue>>& Tempos = Root->GetArrayField(TEXT("tempoCandidates"));
        for (const TSharedPtr<FJsonValue>& TempoValue : Tempos)
        {
            const TSharedPtr<FJsonObject> TempoObject = TempoValue->AsObject();
            if (!TempoObject)
            {
                continue;
            }
            FInfinityTempoCandidate& Candidate = Map->TempoCandidates.AddDefaulted_GetRef();
            Candidate.Bpm = TempoObject->GetNumberField(TEXT("bpm"));
            Candidate.Confidence = TempoObject->GetNumberField(TEXT("confidence"));
            Candidate.Rank = FMath::RoundToInt(TempoObject->GetNumberField(TEXT("rank")));
            const int32 StateKey = FMath::RoundToInt(Candidate.Bpm * 100.0);
            Candidate.State = TempoStates.Contains(StateKey)
                ? TempoStates.FindRef(StateKey)
                : EInfinityMusicProposalState::Suggested;
        }

        Map->WaveformBins.Reset();
        const TArray<TSharedPtr<FJsonValue>>& Waveform = Root->GetArrayField(TEXT("waveform"));
        Map->WaveformBins.Reserve(Waveform.Num());
        for (const TSharedPtr<FJsonValue>& BinValue : Waveform)
        {
            const TSharedPtr<FJsonObject> Bin = BinValue->AsObject();
            if (Bin)
            {
                Map->WaveformBins.Add(FVector3f(
                    Bin->GetNumberField(TEXT("min")),
                    Bin->GetNumberField(TEXT("max")),
                    Bin->GetNumberField(TEXT("rms"))));
            }
        }

        ReadMarkers(Root, TEXT("onsetProposals"), TEXT("Onset"), Map->SourceSha256, NSLOCTEXT("InfinityStage", "OnsetProposal", "Onset suggestion"), Map->OnsetProposals);
        ReadMarkers(Root, TEXT("beatProposals"), TEXT("Beat"), Map->SourceSha256, NSLOCTEXT("InfinityStage", "BeatProposal", "Beat suggestion"), Map->BeatProposals);
        ReadMarkers(Root, TEXT("majorChangeProposals"), TEXT("MajorChange"), Map->SourceSha256, NSLOCTEXT("InfinityStage", "ChangeProposal", "Major change suggestion"), Map->MajorChangeProposals);

        // Continuous envelopes and characterised spans (analysis schema 2).
        // Absent in older files, so this stays optional rather than failing.
        Map->FeatureCurves.Reset();
        Map->ExpressiveSections.Reset();
        const TSharedPtr<FJsonObject>* CurveRoot = nullptr;
        if (Root->TryGetObjectField(TEXT("featureCurves"), CurveRoot) && CurveRoot && CurveRoot->IsValid())
        {
            const double RateHz = (*CurveRoot)->HasField(TEXT("rateHz"))
                ? (*CurveRoot)->GetNumberField(TEXT("rateHz"))
                : 10.0;
            const TSharedPtr<FJsonObject>* NamedCurves = nullptr;
            if ((*CurveRoot)->TryGetObjectField(TEXT("curves"), NamedCurves) && NamedCurves && NamedCurves->IsValid())
            {
                for (const TPair<FString, TSharedPtr<FJsonValue>>& Entry : (*NamedCurves)->Values)
                {
                    const TArray<TSharedPtr<FJsonValue>>* Samples = nullptr;
                    if (!Entry.Value.IsValid() || !Entry.Value->TryGetArray(Samples) || !Samples)
                    {
                        continue;
                    }
                    FInfinityAnalysisCurve& Curve = Map->FeatureCurves.AddDefaulted_GetRef();
                    Curve.Name = FName(*Entry.Key);
                    Curve.RateHz = static_cast<float>(RateHz);
                    Curve.Values.Reserve(Samples->Num());
                    for (const TSharedPtr<FJsonValue>& Sample : *Samples)
                    {
                        Curve.Values.Add(Sample.IsValid() ? static_cast<float>(Sample->AsNumber()) : 0.0f);
                    }
                }
            }
        }
        const TArray<TSharedPtr<FJsonValue>>* SectionValues = nullptr;
        if (Root->TryGetArrayField(TEXT("expressiveSections"), SectionValues) && SectionValues)
        {
            for (const TSharedPtr<FJsonValue>& Value : *SectionValues)
            {
                const TSharedPtr<FJsonObject>* Object = nullptr;
                if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object)
                {
                    continue;
                }
                FInfinityExpressiveSection& Section = Map->ExpressiveSections.AddDefaulted_GetRef();
                Section.StartSeconds = (*Object)->GetNumberField(TEXT("startSeconds"));
                Section.EndSeconds = (*Object)->GetNumberField(TEXT("endSeconds"));
                Section.MeanIntensity = (*Object)->GetNumberField(TEXT("meanIntensity"));
                Section.Trend = (*Object)->GetNumberField(TEXT("trend"));
                (*Object)->TryGetStringField(TEXT("label"), Section.Label);
            }
        }

        Map->MarkPackageDirty();
        PackagesToSave.AddUnique(Map->GetOutermost());
        Show->MusicRails[Passage - 1].AnalysisMap = Map;
        ++Imported;
    }

    Show->MarkPackageDirty();
    PackagesToSave.AddUnique(Show->GetOutermost());
    if (!UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, false))
    {
        OutReport = TEXT("Analysis maps were imported but one or more packages did not save.");
        return false;
    }
    OutReport = FString::Printf(TEXT("Imported %d versioned Music Map asset(s); Cue Score rows were not changed."), Imported);
    return true;
}

namespace
{
/** Canonical 44-byte RIFF header for 16-bit PCM. */
void AppendWavHeader(TArray<uint8>& Out, const int32 PcmBytes, const uint32 SampleRate, const uint16 Channels)
{
    const uint16 BitsPerSample = 16;
    const uint16 BlockAlign = Channels * BitsPerSample / 8;
    const uint32 ByteRate = SampleRate * BlockAlign;
    auto Push32 = [&Out](const uint32 Value)
    {
        Out.Append(reinterpret_cast<const uint8*>(&Value), 4);
    };
    auto Push16 = [&Out](const uint16 Value)
    {
        Out.Append(reinterpret_cast<const uint8*>(&Value), 2);
    };
    Out.Append(reinterpret_cast<const uint8*>("RIFF"), 4);
    Push32(static_cast<uint32>(36 + PcmBytes));
    Out.Append(reinterpret_cast<const uint8*>("WAVEfmt "), 8);
    Push32(16);
    Push16(1);
    Push16(Channels);
    Push32(SampleRate);
    Push32(ByteRate);
    Push16(BlockAlign);
    Push16(BitsPerSample);
    Out.Append(reinterpret_cast<const uint8*>("data"), 4);
    Push32(static_cast<uint32>(PcmBytes));
}

/** Interpreter candidates for the analyzer, in the order they are tried.
 *
 * The analyzer imports numpy, which the engine's bundled Python does not ship,
 * so this deliberately looks for a *system* interpreter rather than Unreal's
 * own. Set INFINITYSTAGE_PYTHON to name one explicitly on a machine whose
 * layout is unusual.
 *
 * Each entry is an executable plus any argument prefix it needs before the
 * script path.
 */
void GatherPythonCandidates(TArray<TPair<FString, FString>>& OutCandidates)
{
    const FString Override = FPlatformMisc::GetEnvironmentVariable(TEXT("INFINITYSTAGE_PYTHON"));
    if (!Override.IsEmpty())
    {
        OutCandidates.Emplace(Override, FString());
        return;
    }

#if PLATFORM_WINDOWS
    // There is no /usr/bin/env on Windows. The py launcher ships with any
    // python.org install and resolves the active interpreter; a bare python.exe
    // covers a PATH install without the launcher.
    OutCandidates.Emplace(TEXT("py.exe"), FString());
    OutCandidates.Emplace(TEXT("python.exe"), FString());
#else
    OutCandidates.Emplace(TEXT("/usr/bin/env"), TEXT("python3 "));
#endif
}
}

bool FInfinityStageMusicAnalysisImporter::AnalyzeSound(
    USoundBase* Sound,
    const int32 PassageNumber,
    FString& OutReport)
{
    USoundWave* Wave = Cast<USoundWave>(Sound);
    if (!Wave)
    {
        OutReport = TEXT("Select a Sound Wave. Cues and procedural sounds cannot be analysed.");
        return false;
    }

    TArray<uint8> Pcm;
    uint32 SampleRate = 0;
    uint16 Channels = 0;
    if (!Wave->GetImportedSoundWaveData(Pcm, SampleRate, Channels) || Pcm.IsEmpty() || SampleRate == 0)
    {
        OutReport = FString::Printf(
            TEXT("'%s' has no imported audio data to analyse. Re-import the asset from its source file."),
            *Wave->GetName());
        return false;
    }

    TArray<uint8> WavBytes;
    WavBytes.Reserve(Pcm.Num() + 44);
    AppendWavHeader(WavBytes, Pcm.Num(), SampleRate, FMath::Max<uint16>(1, Channels));
    WavBytes.Append(Pcm);

    const FString DropDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("InfinityStage/MusicDrop"));
    IFileManager::Get().MakeDirectory(*DropDirectory, true);
    // The P<NN>_ prefix is how the analyzer assigns a Passage, so the caller's
    // selection decides the slot rather than filename order.
    const FString WavPath = FPaths::Combine(
        DropDirectory,
        FString::Printf(TEXT("P%02d_%s.wav"), PassageNumber, *Wave->GetName()));
    if (!FFileHelper::SaveArrayToFile(WavBytes, *WavPath))
    {
        OutReport = FString::Printf(TEXT("Could not write %s."), *WavPath);
        return false;
    }

    const FString Script = FPaths::Combine(
        FPaths::ProjectDir(), TEXT("Tools/InfinityStage/music_analysis.py"));
    const FString OutputDirectory = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("InfinityStage/MusicAnalysis"));
    const FString ScriptArguments = FString::Printf(
        TEXT("\"%s\" --drop-dir \"%s\" --output-dir \"%s\""),
        *Script,
        *DropDirectory,
        *OutputDirectory);

    TArray<TPair<FString, FString>> Candidates;
    GatherPythonCandidates(Candidates);

    int32 ReturnCode = -1;
    FString StdOut;
    FString StdErr;
    bool bLaunched = false;
    FString Attempted;
    for (const TPair<FString, FString>& Candidate : Candidates)
    {
        const FString Arguments = Candidate.Value + ScriptArguments;
        bLaunched = FPlatformProcess::ExecProcess(
            *Candidate.Key, *Arguments, &ReturnCode, &StdOut, &StdErr);

        Attempted += Attempted.IsEmpty() ? Candidate.Key : (TEXT(", ") + Candidate.Key);

        // Failing to launch means that interpreter is not present, so try the
        // next. A non-zero exit means it ran and the script itself failed —
        // stop there and report that, rather than masking it with a retry.
        if (bLaunched)
        {
            break;
        }
    }

    if (!bLaunched || ReturnCode != 0)
    {
        // The export still succeeded, so hand back a command that works rather
        // than losing the work.
        const FString Reason = bLaunched
            ? (StdErr.IsEmpty() ? FString::Printf(TEXT("exit %d"), ReturnCode) : StdErr.TrimEnd())
            : FString::Printf(TEXT("no Python interpreter found; tried %s"), *Attempted);
        OutReport = FString::Printf(
            TEXT("Exported %s but the analyzer did not run (%s). Run by hand: ")
            TEXT("python3 \"%s\" --drop-dir \"%s\" --output-dir \"%s\"  ")
            TEXT("(the analyzer needs numpy; set INFINITYSTAGE_PYTHON to choose an interpreter)"),
            *FPaths::GetCleanFilename(WavPath),
            *Reason,
            *Script,
            *DropDirectory,
            *OutputDirectory);
        return false;
    }

    OutReport = FString::Printf(
        TEXT("Analysed '%s' as Passage %d. %s"),
        *Wave->GetName(),
        PassageNumber,
        *StdOut.TrimEnd());
    return true;
}
