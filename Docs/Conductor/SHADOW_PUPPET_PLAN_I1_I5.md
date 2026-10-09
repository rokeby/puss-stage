# Shadow-puppet plan for Interactions I1-I5

**Status (8 Oct 2026): documentation-only, offline proposal. Nothing here applies an Unreal, MCP, Blender, code, asset, timing, staging, or creative change.** [measured: this worktree run]

**Creative authority:** all staging, scale, rhythm, prop, and performance values below are recommendations for Gary to choose, not decisions. [declaration-proven: `Docs/Conductor/codex_briefs/_house_rules.md:6-7`]**

**Source gap:** `Docs/ShadowPuppetCaptureSpec.md` is absent from this worktree and its tracked history. The prior P6 investigation records the same search and an UNCLEAR worktree status, so this plan does not pretend to cite or recover that document. [measured: `Docs/Conductor/P6_ANIMATED_GOBO_FINDINGS_2026-10-08.md:3-7`]

## One-page summary

| Interaction | Puppets / proposed frame positions | New poses or parts (existing poses are reused first) | Cut-paper props | Estimated unique atlas cells |
| --- | --- | --- | --- | ---: |
| **I1 - Washing the boy** | Both: boy at x=0.30 facing right; Puss at x=0.70 facing left | Boy `kneel_for_wash`, `clean_reveal`; Puss `wash_other`, optional tongue | Detachable dirt fringe; tongue **or** cloth; optional water arcs | **~121** |
| **I2 - Turnips** | Both: boy low at x=0.30; Puss upright at x=0.73; food in the centre | Boy `sit_eat`, `hand_to_mouth`, `empty_hands`; Puss `offer_paw` | 3-5 turnips, leaf/scrap pile; optional father-memory cameo | **~168** |
| **I3 - Forgets his name** | Both: boy at x=0.32; Puss at x=0.74; song/pearl crosses centre | Boy `listen`, `tongue_loll`, `cough_gag`, `hand_to_throat`; Puss `present_pearl`, `concerned_watch` | Pearl/song disc; optional father-memory cameo and name token | **~190** |
| **I4 - Gets a name** | Both: boy at x=0.30; Puss at x=0.72; page travels between them | Boy `catch_page`, `read_page`, `collapse`, `named_recognition`; Puss `present_page`, `purr_hold` | Stolen page with a large `Cagliuso` mark | **~211** |
| **I5 - Becomes King** | Both: boy at x=0.35; Puss at x=0.72; crown above boy; village low | Boy `kneel_for_crown`, `crowned_upright`, `king_proud`; Puss existing `sit_proud` plus `declare`; optional boy aftermath pose | Crown; optional crushed-village strip / dust pieces | **~232** |

All positions, pose names, prop counts, durations, and cell totals in this table are **inferred recommendations**, not approved values. The boy-facing-right and Puss-facing-left convention is declaration-proven by the rigs (`Tools/ShadowGobo/Puppets/boy_rig.py:1-10`; `Tools/ShadowGobo/Puppets/cat_rig.py:1-10`).

## Shared plan rules and estimating method

