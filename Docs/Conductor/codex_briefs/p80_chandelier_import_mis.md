# P80 — Import Iron 3 chandelier (+ chain) and author its aged MIs (Codex, offline tool; live by conductor)

Read `_house_rules.md` + memory notes ue58-fbx-import-traps (Interchange ignores FbxImportUI; LODs/sockets API names;
modify() before setters), ue58-python-material-authoring (NEVER delete nodes on existing assets; setters lie, read back;
LINEAR_GRAYSCALE; create-only), ue58-bulk-import-oom-crash (batch + GC), and known traps (str(FGuid) changes per call;
CineCameraActor → get_cine_camera_component()). Offline only.
Inputs (Hyper3D, done 18:57Z): `DerivedAssets/ChandelierBuild/Output/Iron3/` (SM_Chandelier_Iron3.fbx with 44
SOCKET_Candle_* at wick tips + ChainAttach; SM_Chandelier_Iron3_Chain.fbx; chandelier_Iron3_chain.json v1) and the 5 maps
for Chandelier_Iron3 in `DerivedAssets/StageFrontBuild/BakedStageFront/` (BaseColor_Dusty / BaseColor_Clean sRGB; Masks
RGBA linear R dust G soot B AO A peel; N DirectX → convert/flip to UE's convention and say which; Roughness linear).
Dedupe: reuse an existing create-only aged/masked master if one exists (grep Content-facing tools for "Masks"/dust/soot/
peel masters, e.g. the stage-front or FlatV3 skin masters); else create ONE new master (create-only) with the mask
channels exposed.
Build: DRY/IMPORT/MAT_CHECK/APPLY-style tool `Saved/CodexConductor/ChandelierImport_20261009/` that imports both FBXs to
`/Game/Scenes/Props/Chandelier/` (sockets preserved and read back: 44 SOCKET_Candle_* + ChainAttach), imports the 5
textures with correct compression/sRGB, creates MI_Chandelier_Iron3 (dusty default, clean switch), assigns it, and
verifies — places NOTHING (placement is job 75). Exact census, targeted saves, read-back markers; one import per call.
Harness +/- (socket count, sRGB flags, normal convention, refuse overwrite of existing assets). Tiered report.
