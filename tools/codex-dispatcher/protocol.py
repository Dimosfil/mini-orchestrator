from __future__ import annotations

from typing import Final


EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "task_created",
        "dispatch_decision",
        "app_server_started",
        "agent_thread_started",
        "handoff",
        "agent_turn_started",
        "codex_notification",
        "agent_started",
        "agent_result",
        "final",
        "error",
    }
)


def validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPES:
        allowed = ", ".join(sorted(EVENT_TYPES))
        raise ValueError(f"Unknown dispatcher event type {event_type!r}. Allowed: {allowed}")
