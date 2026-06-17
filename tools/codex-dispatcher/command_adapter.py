from __future__ import annotations

import subprocess
from pathlib import Path

from models import CommandResult


def run_command(command: list[str], cwd: Path, timeout_seconds: float = 15) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return CommandResult(
        command=command,
        cwd=cwd,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


def render_command_result(result: CommandResult) -> str:
    command = " ".join(result.command)
    parts = [f"{command} (exit {result.exit_code})"]
    if result.stdout:
        parts.append(f"stdout:\n{result.stdout}")
    if result.stderr:
        parts.append(f"stderr:\n{result.stderr}")
    return "\n".join(parts)
