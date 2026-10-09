# PG1b — Puss cat puppet: revision after review (offline)

Read `_house_rules.md` and `pg1_puss_cat_shadow_puppet.md`. Your previous run's files are NOT committed; copy them
from `C:\Users\Administrator\.codex\worktrees\2a7b\PussStage\Tools\ShadowGobo\Puppets\` (`cat_rig.py`,
`test_cat_rig_offline.py`) into your worktree and revise them. Review of `cat_v1/cat_poses.png` (by eye):

1. **Tail (main fault).** The three straight segments fold into an angular bracket behind the haunch that reads as
   a chair frame. Make the tail ONE thick, smoothly tapering curved shape per segment: each segment a curved,
   tapering sleeve whose ends are ROUNDED and overlap the next segment (like real card joints), base as thick as
   a wrist, tip rounded. Default `sit_upright`: the tail curls forward round the front paws along the ground and
   its tip lifts slightly into empty space in front (it must read through negative space, not hide in the body).
   `tail_flick`: the tip half rises and curls up into a hook behind the back, clearly separated from the body.
2. **Head too small for a big tom.** Scale the head up ~25 %, broader skull, heavier jowls/cheek ruff, keep the
   notched ear and scar. The muzzle should read cat (short, rounded nose, chin small) not dog.
3. **`sit_proud` vs `sit_upright` are nearly identical.** Proud: chest pushed out and up, head high and tilted back,
   ears up, eyes half-lidded (smug), tail upright behind like a question mark.
4. **Hind leg.** The sitting haunch should show a big rounded thigh and a hind paw on the ground in front of the
   haunch (side view), so the sitting silhouette reads as a seated cat, not an egg.
5. Keep everything else: architecture, faces, rods, whiskers, harness. Extend the harness: the tail tip in
   `sit_upright` must lie OUTSIDE the body silhouette's convex hull (+control) and a tail drawn inside the body
   must fail (−control).
6. Commit: if git cannot write in your sandbox, say so and list the files; do not retry.

Output to `Tools/ShadowGobo/Puppets/cat_v2/`. Final message per rule 8, plus which poses read (by eye).
