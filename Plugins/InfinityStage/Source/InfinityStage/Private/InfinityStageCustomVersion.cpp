#include "InfinityStageCustomVersion.h"

#include "Serialization/CustomVersion.h"

const FGuid FInfinityStageCustomVersion::GUID(0x518C1B7D, 0xE18A43F2, 0xB44B95A3, 0xE71C9610);

static FCustomVersionRegistration GRegisterInfinityStageCustomVersion(
    FInfinityStageCustomVersion::GUID,
    FInfinityStageCustomVersion::LatestVersion,
    TEXT("InfinityStageCustomVersion"));