- **Composite frame:** recommend one composite flipbook atlas per Interaction, assigned to that Interaction's matched Hangar/Mouth spot pair. Draw boy, Puss, and props together in every cell so the sleight cut cannot desynchronise separate performers. [inferred recommendation] The existing design gives both spots the same gobo material instance and shared frame control. [declaration-proven: `Docs/ShadowGoboPipeline_2026-10-06.md:204-209`]
- **Frame:** use a landscape 1.88:1 lit rectangle. Proposed safe staging is the boy in the left third and Puss in the right third, facing each other, with an 8% outer margin and the centre third reserved for handoffs. [inferred recommendation] The 1.88 border is supported by the gobo findings. [declaration-proven: `Docs/Conductor/P6_ANIMATED_GOBO_FINDINGS_2026-10-08.md:149-166`]
- **Holds and movement:** each distinct held composite pose costs one cell. A move costs `25 x duration_seconds` cells because it is rendered at the 25 fps display rate; identical poses and exact reversed motion may reuse cells. [declaration-proven: `Docs/Conductor/codex_briefs/pg2_puppet_realtime_moves.md:10-12,31-35,53-57`] Cell totals below are inferred from that rule and the proposed durations; they exclude live handheld wobble.
- **Wobble:** do not bake handheld wobble into any atlas. It remains live so holds can deduplicate to one cell. [declaration-proven: `Docs/Conductor/codex_briefs/pg2_puppet_realtime_moves.md:44-49`]
- **Timing estimate:** the cue sheet contains cue order and words but no row timestamps. Spoken estimates use **150 words/minute (2.5 words/second)**, counted offline from `working.csv`; breaths, pauses, performer sounds, and physical action remain untimed unless this plan proposes a rough movement duration. [measured word counts; inferred delivery rate: `Docs/CueSheet/working.csv:1-106`]
- **Available boy vocabulary:** current reusable body poses are rest, head-in-hands, and arm-out; current face replacements cover normal/worried/blubber/crying/surprised/sad. [declaration-proven: `Tools/ShadowGobo/Puppets/boy_rig.py:308-333,389-414`]
- **Available Puss vocabulary:** current reusable poses are `sit_upright`, `sit_proud`, `loaf_hunched`, `sit_look_up`, `paw_lick`, `washing`, `meow`, and `tail_flick`; face parts cover four eye, three ear, and two mouth states. [declaration-proven: `Tools/ShadowGobo/Puppets/cat_rig.py:191-239`]
- **Duration authority:** Gary has said the Interaction happens on the curtain and may run about 60 seconds or longer; sequence playback range, not this plan, owns final duration. [declaration-proven: `Docs/ChaosClothCurtain.md:542-558`]

## I1 - Washing the boy

The cue-spine action is rejection/whimper, Puss washing the boy clean, then response. [declaration-proven: `Docs/BoyCatInterstitialTransition.md:29-35`]

### Cue beats and approximate time

| Cue | Cue-sheet beat | Approx. seconds | Proof / limit |
| --- | --- | ---: | --- |
| `R0034` | Boy is dirty; narration describes the accumulated muck | 20.4 spoken | [measured: 51 words; `Docs/CueSheet/PUSS_CUE_LIST.md:46-51`; `Docs/CueSheet/working.csv:37-42`] |
| `R0035` | Puss drains the fountain and heaps water onto the boy | 12.4 spoken, physical duration open | [measured: 31 words; `Docs/CueSheet/PUSS_CUE_LIST.md:50-52`; `Docs/CueSheet/working.csv:42`] |
| `R0038` | Boy is now clean but still full of wants | 5.2 spoken | [measured: 13 words; `Docs/CueSheet/PUSS_CUE_LIST.md:55-58`; `Docs/CueSheet/working.csv:45`] |
| `R0039` | Boy whimpers | performer-set | [declaration-proven cue; timing absent: `Docs/CueSheet/PUSS_CUE_LIST.md:57-59`] |
| `R0040` | "So Puss walked on" | 1.6 spoken | [measured: 4 words; `Docs/CueSheet/PUSS_CUE_LIST.md:59-60`] |

`R0034-R0035` are currently listed inside S1 Animals, while `R0038-R0040` are under Transition. Replaying or moving the wash into I1 is therefore a creative/editorial decision, even though the normative cue spine calls I1 "Washing the boy." [declaration-proven source placement: `Docs/CueSheet/PUSS_CUE_LIST.md:44-60`; inferred conflict]

### Screen and staging

Recommend both puppets in one composite frame: boy at x=0.30, feet near y=0.88; Puss at x=0.70, rump near y=0.86. Keep the boy's right-facing face and Puss's left-facing face separated by at least 0.16 frame width during the wash so head, paw/tongue, and rods remain legible in negative space. [inferred recommendation]

### Pose and part list

