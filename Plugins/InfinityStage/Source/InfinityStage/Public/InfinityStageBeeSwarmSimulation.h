#pragma once

#include "CoreMinimal.h"
#include "Math/RandomStream.h"

#include "InfinityStageBeeSwarmSimulation.generated.h"

/**
 * Deterministic behaviour parameters for the S6 bee/firefly swarm.
 * v3 defaults were tuned offline with Tools/BeeSwarm/bee_swarm_harness.py (the
 * Python mirror of this simulation) against pre-registered look gates; the box
 * assumes the actor sits 150 cm above the floor (Z half-extent 140 cm).
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageBeeSwarmParameters
{
    GENERATED_BODY()

    /** NS_BeeSwarm spawns 512 particles and hides any index past the array length. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm", meta = (ClampMin = "1", ClampMax = "512"))
    int32 BeeCount = 200;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    int32 Seed = static_cast<int32>(0xBEE62026u);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float FixedStepSeconds = 1.0f / 120.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    FVector BoundsExtentCm = FVector(600.0, 450.0, 140.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float TargetWanderSpeedCmPerSecond = 150.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    FVector2D TargetJumpIntervalSeconds = FVector2D(0.8, 2.6);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    FVector2D OrbitRadiusRangeCm = FVector2D(30.0, 140.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float LargeNoiseScalePerCm = 0.003f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float SmallNoiseScalePerCm = 0.09f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float LargeNoiseAccelerationCmPerSecondSquared = 220.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float SmallNoiseAccelerationCmPerSecondSquared = 1200.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float DartRatePerSecond = 0.45f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float DartStrengthCmPerSecond = 320.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float DragPerSecond = 1.6f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float MaxSpeedCmPerSecond = 650.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float CameraAttractWeight = 0.9f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float CameraRepulsionRadiusCm = 25.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float FlyByRatePerSecond = 0.8f;

    /** v3: exponential damping of the target between jumps (dart, then hover).
     * Zero reproduces v2, where the target ran pinned at its 3x speed cap. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float TargetDragPerSecond = 1.5f;

    /** v3: radial spring towards each bee's orbit radius (v2 literal: 4). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float OrbitSpringPerSecondSquared = 12.0f;

    /** v3: constant tangential push round the target (v2 literal: 240). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bee Swarm")
    float OrbitTangentialAccelerationCmPerSecondSquared = 240.0f;
};

struct INFINITYSTAGE_API FInfinityStageBeeKinematics
{
    FVector Position = FVector::ZeroVector;
    FVector Velocity = FVector::ZeroVector;
};

/**
 * Fixed-step swarm core. Niagara owns rendering only. Replay is deterministic
 * for the same UE build/platform; floating transcendentals do not promise
 * bit-identical state across platforms.
 */
class INFINITYSTAGE_API FInfinityStageBeeSwarmSimulation
{
public:
    void Reset(
        const FInfinityStageBeeSwarmParameters& InParameters,
        const FVector& InSwarmOrigin,
        const FVector& InCameraPosition);

    /**
     * Advances by real time. Camera motion is interpolated at every fixed
     * substep. A cut disables interpolation and constrains against the new
     * camera immediately. The hard camera bubble is also enforced if no step
     * runs (zero delta, pause, or a sub-step-sized frame).
     */
    void Advance(float DeltaSeconds, const FVector& CameraPosition, bool bCameraCut = false);

    TConstArrayView<FInfinityStageBeeKinematics> GetBees() const { return Bees; }
    const FVector& GetTargetPosition() const { return TargetPosition; }
    double GetSimulationSeconds() const { return SimulationSeconds; }

private:
    struct FBeeRuntime
    {
        FVector OrbitAxis = FVector::UpVector;
        float OrbitRadiusCm = 100.0f;
        double NextDartSeconds = 0.0;
        FRandomStream RandomStream;
    };

    void StepFixed(float StepSeconds, const FVector& CameraPosition);
    void UpdateTarget(float StepSeconds);
    void InjectFlyBy(const FVector& CameraPosition);
    void ResolveAllConstraints(const FVector& CameraPosition);
    void ResolveConstraints(
        FVector& Position,
        FVector& Velocity,
        const FVector& CameraPosition,
        const FVector& FallbackDirection,
        float ExtentScale) const;
    void ConstrainToBounds(FVector& Position, FVector& Velocity, float ExtentScale) const;

    static float RandomRange(FRandomStream& Stream, float Minimum, float Maximum);
    static FVector RandomUnitVector(FRandomStream& Stream);
    static FVector CurlNoise(const FVector& Position, double TimeSeconds, float Scale, float TimeScale);
    static double SchedulePoisson(double NowSeconds, float RatePerSecond, FRandomStream& Stream);

    FInfinityStageBeeSwarmParameters Parameters;
    FVector SwarmOrigin = FVector::ZeroVector;
    FVector TargetPosition = FVector::ZeroVector;
    FVector TargetVelocity = FVector::ZeroVector;
    FVector LastCameraPosition = FVector::ZeroVector;
    TArray<FInfinityStageBeeKinematics> Bees;
    TArray<FBeeRuntime> BeeRuntime;
    FRandomStream TargetRandomStream;
    double SimulationSeconds = 0.0;
    double AccumulatorSeconds = 0.0;
    double NextTargetJumpSeconds = 0.0;
    double NextFlyBySeconds = 0.0;
    bool bHasCameraPosition = false;
};
