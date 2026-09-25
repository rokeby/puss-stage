#pragma once

#include "CoreMinimal.h"

class FMenuBuilder;
class UInfinityStageShowAsset;

/**
 * Camera piloting with write-back (H.9).
 *
 * Framing is judged by looking, not by typing numbers into curves. Piloting
 * spawns a transient Cine Camera at the Passage camera's authored view for one
 * Master frame, with the rig's filmback, lens and post-process, and locks a
 * perspective Level Viewport to it. The artist flies it with the ordinary
 * viewport controls; nothing is written until they key. Keying solves the
 * flown view back into the Passage camera channels on the managed Master and
 * verifies it through the rig's own evaluation.
 *
 * One pilot session exists at a time and it belongs to one moment: keys always
 * land on the frame piloting began at. To frame a different moment, pilot again
 * at the new playhead. The proxy is transient, so the level is never dirtied.
 */
class FInfinityStageCameraPilot
{
public:
    /** Fills the Cue Desk's Pilot Camera submenu for one Passage at the Music Timeline playhead. */
    static void BuildMenu(
        FMenuBuilder& MenuBuilder,
        UInfinityStageShowAsset* Show,
        const FGuid& PassageGuid,
        FFrameNumber PlayheadFrame);

    static bool Begin(
        UInfinityStageShowAsset* Show,
        const FGuid& PassageGuid,
        FFrameNumber MasterFrame,
        FString& OutReport);

    /** Keys the piloted view (and optionally the pilot camera's focal length and manual focus) at the pilot frame. */
    static bool KeyPilotedPose(bool bIncludeLens, FString& OutReport);

    /** Puts the pilot camera back on the authored view at the pilot frame, discarding the unkeyed flight. */
    static bool SnapToAuthoredCamera(FString& OutReport);

    static void End();

    static bool IsPiloting();
};
