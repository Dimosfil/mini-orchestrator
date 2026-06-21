from __future__ import annotations

from models import Worker


GENERATED_ARTIFACT_POLICY = """Generated project artifact policy:
- For generated applications, demos, release prototypes, CRM builds, calculators, or other runnable results, do not modify an existing unrelated app folder such as launch-desk unless the user explicitly names that folder as the target.
- Create a separate project-named, versioned artifact folder under .mini_orchestrator/test-runs/<task-slug>/<version>/, for example .mini_orchestrator/test-runs/dental-crm/v001/.
- Keep every repeat run isolated. Do not overwrite older result folders, and do not update a stable latest copy unless the user explicitly asks for it.
- The artifact folder must be self-contained enough to inspect later and include a short README or manifest with the original task, run date, entry point, and verification notes.
- Before editing, state the selected artifact path. Reviewer must treat writing into a legacy/experimental or unrelated project folder as a finding unless the user explicitly approved that target."""


def read_instructions(worker: Worker) -> str:
    if worker.instructions_text:
        return worker.instructions_text
    return worker.instructions_path.read_text(encoding="utf-8")


def build_worker_prompt(worker: Worker, task: str, prior: str = "") -> str:
    instructions = read_instructions(worker)
    return (
        f"Worker role: {worker.name}\n\n"
        f"Role configuration:\n{instructions}\n\n"
        f"{GENERATED_ARTIFACT_POLICY}\n\n"
        f"Current task:\n{task}\n\n"
        f"Prior context:\n{prior or 'none'}\n\n"
        "Return only the result needed by the dispatcher."
    )


def build_plan_only_prompt(planner: Worker, task: str) -> str:
    instructions = read_instructions(planner)
    return (
        "Prepare a chat approval plan without editing files, running commands, "
        "or creating project files.\n\n"
        f"Worker role: {planner.name}\n\n"
        f"Role configuration:\n{instructions}\n\n"
        f"{GENERATED_ARTIFACT_POLICY}\n\n"
        f"User task:\n{task}\n\n"
        "Return a task-specific planner proposal for user approval. Include the "
        "objective, proposed steps, key UI/UX notes when the user asks for UI, "
        "the generated artifact folder convention, risks or assumptions, executor handoff, reviewer checklist, and a short "
        "approval sentence. Do not reuse a generic template when the task gives "
        "domain details."
    )


def build_chain_prior(outputs: dict[str, str]) -> str:
    if not outputs:
        return ""
    sections = []
    for role, output in outputs.items():
        if output:
            sections.append(f"{role} output:\n{output}")
    return "\n\n".join(sections)
