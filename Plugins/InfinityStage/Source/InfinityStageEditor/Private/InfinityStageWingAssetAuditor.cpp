#include "InfinityStageWingAssetAuditor.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "FileHelpers.h"
#include "Engine/StaticMesh.h"
#include "InfinityStageWingLibraryAsset.h"
#include "JsonObjectConverter.h"
#include "MeshDescription.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "StaticMeshAttributes.h"
#include "StaticMeshOperations.h"

namespace
{
struct FSourceReportRecord
{
    FVector DimensionsCm = FVector::ZeroVector;
    FString Source;
    FString Fbx;
};

FString NormalizedAssetKey(FString Value)
{
    Value = Value.ToLower();
    Value.RemoveFromStart(TEXT("sm_"));
    FString Result;
    bool bPreviousUnderscore = false;
    for (const TCHAR Character : Value)
    {
        const bool bAlphaNumeric = FChar::IsAlnum(Character);
        if (bAlphaNumeric)
        {
            Result.AppendChar(Character);
            bPreviousUnderscore = false;
        }
        else if (!bPreviousUnderscore)
        {
            Result.AppendChar(TEXT('_'));
            bPreviousUnderscore = true;
        }
    }
    return Result.TrimChar(TEXT('_'));
}

// File-specific name on purpose. InfinityStageDevFixtureBuilder.cpp defines an
// identical helper in its own anonymous namespace; internal linkage keeps those
// apart in a normal build, but a unity build merges both into one translation
// unit and they collide. Do not rename this back to ContainsAny.
bool WingNameContainsAny(const FString& Value, const std::initializer_list<const TCHAR*>& Needles)
{
    for (const TCHAR* Needle : Needles)
    {
        if (Value.Contains(Needle))
        {
            return true;
        }
    }
    return false;
}

EInfinityWingAssetRole ClassifyRole(const FString& AssetName)
{
    FString Name = AssetName.ToLower();
    Name.RemoveFromStart(TEXT("sm_"));
    if (Name.Contains(TEXT("curtain")))
    {
        return EInfinityWingAssetRole::Excluded;
    }
    if (WingNameContainsAny(Name, { TEXT("ceiling"), TEXT("celing"), TEXT("overhead"), TEXT("canopy") }))
    {
        return EInfinityWingAssetRole::Top;
    }
    if (Name.StartsWith(TEXT("l_")) || WingNameContainsAny(Name, { TEXT("_l_"), TEXT("left") }))
    {
        return EInfinityWingAssetRole::LeftArchitectural;
    }
    if (Name.StartsWith(TEXT("r_")) || WingNameContainsAny(Name, { TEXT("_r_"), TEXT("right") }))
    {
        return EInfinityWingAssetRole::RightArchitectural;
    }
    if (WingNameContainsAny(Name, { TEXT("ground"), TEXT("mound"), TEXT("rubble"), TEXT("mossy_rock"), TEXT("blob"), TEXT("log"), TEXT("clam"), TEXT("paper"), TEXT("bone_wave") }))
    {
        return EInfinityWingAssetRole::GroundOrProp;
    }
    if (WingNameContainsAny(Name, {
        TEXT("wing"), TEXT("pillar"), TEXT("pilaster"), TEXT("curtain"), TEXT("wall"),
        TEXT("facade"), TEXT("archway"), TEXT("doorway"), TEXT("tower"), TEXT("downpipe"),
        TEXT("tree"), TEXT("barn"), TEXT("building"), TEXT("cloud"), TEXT("bones"),
        TEXT("excavator"), TEXT("sofa"), TEXT("planter"), TEXT("rebar"), TEXT("villager"),
        TEXT("wet_wave"), TEXT("beginning_stage") }))
    {
        return EInfinityWingAssetRole::SideNeutral;
    }
    return EInfinityWingAssetRole::Unknown;
}

bool IsOrientationNeutralObject(const FString& AssetName)
{
    const FString Name = AssetName.ToLower();
    return WingNameContainsAny(Name, {
        TEXT("building"), TEXT("barn"), TEXT("tree"), TEXT("cloud"), TEXT("bone"),
        TEXT("paper"), TEXT("clam"), TEXT("ground"), TEXT("mound"), TEXT("blob"),
        TEXT("log"), TEXT("animal"), TEXT("object") });
}

void ReadSourceReports(TMap<FString, FSourceReportRecord>& OutRecords)
{
    TArray<FString> ReportFiles;
    IFileManager::Get().FindFilesRecursive(
        ReportFiles,
        *FPaths::Combine(FPaths::ProjectDir(), TEXT("DerivedAssets")),
        TEXT("wing_pipeline_report*.json"),
        true,
        false);
    ReportFiles.Sort();
    for (const FString& ReportFile : ReportFiles)
    {
        FString JsonText;
        if (!FFileHelper::LoadFileToString(JsonText, *ReportFile))
        {
            continue;
        }
        TSharedPtr<FJsonObject> Root;
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
        if (!FJsonSerializer::Deserialize(Reader, Root) || !Root)
        {
            continue;
        }
        const TArray<TSharedPtr<FJsonValue>>* Results = nullptr;
        if (!Root->TryGetArrayField(TEXT("results"), Results) || !Results)
        {
            continue;
        }
        for (const TSharedPtr<FJsonValue>& ResultValue : *Results)
        {
            const TSharedPtr<FJsonObject> Result = ResultValue ? ResultValue->AsObject() : nullptr;
            if (!Result || Result->GetStringField(TEXT("status")) != TEXT("ok"))
            {
                continue;
            }
            FString AssetName;
            if (!Result->TryGetStringField(TEXT("asset_name"), AssetName))
            {
                continue;
            }
            const TArray<TSharedPtr<FJsonValue>>* Dimensions = nullptr;
            if (!Result->TryGetArrayField(TEXT("dimensions_m"), Dimensions) || !Dimensions || Dimensions->Num() != 3)
            {
                continue;
            }
            FSourceReportRecord Record;
            Record.DimensionsCm = FVector(
                (*Dimensions)[0]->AsNumber() * 100.0,
                (*Dimensions)[1]->AsNumber() * 100.0,
                (*Dimensions)[2]->AsNumber() * 100.0);
            Result->TryGetStringField(TEXT("source"), Record.Source);
            Result->TryGetStringField(TEXT("fbx"), Record.Fbx);
            OutRecords.FindOrAdd(NormalizedAssetKey(AssetName)) = MoveTemp(Record);
        }
    }
}

bool GetVertexPositions(const UStaticMesh& Mesh, TArray<FVector>& OutPositions)
{
    const FMeshDescription* MeshDescription = Mesh.GetMeshDescription(0);
    if (!MeshDescription)
    {
        return false;
    }
    FStaticMeshConstAttributes Attributes(*MeshDescription);
    const TVertexAttributesConstRef<FVector3f> Positions = Attributes.GetVertexPositions();
    OutPositions.Reserve(MeshDescription->Vertices().Num());
    for (const FVertexID VertexId : MeshDescription->Vertices().GetElementIDs())
    {
        OutPositions.Add(FVector(Positions[VertexId]));
    }
    return !OutPositions.IsEmpty();
}

FBox BoundsAfterTransform(const TArray<FVector>& Positions, const FTransform& Transform)
{
    FBox Bounds(EForceInit::ForceInit);
    for (const FVector& Position : Positions)
    {
        Bounds += Transform.TransformPosition(Position);
    }
    return Bounds;
}

EInfinityWingThicknessAxis FindThicknessAxis(const FVector& Size)
{
    const double Minimum = FMath::Min3(Size.X, Size.Y, Size.Z);
    const double Maximum = FMath::Max3(Size.X, Size.Y, Size.Z);
    if (Maximum <= UE_SMALL_NUMBER || Minimum > FMath::Min(25.0, Maximum * 0.12))
    {
        return EInfinityWingThicknessAxis::Unknown;
    }
    if (FMath::IsNearlyEqual(Minimum, Size.X)) return EInfinityWingThicknessAxis::X;
    if (FMath::IsNearlyEqual(Minimum, Size.Y)) return EInfinityWingThicknessAxis::Y;
    return EInfinityWingThicknessAxis::Z;
}

EInfinityWingTallEdge DetectTallEdge(const TArray<FVector>& Positions, const FTransform& Transform)
{
    const FBox Bounds = BoundsAfterTransform(Positions, Transform);
    const FVector Size = Bounds.GetSize();
    if (!Bounds.IsValid || Size.Y <= 1.0 || Size.Z <= 1.0)
    {
        return EInfinityWingTallEdge::Unknown;
    }
    const double Band = Size.Y * 0.20;
    double NegativeMax = -DBL_MAX;
    double PositiveMax = -DBL_MAX;
    for (const FVector& Position : Positions)
    {
        const FVector Point = Transform.TransformPosition(Position);
        if (Point.Y <= Bounds.Min.Y + Band)
        {
            NegativeMax = FMath::Max(NegativeMax, Point.Z);
        }
        if (Point.Y >= Bounds.Max.Y - Band)
        {
            PositiveMax = FMath::Max(PositiveMax, Point.Z);
        }
    }
    if (NegativeMax == -DBL_MAX || PositiveMax == -DBL_MAX)
    {
        return EInfinityWingTallEdge::Unknown;
    }
    const double Delta = NegativeMax - PositiveMax;
    if (FMath::Abs(Delta) < Size.Z * 0.04)
    {
        return EInfinityWingTallEdge::Even;
    }
    return Delta > 0.0 ? EInfinityWingTallEdge::NegativeY : EInfinityWingTallEdge::PositiveY;
}

FTransform MakeCanonicalTransform(
    const UStaticMesh& Mesh,
    const TArray<FVector>& Positions,
    FInfinityWingAssetEntry& Entry,
    const FSourceReportRecord* SourceRecord)
{
    const FBox OriginalBounds = Mesh.GetBoundingBox();
    Entry.OriginalBoundsSizeCm = OriginalBounds.GetSize();
    Entry.OriginalThicknessAxis = FindThicknessAxis(Entry.OriginalBoundsSizeCm);

    FTransform AxisTransform = FTransform::Identity;
    if (Entry.OriginalThicknessAxis == EInfinityWingThicknessAxis::Y)
    {
        AxisTransform = FTransform(FRotator(0.0, 90.0, 0.0));
    }
    const FBox AxisBounds = BoundsAfterTransform(Positions, AxisTransform);
    const FVector AxisSize = AxisBounds.GetSize();

    double SourceHeightScale = 1.0;
    if (SourceRecord && SourceRecord->DimensionsCm.Z > 1.0 && AxisSize.Z > 1.0)
    {
        const double Candidate = SourceRecord->DimensionsCm.Z / AxisSize.Z;
        if (Candidate >= 0.01 && Candidate <= 100.0)
        {
            SourceHeightScale = Candidate;
        }
    }
    const double DepthScale = AxisSize.X > UE_SMALL_NUMBER ? 5.0 / AxisSize.X : 1.0;
    const FTransform ScaleTransform(FQuat::Identity, FVector::ZeroVector, FVector(DepthScale, SourceHeightScale, SourceHeightScale));
    FTransform Proposed = AxisTransform * ScaleTransform;

    const FBox ScaledBounds = BoundsAfterTransform(Positions, Proposed);
    const FVector Translation(
        -ScaledBounds.GetCenter().X,
        -ScaledBounds.GetCenter().Y,
        -ScaledBounds.Min.Z);
    Proposed = Proposed * FTransform(Translation);

    Entry.TallEdgeAfterCorrection = DetectTallEdge(Positions, Proposed);
    const bool bArchitectural = (Entry.Role == EInfinityWingAssetRole::LeftArchitectural
        || Entry.Role == EInfinityWingAssetRole::RightArchitectural)
        && !IsOrientationNeutralObject(Mesh.GetName());
    const bool bWrongLeft = Entry.Role == EInfinityWingAssetRole::LeftArchitectural
        && Entry.TallEdgeAfterCorrection == EInfinityWingTallEdge::PositiveY;
    const bool bWrongRight = Entry.Role == EInfinityWingAssetRole::RightArchitectural
        && Entry.TallEdgeAfterCorrection == EInfinityWingTallEdge::NegativeY;
    const bool bWouldNeedHandednessReview = bArchitectural && (bWrongLeft || bWrongRight);
    // Do not bake a negative scale into photographed scenic geometry. Side placement,
    // camera-facing direction and image handedness are separate authoring decisions;
    // the library's placement policy resolves them non-destructively at materialization.
    Entry.bMirroredForOutsideTallEdge = false;
    if (bWouldNeedHandednessReview)
    {
        Entry.Notes = TEXT("Architectural outside edge needs placement review; automatic photographic mirroring was intentionally not applied.");
    }
    Entry.CanonicalBoundsSizeCm = BoundsAfterTransform(Positions, Proposed).GetSize();
    return Proposed;
}

bool ApplyMeshTransform(UStaticMesh& Mesh, const FTransform& Transform, FString& OutError)
{
    if (!Transform.IsValid())
    {
        OutError = FString::Printf(TEXT("Invalid correction transform for %s."), *Mesh.GetPathName());
        return false;
    }
    Mesh.Modify();
    bool bChangedAnyLod = false;
    for (int32 LodIndex = 0; LodIndex < Mesh.GetNumSourceModels(); ++LodIndex)
    {
        FMeshDescription* MeshDescription = Mesh.GetMeshDescription(LodIndex);
        if (!MeshDescription)
        {
            continue;
        }
        FStaticMeshOperations::ApplyTransform(*MeshDescription, Transform, true);
        Mesh.CommitMeshDescription(LodIndex);
        bChangedAnyLod = true;
    }
    if (!bChangedAnyLod)
    {
        OutError = FString::Printf(TEXT("%s has no editable source Mesh Description."), *Mesh.GetPathName());
        return false;
    }
    Mesh.Build(false);
    Mesh.PostEditChange();
    Mesh.MarkPackageDirty();
    return true;
}

bool BackupOriginalMeshPackage(const UStaticMesh& Mesh, FString& OutError)
{
    const FString LongPackageName = Mesh.GetOutermost()->GetName();
    FString SourceFilename;
    if (!FPackageName::DoesPackageExist(LongPackageName, &SourceFilename))
    {
        OutError = FString::Printf(TEXT("Could not resolve the source package for %s."), *Mesh.GetPathName());
        return false;
    }

    FString RelativeName = LongPackageName;
    RelativeName.RemoveFromStart(TEXT("/Game/"));
    const FString BackupFilename = FPaths::Combine(
        FPaths::ProjectSavedDir(),
        TEXT("InfinityStage/WingAssets/OriginalPackages"),
        RelativeName + FPaths::GetExtension(SourceFilename, true));
    if (IFileManager::Get().FileExists(*BackupFilename))
    {
        return true;
    }
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(BackupFilename), true);
    if (IFileManager::Get().Copy(*BackupFilename, *SourceFilename, false, true) != COPY_OK)
    {
        OutError = FString::Printf(TEXT("Could not back up %s to %s."), *SourceFilename, *BackupFilename);
        return false;
    }
    return true;
}

