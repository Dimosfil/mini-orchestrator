from __future__ import annotations

from models import Worker
from routing import CHAIN_ROLES


def read_instructions(worker: Worker) -> str:
    return worker.instructions_path.read_text(encoding="utf-8")


def build_worker_prompt(worker: Worker, task: str, prior: str = "") -> str:
    instructions = read_instructions(worker)
    return (
        f"Worker role: {worker.name}\n\n"
        f"Role configuration:\n{instructions}\n\n"
        f"Current task:\n{task}\n\n"
        f"Prior context:\n{prior or 'none'}\n\n"
        "Return only the result needed by the dispatcher."
    )


def build_plan_only_prompt(planner: Worker, task: str) -> str:
    instructions = read_instructions(planner)
    return (
        "Prepare a chat approval plan without editing files, running commands, "
        "or creating a local demo project.\n\n"
        f"Worker role: {planner.name}\n\n"
        f"Role configuration:\n{instructions}\n\n"
        f"User task:\n{task}\n\n"
        "Return a task-specific planner proposal for user approval. Include the "
        "objective, proposed steps, key UI/UX notes when the user asks for UI, "
        "risks or assumptions, executor handoff, reviewer checklist, and a short "
        "approval sentence. Do not reuse a generic template when the task gives "
        "domain details."
    )


def build_chain_prior(outputs: dict[str, str]) -> str:
    if not outputs:
        return ""
    sections = []
    for role in CHAIN_ROLES:
        output = outputs.get(role)
        if output:
            sections.append(f"{role} output:\n{output}")
    return "\n\n".join(sections)
