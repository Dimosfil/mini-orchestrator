from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable
import uuid

from codex_app import CodexAppServer
from events import write_event
from models import DispatchDecision, Worker
from prompts import build_chain_prior, build_plan_only_prompt, build_worker_prompt
from routing import decide_dispatch, find_worker, ordered_chain_workers


CodexServerFactory = Callable[..., AbstractContextManager[CodexAppServer]]


def _worker_access_mode(worker: Worker) -> str | None:
    return worker.access_mode or None


def _start_thread(server: CodexAppServer, worker: Worker) -> str:
    access_mode = _worker_access_mode(worker)
    if access_mode:
        return server.start_thread(worker, access_mode=access_mode)
    return server.start_thread(worker)


def _run_turn(server: CodexAppServer, thread_id: str, worker: Worker, prompt: str) -> str:
    access_mode = _worker_access_mode(worker)
    if access_mode:
        return server.run_turn(
            thread_id,
            worker,
            prompt,
            effort=worker.reasoning,
            access_mode=access_mode,
        )
    return server.run_turn(thread_id, worker, prompt, effort=worker.reasoning)


def has_cyrillic(text: str) -> bool:
    return any("\u0400" <= char <= "\u04ff" for char in text)


def task_requests_ui(task: str) -> bool:
    normalized = task.casefold()
    return any(
        marker in normalized
        for marker in (
            "ui",
            "ux",
            "interface",
            "интерфейс",
            "экран",
            "визуал",
            "форм",
            "панел",
        )
    )


def build_chat_approval_plan(task: str) -> str:
    if has_cyrillic(task):
        ui_line = ""
        if task_requests_ui(task):
            ui_line = (
                "3. Описать UI: целевой пользователь, основной экран, ключевые "
                "блоки, состояния, действия и границы MVP.\n"
            )
            next_number = 4
        else:
            next_number = 3
        return (
            f"План для подтверждения: {task}\n\n"
            "1. Уточнить цель, пользователя, основные сценарии и ограничения MVP.\n"
            "2. Описать архитектуру: входы, выходы, состояние, интеграции и ошибки.\n"
            f"{ui_line}"
            f"{next_number}. Разбить работу на bounded executor-шаги с проверками после каждого шага.\n"
            f"{next_number + 1}. Запустить review/smoke и вернуть итог: что сделано, что проверено, что осталось риском.\n\n"
            "Нужно подтверждение: ответь, что подтверждаешь план, и тогда можно запускать approved workflow."
        )

    ui_line = ""
    if task_requests_ui(task):
        ui_line = "3. Describe the UI: target user, primary screen, main regions, states, actions, and MVP boundaries.\n"
        next_number = 4
    else:
        next_number = 3
    return (
        f"Approval plan: {task}\n\n"
        "1. Clarify the goal, user, primary scenarios, and MVP constraints.\n"
        "2. Describe the architecture: inputs, outputs, state, integrations, and failure handling.\n"
        f"{ui_line}"
        f"{next_number}. Split the work into bounded executor steps with verification after each step.\n"
        f"{next_number + 1}. Run review/smoke checks and report what changed, what passed, and what remains risky.\n\n"
        "Approval needed: reply that you approve the plan, then run the approved workflow."
    )