void PopulateSummary(const UInfinityStageWingLibraryAsset& Library, FInfinityWingAuditSummary& Summary)
{
    Summary = {};
    Summary.Total = Library.Entries.Num();
    for (const FInfinityWingAssetEntry& Entry : Library.Entries)
    {
        switch (Entry.Status)
        {
        case EInfinityWingAuditStatus::Ready: ++Summary.Ready; break;
        case EInfinityWingAuditStatus::Corrected: ++Summary.Corrected; break;
        case EInfinityWingAuditStatus::ReviewRequired: ++Summary.ReviewRequired; break;
        case EInfinityWingAuditStatus::Error: ++Summary.Errors; break;
        default: break;
        }
        if (Entry.bGeometryCanonical && Entry.Status != EInfinityWingAuditStatus::Corrected)
        {
            ++Summary.AlreadyCanonical;
        }
    }
}
}

FString FInfinityWingAuditSummary::ToString() const
{
    return FString::Printf(
        TEXT("%d assets · %d ready · %d already canonical · %d corrected · %d review · %d errors"),
        Total, Ready, AlreadyCanonical, Corrected, ReviewRequired, Errors);
}

UInfinityStageWingLibraryAsset* FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary()
{
    const TCHAR* ObjectPath = TEXT("/Game/InfinityStage/WingLibrary/DA_InfinityStageWingLibrary.DA_InfinityStageWingLibrary");
    if (UInfinityStageWingLibraryAsset* Existing = LoadObject<UInfinityStageWingLibraryAsset>(nullptr, ObjectPath))
    {
        Existing->EnsureStableIds();
        return Existing;
    }
    UPackage* Package = CreatePackage(TEXT("/Game/InfinityStage/WingLibrary/DA_InfinityStageWingLibrary"));
    UInfinityStageWingLibraryAsset* Library = NewObject<UInfinityStageWingLibraryAsset>(
        Package,
        TEXT("DA_InfinityStageWingLibrary"),
        RF_Public | RF_Standalone | RF_Transactional);
    FAssetRegistryModule::AssetCreated(Library);
    Library->MarkPackageDirty();
    return Library;
}

