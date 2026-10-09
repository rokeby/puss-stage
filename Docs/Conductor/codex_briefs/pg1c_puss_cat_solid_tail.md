# PG1c — Puss cat puppet: thick solid tail (offline)

Read `_house_rules.md`, `pg1_puss_cat_shadow_puppet.md` and `pg1b_puss_cat_revision.md`. Start from the previous
run's uncommitted files in `C:\Users\Administrator\.codex\worktrees\b697\PussStage\Tools\ShadowGobo\Puppets\`
(`cat_rig.py`, `test_cat_rig_offline.py`); copy them into your worktree. Keep everything else as it is.

Gary 9 Oct: "send the cat back for a thick solid tail". Review of `cat_v2/cat_poses.png` (by eye): the tail is drawn
as thin curved strokes that form a hollow wire loop. It must be a **thick, SOLID, filled card shape**:

1. Each tail segment is a filled closed outline (not a stroke): a curved, tapering sleeve. Base width ≈ the front
   leg's width at the shoulder (a big tom's tail is heavy), tapering to ≈ 45 % at the tip; tip rounded and slightly
   bushy (a soft bulge before the tip is fine).
2. Joints overlap: each segment's ends are rounded discs that sit under the next segment, so no gap or seam of light
   appears at any joint in any pose. Union of segments must be ONE solid shape (no holes, no light between segments).
3. The tail must never read as a loop, ring or frame: no part of the tail may enclose light (no closed hole formed
   by the tail with itself or with the body).
4. Poses: `sit_upright` — tail lies along the ground in front of the paws, tip lifting into empty space;
   `sit_proud` — tail upright behind, question-mark curl at the tip, clearly separated from the back by light;
   `tail_flick` — the tip half rises into a hook; the rest as now.
5. Optional: 1–2 short tapered fur-notch cuts near the tail base for texture, respecting the 6-unit margin.

Harness additions (keep all existing checks): tail union is one connected component with no enclosed holes in every
pose (+control); a deliberately thin stroke tail (width < 40 % of the leg) fails a minimum-width check (−control);
a tail with a gap at a joint fails the connectivity check (−control); the `sit_upright` tail-tip-outside-hull check
stays.

Output `Tools/ShadowGobo/Puppets/cat_v3/` (poses, faces, SVGs, stepped GIF). Final message per rule 8 with which poses
read (by eye). If git cannot commit in your sandbox, say so and list the files; do not retry.
