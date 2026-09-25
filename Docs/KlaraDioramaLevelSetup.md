# Klara Diorama Level Setup

## 1. Create the level

In Unreal Engine 5.8, select **File > New Level > Empty Level**.

Save it with a unique name, for example:

```text
/Game/Klara/Diorama01/Maps/L_Klara_Diorama01
```

## 2. Use Unreal's normal scale

Units are not configured separately for each level. Unreal defaults to centimetres:

```text
1 Unreal Unit = 1 cm
100 Unreal Units = 1 metre
```

Build at real-world scale and normally leave placed actors at Scale `1, 1, 1`.

Units can be checked under **Edit > Project Settings > Editor > Appearance > Units > Advanced > Distance/Length: Centimeters**.

[Unreal Engine: Units of Measurement](https://dev.epicgames.com/documentation/unreal-engine/units-of-measurement-in-unreal-engine)

## 3. Add an origin marker

Open **Place Actors**, select **Basic > Empty Actor**, and drag it into the level.

In the World Outliner, rename it:

```text
DioramaOrigin
```

## 4. Give it an identity transform

Select `DioramaOrigin`. Under **Details > Transform**, enter:

```text
Location: X 0, Y 0, Z 0
Rotation: Roll 0, Pitch 0, Yaw 0
Scale:    X 1, Y 1, Z 1
```

"Identity transform" means exactly those values. The actor must not be attached to another actor.

The actor is a visible reference marker. It does not create or alter the level's world origin; every Unreal level already has a fixed world origin at `0, 0, 0`.

## 5. Agree the orientation

Unreal uses:

```text
+X = forward, red
+Y = right, green
+Z = up, blue
```

Confirm which direction faces the audience and whether the stage floor surface is at `Z = 0`. The origin alone does not communicate direction.

[Unreal Engine: Coordinate System and Spaces](https://dev.epicgames.com/documentation/en-us/unreal-engine/coordinate-system-and-spaces-in-unreal-engine)

## 6. Use the supplied stage reference

Use the correctly scaled wing meshes or simplified reference supplied by the main project. It should show:

- Left and right wings.
- Stage width.
- Floor height.
- The `0, 0, 0` position.
- The audience/front direction.

Place this reference at the supplied transform and label it `REFERENCE_ONLY`.

## 7. Keep the diorama self-contained

All scenery, lights, fog, effects, cameras and post-process volumes required by the diorama should live in the diorama level.

Do not rely on actors placed only in an unrelated test or preview level.

## 8. Create the sequence separately

Save the Level Sequence alongside the map, for example:

```text
/Game/Klara/Diorama01/Sequences/LS_Klara_Diorama01
```

The sequence should:

- Bind only to actors inside the diorama level.
- Include a Camera Cuts track.
- Use the agreed frame rate.

## 9. Identify project-dependent requirements

Document anything the level requires that may not exist in the destination project, including:

- Plugins.
- Blueprints.
- Custom collision channels.
- Project or rendering settings.
- Third-party assets.

Map-specific GameMode and World Settings will not replace those of the main map when the diorama is added as a Level Instance.

## 10. Handoff

Select both assets in the Content Browser:

- `L_Klara_Diorama01`
- `LS_Klara_Diorama01`

Then select **Asset Actions > Migrate** and migrate them to the destination project's `Content` folder. Unreal will include their referenced asset dependencies in the Asset Report.

When the migrated level is placed in the main map as a Level Instance, give the Level Instance this transform:

```text
Location: X 0, Y 0, Z 0
Rotation: Roll 0, Pitch 0, Yaw 0
Scale:    X 1, Y 1, Z 1
```

This aligns the diorama level's world origin with the main map's world origin.