bool FInfinityStageWingAssetAuditor::Scan(
    UInfinityStageWingLibraryAsset& Library,
    FInfinityWingAuditSummary& OutSummary,
    FString& OutError)
{
    TMap<FString, FSourceReportRecord> SourceRecords;
    ReadSourceReports(SourceRecords);

    FARFilter Filter;
    Filter.PackagePaths.Add(TEXT("/Game/Wings"));
    Filter.PackagePaths.Add(TEXT("/Game/KK_S2_Shrine/WINGS"));
    Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
    Filter.bRecursivePaths = true;
    TArray<FAssetData> Assets;
    FAssetRegistryModule::GetRegistry().GetAssets(Filter, Assets);
    Assets.Sort([](const FAssetData& A, const FAssetData& B) { return A.PackageName.LexicalLess(B.PackageName); });

    Library.Modify();
    TMap<FSoftObjectPath, FInfinityWingAssetEntry> Existing;
    for (FInfinityWingAssetEntry& Entry : Library.Entries)
    {
        Existing.Add(Entry.Mesh.ToSoftObjectPath(), MoveTemp(Entry));
    }
    Library.Entries.Reset();

    for (const FAssetData& Asset : Assets)
    {
        const FSoftObjectPath MeshPath = Asset.ToSoftObjectPath();
        FInfinityWingAssetEntry Entry;
        if (FInfinityWingAssetEntry* Previous = Existing.Find(MeshPath))
        {
            Entry = MoveTemp(*Previous);
        }
        Entry.Mesh = TSoftObjectPtr<UStaticMesh>(MeshPath);
        if (!Entry.EntryGuid.IsValid())
        {
            Entry.EntryGuid = FGuid::NewGuid();
        }
        const EInfinityWingAssetRole DetectedRole = ClassifyRole(Asset.AssetName.ToString());
        if (DetectedRole == EInfinityWingAssetRole::Excluded
            || !Entry.bGeometryCanonical
            || Entry.Role == EInfinityWingAssetRole::Unknown)
        {
            Entry.Role = DetectedRole;
        }
        if (!Entry.bFrontAxisArtistOverride)
        {
            Entry.FrontAxis = Entry.Role == EInfinityWingAssetRole::RightArchitectural
                ? EInfinityWingFrontAxis::NegativeX
                : EInfinityWingFrontAxis::PositiveX;
        }

        UStaticMesh* Mesh = Cast<UStaticMesh>(Asset.GetAsset());
        TArray<FVector> Positions;
        if (!Mesh || !GetVertexPositions(*Mesh, Positions))
        {
            Entry.Status = EInfinityWingAuditStatus::Error;
            Entry.Notes = TEXT("No editable LOD0 Mesh Description was available.");
            Library.Entries.Add(MoveTemp(Entry));
            continue;
        }

        const FSourceReportRecord* Source = SourceRecords.Find(NormalizedAssetKey(Asset.AssetName.ToString()));
        if (Source)
        {
            Entry.SourceReportDimensionsCm = Source->DimensionsCm;
            Entry.SourceImage = Source->Source;
            Entry.SourceFbx = Source->Fbx;
        }
        if (Entry.bGeometryCanonical)
        {
            Entry.OriginalBoundsSizeCm = Mesh->GetBoundingBox().GetSize();
            Entry.CanonicalBoundsSizeCm = Entry.OriginalBoundsSizeCm;
            Entry.OriginalThicknessAxis = FindThicknessAxis(Entry.OriginalBoundsSizeCm);
            Entry.ProposedCanonicalTransform = FTransform::Identity;
            Entry.Status = Entry.AppliedCanonicalTransform.Equals(FTransform::Identity)
                ? EInfinityWingAuditStatus::Ready
                : EInfinityWingAuditStatus::Corrected;
            Library.Entries.Add(MoveTemp(Entry));
            continue;
        }

        Entry.ProposedCanonicalTransform = MakeCanonicalTransform(*Mesh, Positions, Entry, Source);
        const bool bKnownPlane = Entry.OriginalThicknessAxis == EInfinityWingThicknessAxis::X
            || Entry.OriginalThicknessAxis == EInfinityWingThicknessAxis::Y;
        const bool bPlausibleHeight = Entry.CanonicalBoundsSizeCm.Z >= 100.0
            && Entry.CanonicalBoundsSizeCm.Z <= 4000.0;
        Entry.bSafeToApplyAutomatically = bKnownPlane && bPlausibleHeight;
        const bool bNoMeaningfulChange = Entry.ProposedCanonicalTransform.Equals(FTransform::Identity, 0.001);
        Entry.bGeometryCanonical = Entry.bSafeToApplyAutomatically && bNoMeaningfulChange;
        Entry.Status = Entry.bSafeToApplyAutomatically
            ? EInfinityWingAuditStatus::Ready
            : EInfinityWingAuditStatus::ReviewRequired;
        if (!bKnownPlane)
        {
            Entry.Notes = TEXT("Thickness axis could not be resolved safely to canonical X.");
        }
        else if (!bPlausibleHeight)
        {
            Entry.Notes = TEXT("Resulting height is outside the safe 1–40 m scenic range.");
        }
        Library.Entries.Add(MoveTemp(Entry));
    }
    Library.EnsureStableIds();
    Library.LastAuditUtc = FDateTime::UtcNow();
    Library.MarkPackageDirty();
    PopulateSummary(Library, OutSummary);
    const bool bReportSaved = SaveAuditReport(Library, OutSummary.ReportPath, OutError);
    const bool bLibrarySaved = UEditorLoadingAndSavingUtils::SavePackages({ Library.GetOutermost() }, false);
    if (!bLibrarySaved && OutError.IsEmpty())
    {
        OutError = TEXT("The audit completed, but the Wing Asset Library package did not save.");
    }
    return OutSummary.Errors == 0 && bReportSaved && bLibrarySaved;
}

