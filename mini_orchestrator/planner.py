from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import re
from uuid import uuid4

from .llm import LlmRequestError, LlmUnavailable, OpenAiResponsesClient
from .model_defaults import DEFAULT_COORDINATOR_MODEL, DEFAULT_EXECUTOR_MODEL
from .models import PlanResult, TaskAction


def _extract_quoted(fragment: str) -> List[str]:
    pattern = r'"([^"]+)"|\'([^\']+)\'|«([^»]+)»'
    matches = re.findall(pattern, fragment)
    return [match[0] or match[1] or match[2] for match in matches if any(match)]


def _extract_file_from_text(text: str, default_root: Path) -> str:
    parts = re.split(r"\s+", text.strip(), maxsplit=2)
    if len(parts) < 2:
        return str(default_root / "AGENTS.md")
    candidate = parts[1].strip("'\"«»")
    return candidate or str(default_root / "AGENTS.md")


def _extract_command(segment: str) -> str:
    parts = segment.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _segment_goal(goal: str) -> List[str]:
    return [
        segment.strip()
        for segment in re.split(r"\s*;\s*|\s+\bthen\b\s+|\s+\band\b\s+", goal.strip(), flags=re.IGNORECASE)
        if segment.strip()
    ]


def _add_read_action(actions: List[TaskAction], segment: str, workspace_root: Path) -> None:
    path = _extract_file_from_text(segment, workspace_root)
    actions.append(
        TaskAction(
            action_id=str(uuid4()),
            step=len(actions),
            description=f"Read file: {Path(path).name}",
            tool="read_file",
            args={"path": path},
            model=DEFAULT_EXECUTOR_MODEL,
        )
    )


def _add_search_action(actions: List[TaskAction], segment: str, workspace_root: Path) -> None:
    quoted = _extract_quoted(segment)
    _, _, query_part = segment.partition(" ")
    query = quoted[0] if quoted else query_part.strip()
    if not query:
        query = segment
    actions.append(
        TaskAction(
            action_id=str(uuid4()),
            step=len(actions),
            description=f"Search for: {query[:50]}",
            tool="search",
            args={"query": query, "path": str(workspace_root)},
            model=DEFAULT_EXECUTOR_MODEL,
        )
    )


def _add_run_action(actions: List[TaskAction], segment: str) -> None:
    command = _extract_command(segment)
    actions.append(
        TaskAction(
            action_id=str(uuid4()),
            step=len(actions),
            description=f"Run command: {command[:50]}",
            tool="run_command",
            args={"command": command},
            model=DEFAULT_EXECUTOR_MODEL,
        )
    )


def _add_patch_action(actions: List[TaskAction], segment: str, workspace_root: Path) -> None:
    tokens = re.split(r"\s+", segment.strip(), maxsplit=2)
    path = tokens[1] if len(tokens) > 1 else str(workspace_root / "AGENTS.md")
    quoted = _extract_quoted(segment)
    old = quoted[0] if len(quoted) > 0 else ""
    new = quoted[1] if len(quoted) > 1 else ""
    if not old and "->" in segment:
        before, after = segment.split("->", 1)
        old = before.split(maxsplit=1)[-1].strip().strip("'\"«»")
        new = after.strip().strip("'\"«»")
    actions.append(
        TaskAction(
            action_id=str(uuid4()),
            step=len(actions),
            description=f"Patch file: {Path(path).name}",
            tool="apply_patch",
            args={"path": path, "old": old, "new": new},
            model=DEFAULT_EXECUTOR_MODEL,
        )
    )


def _parse_segment(segment: str, workspace_root: Path) -> List[TaskAction]:
    segment = segment.strip()
    lowered = segment.lower()
    actions: List[TaskAction] = []

    if lowered.startswith(("read", "cat", "open", "show")):
        _add_read_action(actions, segment, workspace_root)
    elif lowered.startswith(("search", "find", "grep")):
        _add_search_action(actions, segment, workspace_root)
    elif lowered.startswith(("run", "execute", "command")):
        _add_run_action(actions, segment)
    elif lowered.startswith(("patch", "replace", "apply_patch")):
        _add_patch_action(actions, segment, workspace_root)
    else:
        for token in (" read ", " search ", " find ", " run ", " patch ", " replace "):
            if token.strip() in lowered:
                prefix, _, rest = lowered.partition(token)
                if rest:
                    synthetic = f"{token.strip()} {rest}".strip()
                    actions.extend(_parse_segment(synthetic, workspace_root))
                break

    return actions


def _contains_automation_markers(goal: str) -> bool:
    lowered = f" {goal.strip().lower()} "
    return any(f" {marker} " in lowered for marker in ("read", "search", "find", "patch", "replace", "run", "execute", "cat", "open", "show"))


def _add_response_action(actions: List[TaskAction], message: str, coordinator_model: str) -> None:
    actions.append(
        TaskAction(
            action_id=str(uuid4()),
            step=len(actions),
            description="Respond to user",
            tool="respond",
            args={"message": message},
            model=coordinator_model,
        )
    )


_PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "tool": {
                        "type": "string",
                        "enum": ["respond", "read_file", "search", "run_command", "apply_patch"],
                    },
                    "args": {"type": "object"},
                },
                "required": ["description", "tool", "args"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rationale", "actions"],
    "additionalProperties": False,
}


