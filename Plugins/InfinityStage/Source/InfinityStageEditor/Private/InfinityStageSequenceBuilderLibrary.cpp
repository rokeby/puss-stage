#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageSceneHandoffBuilder.h"

#include "InfinityStageCompiler.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "EngineUtils.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneObjectBindingID.h"
#include "MovieScenePossessable.h"
#include "MovieSceneSpawnable.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "MovieSceneInfinitySceneTrack.h"
#include "MovieSceneInfinityAudioTrack.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "Channels/MovieSceneChannelProxy.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "ScopedTransaction.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieSceneSubTrack.h"

bool UInfinityStageSequenceBuilderLibrary::CheckSceneHandoffs(
    UInfinityStageShowAsset* Show,
    UWorld* BindingWorld,
    TArray<FGuid>& OutStaleSceneGuids,
    FString& OutReport)
{
    OutStaleSceneGuids.Reset();
    if (!Show || !BindingWorld)
    {
        OutReport = TEXT("A Show and its binding world are required.");
        return false;
    }
    return FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(
        *Show, *BindingWorld, {}, OutStaleSceneGuids, OutReport);
}

namespace
{
template <typename SectionType>
void RemoveStaleSections(UMovieSceneTrack& Track, const TSet<FGuid>& LiveBlocks)
{
    const TArray<UMovieSceneSection*> Existing = Track.GetAllSections();
    for (UMovieSceneSection* BaseSection : Existing)
    {
        SectionType* Section = Cast<SectionType>(BaseSection);
        if (!Section || !LiveBlocks.Contains(Section->BlockGuid))
        {
            Track.RemoveSection(*BaseSection);
        }
    }
}

TRange<FFrameNumber> MakeSectionRange(const FFrameNumber Start, const FFrameNumber End)
{
    return TRange<FFrameNumber>(TRangeBound<FFrameNumber>::Inclusive(Start), TRangeBound<FFrameNumber>::Exclusive(End));
}

const FInfinityMusicRail* FindRail(const UInfinityStageShowAsset& Show, const FGuid RailGuid)
{
    return Show.MusicRails.FindByPredicate([RailGuid](const FInfinityMusicRail& Rail)
    {
        return Rail.RailGuid == RailGuid;
    });
}

const FInfinityPassageSettings* FindPassageSettings(const UInfinityStageShowAsset& Show, const FGuid PassageGuid)
{
    return Show.PassageSettings.FindByPredicate([PassageGuid](const FInfinityPassageSettings& Settings)
    {
        return Settings.PassageGuid == PassageGuid;
    });
}

void ApplyVolumeEnvelope(UMovieSceneInfinityAudioSection& Section, const FInfinityMusicRail& Rail, const FFrameNumber Start, const FFrameNumber End)
{
    FMovieSceneFloatChannel* Volume = Section.GetChannelProxy().GetChannel<FMovieSceneFloatChannel>(0);
    if (!Volume)
    {
        return;
    }
    Volume->Reset();
    Volume->SetDefault(1.0f);
    if (Rail.FadeInFrames.Value > 0)
    {
        Volume->AddLinearKey(Start, 0.0f);
        Volume->AddLinearKey(FMath::Min(Start + Rail.FadeInFrames, End), 1.0f);
    }
    if (Rail.FadeOutFrames.Value > 0)
    {
        Volume->AddLinearKey(FMath::Max(Start, End - Rail.FadeOutFrames), 1.0f);
        Volume->AddLinearKey(End, 0.0f);
    }
}

bool ResolveRenderRange(
    const UInfinityStageShowAsset& Show,
    const FInfinityCompileResult& Compiled,
    const TArray<FGuid>& SelectedCueGuids,
    const FGuid SelectedPassageGuid,
    FFrameNumber& OutStart,
    FFrameNumber& OutEnd,
    FString& OutError)
{
    if (SelectedPassageGuid.IsValid())
    {
        const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
            [SelectedPassageGuid](const FInfinityCompiledPassage& Candidate)
            {
                return Candidate.PassageGuid == SelectedPassageGuid;
            });
        if (!Passage)
        {
            OutError = TEXT("The selected Passage is not present in the compiled Show.");
            return false;
        }
        OutStart = Passage->SegmentStartFrame;
        OutEnd = Passage->SegmentEndFrame;
        return OutEnd > OutStart;
    }

