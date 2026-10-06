#include "InfinityStageLightEvents.h"

#include "Components/LocalLightComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageLightEvents, Log, All);

namespace
{
TAutoConsoleVariable<int32> CVarInfinityStageShowLightEvents(
    TEXT("InfinityStage.ShowLightEvents"),
    0,
    TEXT("Light tuning aid: report each light as it comes on, in Game/PIE worlds only.\n")
    TEXT("0: off (default; no polling work at all).\n")
    TEXT("1: on screen (never in performance mode) and to the log, LogInfinityStageLightEvents.\n")
    TEXT("2: log only."));

TAutoConsoleVariable<float> CVarInfinityStageShowLightEventsOnLevel(
    TEXT("InfinityStage.ShowLightEvents.OnLevel"),
    1.0f,
    TEXT("Effective intensity, in the light's own units, at which a light counts as ON. It counts as OFF again\n")
    TEXT("only below a quarter of this, so flicker inside that band never prints."));

/** On-screen lines: a rolling set of keys, so roughly the last eight stay up. */
constexpr uint64 ScreenKeyBase = 0x1E5E0000ull;
constexpr int32 ScreenSlots = 8;
constexpr float ScreenSeconds = 4.0f;

/** A full rescan for new lights; spawned actors are picked up at once in between. */
constexpr double RescanSeconds = 10.0;
/** The ON log line waits this long for the rise to settle, so it carries the level reached. */
constexpr double RiseSettleSeconds = 0.75;
/** A repeating light's count is logged at most this often. */
constexpr double RepeatLogSeconds = 4.0;
/** Work cap for finding lights: level actors visited per poll by the sliced sweep. */
constexpr int32 SweepActorsPerPoll = 256;
/** Work cap: beyond this many lights a poll takes a rotating slice. */
constexpr int32 MaxLightsPerPoll = 1024;

const FString LightEventsAttachmentTagPrefix(TEXT("InfinityStage.Attachment."));

bool CarriesAttachmentTag(const AActor& Actor)
{
    return Actor.Tags.ContainsByPredicate([](const FName& Tag)
        { return Tag.ToString().StartsWith(LightEventsAttachmentTagPrefix); });
}

FString LabelFromPassage(const AInfinityStagePassageActor& Passage, const AActor& Actor)
{
    FGuid CueGuid;
    FGuid AttachmentGuid;
    if (!Passage.ShowAsset || !Passage.FindAttachmentByActor(&Actor, CueGuid, AttachmentGuid))
    {
        return FString();
    }
    for (const FInfinityShowCue& Cue : Passage.ShowAsset->Cues)
    {
        if (Cue.CueGuid != CueGuid)
        {
            continue;
        }
        for (const FInfinityCueAttachment& Attachment : Cue.WingPair.Attachments)
        {
            if (Attachment.AttachmentGuid == AttachmentGuid && !Attachment.Label.IsEmpty())
            {
                return Attachment.Label.ToString();
            }
        }
    }
    return FString();
}

/** The Show's label for a materialised attachment, or empty. Its owning Passage is
 * the attach parent (PassageActor.cpp AttachToActor at materialise); a detached lamp
 * falls back to asking every Passage in the world. Runs per light per scan, not per frame. */
FString ShowAttachmentLabel(const AActor& Actor)
{
    if (!CarriesAttachmentTag(Actor))
    {
        return FString();
    }
    for (const AActor* Parent = Actor.GetAttachParentActor(); Parent; Parent = Parent->GetAttachParentActor())
    {
        if (const AInfinityStagePassageActor* Passage = Cast<AInfinityStagePassageActor>(Parent))
        {
            const FString Label = LabelFromPassage(*Passage, Actor);
            if (!Label.IsEmpty())
            {
                return Label;
            }
        }
    }
    if (UWorld* World = Actor.GetWorld())
    {
        for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
        {
            const FString Label = LabelFromPassage(**It, Actor);
            if (!Label.IsEmpty())
            {
                return Label;
            }
        }
    }
    return FString();
}

FString FormatIntensity(const float Intensity)
{
    return FMath::Abs(Intensity) >= 10.0f
        ? FString::Printf(TEXT("%.0f"), Intensity)
        : FString::Printf(TEXT("%.2f"), Intensity);
}

/** Log fields are '|'-separated, so a label never carries one. */
FString LogSafe(const FString& Text)
{
    return Text.Replace(TEXT("|"), TEXT("/"));
}
}