_SYSTEM_PROMPT = """You are the first coordinator/planner layer of a local mini-orchestrator.
Return one JSON object with keys: rationale and actions.
Do not include Markdown or prose outside JSON.

Allowed tools:
- respond: answer the user directly. Args: {"message": "..."}.
- read_file: read one UTF-8 file in the workspace. Args: {"path": "..."}.
- search: search text in the workspace. Args: {"query": "...", "path": "..."}.
- run_command: run a command only when the user explicitly asks to run a command. Args: {"command": "..."}.
- apply_patch: replace exact text only when the user supplies exact old and new text. Args: {"path": "...", "old": "...", "new": "..."}.

Rules:
- Prefer respond for greetings, explanations, unsupported requests, and general questions.
- Do not invent capabilities. If image generation, browsing, private data access, or GUI control is requested and no tool exists, explain that the current mini-orchestrator layer cannot do it yet.
- Keep actions bounded, local, and reversible.
- Never choose destructive shell commands unless the user explicitly requested that command.
- Use the user's language in respond.message.
"""


def _user_prompt(goal: str, workspace_root: Path) -> str:
    return (
        f"Workspace root: {workspace_root}\n"
        f"User goal:\n{goal}\n\n"
        "Plan the safest next action list for this mini-orchestrator."
    )


def _string_arg(args: Dict[str, Any], name: str, default: str = "") -> str:
    value = args.get(name, default)
    return value if isinstance(value, str) else default


def _normalize_llm_action(
    raw: Dict[str, Any],
    index: int,
    workspace_root: Path,
    coordinator_model: str,
    executor_model: str,
) -> TaskAction | None:
    tool = raw.get("tool")
    if tool not in {"respond", "read_file", "search", "run_command", "apply_patch"}:
        return None

    args = raw.get("args")
    if not isinstance(args, dict):
        args = {}

    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        description = f"{tool} step"

    normalized_args: Dict[str, Any]
    action_model = executor_model
    if tool == "respond":
        message = _string_arg(args, "message").strip()
        if not message:
            return None
        normalized_args = {"message": message}
        action_model = coordinator_model
    elif tool == "read_file":
        path = _string_arg(args, "path").strip()
        if not path:
            return None
        normalized_args = {"path": path}
    elif tool == "search":
        query = _string_arg(args, "query").strip()
        if not query:
            return None
        path = _string_arg(args, "path", str(workspace_root)).strip() or str(workspace_root)
        normalized_args = {"query": query, "path": path}
    elif tool == "run_command":
        command = _string_arg(args, "command").strip()
        if not command:
            return None
        normalized_args = {"command": command}
    else:
        path = _string_arg(args, "path").strip()
        old = _string_arg(args, "old")
        new = _string_arg(args, "new")
        if not path or not old:
            return None
        normalized_args = {"path": path, "old": old, "new": new}

    return TaskAction(
        action_id=str(uuid4()),
        step=index,
        description=description.strip(),
        tool=tool,
        args=normalized_args,
        model=action_model,
    )


@dataclass(frozen=True)
class Planner:
    workspace_root: Path
    coordinator_model: str = DEFAULT_COORDINATOR_MODEL
    executor_model: str = DEFAULT_EXECUTOR_MODEL
    llm_client: OpenAiResponsesClient | None = None

    def plan(self, goal: str) -> PlanResult:
        if self.llm_client and self.llm_client.is_enabled:
            try:
                planned = self._plan_with_llm(goal)
                if planned.actions:
                    return planned
            except LlmUnavailable as exc:
                if self.llm_client.is_required:
                    actions: List[TaskAction] = []
                    _add_response_action(actions, f"LLM coordinator is not configured: {exc}", self.coordinator_model)
                    return PlanResult(actions=actions, rationale="LLM provider is required but unavailable.")
            except LlmRequestError as exc:
                if self.llm_client.is_required:
                    actions = []
                    _add_response_action(actions, f"LLM coordinator request failed: {exc}", self.coordinator_model)
                    return PlanResult(actions=actions, rationale="LLM provider request failed.")

        return self._plan_with_rules(goal)

    def _plan_with_llm(self, goal: str) -> PlanResult:
        if self.llm_client is None:
            raise LlmUnavailable("LLM client is not configured.")

        result = self.llm_client.create_json_plan(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=_user_prompt(goal, self.workspace_root),
            schema=_PLAN_SCHEMA,
        )
        raw_actions = result.payload.get("actions", [])
        if not isinstance(raw_actions, list):
            raw_actions = []

        actions: List[TaskAction] = []
        for raw in raw_actions[:6]:
            if not isinstance(raw, dict):
                continue
            action = _normalize_llm_action(
                raw=raw,
                index=len(actions),
                workspace_root=self.workspace_root,
                coordinator_model=self.coordinator_model,
                executor_model=self.executor_model,
            )
            if action:
                actions.append(action)

        rationale = result.payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            rationale = "LLM coordinator produced a tool plan."

        if not actions:
            _add_response_action(
                actions,
                "The LLM coordinator did not return a safe executable action.",
                self.coordinator_model,
            )
            rationale = "LLM coordinator returned no safe actions."

        for index, action in enumerate(actions):
            action.step = index

        return PlanResult(actions=actions, rationale=rationale)

    def _plan_with_rules(self, goal: str) -> PlanResult:
        actions: List[TaskAction] = []
        for segment in _segment_goal(goal):
            actions.extend(_parse_segment(segment, self.workspace_root))

        if not actions:
            rationale = "No rule-based tool action could be inferred from the request."
            _add_response_action(
                actions,
                "I can run local orchestrator tools for read/search/run/patch tasks. Enable the LLM coordinator with OPENAI_API_KEY for natural-language planning.",
                self.coordinator_model,
            )
            return PlanResult(actions=actions, rationale=rationale)

        if not _contains_automation_markers(goal):
            rationale = "No direct tool action was matched in request."
        else:
            rationale = "Parsed user goal into rule-based tool actions."

        for index, action in enumerate(actions):
            action.step = index

        return PlanResult(actions=actions, rationale=rationale)