- **Boy existing:** rest + worried face for dirty/rejected; head-in-hands + crying/blubber face for the whimper; arm-out + surprised face for a recoil. [declaration-proven availability: `Tools/ShadowGobo/Puppets/boy_rig.py:322-333,389-414`; inferred mapping]
- **Boy new:** `kneel_for_wash` (shortened lower body or separate thigh/shin pieces), `clean_reveal` (upright chest and open arms), and optional detachable `dirt_fringe` silhouette pieces around hair/tunic/legs. [inferred recommendation]
- **Puss existing:** `sit_upright`, `sit_look_up`, `washing`, then `sit_proud`. Existing `washing` is self-washing, so it is only a motion/attitude reference. [declaration-proven availability: `Tools/ShadowGobo/Puppets/cat_rig.py:204-221`; inferred mapping]
- **Puss new:** `wash_other`, with the head and near paw reaching left beyond the face profile; optional hinged tongue replacement part. [inferred recommendation]

### Prop specifications

- **Tongue option:** a tapered hinged card tongue, about 0.10 boy-height long, attached at Puss's jaw; no independent rod if the jaw/head rod carries it. [inferred recommendation]
- **Cloth option:** ragged oval cloth, about 0.18 boy-height, first held in Puss's near paw and then crossing the boy's head/shoulder; thin rod from below-right, kept outside the gap between faces. [inferred recommendation]
- **Water option:** two or three detachable curved slivers, each about 0.15 boy-height, travelling from centre-right to the boy; side rod from below. Water may clutter a silhouette and is optional. [inferred recommendation]
- **Dirt:** 4-6 removable edge patches, each 0.03-0.07 boy-height, pinned to the boy card so their removal changes the outer contour; interior spots will not read as shadow. [inferred recommendation]

### Proposed move list and atlas budget

| Held pose | Real-time move | Duration | Next held pose |
| --- | --- | ---: | --- |
| H1 dirty boy / Puss upright | Boy recoils and face changes | 0.4 s | H2 whimper tableau |
| H2 whimper | Boy lowers; Puss leans in | 0.8 s | H3 wash-ready |
| H3 wash-ready | Three broad tongue/cloth strokes; dirt disappears on the last | 1.8 s | H4 clean reveal |
| H4 clean reveal | Boy rises; Puss resets | 0.8 s | H5 relieved tableau |
| H5 relieved | Puss gestures onward / both re-aim | 0.8 s | H6 onward hold |

Budget: 6 holds + `25 x 4.6 s` of moves = **about 121 cells**. [inferred calculation]

### Open creative questions for Gary

1. Should the wash move from S1 into I1, be repeated as a short recap, or remain only in S1?
2. Is Puss washing with a visible tongue, a cloth, water, or a mixture?
3. Should dirt vanish literally from the boy's contour, or should cleanliness be carried only by posture?
4. Is physical lick/contact affectionate, comic, or deliberately uncomfortable?

## I2 - Turnips

The cue spine requires turnips received/eaten, food running out, the father remembered/cursed, a whimper, and Puss's response. [declaration-proven: `Docs/BoyCatInterstitialTransition.md:32`]

### Cue beats and approximate time

| Cue(s) | Cue-sheet beat | Approx. seconds | Proof / limit |
| --- | --- | ---: | --- |
| `R0046-R0048` | Puss: what is good enough for a god is good enough for the boy | 6.0 spoken | [measured: 15 words; `Docs/CueSheet/PUSS_CUE_LIST.md:69-74`] |
| `R0049` | Puss takes the turnips; their absence breaks the god/old-man ritual | 23.2 spoken | [measured: 58 words; `Docs/CueSheet/PUSS_CUE_LIST.md:74-75`] |
| `R0050` | Boy eats all turnips, lacks again, remembers his dead father/past, and whimpers | 20.8 spoken | [measured: 52 words; `Docs/CueSheet/PUSS_CUE_LIST.md:76-79`; `Docs/CueSheet/working.csv:57`] |
| `R0051` | Whimper | performer-set | [declaration-proven cue; timing absent: `Docs/CueSheet/PUSS_CUE_LIST.md:79`] |
| `R0052-R0053` | Puss thinks: "Poor boy, he thinks of the past" | 4.8 spoken | [measured: 12 words; `Docs/CueSheet/PUSS_CUE_LIST.md:80-81`] |
| `R0054` | "And so Puss walked on" | 2.0 spoken | [measured: 5 words; `Docs/CueSheet/PUSS_CUE_LIST.md:82`] |