namespace InfinityStageLightEvents
{
EInfinityLightEdge StepEdge(
    FInfinityLightEdgeState& State,
    const double EffectiveLevel,
    const double NowSeconds,
    const FInfinityLightEdgeThresholds& Thresholds)
{
    if (!State.bOn)
    {
        if (EffectiveLevel < Thresholds.OnLevel)
        {
            return EInfinityLightEdge::None;
        }
        State.bOn = true;
        // A scrub or restart can run the clock backwards: that is a fresh ON, never a repeat.
        const double SincePrevious = NowSeconds - State.LastOnSeconds;
        const bool bRepeat = State.RunCount > 0
            && SincePrevious >= 0.0
            && SincePrevious <= Thresholds.RepeatWindowSeconds;
        State.LastOnSeconds = NowSeconds;
        if (bRepeat)
        {
            ++State.RunCount;
            return EInfinityLightEdge::Repeat;
        }
        State.RunCount = 1;
        return EInfinityLightEdge::On;
    }
    if (EffectiveLevel < Thresholds.OffLevel)
    {
        State.bOn = false;
        return EInfinityLightEdge::Off;
    }
    return EInfinityLightEdge::None;
}

void SeedEdge(FInfinityLightEdgeState& State, const double EffectiveLevel, const FInfinityLightEdgeThresholds& Thresholds)
{
    State = FInfinityLightEdgeState();
    State.bOn = EffectiveLevel >= Thresholds.OnLevel;
}

double EffectiveLevel(const ULocalLightComponent& Light)
{
    if (!Light.IsRegistered() || !Light.IsVisible() || Light.bHiddenInGame || !Light.bAffectsWorld)
    {
        return 0.0;
    }
    if (Light.IntensityUnits == ELightUnits::EV)
    {
        // EV is logarithmic: map it onto a linear scale so the thresholds keep their meaning.
        return FMath::Exp2(static_cast<double>(Light.Intensity));
    }
    return FMath::Max(0.0, static_cast<double>(Light.Intensity));
}

const TCHAR* UnitsLabel(const ULocalLightComponent& Light)
{
    switch (Light.IntensityUnits)
    {
    case ELightUnits::Candelas: return TEXT("cd");
    case ELightUnits::Lumens: return TEXT("lm");
    case ELightUnits::EV: return TEXT("EV");
    case ELightUnits::Nits: return TEXT("nits");
    default: return TEXT("");
    }
}

FString ResolveLabel(const ULocalLightComponent& Light)
{
    const AActor* Owner = Light.GetOwner();
    if (!Owner)
    {
        return Light.GetName();
    }
    FString Label = ShowAttachmentLabel(*Owner);
    if (Label.IsEmpty())
    {
        Label = Owner->GetActorNameOrLabel();
    }
    TInlineComponentArray<ULocalLightComponent*> Lights(Owner);
    if (Lights.Num() > 1)
    {
        // Structure tube lights and the Sweep's spot/rect pair share one actor.
        Label += TEXT("/") + Light.GetName();
    }
    return Label;
}

int32 GetLevel()
{
    return FMath::Clamp(CVarInfinityStageShowLightEvents.GetValueOnGameThread(), 0, 2);
}
}

bool UInfinityStageLightEventSubsystem::SupportsWorldType(const EWorldType::Type WorldType)
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

bool UInfinityStageLightEventSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return SupportsWorldType(WorldType);
}

void UInfinityStageLightEventSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
}

void UInfinityStageLightEventSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld(); World && SpawnHandle.IsValid())
    {
        World->RemoveOnActorSpawnedHandler(SpawnHandle);
    }
    SpawnHandle.Reset();
    Tracked.Reset();
    TrackedIndex.Reset();
    Super::Deinitialize();
}

bool UInfinityStageLightEventSubsystem::IsTickable() const
{
    // Off by default: at 0 the tick is never even called.
    return IsInitialized() && InfinityStageLightEvents::GetLevel() > 0;
}

TStatId UInfinityStageLightEventSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UInfinityStageLightEventSubsystem, STATGROUP_Tickables);
}

void UInfinityStageLightEventSubsystem::Tick(const float DeltaTime)
{
    Super::Tick(DeltaTime);
    const UWorld* World = GetWorld();
    TickAt(World ? World->GetRealTimeSeconds() : 0.0);
}

void UInfinityStageLightEventSubsystem::TickAt(const double RealSeconds)
{
    const int32 Level = InfinityStageLightEvents::GetLevel();
    const UWorld* World = GetWorld();
    // Second gate: Tick is reachable directly, and the editor world must never be polled.
    if (Level <= 0 || !World || !World->IsGameWorld())
    {
        return;
    }
    Poll(RealSeconds, Level);
}

FInfinityLightEdgeThresholds UInfinityStageLightEventSubsystem::GetThresholds() const
{
    if (ThresholdsForTests.IsSet())
    {
        return ThresholdsForTests.GetValue();
    }
    FInfinityLightEdgeThresholds Thresholds;
    Thresholds.OnLevel = FMath::Max(1.0e-3, static_cast<double>(CVarInfinityStageShowLightEventsOnLevel.GetValueOnGameThread()));
    Thresholds.OffLevel = Thresholds.OnLevel * 0.25;
    return Thresholds;
}

AInfinityStageShowRoot* UInfinityStageLightEventSubsystem::FindShowRoot()
{
    return CachedShowRoot.Get();
}

void UInfinityStageLightEventSubsystem::ReadClock(
    double& OutMasterSeconds,
    bool& bOutMasterClock,
    int32& OutSegmentIndex,
    FString& OutSegment)
{
    OutMasterSeconds = 0.0;
    bOutMasterClock = false;
    OutSegmentIndex = INDEX_NONE;
    OutSegment = TEXT("-");
    const AInfinityStageShowRoot* Root = FindShowRoot();
    if (Root && Root->Transport && Root->ShowAsset && Root->ShowAsset->TickResolution.IsValid())
    {
        const FFrameNumber Frame = Root->Transport->GetCurrentMasterFrame();
        OutMasterSeconds = Frame.Value / Root->ShowAsset->TickResolution.AsDecimal();
        bOutMasterClock = true;
        OutSegmentIndex = Root->Transport->FindSegmentAtFrame(Frame);
        if (Root->Transport->Segments.IsValidIndex(OutSegmentIndex))
        {
            OutSegment = Root->Transport->Segments[OutSegmentIndex].Label.ToString();
        }
        return;
    }
    if (const UWorld* World = GetWorld())
    {
        OutMasterSeconds = World->GetTimeSeconds();
    }
}

void UInfinityStageLightEventSubsystem::AddLight(
    ULocalLightComponent& Light,
    const bool bBaseline,
    const FInfinityLightEdgeThresholds& Thresholds)
{
    const FObjectKey Key(&Light);
    if (TrackedIndex.Contains(Key))
    {
        return;
    }
    FTrackedLight& Entry = Tracked.AddDefaulted_GetRef();
    Entry.Light = &Light;
    Entry.Label = InfinityStageLightEvents::ResolveLabel(Light);
    if (bBaseline)
    {
        // Lights already lit when tracking starts are the state of the stage, not events.
        InfinityStageLightEvents::SeedEdge(Entry.Edge, InfinityStageLightEvents::EffectiveLevel(Light), Thresholds);
    }
    // Otherwise the light is new to the world: if it arrives lit, that is a light coming on.
    TrackedIndex.Add(Key, Tracked.Num() - 1);
}

