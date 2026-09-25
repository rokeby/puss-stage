#pragma once

#include "CoreMinimal.h"

struct INFINITYSTAGE_API FInfinityStageCustomVersion
{
    enum Type
    {
        BeforeCustomVersionWasAdded = 0,
        InitialFiniteCueSchema = 1,
        MusicFitAndFacingPolicy = 2,
        ExplicitPanelImageFlip = 3,
        CameraGustFanReveal = 4,
        CameraLedRevealWindow = 5,
        LatestVersion = CameraLedRevealWindow
    };

    static const FGuid GUID;
};
