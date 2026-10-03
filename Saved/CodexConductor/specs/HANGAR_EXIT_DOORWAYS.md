# Hangar exit doorways (Gary, 3 Oct night, his own words in the Conductor 4 session: "prepare a subtle exit doorway at the back
# of each rig hangar too, like a backstage hidden doorway which usually out of view or where a backdrop is in place, it mimics
# the backdrop"). Purpose: the Scene -> Interaction exit (today a cut to the rig ceiling, then the next curtain:
# Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md item 10). DRAFT for Gary to judge; nothing keyed to the camera yet.
## PASS 1 (offline + read-only probe; no writes)
- Per hangar S1..S6: the far wall actor(s) (labels like `S<N> Hangar Far Wall`), its landed dock bounds, material slots, any
  backdrop on it (S3: `S3 Backdrop`, Opal Beach art), and the Scene's Exit camera pose (the camera that holds at the end).
  S5 is 200x150x50 m; S6 is roofless.
- Design per hangar: a door opening ~3 m wide x 4.5 m high centred (or offset where the backdrop composition suggests) in the
  far wall, made as a SEPARATE leaf actor attached to `S<N> Hangar Root` that, when closed, is flush with the wall and carries
  the SAME surface (the wall material, or on S3 the backdrop's own art region, UV-matched so the seam is near invisible); a
  thin dark shadow gap (~1 cm) at the seam is acceptable. Open state: the leaf swings or slides backstage, revealing black.
- Tools: Saved/CodexConductor/hangar_exit_doors.py (DRY/APPLY/REVERT; leaves CLOSED; backups, census, narrow saves, read-back,
  landed preview still UP, both tests), harness. Also report, per hangar, the camera distance from the Exit camera to the door
  and whether a straight walk to it clears the cast/props (for the later exit move).
Final message SHORT: per-hangar table, the probe/tool paths, open questions; tags per AGENTS.md. Commit nothing.
RULES: never end PIE, never quit, never Save All, purge cached modules, MCP envelope from quit_request.json; probe asserts an
unchanged census.