    if (SelectedCueGuids.IsEmpty())
    {
        OutError = TEXT("Select one or more Cue rows, or select a Passage heading.");
        return false;
    }

    int32 MinimumFrame = TNumericLimits<int32>::Max();
    int32 MaximumFrame = TNumericLimits<int32>::Lowest();
    int32 ResolvedCueCount = 0;
    for (const FGuid CueGuid : SelectedCueGuids)
    {
        const int32 CueIndex = Show.FindCueIndex(CueGuid);
        if (!Show.Cues.IsValidIndex(CueIndex) || !Show.Cues[CueIndex].bEnabled)
        {
            continue;
        }

        bool bResolved = false;
        if (Show.Cues[CueIndex].Type == EInfinityCueType::WingPair)
        {
            for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
            {
                const int32 WingIndex = Passage.Wings.IndexOfByPredicate(
                    [CueGuid](const FInfinityCompiledWing& Wing)
                    {
                        return Wing.CueGuid == CueGuid;
                    });
                if (WingIndex == INDEX_NONE)
                {
                    continue;
                }

                const FFrameNumber Start = Passage.Wings[WingIndex].PassFrame;
                const FFrameNumber End = Passage.Wings.IsValidIndex(WingIndex + 1)
                    ? Passage.Wings[WingIndex + 1].PassFrame
                    : Passage.SegmentEndFrame;
                MinimumFrame = FMath::Min(MinimumFrame, Start.Value);
                MaximumFrame = FMath::Max(MaximumFrame, End.Value);
                bResolved = true;
                break;
            }
        }
        else
        {
            const FInfinityCompiledSegment* Segment = Compiled.Segments.FindByPredicate(
                [CueIndex](const FInfinityCompiledSegment& Candidate)
                {
                    return CueIndex >= Candidate.FirstCueIndex && CueIndex <= Candidate.LastCueIndex;
                });
            if (Segment)
            {
                MinimumFrame = FMath::Min(MinimumFrame, Segment->StartFrame.Value);
                MaximumFrame = FMath::Max(MaximumFrame, Segment->EndFrame.Value);
                bResolved = true;
            }
        }

        ResolvedCueCount += bResolved ? 1 : 0;
    }

    if (ResolvedCueCount == 0 || MaximumFrame <= MinimumFrame)
    {
        OutError = TEXT("None of the selected Cues resolves to a positive compiled Master range.");
        return false;
    }
    OutStart = FFrameNumber(MinimumFrame);
    OutEnd = FFrameNumber(MaximumFrame);
    return true;
}
}

