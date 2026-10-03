# S3: a beach for the figures + marble side walls (Gary, 3 Oct, his own words in the Conductor 4 session: "the figures need a
# beach to stand on, so perhaps megascan rocks that're already in content and some plants and actually lets make the side walls
# marble like the plinth before the bloody hand stains"). DRAFT placement for Gary to adjust (like the S3 shot-list draft).
Context: Docs/Scene3BeatSheet_2026-10-01.md (diorama at dock (3500,0), landed box x 500..6500, y +/-1000, floor top z -5; ring
of figures r 260/320; waves rows at x 4200/5000/5800; backdrop on the far wall), Saved/CodexConductor/s3_flats_place.py
(the house pattern: actors attached to `S3 Hangar Root`, landed->rest composition, tags, record, revert).
## PASS 1 (offline + read-only editor probe; no writes)
- Inventory Content for Megascans/Quixel assets (rocks, beach/sand/shingle surfaces, plants/grasses/seaweed): paths, triangle
  counts if readable, Nanite yes/no, material instances. Also the material actually on `Clam_Pedastal` (the plinth) and the
  S3 side-wall actors' current materials (labels, slots).
- Draft plan (JSON + a top-down PNG diagram): a low beach mound/shingle under and around the ring (not on the camera-side gap),
  rocks clustered at the ring's back and sides, a few plants; nothing within 1.5 m of any S3 Shot camera, and nothing in the
  wave rows' travel (±100 cm). Marble: which wall actors/slots get the plinth's material (or a copy MI tinted), on the INNER
  faces only, leaving room for the later hand-print decals.
- Tools: Saved/CodexConductor/s3_beach_place.py and s3_walls_marble.py (DRY/APPLY/REVERT, backups, census, narrow saves,
  read-back), offline harness each. Final message: inventory, plan, open questions; tags per AGENTS.md. Commit nothing.
STANDING RULES: never end PIE, never quit the editor, never Save All, purge cached Saved/ modules, MCP envelope from
Saved/CodexConductor/quit_request.json; the read-only probe must assert an unchanged census.
