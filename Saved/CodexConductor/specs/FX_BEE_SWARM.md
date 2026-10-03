# S6 bee/firefly swarm (Gary, 2 Oct night, his own words in the Conductor 4 session: a fairly realistic-looking (not
# biological) swarm that behaves chaotically, non-repetitively, swarms around the camera and blurs when too close; SOUND
# PAUSED ("a single track will probably do"). Design: the conductor's answer in that session: an attractor target that darts
# (wander + jumps), per-bee randomised orbits, time-evolving 2-scale curl noise, random per-bee dart impulses, drag + speed
# limit; camera as a weak 2nd attractor + 15-25 cm repulsion bubble + a rate-limited fly-by emitter; opaque/masked MESH bees
# (~1.5 cm, dark body, rim-lit blurred wings), emissive glint + twinkle for "firefly"; near meshes / far sprites; fixed seed
# for recordings. Owner domain: Effects sources (Docs/EffectsSourcesDesign.md).
## PASS 1 (offline + read-only; no editor writes): VERIFY and choose the route
V1. DOF on Niagara MESH particles with opaque/masked materials in UE 5.8: declaration-proven from engine headers/shaders under
    D:/Unreal Engine/UE_5.8 (cite file:line), and what translucent particles would need instead.
V2. Velocity output / motion vectors for the Niagara MESH renderer (property name, enum values, default), so TSR + motion blur
    smear fast bees: cite the header.
V3. AUTHORING ROUTE: which is actually scriptable here? (a) Python editing of Niagara emitter stacks/modules (probe the API
    surface in the 5.8 Python stubs or headers: what's BlueprintCallable/exposed); (b) duplicate an engine/plugin Niagara
    template asset and only set exposed user parameters; (c) a C++ swarm simulation (deterministic, unit-testable) that writes
    positions/velocities into a Niagara Array data interface each tick, with Niagara only RENDERING (mesh renderer). Rank them,
    with evidence; recommend one. My prior: (c) or (b)+(c), because behaviour must be tunable and testable without hand graph
    editing, but follow the evidence.
V4. Camera position input: how the swarm reads the live view location (player camera manager in game worlds, editor
    viewport otherwise), cited.
Deliverables this pass: Docs/BeeSwarmDesign_2026-10-02.md (verify results V1-V4 tagged per AGENTS.md, the chosen route, the
parameter list (target wander speed/jump interval, orbit radius range, noise scales, dart rate/strength, drag, max speed,
camera attract weight, repulsion radius, fly-by rate, counts per LOD), and the build plan: sandbox map (NOT the show level) ->
behaviour with debug sprites -> mesh bees + wings + velocity output + DOF test shots at 30/60/200 cm -> camera behaviour ->
S6 placement). If (c): also a HELD C++ patch draft in your worktree with a behaviour unit test (non-repetition: autocorrelation
of a bee's path over 60 s below a threshold; bounds; repulsion never violated) and the git diff in your final message.
No Unreal writes, no build. Commit nothing.
