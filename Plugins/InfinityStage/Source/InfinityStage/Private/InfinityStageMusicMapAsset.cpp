#include "InfinityStageMusicMapAsset.h"

FPrimaryAssetId UInfinityStageMusicMapAsset::GetPrimaryAssetId() const
{
    return FPrimaryAssetId(TEXT("InfinityStageMusicMap"), GetFName());
}

float FInfinityAnalysisCurve::Sample(const double TimeSeconds) const
{
    if (Values.IsEmpty() || RateHz <= 0.0f)
    {
        return 0.0f;
    }
    const double Position = FMath::Clamp(TimeSeconds * RateHz, 0.0, static_cast<double>(Values.Num() - 1));
    const int32 Lower = FMath::FloorToInt32(Position);
    const int32 Upper = FMath::Min(Lower + 1, Values.Num() - 1);
    return FMath::Lerp(Values[Lower], Values[Upper], static_cast<float>(Position - Lower));
}

const FInfinityAnalysisCurve* UInfinityStageMusicMapAsset::FindCurve(const FName CurveName) const
{
    return FeatureCurves.FindByPredicate(
        [CurveName](const FInfinityAnalysisCurve& Candidate) { return Candidate.Name == CurveName; });
}
