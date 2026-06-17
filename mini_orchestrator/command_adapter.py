from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandExecutionResult:
    command: list[str]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str


DESTRUCTIVE_COMMAND_MARKERS = (
    "rm",
    "del",
    "erase",
    "rmdir",
    "remove-item",
    "rd",
    "format",
    "shutdown",
    "git reset",
    "git clean",
    "git checkout",
)


def split_command(command: str) -> list[str]:
    if os.name == "nt":
        return shlex.split(command, posix=False)
    return shlex.split(command)


def validate_command(command: str) -> str | None:
    normalized = " ".join(command.casefold().split())
    if not normalized:
        return "empty command"
    for marker in DESTRUCTIVE_COMMAND_MARKERS:
        if normalized == marker or normalized.startswith(marker + " "):
            return f"blocked potentially destructive command: {marker}"
    return None


def run_command_argv(
    command: str | list[str],
    cwd: Path,
    timeout_seconds: float,
    output_limit: int,
) -> CommandExecutionResult:
    if isinstance(command, str):
        blocker = validate_command(command)
        if blocker:
            raise ValueError(blocker)
        argv = split_command(command)
    else:
        argv = [str(part) for part in command]
        blocker = validate_command(" ".join(argv))
        if blocker:
            raise ValueError(blocker)
    if not argv:
        raise ValueError("empty command")

    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return CommandExecutionResult(
        command=argv,
        cwd=cwd,
        exit_code=completed.returncode,
        stdout=(completed.stdout or "")[:output_limit],
        stderr=(completed.stderr or "")[:output_limit],
    )
