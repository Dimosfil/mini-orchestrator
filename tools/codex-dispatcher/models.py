from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Worker:
    name: str
    model: str
    reasoning: str
    instructions_path: Path


@dataclass(frozen=True)
class DispatchDecision:
    role: str
    reason: str
    confidence: float
    next_input: str


@dataclass(frozen=True)
class OrchestratorChatCommand:
    task: str
    forced_role: str | None = None


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