bool FInfinityStageWingAssetAuditor::ApplySafeCorrections(
    UInfinityStageWingLibraryAsset& Library,
    FInfinityWingAuditSummary& OutSummary,
    FString& OutError)
{
    Library.Modify();
    TArray<UPackage*> PackagesToSave;
    for (FInfinityWingAssetEntry& Entry : Library.Entries)
    {
        if (!Entry.bSafeToApplyAutomatically || Entry.bGeometryCanonical)
        {
            continue;
        }
        UStaticMesh* Mesh = Entry.Mesh.LoadSynchronous();
        if (!Mesh || !BackupOriginalMeshPackage(*Mesh, OutError)
            || !ApplyMeshTransform(*Mesh, Entry.ProposedCanonicalTransform, OutError))
        {
            Entry.Status = EInfinityWingAuditStatus::Error;
            continue;
        }
        Entry.AppliedCanonicalTransform = Entry.ProposedCanonicalTransform;
        Entry.ProposedCanonicalTransform = FTransform::Identity;
        Entry.bGeometryCanonical = true;
        Entry.Status = EInfinityWingAuditStatus::Corrected;
        Entry.CanonicalBoundsSizeCm = Mesh->GetBoundingBox().GetSize();
        PackagesToSave.AddUnique(Mesh->GetOutermost());
    }
    PackagesToSave.AddUnique(Library.GetOutermost());
    if (!UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, false))
    {
        OutError = TEXT("One or more corrected mesh packages failed to save.");
        return false;
    }
    PopulateSummary(Library, OutSummary);
    SaveAuditReport(Library, OutSummary.ReportPath, OutError);
    return OutSummary.Errors == 0;
}