The spoken material is about **56.8 seconds plus the whimper and pauses** if all rows are carried into/over I2 at 150 wpm. That is an inferred timing envelope, not a cue lock. `R0046-R0049` are placed in Scene 2 and `R0050-R0054` in Transition. [declaration-proven placement: `Docs/CueSheet/PUSS_CUE_LIST.md:67-83`; inferred timing]

### Screen and staging

Recommend both puppets in one composite frame. Boy sits low at x=0.30 so turnips can travel through the open centre; Puss holds at x=0.73 in `sit_upright`. Keep the optional father-memory cameo high-left and smaller than the live boy so it cannot be mistaken for a third full-scale performer. [inferred recommendation]

### Pose and part list

- **Boy existing:** arm-out for accepting food; worried/sad, head-in-hands, and crying/blubber for loss and whimper. [declaration-proven availability: `Tools/ShadowGobo/Puppets/boy_rig.py:322-333,389-414`; inferred mapping]
- **Boy new:** `sit_eat`, `hand_to_mouth`, `bite_chew` (jaw replacement or head bob), `empty_hands`, and `memory_slump`. [inferred recommendation]
- **Puss existing:** `sit_upright` for watching, `sit_look_up` for thought, and `loaf_hunched` for the sympathetic response. [declaration-proven availability: `Tools/ShadowGobo/Puppets/cat_rig.py:204-221`; inferred mapping]
- **Puss new:** `offer_paw` only if the receipt is shown in I2; the existing raised paw is targeted to Puss's own mouth and does not extend far enough for a handoff. [declaration-proven existing target: `Tools/ShadowGobo/Puppets/cat_rig.py:213-217`; inferred need]

### Prop specifications

- **Turnips:** recommend 3-5 separate round/root cards, each 0.10-0.13 boy-height with a leafy crown; one held in the boy's near hand, the rest on a shared low tray rod entering from the left. [inferred recommendation]
- **Scraps:** one leafy remnant at 0.06 boy-height, dropped at the boy's feet on a short lower rod to make "food runs out" readable. [inferred recommendation]
- **Father-memory option:** a pale-size silhouette card about 0.32 boy-height, simplified to the old man's head/shoulders, entering from upper-left on a top rod and withdrawing rather than "dying" on screen. [inferred recommendation]

### Proposed move list and atlas budget

| Held pose | Real-time move | Duration | Next held pose |
| --- | --- | ---: | --- |
| H1 Puss offers / boy reaches | Boy takes turnip and sits | 0.8 s | H2 first bite |
| H2 first bite | Three hand-to-mouth / jaw cycles | 2.4 s | H3 last turnip gone |
| H3 empty | Boy drops leaf scrap | 0.4 s | H4 empty-hands hold |
| H4 empty-hands | Boy folds into memory slump; cameo enters if used | 0.8 s | H5 father-memory hold |
| H5 memory | Boy trembles/whimpers | 0.6 s | H6 whimper hold |
| H6 whimper | Puss turns head and looks up | 0.6 s | H7 Puss-thinks hold |
| H7 thought | Puss indicates onward; boy resets enough to follow | 0.8 s | H8 onward hold |

Budget: 8 holds + `25 x 6.4 s` of moves = **about 168 cells**. [inferred calculation]

### Open creative questions for Gary

1. How many turnips should be visible, and should eating read comic, desperate, or ugly?
2. Should I2 repeat the receipt of the turnips from Scene 2, or begin with the boy already eating?
3. Is the father a literal cameo, an empty space the boy looks toward, or sound only?
4. Does Puss comfort the boy, merely observe him, or become impatient and lead on?

## I3 - Forgets his name

The cue spine requires the Song of Forgetting, loss of father and then own name, gagging/nasal whimper, and Puss's response. [declaration-proven: `Docs/BoyCatInterstitialTransition.md:33`]

### Cue beats and approximate time

