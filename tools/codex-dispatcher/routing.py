from __future__ import annotations

from models import DispatchDecision, OrchestratorChatCommand, Worker


CHAIN_ROLES = ("planner", "executor", "reviewer")

ORCHESTRATOR_CHAT_PREFIXES = (
    "оркестратор",
    "orchestrator",
)

ORCHESTRATOR_ROLE_ALIASES = {
    "план": "planner",
    "планер": "planner",
    "планировщик": "planner",
    "planner": "planner",
    "plan": "planner",
    "исполнитель": "executor",
    "исполнение": "executor",
    "executor": "executor",
    "execute": "executor",
    "exec": "executor",
    "ревью": "reviewer",
    "рецензент": "reviewer",
    "проверка": "reviewer",
    "reviewer": "reviewer",
    "review": "reviewer",
}

PLANNER_TASK_MARKERS = (
    "plan",
    "planner",
    "proposed steps",
    "objective:",
    "next smallest improvement",
    "план",
    "спланируй",
    "планировщик",
)

EXECUTOR_TASK_MARKERS = (
    "implement",
    "fix",
    "patch",
    "edit",
    "change the code",
    "update the code",
    "сделай",
    "реализуй",
    "почини",
    "исправь",
    "измени",
    "обнови",
    "внеси правку",
)

REVIEWER_TASK_MARKERS = (
    "review",
    "code review",
    "find bugs",
    "inspect the diff",
    "verify the implementation",
    "ревью",
    "проверь",
    "найди баги",
    "проверка",
)


def find_worker(workers: list[Worker], role: str) -> Worker:
    for worker in workers:
        if worker.name == role:
            return worker
    available = ", ".join(worker.name for worker in workers)
    raise ValueError(f"Dispatch selected unknown role {role!r}. Available roles: {available}")


def parse_orchestrator_chat_command(task: str) -> OrchestratorChatCommand | None:
    stripped = task.strip()
    if not stripped:
        return None
    parts = stripped.split(maxsplit=2)
    prefix = parts[0].casefold()
    if prefix not in ORCHESTRATOR_CHAT_PREFIXES:
        return None
    if len(parts) == 1:
        return OrchestratorChatCommand(task="")
    second = parts[1].casefold()
    forced_role = ORCHESTRATOR_ROLE_ALIASES.get(second)
    if forced_role:
        next_input = parts[2].strip() if len(parts) > 2 else ""
        return OrchestratorChatCommand(task=next_input, forced_role=forced_role)
    return OrchestratorChatCommand(task=stripped[len(parts[0]):].strip())


def decide_dispatch(task: str, workers: list[Worker]) -> DispatchDecision:
    find_worker(workers, "planner")
    find_worker(workers, "executor")
    find_worker(workers, "reviewer")
    chat_command = parse_orchestrator_chat_command(task)
    if chat_command and chat_command.forced_role:
        find_worker(workers, chat_command.forced_role)
        return DispatchDecision(
            role=chat_command.forced_role,
            reason=f"orchestrator chat command forced {chat_command.forced_role} role",
            confidence=0.95,
            next_input=chat_command.task,
        )
    next_input = chat_command.task if chat_command else task.strip()
    normalized = next_input.casefold()
    if any(marker in normalized for marker in PLANNER_TASK_MARKERS):
        return DispatchDecision(
            role="planner",
            reason="planner-directed task marker matched",
            confidence=0.85,
            next_input=next_input,
        )
    if any(marker in normalized for marker in REVIEWER_TASK_MARKERS):
        return DispatchDecision(
            role="reviewer",
            reason="reviewer-directed task marker matched",
            confidence=0.8,
            next_input=next_input,
        )
    if any(marker in normalized for marker in EXECUTOR_TASK_MARKERS):
        return DispatchDecision(
            role="executor",
            reason="executor-directed task marker matched",
            confidence=0.75,
            next_input=next_input,
        )
    return DispatchDecision(
        role="planner",
        reason="ambiguous request; planner fallback",
        confidence=0.5,
        next_input=next_input,
    )


def ordered_chain_workers(workers: list[Worker]) -> list[Worker]:
    return [find_worker(workers, role) for role in CHAIN_ROLES]
