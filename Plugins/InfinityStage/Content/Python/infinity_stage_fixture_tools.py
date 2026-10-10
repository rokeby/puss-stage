"""Small editor-only fixture helpers exposed through the Puss menu."""

import time

import unreal


def _selected_attachment_passage():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active; Passage fixtures are editor-authoring data")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = []
    for selected in actors.get_selected_level_actors():
        if selected.get_component_by_class(unreal.LightComponentBase) is None:
            continue
        passage = selected.get_attach_parent_actor()
        if not isinstance(passage, unreal.InfinityStagePassageActor):
            continue
        managed = list(passage.get_editor_property("managed_attachment_actors"))
        if selected in managed and passage not in matches:
            matches.append(passage)
    if len(matches) != 1:
        raise RuntimeError(
            "Select exactly one materialized Passage attachment light (found %d Passages)" % len(matches)
        )
    return matches[0]


def rebuild_selected_passage_fixtures():
    """Rebuild fixture ISMs for the selected attachment's Passage; never saves."""
    try:
        passage = _selected_attachment_passage()
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        structures = [
            actor
            for actor in actors.get_all_level_actors()
            if isinstance(actor, unreal.InfinityStageStructureActor)
            and actor.get_editor_property("passage") == passage
        ]
        if not structures:
            raise RuntimeError("No structure actor points at %s" % passage.get_actor_label())

        started = time.perf_counter()
        bodies = 0
        for structure in structures:
            if not structure.rebuild_fixtures_only():
                raise RuntimeError("Fixture-only rebuild failed for %s" % structure.get_actor_label())
            bodies += int(structure.get_editor_property("fixture_body_count"))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        unreal.log(
            "INFINITY_STAGE_FIXTURES_REBUILT passage=%s bodies=%d ms=%.2f"
            % (passage.get_actor_label(), bodies, elapsed_ms)
        )
        return True
    except Exception as exc:
        unreal.log_error("INFINITY_STAGE_FIXTURES_REBUILD_FAILED|%s" % exc)
        return False