bool UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(
    UInfinityStageShowAsset* Show,
    ULevelSequence* MasterSequence,
    FString& OutReport)
{
    OutReport.Reset();
    if (!Show || !MasterSequence)
    {
        OutReport = TEXT("Show and Master Sequence are required.");
        return false;
    }

    Show->EnsureStableIds();
    Show->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (Compiled.HasErrors())
    {
        OutReport = FString::Printf(TEXT("Show has %d compile issue(s); managed rebuild refused."), Compiled.Issues.Num());
        return false;
    }

    UMovieScene* MovieScene = MasterSequence->GetMovieScene();
    if (!MovieScene)
    {
        OutReport = TEXT("Master Sequence has no Movie Scene.");
        return false;
    }

    const FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "BuildMasterTransaction", "Rebuild Infinity Stage Master"));
    MasterSequence->Modify();
    MovieScene->Modify();
    MovieScene->SetDisplayRate(Show->DisplayRate);
    MovieScene->SetTickResolutionDirectly(Show->TickResolution);
    MovieScene->SetPlaybackRange(0, FMath::Max(1, Compiled.ShowEndFrame.Value));

    UMovieSceneInfinityPassageTrack* PassageTrack = MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>();
    if (!PassageTrack)
    {
        PassageTrack = MovieScene->AddTrack<UMovieSceneInfinityPassageTrack>();
        PassageTrack->OwnerGuid = Show->ShowGuid;
    }
    if (!PassageTrack || (PassageTrack->OwnerGuid.IsValid() && PassageTrack->OwnerGuid != Show->ShowGuid))
    {
        OutReport = TEXT("Existing Infinity Passage track belongs to another Show.");
        return false;
    }
    PassageTrack->Modify();
    PassageTrack->OwnerGuid = Show->ShowGuid;

    TSet<FGuid> LivePassageBlocks;
    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        LivePassageBlocks.Add(Passage.PassageGuid);
        UMovieSceneInfinityPassageSection* Section = nullptr;
        for (UMovieSceneSection* Existing : PassageTrack->GetAllSections())
        {
            UMovieSceneInfinityPassageSection* Candidate = Cast<UMovieSceneInfinityPassageSection>(Existing);
            if (Candidate && Candidate->BlockGuid == Passage.PassageGuid)
            {
                Section = Candidate;
                break;
            }
        }
        const bool bNewSection = Section == nullptr;
        if (!Section)
        {
            Section = CastChecked<UMovieSceneInfinityPassageSection>(PassageTrack->CreateNewSection());
            PassageTrack->AddSection(*Section);
        }
        Section->Modify();
        Section->OwnerGuid = Show->ShowGuid;
        Section->BlockGuid = Passage.PassageGuid;
        Section->PassageGuid = Passage.PassageGuid;
        Section->BuildVersion = 3;
        for (uint8 RawChannel = static_cast<uint8>(InfinityFirstPassageChannel);
            RawChannel <= static_cast<uint8>(InfinityLastPassageChannel);
            ++RawChannel)
        {
            if (FMovieSceneDoubleChannel* Channel = Section->GetCameraChannel(
                static_cast<EInfinityPassageCameraChannel>(RawChannel)))
            {
                Channel->SetTickResolution(Show->TickResolution);
            }
        }
        Section->PinnedWingCueGuids.RemoveAll([&Passage](const FGuid CueGuid)
        {
            return !Passage.Wings.ContainsByPredicate([CueGuid](const FInfinityCompiledWing& Wing)
            {
                return Wing.CueGuid == CueGuid;
            });
        });
        const int32 PassageDurationFrames = Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value;
        Section->PinnedPassageFrames.RemoveAll([PassageDurationFrames](const FFrameNumber RelativeFrame)
        {
            return RelativeFrame.Value <= 0 || RelativeFrame.Value >= PassageDurationFrames;
        });
        Section->PinnedPassageFrames.Sort();
        for (int32 PinIndex = Section->PinnedPassageFrames.Num() - 1; PinIndex > 0; --PinIndex)
        {
            if (Section->PinnedPassageFrames[PinIndex] == Section->PinnedPassageFrames[PinIndex - 1])
            {
                Section->PinnedPassageFrames.RemoveAt(PinIndex);
            }
        }
        // Channel keys sit at absolute Master frames and SetRange moves only the
        // range, so a Passage pushed later by a longer Scene used to keep its
        // camera score where it was. MoveSection carries every channel in the
        // proxy with the section, the way the relative pins already travel.
        if (!bNewSection && Section->HasStartFrame()
            && Section->GetInclusiveStartFrame() != Passage.SegmentStartFrame)
        {
            Section->MoveSection(Passage.SegmentStartFrame - Section->GetInclusiveStartFrame());
        }
        Section->SetRange(MakeSectionRange(Passage.SegmentStartFrame, Passage.SegmentEndFrame));
    }
    RemoveStaleSections<UMovieSceneInfinityPassageSection>(*PassageTrack, LivePassageBlocks);

    UMovieSceneInfinitySceneTrack* SceneTrack = MovieScene->FindTrack<UMovieSceneInfinitySceneTrack>();
    if (!SceneTrack)
    {
        SceneTrack = MovieScene->AddTrack<UMovieSceneInfinitySceneTrack>();
        SceneTrack->OwnerGuid = Show->ShowGuid;
    }
    if (!SceneTrack || (SceneTrack->OwnerGuid.IsValid() && SceneTrack->OwnerGuid != Show->ShowGuid))
    {
        OutReport = TEXT("Existing Infinity Scene track belongs to another Show.");
        return false;
    }
    SceneTrack->Modify();
    SceneTrack->OwnerGuid = Show->ShowGuid;

    TSet<FGuid> LiveSceneBlocks;
    int32 MissingSceneSequences = 0;
    for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
    {
        if (Segment.Type == EInfinityCueType::WingPair || !Show->Cues.IsValidIndex(Segment.FirstCueIndex))
        {
            continue;
        }
        const FInfinityShowCue& Cue = Show->Cues[Segment.FirstCueIndex];
        ULevelSequence* ChildSequence = Cue.Scene.Sequence.LoadSynchronous();
        if (!ChildSequence)
        {
            ++MissingSceneSequences;
            continue;
        }

        LiveSceneBlocks.Add(Segment.SegmentGuid);
        UMovieSceneInfinitySceneSection* Section = nullptr;
        for (UMovieSceneSection* Existing : SceneTrack->GetAllSections())
        {
            UMovieSceneInfinitySceneSection* Candidate = Cast<UMovieSceneInfinitySceneSection>(Existing);
            if (Candidate && Candidate->BlockGuid == Segment.SegmentGuid)
            {
                Section = Candidate;
                break;
            }
        }
        if (!Section)
        {
            Section = CastChecked<UMovieSceneInfinitySceneSection>(SceneTrack->CreateNewSection());
            SceneTrack->AddSection(*Section);
        }
        Section->Modify();
        Section->OwnerGuid = Show->ShowGuid;
        Section->BlockGuid = Segment.SegmentGuid;
        Section->SetSequence(ChildSequence);
        Section->SetRange(MakeSectionRange(Segment.StartFrame, Segment.EndFrame));
    }
    RemoveStaleSections<UMovieSceneInfinitySceneSection>(*SceneTrack, LiveSceneBlocks);

    UMovieSceneInfinityAudioTrack* MusicTrack = MovieScene->FindTrack<UMovieSceneInfinityAudioTrack>();
    if (!MusicTrack)
    {
        MusicTrack = MovieScene->AddTrack<UMovieSceneInfinityAudioTrack>();
        MusicTrack->OwnerGuid = Show->ShowGuid;
        MusicTrack->SetDisplayName(NSLOCTEXT("InfinityStage", "ManagedMusicTrack", "Infinity Stage Music (Managed)"));
    }
    if (!MusicTrack || (MusicTrack->OwnerGuid.IsValid() && MusicTrack->OwnerGuid != Show->ShowGuid))
    {
        OutReport = TEXT("Existing Infinity Music track belongs to another Show.");
        return false;
    }
    MusicTrack->Modify();
    MusicTrack->OwnerGuid = Show->ShowGuid;

    TSet<FGuid> LiveMusicBlocks;
    int32 MissingMusicRails = 0;
    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        const FInfinityPassageSettings* Settings = FindPassageSettings(*Show, Passage.PassageGuid);
        if (!Settings || (Settings->Music.Mode != EInfinityMusicBindingMode::Start
            && Settings->Music.Mode != EInfinityMusicBindingMode::ExplicitCrossfade))
        {
            continue;
        }
        const FInfinityMusicRail* Rail = FindRail(*Show, Settings->Music.PrimaryRailGuid);
        USoundBase* Sound = Rail ? Rail->Sound.LoadSynchronous() : nullptr;
        if (!Rail || !Sound)
        {
            ++MissingMusicRails;
            continue;
        }

        LiveMusicBlocks.Add(Passage.PassageGuid);
        UMovieSceneInfinityAudioSection* Section = nullptr;
        for (UMovieSceneSection* Existing : MusicTrack->GetAllSections())
        {
            UMovieSceneInfinityAudioSection* Candidate = Cast<UMovieSceneInfinityAudioSection>(Existing);
            if (Candidate && Candidate->BlockGuid == Passage.PassageGuid)
            {
                Section = Candidate;
                break;
            }
        }
        if (!Section)
        {
            Section = CastChecked<UMovieSceneInfinityAudioSection>(MusicTrack->CreateNewSection());
            MusicTrack->AddSection(*Section);
        }
        Section->Modify();
        Section->OwnerGuid = Show->ShowGuid;
        Section->BlockGuid = Passage.PassageGuid;
        Section->RailGuid = Rail->RailGuid;
        Section->SetSound(Sound);
        Section->SetStartOffset(Rail->SourceInFrame + Settings->Music.RailOffsetFrames);
        Section->SetRange(MakeSectionRange(Passage.SegmentStartFrame, Passage.SegmentEndFrame));
        Section->SetRepeating(false);
        ApplyVolumeEnvelope(*Section, *Rail, Passage.SegmentStartFrame, Passage.SegmentEndFrame);
    }
    // Scenes own their sound the same way Passages do: one Master-owned audio
    // section over the Scene's segment. A Scene is a fixed set piece with no
    // Wing Pair structure, so it has no Music Rail fit — it simply plays its
    // chosen rail from the requested offset for the length of the segment.
    for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
    {
        if (Segment.Type == EInfinityCueType::WingPair)
        {
            continue;
        }
        const FInfinityShowCue* Cue = Show->Cues.FindByPredicate(
            [&Segment](const FInfinityShowCue& Candidate)
            {
                return Candidate.CueGuid == Segment.SegmentGuid;
            });
        if (!Cue || !Cue->bEnabled
            || (Cue->Scene.Music.Mode != EInfinityMusicBindingMode::Start
                && Cue->Scene.Music.Mode != EInfinityMusicBindingMode::ExplicitCrossfade))
        {
            continue;
        }
        const FInfinityMusicRail* Rail = FindRail(*Show, Cue->Scene.Music.PrimaryRailGuid);
        USoundBase* Sound = Rail ? Rail->Sound.LoadSynchronous() : nullptr;
        if (!Rail || !Sound)
        {
            ++MissingMusicRails;
            continue;
        }

        LiveMusicBlocks.Add(Segment.SegmentGuid);
        UMovieSceneInfinityAudioSection* Section = nullptr;
        for (UMovieSceneSection* Existing : MusicTrack->GetAllSections())
        {
            UMovieSceneInfinityAudioSection* Candidate = Cast<UMovieSceneInfinityAudioSection>(Existing);
            if (Candidate && Candidate->BlockGuid == Segment.SegmentGuid)
            {
                Section = Candidate;
                break;
            }
        }
        if (!Section)
        {
            Section = CastChecked<UMovieSceneInfinityAudioSection>(MusicTrack->CreateNewSection());
            MusicTrack->AddSection(*Section);
        }
        Section->Modify();
        Section->OwnerGuid = Show->ShowGuid;
        Section->BlockGuid = Segment.SegmentGuid;
        Section->RailGuid = Rail->RailGuid;
        Section->SetSound(Sound);
        Section->SetStartOffset(Rail->SourceInFrame + Cue->Scene.Music.RailOffsetFrames);
        Section->SetRange(MakeSectionRange(Segment.StartFrame, Segment.EndFrame));
        Section->SetRepeating(false);
        ApplyVolumeEnvelope(*Section, *Rail, Segment.StartFrame, Segment.EndFrame);
    }
    RemoveStaleSections<UMovieSceneInfinityAudioSection>(*MusicTrack, LiveMusicBlocks);

    MasterSequence->MarkPackageDirty();
    OutReport = FString::Printf(
        TEXT("Rebuilt %d Passage, %d Scene, and %d music section(s); %d Scene cue(s) lack a sequence and %d music binding(s) lack a rail/sound."),
        PassageTrack->GetAllSections().Num(),
        SceneTrack->GetAllSections().Num(),
        MusicTrack->GetAllSections().Num(),
        MissingSceneSequences,
        MissingMusicRails);
    return true;
}