bool FInfinityStageWingAssetAuditor::RepairLegacyRightPhotographicMirrors(
    UInfinityStageWingLibraryAsset& Library,
    int32& OutRepaired,
    FString& OutError)
{
    OutRepaired = 0;
    Library.Modify();
    TArray<UPackage*> PackagesToSave;
    const FTransform RemoveLegacyMirror(FQuat::Identity, FVector::ZeroVector, FVector(1.0, -1.0, 1.0));
    for (FInfinityWingAssetEntry& Entry : Library.Entries)
    {
        if (!Entry.bMirroredForOutsideTallEdge
            || Entry.Role != EInfinityWingAssetRole::RightArchitectural)
        {
            continue;
        }
        UStaticMesh* Mesh = Entry.Mesh.LoadSynchronous();
        if (!Mesh || !BackupOriginalMeshPackage(*Mesh, OutError)
            || !ApplyMeshTransform(*Mesh, RemoveLegacyMirror, OutError))
        {
            Entry.Status = EInfinityWingAuditStatus::Error;
            return false;
        }
        Entry.AppliedCanonicalTransform = Entry.AppliedCanonicalTransform * RemoveLegacyMirror;
        Entry.bMirroredForOutsideTallEdge = false;
        Entry.Status = EInfinityWingAuditStatus::Corrected;
        Entry.Notes = TEXT("Removed the legacy automatic photographic mirror; right-side facing is now a non-destructive placement rotation.");
        if (Entry.TallEdgeAfterCorrection == EInfinityWingTallEdge::NegativeY)
        {
            Entry.TallEdgeAfterCorrection = EInfinityWingTallEdge::PositiveY;
        }
        else if (Entry.TallEdgeAfterCorrection == EInfinityWingTallEdge::PositiveY)
        {
            Entry.TallEdgeAfterCorrection = EInfinityWingTallEdge::NegativeY;
        }
        Entry.CanonicalBoundsSizeCm = Mesh->GetBoundingBox().GetSize();
        PackagesToSave.AddUnique(Mesh->GetOutermost());
        ++OutRepaired;
    }
    PackagesToSave.AddUnique(Library.GetOutermost());
    Library.MarkPackageDirty();
    if (!UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, false))
    {
        OutError = TEXT("One or more legacy right-wing mirror repairs failed to save.");
        return false;
    }
    FInfinityWingAuditSummary Summary;
    PopulateSummary(Library, Summary);
    FString ReportPath;
    return SaveAuditReport(Library, ReportPath, OutError);
}