| Cue(s) | Cue-sheet beat | Approx. seconds | Proof / limit |
| --- | --- | ---: | --- |
| `R0063-R0065` | Puss identifies the forgetting song as what the boy needs | 10.4 spoken | [measured: 26 words; `Docs/CueSheet/PUSS_CUE_LIST.md:97-100`] |
| `R0066` | Pearl moves | action, untimed | [declaration-proven cue; timing absent: `Docs/CueSheet/PUSS_CUE_LIST.md:100`] |
| `R0069` | Boy forgets father, then his own name; tongue weakens/lolls; he coughs | 26.0 spoken | [measured: 65 words; `Docs/CueSheet/PUSS_CUE_LIST.md:104-107`; `Docs/CueSheet/working.csv:76`] |
| `R0070` | Cough, whimper | performer-set | [declaration-proven cue; timing absent: `Docs/CueSheet/PUSS_CUE_LIST.md:107`] |
| `R0071` | "So Puss..." | 0.8 spoken | [measured: 2 words; `Docs/CueSheet/PUSS_CUE_LIST.md:108`] |

The spoken envelope is about **37.2 seconds plus pearl movement, cough, whimper, and pauses** at 150 wpm. `R0063-R0066` are in Scene 3 and `R0069-R0071` are in Transition. [declaration-proven placement: `Docs/CueSheet/PUSS_CUE_LIST.md:89-112`; inferred timing]

### Screen and staging

Recommend boy at x=0.32 and Puss at x=0.74, both full enough to read the boy's mouth and Puss's head turn. The pearl/song disc travels from Puss toward the boy through the centre. If the father cameo is used, it recedes behind/above the boy before the name-loss beat. [inferred recommendation]

### Pose and part list

- **Boy existing:** rest for listening; worried/sad for memory loss; surprised/wide for the instant he cannot name himself; head-in-hands/blubber for the whimper. [declaration-proven availability: `Tools/ShadowGobo/Puppets/boy_rig.py:308-333,389-414`; inferred mapping]
- **Boy new:** `listen`, `hand_to_throat`, `tongue_loll` replacement mouth/head, and `cough_gag` with hinged jaw/torso contraction. [inferred recommendation]
- **Puss existing:** `sit_look_up`, `meow`, `loaf_hunched`, and `tail_flick` as possible bookends. [declaration-proven availability: `Tools/ShadowGobo/Puppets/cat_rig.py:204-221`; inferred mapping]
- **Puss new:** `present_pearl` and `concerned_watch`; the latter can be a new pose-table combination using flat/one-swivelled ears without new geometry. [declaration-proven face parts: `Tools/ShadowGobo/Puppets/cat_rig.py:229-239`; inferred mapping]

### Prop specifications

- **Pearl/song disc:** circular card about 0.10 boy-height, with one crescent cut that stays inside the edge; top rod so it can float from Puss to the boy. [inferred recommendation]
- **Father-memory option:** same 0.32 boy-height cameo proposed for I2, reused for continuity, withdrawn upward as the memory disappears. [inferred recommendation]
- **Name token option:** a small name-card about 0.18 boy-height held near the boy's chest, then rotated edge-on/removed. Literal writing may not read in silhouette, so the token's disappearance would carry the beat. [inferred recommendation]

### Proposed move list and atlas budget

| Held pose | Real-time move | Duration | Next held pose |
| --- | --- | ---: | --- |
| H1 Puss attentive / boy neutral | Puss presents pearl/song disc | 0.8 s | H2 offer hold |
| H2 offer | Boy leans/listens; disc crosses centre | 0.8 s | H3 listening hold |
| H3 listening | Father cameo withdraws / name token dims by removal | 1.0 s | H4 blank-memory hold |
| H4 blank memory | Boy snaps to wide-eyed recognition of loss | 0.6 s | H5 nameless hold |
| H5 nameless | Tongue replacement lowers | 0.6 s | H6 tongue-loll hold |
| H6 tongue loll | Two cough/gag contractions | 1.2 s | H7 cough hold |
| H7 cough | Boy folds into whimper | 0.8 s | H8 whimper hold |
| H8 whimper | Puss ears/head shift to concern | 0.6 s | H9 Puss-response hold |
| H9 response | Puss and boy re-aim onward | 0.8 s | H10 onward hold |

