#include "InfinityStageMechanismSound.h"

namespace InfinityStageMechanismSound
{
bool IsForwardPlaybackStep(
    const double ShowDeltaSeconds,
    const double RealElapsedSeconds,
    const double MaxRateRatio,
    const double MaxStepSeconds)
{
    if (!(ShowDeltaSeconds > 0.0) || ShowDeltaSeconds > FMath::Max(0.0, MaxStepSeconds))
    {
        return false;
    }
    // One 60 Hz frame of slack covers Sequencer frame quantisation (a 24/30 fps
    // locked evaluation advancing in uneven steps against the world tick).
    constexpr double SlackSeconds = 1.0 / 60.0;
    const double Allowed = FMath::Max(0.0, RealElapsedSeconds) * FMath::Max(0.0, MaxRateRatio) + SlackSeconds;
    return ShowDeltaSeconds <= Allowed;
}

bool CrossesForward(const double PrevPhase, const double CurrPhase, const double CuePhase, const bool bLooping)
{
    if (!(CurrPhase > PrevPhase))
    {
        return false;
    }
    if (!bLooping)
    {
        return PrevPhase < CuePhase && CuePhase <= CurrPhase;
    }
    // The smallest k + CuePhase strictly above Prev; one statement per value.
    const double FirstK = FMath::FloorToDouble(PrevPhase - CuePhase) + 1.0;
    const double Next = FirstK + CuePhase;
    return Next > PrevPhase && Next <= CurrPhase;
}

bool CrossesThresholdUpward(const double PrevTravel, const double CurrTravel, const double Threshold)
{
    const double PrevMagnitude = FMath::Abs(PrevTravel);
    const double CurrMagnitude = FMath::Abs(CurrTravel);
    return PrevMagnitude < Threshold && Threshold <= CurrMagnitude;
}

void CollectCrossedCues(
    const TArray<FInfinityMechanismSoundCue>& Cues,
    const EInfinityMechanismSoundCueSide Side,
    const double PrevPhase,
    const double CurrPhase,
    const bool bLooping,
    const bool bMuted,
    TArray<int32>& OutIndices)
{
    OutIndices.Reset();
    if (bMuted)
    {
        return;
    }
    for (int32 Index = 0; Index < Cues.Num(); ++Index)
    {
        const FInfinityMechanismSoundCue& Cue = Cues[Index];
        if (Cue.Side != Side || Cue.Sound.IsNull())
        {
            continue;
        }
        if (CrossesForward(PrevPhase, CurrPhase, Cue.Phase, bLooping))
        {
            OutIndices.Add(Index);
        }
    }
}
}
