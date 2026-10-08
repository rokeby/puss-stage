# Gary's finishing-touch notes — 8 Oct 2026 (evening run-through)

Recorded by the finishing-touches session from Gary's message (his words quoted where they set the look). F-numbered
to avoid clashing with GARY_NOTES_LIST / GARY_PIE_NOTES numbering. Owner = proposed; Conductor 5 assigns.
Leads are marked [decl] (read in a file) or [inf] (a guess to check), never as fact.

| # | Where | Note (Gary) | Lead / first step | Owner |
|---|---|---|---|---|
| F1 | P01 | Practicals visible from the wings "just float there". Either hide them, or move/swing them gently with the wings, or put the physical lamp objects on the floor / in the bottom corner ("that might be enough"). | List every practical light + its body mesh visible from the P01 route (meshy_swap records give label/mesh/anchor). Cheapest: move the BODY mesh to the floor / bottom corner per bay, light stays; else attach to the wing. | finishing-touches (offline list + plan) |
| F2 | P01 | "Domestic looking lamp objects" still in there; can be removed. | Likely SM_Lamp_Ceiling / SM_Lamp_Wall StarterContent bodies (meshy_swap left them, NOT_A_SPHERE_BULB) [inf]; the glimmer pairs are already in Conductor 5's fixtures plan. | Conductor 5 fixtures plan |
| F3 | P01 | Finishing touch: check gobos and more uplights. | Look pass; Gary's call on stills. | Conductor 5 / look |
| F4 | P01 → S1 | Before Klara's light strike we slowly zoom into a dimly lit version of her stage in a different lighting setting. In that moment the stage lighting should be TOTAL DARKNESS; only the very dim rig lights may appear. | Find which lights light her stage before the strike (her streamed lights at a low level, or our wash). | Conductor 5 |
| F5 | S1 @ 3:44 | Rig lights turn off/disappear, "jolted into disappearance" as her street-lamp lights light the trees. The transition is fine but it "shouldn't snap". | Replace the step with a fade (~1–2 s) on the rig-light keys at 3:44. | Conductor 5 / lighting |
| F6 | S1 → I1 | Exit to total darkness works: keep. | none | — |
| F7 | I1 | No light / gobo / curtain yet: fine for now. | none | — |
| F8 | P02 | "Overwhelmingly bright … way too bright … not sure if lighting doubled up". | [decl] p02_brighten.py was applied 7 Oct (records APPLY_20261007-022538/-022814/-025331, two reverted between) and lighting_scores P02 is applied too. Check for a double application / two scores stacked [inf]. | finishing-touches (offline diff) → Conductor 5 |
| F9 | P02 | The floor is a different wood, not shiny, "reducing the atmospheric feel a lot". | [decl] floor_dark_wet_apply.py:27 deliberately skipped P02 ("Leave P02 for now", 5 Oct). Gary now wants it: apply the dark glossy floor to P02's four slabs (floor_dark_wet_apply.py:83 P02_LABELS). | Conductor 5 |
| F10 | P02 → S2 @ 9:34 | As the rig rises and the lights go off, there's "a seam between two moments" and the lighting differs across it; it needs to match. | Probe the lighting state both sides of 9:34 (frame-by-frame). | Conductor 5 |
| F11 | S2 | Don't STRIKE the fog actor / big cloudy fog before the cut ("looks quite bad when we strike it"); it should just be there when we arrive in her scene. | Move the fog's visibility/strike key to the cut. | Conductor 5 |
| F12 | S2 | The wings falling out of her sky are OK, but all the wings in her part "could use some attention". | Look pass. | Wings & Textures |
| F13 | S2 | Her shots are "quite dark": a lighting attention pass. | Lighting pass with stills. | Conductor 5 / lighting |
| F14 | S2 | Turnip assets could be replaced with something fresher; NOT a priority. | Later. | — |