def dry_run(task: str, log_path: Path, workers: list[Worker]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for worker in workers:
        write_event(log_path, "agent_started", agent=worker.name, model=worker.model, dryRun=True)
        output = f"[dry-run:{worker.name}] would process task with model {worker.model}."
        outputs[worker.name] = output
        write_event(log_path, "agent_result", agent=worker.name, output=output, dryRun=True)
    return outputs


def dry_run_chain(task: str, log_path: Path, workers: list[Worker]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for worker in ordered_chain_workers(workers):
        prior = build_chain_prior(outputs)
        prompt = build_worker_prompt(worker, task, prior=prior)
        write_event(log_path, "handoff", to=worker.name, prompt=prompt, dryRun=True)
        write_event(log_path, "agent_started", agent=worker.name, model=worker.model, dryRun=True)
        if worker.name == "planner":
            output = f"[dry-run:planner] would plan task: {task}"
        elif worker.name == "executor":
            output = "[dry-run:executor] would execute the planner output."
        else:
            output = "[dry-run:reviewer] would review the executor output and produce final notes."
        outputs[worker.name] = output
        write_event(log_path, "agent_result", agent=worker.name, output=output, dryRun=True)
    return outputs


def run_pipeline(
    task: str,
    dry: bool,
    workers: list[Worker],
    codex_command: str | None,
    request_timeout_seconds: float,
    turn_timeout_seconds: float,
    use_worker_models: bool,
    *,
    root: Path,
    runs_dir: Path,
    run_id: str | None = None,
    chain: bool = False,
    plan_only: bool = False,
    codex_server_factory: CodexServerFactory = CodexAppServer,
) -> tuple[Path, dict[str, str], DispatchDecision]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    selected_run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    log_path = runs_dir / f"{selected_run_id}.jsonl"
    write_event(
        log_path,
        "task_created",
        task=task,
        dryRun=dry,
        chain=chain,
        planOnly=plan_only,
    )
    decision = decide_dispatch(task, workers)
    selected_worker = find_worker(workers, decision.role)
    write_event(
        log_path,
        "dispatch_decision",
        **asdict(decision),
        dryRun=dry,
        chain=chain,
        planOnly=plan_only,
    )

    if plan_only:
        planner = find_worker(workers, "planner")
        prompt = build_plan_only_prompt(planner, decision.next_input)
        write_event(log_path, "handoff", to=planner.name, prompt=prompt, planOnly=True)
        write_event(log_path, "agent_started", agent=planner.name, model=planner.model, planOnly=True)
        if dry:
            output = build_chat_approval_plan(decision.next_input)
        else:
            with codex_server_factory(
                log_path,
                root=root,
                codex_command=codex_command,
                request_timeout_seconds=request_timeout_seconds,
                turn_timeout_seconds=turn_timeout_seconds,
                use_worker_models=use_worker_models,
            ) as server:
                thread_id = _start_thread(server, planner)
                try:
                    output = _run_turn(server, thread_id, planner, prompt)
                except Exception as exc:
                    write_event(log_path, "error", agent=planner.name, error=str(exc), planOnly=True)
                    raise
        outputs = {"planner": output}
        write_event(log_path, "agent_result", agent=planner.name, output=output, planOnly=True)
        write_event(log_path, "final", outputs=outputs, planOnly=True)
        return log_path, outputs, decision

    if chain:
        if dry:
            outputs = dry_run_chain(decision.next_input, log_path, workers)
            write_event(log_path, "final", outputs=outputs, dryRun=True, chain=True)
            return log_path, outputs, decision

        outputs: dict[str, str] = {}
        with codex_server_factory(
            log_path,
            root=root,
            codex_command=codex_command,
            request_timeout_seconds=request_timeout_seconds,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=use_worker_models,
        ) as server:
            for worker in ordered_chain_workers(workers):
                thread_id = _start_thread(server, worker)
                prior = build_chain_prior(outputs)
                prompt = build_worker_prompt(worker, decision.next_input, prior=prior)
                write_event(log_path, "handoff", to=worker.name, prompt=prompt, chain=True)
                try:
                    output = _run_turn(server, thread_id, worker, prompt)
                except Exception as exc:
                    write_event(log_path, "error", agent=worker.name, error=str(exc), chain=True)
                    raise
                outputs[worker.name] = output
                write_event(log_path, "agent_result", agent=worker.name, output=output, chain=True)

        write_event(log_path, "final", outputs=outputs, chain=True)
        return log_path, outputs, decision

    if dry:
        outputs = dry_run(decision.next_input, log_path, [selected_worker])
        write_event(log_path, "final", outputs=outputs, dryRun=True)
        return log_path, outputs, decision

    outputs: dict[str, str] = {}
    with codex_server_factory(
        log_path,
        root=root,
        codex_command=codex_command,
        request_timeout_seconds=request_timeout_seconds,
        turn_timeout_seconds=turn_timeout_seconds,
        use_worker_models=use_worker_models,
    ) as server:
        thread_id = _start_thread(server, selected_worker)
        prompt = build_worker_prompt(selected_worker, decision.next_input)
        write_event(log_path, "handoff", to=selected_worker.name, prompt=prompt)
        try:
            output = _run_turn(server, thread_id, selected_worker, prompt)
        except Exception as exc:
            write_event(log_path, "error", agent=selected_worker.name, error=str(exc))
            raise
        outputs[selected_worker.name] = output
        write_event(log_path, "agent_result", agent=selected_worker.name, output=output)

    write_event(log_path, "final", outputs=outputs)
    return log_path, outputs, decision
