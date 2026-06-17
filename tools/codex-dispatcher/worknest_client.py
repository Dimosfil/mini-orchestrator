from __future__ import annotations

from worknest import WorkNestClient, WorkNestTask


def load_worknest_task(project: str, config_service_url: str | None) -> WorkNestTask:
    client = WorkNestClient(config_service_url=config_service_url)
    contract = client.contract()
    if "task-completion" not in set(client.service.get("capabilities", [])):
        raise RuntimeError("Configured task manager does not advertise task-completion capability.")
    if "next-task" not in " ".join(contract.get("taskMovementPolicy", {}).get("externalAgents", [])):
        raise RuntimeError("Task manager contract does not document next-task workflow.")
    task = client.next_task(project)
    if task is None:
        raise RuntimeError(f"No available WorkNest task for project {project!r}.")
    return task