Budget: 10 holds + `25 x 7.2 s` of moves = **about 190 cells**. [inferred calculation]

### Open creative questions for Gary

1. Should the pearl/song be visible again in I3 or remain a Scene 3 event only?
2. Is forgetting shown by a literal father cameo/name token, or only by the boy's performance?
3. How grotesque should the lolling tongue and cough become?
4. Does Puss recognise that the cure caused harm, or remain satisfied and move on?

## I4 - Gets a name

The cue spine requires Puss to present the stolen page/name "Cagliuso," the boy to recognise it, then whimper and receive Puss's response. [declaration-proven: `Docs/BoyCatInterstitialTransition.md:34`]

### Cue beats and approximate time

| Cue(s) | Cue-sheet beat | Approx. seconds | Proof / limit |
| --- | --- | ---: | --- |
| `R0077-R0079` | "Cagliuso" is called; Puss thinks it is a fine name | 3.6 spoken plus called-name beat | [measured: 9 narrated words; `Docs/CueSheet/PUSS_CUE_LIST.md:117-123`] |
| `R0080` | Page floats across screen; boy falls | action, untimed | [declaration-proven cue: `Docs/CueSheet/PUSS_CUE_LIST.md:123-124`] |
| `R0081` | Exit | action, untimed | [declaration-proven cue: `Docs/CueSheet/PUSS_CUE_LIST.md:124`] |
| `R0082` | Boy is named Cagliuso but remains full of wants and whimpers | 8.0 spoken | [measured: 20 words; `Docs/CueSheet/PUSS_CUE_LIST.md:126-129`; `Docs/CueSheet/working.csv:89`] |
| `R0083-R0084` | Whimper; Puss purrs | performer-set | [declaration-proven cues; timing absent: `Docs/CueSheet/PUSS_CUE_LIST.md:129-130`] |
| `R0085` | "Purred Puss. And they set off again" | 2.8 spoken | [measured: 7 words; `Docs/CueSheet/PUSS_CUE_LIST.md:131`] |

The spoken envelope is about **14.4 seconds plus page flight, fall, exit, whimper, purr, and pauses**. Page flight/fall are placed in Scene 4 while naming/whimper/purr are in Transition, so repeating the page in I4 is a creative/editorial decision. [declaration-proven placement: `Docs/CueSheet/PUSS_CUE_LIST.md:115-132`; inferred timing/conflict]

### Screen and staging

Recommend boy at x=0.30 and Puss at x=0.72. The page begins near Puss, crosses the centre at chest height, and ends in the boy's near hand. The fall stays within the lower-left quadrant so Puss and the page remain readable and the boy never exits the 1.88 frame. [inferred recommendation]

### Pose and part list

- **Boy existing:** arm-out + surprised face for reaching/catching; worried/sad and head-in-hands for the post-name want/whimper. [declaration-proven availability: `Tools/ShadowGobo/Puppets/boy_rig.py:322-333,389-414`; inferred mapping]
- **Boy new:** `catch_page`, `read_page`, `named_recognition`, `collapse`, and a low `fallen_hold`. The current body is a single torso/legs root, so a convincing fall likely needs a replacement whole-body card rather than extreme rotation of the standing part. [declaration-proven body construction: `Tools/ShadowGobo/Puppets/boy_rig.py:136-175`; inferred need]
- **Puss existing:** `sit_upright`, `sit_proud`, and eyes-shut face parts for a purr hold. [declaration-proven availability: `Tools/ShadowGobo/Puppets/cat_rig.py:204-239`; inferred mapping]
- **Puss new:** `present_page` with near paw extended into the centre; `purr_hold` can be a pose-table combination rather than new geometry unless Gary wants visible chest pulses. [inferred recommendation]

### Prop specifications