bool FInfinityStageWingAssetAuditor::RevertCorrections(
    UInfinityStageWingLibraryAsset& Library,
    const TSet<FGuid>& EntryGuids,
    FString& OutError)
{
    Library.Modify();
    TArray<UPackage*> PackagesToSave;
    for (FInfinityWingAssetEntry& Entry : Library.Entries)
    {
        if (!EntryGuids.Contains(Entry.EntryGuid) || !Entry.bGeometryCanonical
            || Entry.AppliedCanonicalTransform.Equals(FTransform::Identity))
        {
            continue;
        }
        UStaticMesh* Mesh = Entry.Mesh.LoadSynchronous();
        if (!Mesh || !ApplyMeshTransform(*Mesh, Entry.AppliedCanonicalTransform.Inverse(), OutError))
        {
            return false;
        }
        Entry.bGeometryCanonical = false;
        Entry.ProposedCanonicalTransform = Entry.AppliedCanonicalTransform;
        Entry.AppliedCanonicalTransform = FTransform::Identity;
        Entry.Status = EInfinityWingAuditStatus::Ready;
        PackagesToSave.AddUnique(Mesh->GetOutermost());
    }
    PackagesToSave.AddUnique(Library.GetOutermost());
    return UEditorLoadingAndSavingUtils::SavePackages(PackagesToSave, false);
}

bool FInfinityStageWingAssetAuditor::SaveAuditReport(
    const UInfinityStageWingLibraryAsset& Library,
    FString& OutPath,
    FString& OutError)
{
    OutPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("InfinityStage/WingAssets/wing_asset_audit.json"));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutPath), true);
    FString Json;
    if (!FJsonObjectConverter::UStructToJsonObjectString(Library.GetClass(), &Library, Json, 0, 0))
    {
        OutError = TEXT("Could not serialize the Wing Asset audit report.");
        return false;
    }
    if (!FFileHelper::SaveStringToFile(Json, *OutPath))
    {
        OutError = FString::Printf(TEXT("Could not write %s."), *OutPath);
        return false;
    }
    return true;
}
