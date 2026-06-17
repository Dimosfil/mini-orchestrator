from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List
import os


DEFAULT_ALLOWED_TOOLS = ("read_file", "search", "apply_patch", "run_command", "respond")


@dataclass(frozen=True)
class OrchestratorConfig:
    workspace_root: Path
    allowed_roots: List[Path]
    max_iterations: int = 12
    max_retries: int = 3
    command_timeout_seconds: int = 20
    command_output_limit: int = 12000
    llm_provider: str = "auto"
    coordinator_model: str = "gpt-5.5"
    executor_model: str = "gpt-5.3-codex-spark"
    translation_model: str = "gpt-4.1-mini"
    campaign_text_model: str = "gpt-5.5"
    campaign_image_model: str = "gpt-image-2"
    campaign_image_size: str = "1024x1024"
    campaign_image_quality: str = "medium"
    campaign_image_count: int = 3
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key_env: str = "OPENAI_API_KEY"
    llm_timeout_seconds: int = 30


def parse_runtime_config(
    workdir: str,
    max_iterations: int | None,
    max_retries: int | None,
    llm_provider: str | None = None,
    coordinator_model: str | None = None,
    executor_model: str | None = None,
    openai_base_url: str | None = None,
) -> OrchestratorConfig:
    root = Path(workdir).resolve()
    explicit_roots = os.environ.get("MINI_ORCHESTRATOR_ALLOWED_ROOTS", "")
    additional_roots = [
        Path(entry.strip()).resolve()
        for entry in explicit_roots.split(";")
        if entry.strip()
    ]
    allowed_roots = [root] + [item for item in additional_roots if item not in (None, root)]
    return OrchestratorConfig(
        workspace_root=root,
        allowed_roots=allowed_roots,
        max_iterations=max_iterations or int(os.environ.get("MINI_ORCHESTRATOR_MAX_ITERATIONS", 12)),
        max_retries=max_retries or int(os.environ.get("MINI_ORCHESTRATOR_MAX_RETRIES", 3)),
        command_timeout_seconds=int(os.environ.get("MINI_ORCHESTRATOR_COMMAND_TIMEOUT_SECONDS", 20)),
        command_output_limit=int(os.environ.get("MINI_ORCHESTRATOR_COMMAND_OUTPUT_LIMIT", 12000)),
        llm_provider=(llm_provider or os.environ.get("MINI_ORCHESTRATOR_LLM_PROVIDER", "auto")).strip().lower(),
        coordinator_model=coordinator_model
        or os.environ.get("MINI_ORCHESTRATOR_COORDINATOR_MODEL", "gpt-5.5"),
        executor_model=executor_model
        or os.environ.get("MINI_ORCHESTRATOR_EXECUTOR_MODEL", "gpt-5.3-codex-spark"),
        translation_model=os.environ.get("MINI_ORCHESTRATOR_TRANSLATION_MODEL", "gpt-4.1-mini"),
        campaign_text_model=os.environ.get("MINI_ORCHESTRATOR_CAMPAIGN_TEXT_MODEL", "gpt-5.5"),
        campaign_image_model=os.environ.get("MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_MODEL", "gpt-image-2"),
        campaign_image_size=os.environ.get("MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_SIZE", "1024x1024"),
        campaign_image_quality=os.environ.get("MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_QUALITY", "medium"),
        campaign_image_count=max(1, int(os.environ.get("MINI_ORCHESTRATOR_CAMPAIGN_IMAGE_COUNT", "3"))),
        openai_base_url=(openai_base_url or os.environ.get("MINI_ORCHESTRATOR_OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/"),
        openai_api_key_env=os.environ.get("MINI_ORCHESTRATOR_OPENAI_API_KEY_ENV", "OPENAI_API_KEY"),
        llm_timeout_seconds=int(os.environ.get("MINI_ORCHESTRATOR_LLM_TIMEOUT_SECONDS", 30)),
    )
