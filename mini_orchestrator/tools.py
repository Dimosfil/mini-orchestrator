from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Any, Dict

from .config import DEFAULT_ALLOWED_TOOLS, OrchestratorConfig


@dataclass(frozen=True)
class ToolResult:
    tool: str
    success: bool
    output: str
    metadata: Dict[str, Any]
    error: str | None = None


def _is_within_allowed_root(path: Path, allowed_roots: list[Path]) -> bool:
    normalized = path.resolve()
    for root in allowed_roots:
        try:
            normalized.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


class ToolRuntime:
    def __init__(self, config: OrchestratorConfig):
        self.config = config

    @property
    def tool_allowlist(self) -> tuple[str, ...]:
        return DEFAULT_ALLOWED_TOOLS

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        if tool_name not in self.tool_allowlist:
            return ToolResult(
                tool=tool_name,
                success=False,
                output="",
                metadata={},
                error=f"tool '{tool_name}' is not in allowlist {self.tool_allowlist}",
            )

        method = getattr(self, f"_{tool_name}", None)
        if not method:
            return ToolResult(
                tool=tool_name,
                success=False,
                output="",
                metadata={},
                error=f"tool '{tool_name}' is not implemented",
            )
        return method(args or {})

    def _read_file(self, args: Dict[str, Any]) -> ToolResult:
        path = Path(args.get("path", "")).expanduser()
        if not path.is_absolute():
            path = (self.config.workspace_root / path).resolve()
        if not _is_within_allowed_root(path, self.config.allowed_roots):
            return ToolResult(
                tool="read_file",
                success=False,
                output="",
                metadata={},
                error="path is outside allowed workspace roots",
            )
        if not path.exists():
            return ToolResult(
                tool="read_file",
                success=False,
                output="",
                metadata={},
                error="file does not exist",
            )
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(
                tool="read_file",
                success=False,
                output="",
                metadata={},
                error="file is not UTF-8 text",
            )
        limit = self.config.command_output_limit
        return ToolResult(
            tool="read_file",
            success=True,
            output=text[:limit],
            metadata={"path": str(path), "bytes": len(text)},
        )

    def _search(self, args: Dict[str, Any]) -> ToolResult:
        root = Path(args.get("path", self.config.workspace_root)).expanduser().resolve()
        query = str(args.get("query", "")).lower()
        if not query:
            return ToolResult(tool="search", success=False, output="", metadata={}, error="search query is empty")
        if not _is_within_allowed_root(root, self.config.allowed_roots):
            return ToolResult(
                tool="search",
                success=False,
                output="",
                metadata={},
                error="search path is outside allowed workspace roots",
            )
        hits = []
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.name.startswith("."):
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore").lower()
            except UnicodeDecodeError:
                continue
            except OSError:
                continue
            if query in content:
                hits.append(str(candidate))
                if len(hits) >= 20:
                    break
        output = "\n".join(hits)
        return ToolResult(tool="search", success=True, output=output, metadata={"count": len(hits)})

    def _apply_patch(self, args: Dict[str, Any]) -> ToolResult:
        target = args.get("path", "")
        old = args.get("old", "")
        new = args.get("new", "")
        path = Path(target).expanduser()
        if not path.is_absolute():
            path = (self.config.workspace_root / path).resolve()
        if not _is_within_allowed_root(path, self.config.allowed_roots):
            return ToolResult(
                tool="apply_patch",
                success=False,
                output="",
                metadata={},
                error="path is outside allowed workspace roots",
            )
        if not path.exists():
            return ToolResult(
                tool="apply_patch",
                success=False,
                output="",
                metadata={},
                error="file does not exist",
            )
        if not old:
            return ToolResult(
                tool="apply_patch",
                success=False,
                output="",
                metadata={},
                error="missing required 'old' value",
            )
        content = path.read_text(encoding="utf-8")
        if old not in content:
            return ToolResult(
                tool="apply_patch",
                success=False,
                output="",
                metadata={},
                error="old content block was not found",
            )
        updated = content.replace(old, new, 1)
        path.write_text(updated, encoding="utf-8")
        return ToolResult(
            tool="apply_patch",
            success=True,
            output=f"Applied one replacement in {path}",
            metadata={"path": str(path), "replaced": True},
        )

    def _run_command(self, args: Dict[str, Any]) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(tool="run_command", success=False, output="", metadata={}, error="empty command")
        try:
            result: CompletedProcess = run(
                command,
                cwd=str(self.config.workspace_root),
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.command_timeout_seconds,
            )
            out = (result.stdout or "") + (result.stderr or "")
            out = out[: self.config.command_output_limit]
            return ToolResult(
                tool="run_command",
                success=result.returncode == 0,
                output=out,
                metadata={"returncode": result.returncode},
                error=None if result.returncode == 0 else f"command failed with {result.returncode}",
            )
        except Exception as exc:
            return ToolResult(
                tool="run_command",
                success=False,
                output="",
                metadata={},
                error=f"command execution error: {exc}",
            )

    def _respond(self, args: Dict[str, Any]) -> ToolResult:
        message = str(args.get("message", "")).strip()
        if not message:
            return ToolResult(tool="respond", success=False, output="", metadata={}, error="empty response")
        return ToolResult(
            tool="respond",
            success=True,
            output=message[: self.config.command_output_limit],
            metadata={"kind": "direct_response"},
        )