void UInfinityStageLightEventSubsystem::StartSweep(const bool bBaseline)
{
    // Drop destroyed lights (a re-spawned lamp is a new light), then rebuild the index.
    Tracked.RemoveAll([](const FTrackedLight& Entry) { return !Entry.Light.IsValid(); });
    TrackedIndex.Reset();
    for (int32 Index = 0; Index < Tracked.Num(); ++Index)
    {
        TrackedIndex.Add(FObjectKey(Tracked[Index].Light.Get()), Index);
    }
    PollCursor = 0;
    bSweepActive = true;
    bSweepBaseline = bBaseline;
    SweepLevelIndex = 0;
    SweepActorIndex = 0;
}

void UInfinityStageLightEventSubsystem::ContinueSweep(const int32 ActorBudget, const FInfinityLightEdgeThresholds& Thresholds)
{
    const UWorld* World = GetWorld();
    if (!bSweepActive || !World)
    {
        return;
    }
    // Sliced over frames through the level actor lists, so finding new lights never
    // costs one frame a whole-world walk (a hitch would read as stutter while tuning).
    const TArray<ULevel*>& Levels = World->GetLevels();
    int32 Visited = 0;
    while (Visited < ActorBudget && Levels.IsValidIndex(SweepLevelIndex))
    {
        const ULevel* Level = Levels[SweepLevelIndex];
        if (!Level || !Level->Actors.IsValidIndex(SweepActorIndex))
        {
            ++SweepLevelIndex;
            SweepActorIndex = 0;
            continue;
        }
        AActor* Actor = Level->Actors[SweepActorIndex++];
        ++Visited;
        if (!IsValid(Actor))
        {
            continue;
        }
        if (AInfinityStageShowRoot* Root = Cast<AInfinityStageShowRoot>(Actor); Root && !CachedShowRoot.IsValid())
        {
            CachedShowRoot = Root;
        }
        TInlineComponentArray<ULocalLightComponent*> Lights(Actor);
        for (ULocalLightComponent* Light : Lights)
        {
            if (IsValid(Light))
            {
                AddLight(*Light, bSweepBaseline, Thresholds);
            }
        }
    }
    if (!Levels.IsValidIndex(SweepLevelIndex))
    {
        bSweepActive = false;
    }
}

void UInfinityStageLightEventSubsystem::HandleActorSpawned(AActor* Actor)
{
    if (!IsValid(Actor) || !bScanned || InfinityStageLightEvents::GetLevel() <= 0)
    {
        return;
    }
    const FInfinityLightEdgeThresholds Thresholds = GetThresholds();
    TInlineComponentArray<ULocalLightComponent*> Lights(Actor);
    for (ULocalLightComponent* Light : Lights)
    {
        if (IsValid(Light))
        {
            AddLight(*Light, false, Thresholds);
        }
    }
}

void UInfinityStageLightEventSubsystem::EmitScreen(FTrackedLight& Entry, const FString& Line, const bool bAllowScreen)
{
    if (!bAllowScreen)
    {
        return;
    }
    const FObjectKey Owner(Entry.Light.Get());
    if (SlotOwners.Num() != ScreenSlots)
    {
        SlotOwners.Init(FObjectKey(), ScreenSlots);
    }
    if (Entry.ScreenSlot != INDEX_NONE && SlotOwners[Entry.ScreenSlot] != Owner)
    {
        // A newer light has taken this line since: never overwrite its text.
        Entry.ScreenSlot = INDEX_NONE;
    }
    if (Entry.ScreenSlot == INDEX_NONE)
    {
        Entry.ScreenSlot = NextScreenSlot;
        NextScreenSlot = (NextScreenSlot + 1) % ScreenSlots;
        SlotOwners[Entry.ScreenSlot] = Owner;
    }
    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(
            static_cast<uint64>(ScreenKeyBase + static_cast<uint64>(Entry.ScreenSlot)),
            ScreenSeconds,
            FColor::Yellow,
            Line);
    }
    if (LineSinkForTests)
    {
        LineSinkForTests(Line, true);
    }
}

