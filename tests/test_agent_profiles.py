from __future__ import annotations

import json

import pytest

from mini_orchestrator.agent_profiles import (
    AgentProfileError,
    DEFAULT_DENTAL_CRM_CARD_ID,
    DEFAULT_DENTAL_CRM_TASK,
    compile_worker_profile,
    default_dental_crm_agent_card,
    load_or_create_default_agent_card,
    persist_agent_card,
    visual_agent_task_prompt,
)


def test_default_dental_crm_card_persists_and_compiles(tmp_path) -> None:
    card = default_dental_crm_agent_card(tmp_path)

    persisted = persist_agent_card(card, tmp_path)
    loaded = load_or_create_default_agent_card(tmp_path)
    profile = compile_worker_profile(loaded, DEFAULT_DENTAL_CRM_TASK, tmp_path)

    assert persisted["card"]["id"] == DEFAULT_DENTAL_CRM_CARD_ID
    assert loaded["name"] == "Dental CRM Builder"
    assert profile["sourceCardId"] == DEFAULT_DENTAL_CRM_CARD_ID
    assert profile["runtime"]["worker"] == "visual-agent"
    assert profile["runtime"]["accessMode"] == "workspace-write"
    assert "dental CRM demo" in visual_agent_task_prompt(profile)

    card_path = tmp_path / ".mini_orchestrator" / "agent-cards" / f"{DEFAULT_DENTAL_CRM_CARD_ID}.json"
    profile_path = tmp_path / profile["path"]
    assert json.loads(card_path.read_text(encoding="utf-8"))["card"]["name"] == "Dental CRM Builder"
    assert json.loads(profile_path.read_text(encoding="utf-8"))["snapshotId"] == profile["snapshotId"]


def test_compile_rejects_rules_agent(tmp_path) -> None:
    card = default_dental_crm_agent_card(tmp_path)
    card["llm"] = "rules"

    with pytest.raises(AgentProfileError) as exc_info:
        compile_worker_profile(card, DEFAULT_DENTAL_CRM_TASK, tmp_path)

    assert "rules" in str(exc_info.value)
