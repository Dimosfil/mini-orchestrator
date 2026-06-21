from __future__ import annotations

import pytest

from mini_orchestrator import runtime_store
from mini_orchestrator.agent_profiles import (
    AgentProfileError,
    DEFAULT_PROJECT_BUILDER_CARD_ID,
    DEFAULT_PROJECT_BUILDER_TASK,
    compile_worker_profile,
    default_project_builder_agent_card,
    load_or_create_default_agent_card,
    persist_agent_card,
    visual_agent_task_prompt,
)


def test_default_project_builder_card_persists_and_compiles(tmp_path) -> None:
    card = default_project_builder_agent_card(tmp_path)

    persisted = persist_agent_card(card, tmp_path)
    loaded = load_or_create_default_agent_card(tmp_path)
    profile = compile_worker_profile(loaded, DEFAULT_PROJECT_BUILDER_TASK, tmp_path)

    assert persisted["card"]["id"] == DEFAULT_PROJECT_BUILDER_CARD_ID
    assert loaded["name"] == "Project Builder"
    assert profile["sourceCardId"] == DEFAULT_PROJECT_BUILDER_CARD_ID
    assert profile["runtime"]["worker"] == "visual-agent"
    assert profile["runtime"]["accessMode"] == "workspace-write"
    assert "project artifact requested by the user" in visual_agent_task_prompt(profile)

    stored_card = runtime_store.get_json_document(tmp_path, "agent_cards", DEFAULT_PROJECT_BUILDER_CARD_ID)
    stored_profile = runtime_store.get_json_document(tmp_path, "worker_profiles", profile["snapshotId"])
    assert stored_card and stored_card["card"]["name"] == "Project Builder"
    assert stored_profile and stored_profile["snapshotId"] == profile["snapshotId"]


def test_compile_rejects_rules_agent(tmp_path) -> None:
    card = default_project_builder_agent_card(tmp_path)
    card["llm"] = "rules"

    with pytest.raises(AgentProfileError) as exc_info:
        compile_worker_profile(card, DEFAULT_PROJECT_BUILDER_TASK, tmp_path)

    assert "rules" in str(exc_info.value)
