from __future__ import annotations

import os


DEFAULT_COORDINATOR_MODEL = "gpt-5.5"
DEFAULT_EXECUTOR_MODEL = "gpt-5.3-codex-spark"
DEFAULT_TRANSLATION_MODEL = "gpt-4.1-mini"
DEFAULT_VISUAL_AGENT_MODEL = "gpt-5.4"
DEFAULT_VISUAL_TRANSLATION_MODEL = "gpt-5.4-mini"
DEFAULT_CAMPAIGN_IMAGE_MODEL = "gpt-image-2"


def env_model(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def coordinator_model() -> str:
    return env_model("MINI_ORCHESTRATOR_COORDINATOR_MODEL", DEFAULT_COORDINATOR_MODEL)


def executor_model() -> str:
    return env_model("MINI_ORCHESTRATOR_EXECUTOR_MODEL", DEFAULT_EXECUTOR_MODEL)


def reviewer_model() -> str:
    return env_model("MINI_ORCHESTRATOR_REVIEWER_MODEL", coordinator_model())