void UInfinityStageLightEventSubsystem::EmitLog(const FString& Line)
{
    UE_LOG(LogInfinityStageLightEvents, Display, TEXT("%s"), *Line);
    if (LineSinkForTests)
    {
        LineSinkForTests(Line, false);
    }
}

void UInfinityStageLightEventSubsystem::Poll(const double RealSeconds, const int32 Level)
{
    ++PollCount;
    const FInfinityLightEdgeThresholds Thresholds = GetThresholds();
    UWorld* World = GetWorld();

    double MasterSeconds = 0.0;
    bool bMasterClock = false;
    int32 SegmentIndex = INDEX_NONE;
    FString Segment;

    if (!bScanned)
    {
        // First poll since the cvar went up: what is lit during this first sweep is the
        // baseline, seeded silently, so turning the aid on never prints a burst.
        bScanned = true;
        StartSweep(true);
        LastRescanSeconds = RealSeconds;
        if (World && !SpawnHandle.IsValid())
        {
            // Spawned actors are tracked at once (not seeded): a lamp that arrives lit is coming on.
            SpawnHandle = World->AddOnActorSpawnedHandler(
                FOnActorSpawned::FDelegate::CreateUObject(this, &UInfinityStageLightEventSubsystem::HandleActorSpawned));
        }
    }
    else if (GFrameCounter > LastPollFrame + 1)
    {
        // The cvar was off for a while (no ticks): re-seed silently rather than print
        // everything that changed while nobody was watching.
        for (FTrackedLight& Entry : Tracked)
        {
            if (const ULocalLightComponent* Light = Entry.Light.Get())
            {
                InfinityStageLightEvents::SeedEdge(Entry.Edge, InfinityStageLightEvents::EffectiveLevel(*Light), Thresholds);
                Entry.bLogPending = false;
            }
        }
    }
    LastPollFrame = GFrameCounter;

    ReadClock(MasterSeconds, bMasterClock, SegmentIndex, Segment);
    // Look for lights the spawn hook cannot see (components added to existing actors):
    // a sliced sweep on a segment change, every RescanSeconds, or if the clock ran back.
    if (!bSweepActive
        && (SegmentIndex != LastSegmentIndex
            || RealSeconds - LastRescanSeconds >= RescanSeconds
            || RealSeconds < LastRescanSeconds))
    {
        StartSweep(false);
        LastRescanSeconds = RealSeconds;
    }
    LastSegmentIndex = SegmentIndex;
    ContinueSweep(SweepActorsPerPoll, Thresholds);
    if (!bMasterClock && CachedShowRoot.IsValid())
    {
        // The sweep has just found the Show Root: read the Master clock from it this poll.
        ReadClock(MasterSeconds, bMasterClock, SegmentIndex, Segment);
        LastSegmentIndex = SegmentIndex;
    }

    const AInfinityStageShowRoot* Root = FindShowRoot();
    const bool bPerformance = Root && Root->Transport && Root->Transport->bPerformanceMode;
    const bool bAllowScreen = Level == 1 && !bPerformance;
    const TCHAR* Clock = bMasterClock ? TEXT("master") : TEXT("world");

    const int32 Num = Tracked.Num();
    if (Num == 0)
    {
        return;
    }
    const int32 Count = FMath::Min(Num, MaxLightsPerPoll);
    const int32 Start = Num > MaxLightsPerPoll ? PollCursor % Num : 0;
    for (int32 Step = 0; Step < Count; ++Step)
    {
        FTrackedLight& Entry = Tracked[(Start + Step) % Num];
        const ULocalLightComponent* Light = Entry.Light.Get();
        if (!Light)
        {
            continue;
        }
        ++LightsSampled;
        const double Effective = InfinityStageLightEvents::EffectiveLevel(*Light);
        const EInfinityLightEdge Edge = InfinityStageLightEvents::StepEdge(Entry.Edge, Effective, RealSeconds, Thresholds);
        const TCHAR* Units = InfinityStageLightEvents::UnitsLabel(*Light);

        if (Edge == EInfinityLightEdge::On)
        {
            Entry.bLogPending = true;
            Entry.PendingUntilSeconds = RealSeconds + RiseSettleSeconds;
            Entry.PeakLevel = Effective;
            Entry.PeakIntensity = Light->Intensity;
            Entry.OnMasterSeconds = MasterSeconds;
            Entry.OnSegment = Segment;
            Entry.LastRepeatLogSeconds = RealSeconds;
            Entry.ScreenSlot = INDEX_NONE;   // a fresh ON takes the next rolling line
            EmitScreen(Entry, FString::Printf(TEXT("%.1f s  %s  %s  ON ->%s %s"),
                MasterSeconds, *Segment, *Entry.Label, *FormatIntensity(Entry.PeakIntensity), Units), bAllowScreen);
        }
        else if (Edge == EInfinityLightEdge::Repeat)
        {
            // Strobes and flickers: one line, rewritten in place with the count.
            EmitScreen(Entry, FString::Printf(TEXT("%.1f s  %s  %s  ON ->%s %s (x%d)"),
                Entry.OnMasterSeconds, *Entry.OnSegment, *Entry.Label, *FormatIntensity(Entry.PeakIntensity), Units,
                Entry.Edge.RunCount), bAllowScreen);
            if (RealSeconds - Entry.LastRepeatLogSeconds >= RepeatLogSeconds)
            {
                Entry.LastRepeatLogSeconds = RealSeconds;
                EmitLog(FString::Printf(TEXT("INFINITY_LIGHT_REPEAT|t=%.2f|clock=%s|seg=%s|label=%s|count=%d"),
                    MasterSeconds, Clock, *LogSafe(Segment), *LogSafe(Entry.Label), Entry.Edge.RunCount));
            }
        }

        if (Entry.bLogPending)
        {
            if (Effective > Entry.PeakLevel)
            {
                const bool bVisibleRise = Effective > Entry.PeakLevel * 1.05;
                Entry.PeakLevel = Effective;
                Entry.PeakIntensity = Light->Intensity;
                if (bVisibleRise)
                {
                    EmitScreen(Entry, FString::Printf(TEXT("%.1f s  %s  %s  ON ->%s %s"),
                        Entry.OnMasterSeconds, *Entry.OnSegment, *Entry.Label, *FormatIntensity(Entry.PeakIntensity), Units),
                        bAllowScreen);
                }
            }
            if (RealSeconds >= Entry.PendingUntilSeconds || Edge == EInfinityLightEdge::Off)
            {
                Entry.bLogPending = false;
                EmitLog(FString::Printf(TEXT("INFINITY_LIGHT_ON|t=%.2f|clock=%s|seg=%s|label=%s|to=%s|units=%s"),
                    Entry.OnMasterSeconds, Clock, *LogSafe(Entry.OnSegment), *LogSafe(Entry.Label),
                    *FormatIntensity(Entry.PeakIntensity), Units));
            }
        }

        // OFF goes to the log only, and not for a light in a repeating run (a strobe would flood it).
        if (Edge == EInfinityLightEdge::Off && Entry.Edge.RunCount <= 1)
        {
            EmitLog(FString::Printf(TEXT("INFINITY_LIGHT_OFF|t=%.2f|clock=%s|seg=%s|label=%s"),
                MasterSeconds, Clock, *LogSafe(Segment), *LogSafe(Entry.Label)));
        }
    }
    PollCursor = (Start + Count) % Num;
}