bool UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
    UInfinityStageShowAsset* Show,
    ULevelSequence* MasterSequence,
    ULevelSequence* RenderSequence,
    UWorld* BindingWorld,
    const TArray<FGuid>& SelectedCueGuids,
    const FGuid SelectedPassageGuid,
    FFrameNumber& OutStartFrame,
    FFrameNumber& OutEndFrame,
    FString& OutReport)
{
    OutStartFrame = 0;
    OutEndFrame = 0;
    OutReport.Reset();
    if (!Show || !MasterSequence || !RenderSequence || !BindingWorld)
    {
        OutReport = TEXT("Show, Master Sequence, render wrapper and binding World are required.");
        return false;
    }

    Show->EnsureStableIds();
    Show->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (Compiled.HasErrors())
    {
        OutReport = FString::Printf(
            TEXT("Show has %d compile issue(s); render wrapper rebuild refused."),
            Compiled.Issues.Num());
        return false;
    }
    if (!ResolveRenderRange(
        *Show,
        Compiled,
        SelectedCueGuids,
        SelectedPassageGuid,
        OutStartFrame,
        OutEndFrame,
        OutReport))
    {
        return false;
    }

    UMovieScene* MovieScene = RenderSequence->GetMovieScene();
    if (!MovieScene)
    {
        RenderSequence->Initialize();
        MovieScene = RenderSequence->GetMovieScene();
    }
    if (!MovieScene)
    {
        OutReport = TEXT("Render wrapper has no Movie Scene.");
        return false;
    }

    // This asset is an explicitly generated wrapper. Clear only its own managed content;
    // neither the authoritative Master nor any nested artist-authored Scene is flattened.
    const FScopedTransaction Transaction(NSLOCTEXT(
        "InfinityStage", "BuildRenderWrapperTransaction", "Rebuild Infinity Stage Render Selection"));
    RenderSequence->Modify();
    MovieScene->Modify();
    MovieScene->RemoveCameraCutTrack();
    const TArray<UMovieSceneTrack*> ExistingTracks = MovieScene->GetTracks();
    for (UMovieSceneTrack* Track : ExistingTracks)
    {
        if (Track)
        {
            MovieScene->RemoveTrack(*Track);
        }
    }
    for (int32 Index = MovieScene->GetPossessableCount() - 1; Index >= 0; --Index)
    {
        const FGuid Guid = MovieScene->GetPossessable(Index).GetGuid();
        RenderSequence->UnbindPossessableObjects(Guid);
        MovieScene->RemovePossessable(Guid);
    }
    for (int32 Index = MovieScene->GetSpawnableCount() - 1; Index >= 0; --Index)
    {
        MovieScene->RemoveSpawnable(MovieScene->GetSpawnable(Index).GetGuid());
    }

    MovieScene->SetDisplayRate(Show->DisplayRate);
    MovieScene->SetTickResolutionDirectly(Show->TickResolution);
    MovieScene->SetPlaybackRange(
        OutStartFrame,
        FMath::Max(1, OutEndFrame.Value - OutStartFrame.Value));

    UMovieSceneSubTrack* MasterTrack = MovieScene->AddTrack<UMovieSceneSubTrack>();
    if (!MasterTrack)
    {
        OutReport = TEXT("Could not create the managed Master source track.");
        return false;
    }
    MasterTrack->SetDisplayName(NSLOCTEXT(
        "InfinityStage", "RenderMasterSourceTrack", "Infinity Stage Master Source (Managed)"));
    if (!MasterTrack->AddSequence(
        MasterSequence,
        FFrameNumber(0),
        FMath::Max(1, Compiled.ShowEndFrame.Value)))
    {
        OutReport = TEXT("Could not nest the authoritative Master in the render wrapper.");
        return false;
    }

    UMovieSceneCameraCutTrack* CameraCutTrack = Cast<UMovieSceneCameraCutTrack>(
        MovieScene->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
    if (!CameraCutTrack)
    {
        OutReport = TEXT("Could not create the render Camera Cut Track.");
        return false;
    }
    CameraCutTrack->SetDisplayName(NSLOCTEXT(
        "InfinityStage", "RenderCameraCutTrack", "Infinity Stage Passage Cameras (Managed)"));
    CameraCutTrack->SetIsAutoManagingSections(false);

    int32 CameraCutCount = 0;
    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        const FFrameNumber CutStart(FMath::Max(OutStartFrame.Value, Passage.SegmentStartFrame.Value));
        const FFrameNumber CutEnd(FMath::Min(OutEndFrame.Value, Passage.SegmentEndFrame.Value));
        if (CutEnd <= CutStart)
        {
            continue;
        }

        AInfinityStageCameraRig* ResolvedRig = nullptr;
        int32 MatchingRigCount = 0;
        for (TActorIterator<AInfinityStageCameraRig> It(BindingWorld); It; ++It)
        {
            AInfinityStageCameraRig* Rig = *It;
            if (!IsValid(Rig) || !IsValid(Rig->PassageActor)
                || Rig->PassageActor->ShowAsset != Show
                || Rig->PassageActor->PassageGuid != Passage.PassageGuid)
            {
                continue;
            }
            ResolvedRig = Rig;
            ++MatchingRigCount;
        }
        if (MatchingRigCount != 1 || !ResolvedRig)
        {
            OutReport = FString::Printf(
                TEXT("Passage %s requires exactly one Camera Rig in the current level; found %d."),
                *Passage.PassageGuid.ToString(EGuidFormats::DigitsWithHyphensLower),
                MatchingRigCount);
            return false;
        }

        const FGuid CameraGuid = MovieScene->AddPossessable(
            FString::Printf(TEXT("Infinity Render Camera - %s"), *ResolvedRig->GetActorLabel()),
            ResolvedRig->GetClass());
        RenderSequence->BindPossessableObject(CameraGuid, *ResolvedRig, BindingWorld);
        const UE::MovieScene::FRelativeObjectBindingID RelativeBinding(
            MovieSceneSequenceID::Root,
            MovieSceneSequenceID::Root,
            CameraGuid,
            RenderSequence);
        UMovieSceneCameraCutSection* CameraCut = CameraCutTrack->AddNewCameraCut(
            FMovieSceneObjectBindingID(RelativeBinding),
            CutStart);
        if (!CameraCut)
        {
            OutReport = TEXT("Could not add a Passage Camera Cut section.");
            return false;
        }
        CameraCut->SetRange(TRange<FFrameNumber>(
            TRangeBound<FFrameNumber>::Inclusive(CutStart),
            TRangeBound<FFrameNumber>::Exclusive(CutEnd)));
        ++CameraCutCount;
    }

    RenderSequence->MarkPackageDirty();
    const double DurationSeconds = Show->TickResolution.AsDecimal() > 0.0
        ? (OutEndFrame.Value - OutStartFrame.Value) / Show->TickResolution.AsDecimal()
        : 0.0;
    OutReport = FString::Printf(
        TEXT("Render range [%d, %d) is %.2fs with %d exposed Passage Camera Cut(s); Scene intervals retain nested camera authority."),
        OutStartFrame.Value,
        OutEndFrame.Value,
        DurationSeconds,
        CameraCutCount);
    return true;
}