- **Stolen page:** ragged rectangle about 0.28 boy-height tall by 0.20 boy-height wide. Use a large cut-paper `C` or a three-notch name emblem; the full word `Cagliuso` is likely too fine to read at projected distance. [inferred recommendation]
- **Rod:** thin top rod for the float, with a second short attachment point at the page's lower corner to control rotation; transfer to the boy's near hand for the read hold. [inferred recommendation]

### Proposed move list and atlas budget

| Held pose | Real-time move | Duration | Next held pose |
| --- | --- | ---: | --- |
| H1 Puss with page / boy neutral | Page floats into centre | 1.6 s | H2 page-centre hold |
| H2 page centre | Puss raises offering paw | 0.6 s | H3 presentation hold |
| H3 presentation | Page crosses to boy's near hand | 0.8 s | H4 catch hold |
| H4 catch | Boy draws page close and reads | 0.8 s | H5 reading hold |
| H5 reading | Boy recognises the name / face lifts | 0.6 s | H6 named hold |
| H6 named | Boy collapses into lower-left | 0.8 s | H7 fallen hold |
| H7 fallen | Boy rises to a low seated position | 0.8 s | H8 still-wanting hold |
| H8 wanting | Boy whimpers | 0.6 s | H9 whimper hold |
| H9 whimper | Puss closes eyes / chest gives one purr pulse | 0.6 s | H10 purr hold |
| H10 purr | Both re-aim to depart | 0.8 s | H11 onward hold |

Budget: 11 holds + `25 x 8.0 s` of moves = **about 211 cells**. [inferred calculation]

### Open creative questions for Gary

1. Should page flight and the boy's fall occur only in Scene 4, only in I4, or be echoed in both?
2. Must the audience read the full word "Cagliuso," or is a large emblem plus narration enough?
3. Does the boy stay fallen through the naming beat, or rise before he whimpers?
4. Is Puss's purr a still held silhouette, a small chest pulse, or sound only?

## I5 - Becomes King

The cue spine requires crown/declaration, the boy becoming King, a trace or sound of the crushed village, a whimper, and Puss's response. [declaration-proven: `Docs/BoyCatInterstitialTransition.md:35`]

### Cue beats and approximate time

| Cue(s) | Cue-sheet beat | Approx. seconds | Proof / limit |
| --- | --- | ---: | --- |
| `R0094` | Puss tells the older mountain that the taller mountain proclaimed Cagliuso King | 10.0 spoken | [measured: 25 spoken words; `Docs/CueSheet/PUSS_CUE_LIST.md:145-147`; `Docs/CueSheet/working.csv:101`] |
| `R0095` | Rigi rejects the rival's right and proclaims Cagliuso King | 13.2 spoken | [measured: 33 spoken words, excluding the B7 label; `Docs/CueSheet/PUSS_CUE_LIST.md:146-148`; `Docs/CueSheet/working.csv:102`] |
| `R0096` | Puss turns to the other mountain | 2.8 spoken | [measured: 7 words; `Docs/CueSheet/PUSS_CUE_LIST.md:148-149`] |
| After `R0096` | I5 transition rows are absent from the working cue sheet | not derivable | [measured absence: `Docs/CueSheet/PUSS_CUE_LIST.md:150-160`; `Docs/CueSheet/working.csv:103-106`] |

The available proclamation material is about **26.0 seconds plus pauses** at 150 wpm. The crown, crushed-village trace, whimper, and response come from the normative I5 cue spine, not from currently enumerated post-`R0096` cue rows. [declaration-proven spine: `Docs/BoyCatInterstitialTransition.md:35`; measured cue-sheet gap]

### Screen and staging

Recommend boy at x=0.35 and Puss at x=0.72. Reserve upper-left above the boy for the crown and the lower centre for an optional village strip. Keep the triumph in the upper two-thirds; let the village trace cross below their feet so it can register as consequence without becoming a third character. [inferred recommendation]

### Pose and part list

- **Boy existing:** surprised/wide for proclamation; worried/sad or head-in-hands for the consequence/whimper. [declaration-proven availability: `Tools/ShadowGobo/Puppets/boy_rig.py:322-333,389-414`; inferred mapping]
- **Boy new:** `kneel_for_crown`, `crowned_upright`, `king_proud`, and optional `king_aftermath`. Add a crown attachment socket to the head or treat the crown as a separately rodded prop. [inferred recommendation]
- **Puss existing:** `sit_proud`, `meow` for declaration, and `tail_flick` for satisfaction. [declaration-proven availability: `Tools/ShadowGobo/Puppets/cat_rig.py:204-227`; inferred mapping]
- **Puss new:** `declare` only if `meow` is too open-mouthed/comic; `look_down_at_village` can likely be a new pose-table combination using neck angle and flat/one-swivelled ears. [inferred recommendation]

### Prop specifications

- **Crown:** three-point crown, about 0.18 boy-height wide and 0.10 boy-height tall, entering on a top rod and settling onto a head socket. Keep cut-outs broad and at least a card margin from the outline. [inferred recommendation]
- **Village option:** low skyline strip about 0.18 boy-height high and 0.60 boy-height wide, carried on a horizontal side rod. A second broken version can replace it, with 2-3 loose dust/debris cards on lower rods. [inferred recommendation]
- **Non-literal alternative:** omit village geometry and let the crushing exist only in sound while boy and Puss react to the floor. [inferred recommendation]

### Proposed move list and atlas budget

| Held pose | Real-time move | Duration | Next held pose |
| --- | --- | ---: | --- |
| H1 boy surprised / Puss upright | Puss turns into declaration/meow | 0.8 s | H2 declaration hold |
| H2 declaration | Crown descends over boy | 1.2 s | H3 crown-hover hold |
| H3 crown hover | Boy kneels | 0.8 s | H4 kneeling hold |
| H4 kneeling | Crown settles into socket | 0.4 s | H5 crowned-kneel hold |
| H5 crowned kneel | Boy rises to king-proud | 1.0 s | H6 king tableau |
| H6 king tableau | Puss becomes proud / tail flicks | 0.6 s | H7 shared triumph hold |
| H7 triumph | Village strip crushes/replaces, or both look down on sound | 1.2 s | H8 consequence hold |
| H8 consequence | Boy loses proud posture | 0.8 s | H9 aftermath hold |
| H9 aftermath | Boy whimpers | 0.6 s | H10 whimper hold |
| H10 whimper | Puss responds with head/ear shift | 0.6 s | H11 response hold |
| H11 response | Both re-aim onward | 0.8 s | H12 onward hold |

Budget: 12 holds + `25 x 8.8 s` of moves = **about 232 cells**. [inferred calculation]

### Open creative questions for Gary

1. Does the crown appear in Scene 5, I5, or both?
2. Is becoming King triumphant, absurd, ominous, or all three in sequence?
3. Should the crushed village be a literal cut-paper strip, only a sound, or a brief dust trace?
4. Does Puss register the village's destruction, or remain proudly focused on the boy?
5. What narration/action rows should follow `R0096` in the working cue sheet?

## Production handoff after Gary's decisions

1. Lock which upstream Scene beats are repeated or moved into each Interaction; do not animate from both interpretations. [inferred recommendation]
2. Gary selects the staging values, prop alternatives, rods/hands visibility, and move durations. [declaration-proven creative authority: `Docs/Conductor/codex_briefs/_house_rules.md:7`]
3. Draw new replacement body/face/prop parts and render one contact sheet per Interaction, using existing poses unchanged wherever the mapping above permits. [inferred recommendation]
4. Render holds once and moves at 25 fps; composite both puppets and every prop into each atlas cell; exclude handheld wobble. [declaration-proven motion rule: `Docs/Conductor/codex_briefs/pg2_puppet_realtime_moves.md:10-12,25-35,44-51`; inferred composite recommendation]
5. Recalculate each atlas after approved timing. The totals above are planning estimates, not capacity promises. [inferred recommendation]
6. Review the offline contact sheet and preview before any later Unreal authoring. The existing gobo result proved paired drapes can match and the silhouette can follow the pleats, but it did not visually accept these five performances. [measured prior result: `Docs/Conductor/P6_ANIMATED_GOBO_FINDINGS_2026-10-08.md:182-196`; inferred acceptance boundary]
