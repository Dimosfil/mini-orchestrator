from __future__ import annotations

import argparse
from collections import deque
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from command_adapter import render_command_result as adapter_render_command_result
from command_adapter import run_command as adapter_run_command
from events import utc_now as event_utc_now
from events import write_event as event_write_event
from models import CommandResult as DispatcherCommandResult
from models import DispatchDecision as DispatcherDispatchDecision
from models import OrchestratorChatCommand as DispatcherOrchestratorChatCommand
from models import Worker as DispatcherWorker
from prompts import build_chain_prior as prompts_build_chain_prior
from prompts import build_plan_only_prompt as prompts_build_plan_only_prompt
from prompts import build_worker_prompt as prompts_build_worker_prompt
from prompts import read_instructions as prompts_read_instructions
from routing import decide_dispatch as routing_decide_dispatch
from routing import find_worker as routing_find_worker
from routing import ordered_chain_workers as routing_ordered_chain_workers
from routing import parse_orchestrator_chat_command as routing_parse_orchestrator_chat_command
from worknest import WorkNestClient, WorkNestTask


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = Path(__file__).resolve().parent / "runs"
DEFAULT_TEST_PROJECTS_DIR = ROOT / "test-projects"
DEMO_MARKER_NAME = ".mini-orchestrator-demo.json"


Worker = DispatcherWorker
DispatchDecision = DispatcherDispatchDecision
OrchestratorChatCommand = DispatcherOrchestratorChatCommand
CommandResult = DispatcherCommandResult


WORKERS = [
    Worker("planner", "gpt-5.5", "high", ROOT / ".codex" / "agents" / "planner.toml"),
    Worker("executor", "gpt-5.4", "medium", ROOT / ".codex" / "agents" / "executor.toml"),
    Worker("reviewer", "gpt-5.4-mini", "high", ROOT / ".codex" / "agents" / "reviewer.toml"),
]

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


def utc_now() -> str:
    return event_utc_now()


def write_event(log_path: Path, event_type: str, **payload: Any) -> None:
    event_write_event(log_path, event_type, **payload)


def print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


MOJIBAKE_MARKERS = (
    "Рђ",
    "Рџ",
    "РЎ",
    "Рќ",
    "Рё",
    "Рµ",
    "СЃ",
    "С‚",
    "вЂ",
    "в„",
    "Â",
)


def mojibake_score(text: str) -> int:
    return (text.count("\ufffd") * 8) + sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def repair_text_encoding(text: str) -> str:
    if not text:
        return text

    best = text
    best_score = mojibake_score(text)
    for source_encoding in ("cp1251", "latin1"):
        try:
            candidate = text.encode(source_encoding).decode("utf-8")
        except UnicodeError:
            continue
        score = mojibake_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score
    return best


def read_instructions(worker: Worker) -> str:
    return prompts_read_instructions(worker)


def find_worker(workers: list[Worker], role: str) -> Worker:
    return routing_find_worker(workers, role)


def parse_orchestrator_chat_command(task: str) -> OrchestratorChatCommand | None:
    return routing_parse_orchestrator_chat_command(task)


def decide_dispatch(task: str, workers: list[Worker]) -> DispatchDecision:
    return routing_decide_dispatch(task, workers)


def resolve_codex_command() -> str:
    configured = os.environ.get("CODEX_COMMAND")
    if configured:
        return configured
    if os.name == "nt":
        cmd = shutil.which("codex.cmd")
        if cmd:
            return cmd
    return shutil.which("codex") or "codex"


class CodexAppServer:
    def __init__(
        self,
        log_path: Path,
        codex_command: str | None = None,
        request_timeout_seconds: float = 30,
        turn_timeout_seconds: float = 90,
        use_worker_models: bool = False,
    ) -> None:
        self.log_path = log_path
        self.codex_command = codex_command
        self.request_timeout_seconds = request_timeout_seconds
        self.turn_timeout_seconds = turn_timeout_seconds
        self.use_worker_models = use_worker_models
        self.proc: subprocess.Popen[str] | None = None
        self.next_id = 1
        self.stdout_lines: queue.Queue[str] = queue.Queue()
        self.stderr_lines: deque[str] = deque(maxlen=80)
        self.stdout_thread: threading.Thread | None = None
        self.stderr_thread: threading.Thread | None = None

    def __enter__(self) -> "CodexAppServer":
        self.proc = subprocess.Popen(
            [self.codex_command or resolve_codex_command(), "app-server"],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.stdout_thread = threading.Thread(target=self.read_stdout, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
        self.stderr_thread.start()
        self.request("initialize", {
            "clientInfo": {
                "name": "mini_orchestrator_codex_dispatcher",
                "title": "Mini Orchestrator Codex Dispatcher",
                "version": "0.1.0",
            },
            "capabilities": {
                "experimentalApi": True,
                "requestAttestation": False,
                "optOutNotificationMethods": [
                    "command/exec/outputDelta",
                    "item/agentMessage/delta",
                    "item/plan/delta",
                    "item/fileChange/outputDelta",
                    "item/reasoning/summaryTextDelta",
                    "item/reasoning/textDelta",
                ],
            },
        })
        self.notify("initialized", {})
        write_event(self.log_path, "app_server_started")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def read_stdout(self) -> None:
        if not self.proc or not self.proc.stdout:
            return
        for line in self.proc.stdout:
            self.stdout_lines.put(line)

    def read_stderr(self) -> None:
        if not self.proc or not self.proc.stderr:
            return
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip())

    def send(self, message: dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("Codex app-server is not running.")
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self.send({"method": method, "params": params})

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self.send({"method": method, "id": request_id, "params": params})
        return self.wait_for_response(request_id)

    def stderr_tail(self) -> str:
        return "\n".join(self.stderr_lines)

    def read_message(self, timeout_seconds: float, context: str) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out after {timeout_seconds:.0f}s while waiting for {context}.")
            try:
                line = self.stdout_lines.get(timeout=min(0.25, remaining))
            except queue.Empty:
                if self.proc and self.proc.poll() is not None:
                    stderr = self.stderr_tail()
                    detail = f" Stderr: {stderr}" if stderr else ""
                    raise RuntimeError(f"Codex app-server exited while waiting for {context}.{detail}")
                continue
            return json.loads(line)

    def wait_for_response(self, request_id: int) -> dict[str, Any]:
        while True:
            message = self.read_message(self.request_timeout_seconds, f"response {request_id}")
            if "method" in message:
                write_event(self.log_path, "codex_notification", message=message)
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"Codex request failed: {message['error']}")
                return message["result"]

    def start_thread(self, worker: Worker) -> str:
        result = self.request("thread/start", {
            "model": worker.model if self.use_worker_models else None,
            "modelProvider": None,
            "cwd": None,
            "runtimeWorkspaceRoots": None,
            "approvalPolicy": None,
            "approvalsReviewer": None,
            "sandbox": None,
            "permissions": None,
            "config": None,
            "serviceName": None,
            "baseInstructions": None,
            "developerInstructions": None,
            "personality": None,
            "ephemeral": None,
            "sessionStartSource": None,
            "threadSource": None,
            "environments": None,
            "dynamicTools": None,
            "selectedCapabilityRoots": None,
            "mockExperimentalField": None,
        })
        thread_id = result["thread"]["id"]
        write_event(self.log_path, "agent_thread_started", agent=worker.name, model=result.get("model", worker.model), threadId=thread_id)
        return thread_id

    def run_turn(self, thread_id: str, worker: Worker, prompt: str) -> str:
        result = self.request("turn/start", {
            "threadId": thread_id,
            "clientUserMessageId": None,
            "input": [{"type": "text", "text": prompt, "text_elements": []}],
            "responsesapiClientMetadata": None,
            "additionalContext": None,
            "environments": None,
            "cwd": None,
            "runtimeWorkspaceRoots": None,
            "approvalPolicy": None,
            "approvalsReviewer": None,
            "sandboxPolicy": None,
            "permissions": None,
            "model": None,
            "effort": None,
            "summary": None,
            "personality": None,
            "outputSchema": None,
            "collaborationMode": None,
        })
        turn_id = result.get("turn", {}).get("id")
        write_event(self.log_path, "agent_turn_started", agent=worker.name, threadId=thread_id, turnId=turn_id)
        return self.collect_final_response(turn_id)

    def collect_final_response(self, turn_id: str | None) -> str:
        chunks: list[str] = []
        while True:
            message = self.read_message(self.turn_timeout_seconds, "turn completion")
            method = message.get("method")
            params = message.get("params", {})
            write_event(self.log_path, "codex_notification", message=message)
            if method == "item/agentMessage/delta":
                delta = params.get("delta") or params.get("text") or ""
                if isinstance(delta, str):
                    chunks.append(delta)
            if method == "item/completed":
                item = params.get("item", {})
                if item.get("type") == "agentMessage":
                    text = item.get("text", "")
                    if isinstance(text, str):
                        chunks.append(text)
            if method == "turn/completed":
                if not turn_id or params.get("turn", {}).get("id") == turn_id:
                    return repair_text_encoding("".join(chunks).strip())


def build_worker_prompt(worker: Worker, task: str, prior: str = "") -> str:
    return prompts_build_worker_prompt(worker, task, prior=prior)


def build_plan_only_prompt(planner: Worker, task: str) -> str:
    return prompts_build_plan_only_prompt(planner, task)


def build_chain_prior(outputs: dict[str, str]) -> str:
    return prompts_build_chain_prior(outputs)


def ordered_chain_workers(workers: list[Worker]) -> list[Worker]:
    return routing_ordered_chain_workers(workers)


def path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_test_projects_root(test_projects_dir: Path | None = None) -> Path:
    configured = test_projects_dir or DEFAULT_TEST_PROJECTS_DIR
    candidate = configured if configured.is_absolute() else ROOT / configured
    resolved = candidate.resolve()
    if not path_is_inside(resolved, ROOT):
        raise ValueError(f"Test projects directory must stay inside {ROOT}. Got: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


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
            "\u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441",
            "\u044d\u043a\u0440\u0430\u043d",
            "\u0432\u0438\u0437\u0443\u0430\u043b",
            "\u0444\u043e\u0440\u043c",
            "\u043f\u0430\u043d\u0435\u043b",
        )
    )


def local_demo_project_name(task: str) -> str | None:
    normalized = task.casefold()
    if "calculator" in normalized or "\u043a\u0430\u043b\u044c\u043a" in normalized:
        return "calculator"
    crm_markers = ("crm", "\u0441\u0440\u043c")
    construction_markers = (
        "construction",
        "building store",
        "hardware store",
        "\u0441\u0442\u0440\u043e\u0439",
        "\u0441\u0442\u0440\u043e\u0438\u0442",
    )
    if any(marker in normalized for marker in crm_markers) and any(
        marker in normalized for marker in construction_markers
    ):
        return "construction-crm"
    return None


def select_local_demo_project(task: str) -> str:
    project_name = local_demo_project_name(task)
    if project_name:
        return project_name
    raise RuntimeError(
        "Local test project mode currently supports only calculator and construction-store CRM tasks."
    )


def build_local_test_project_plan(task: str) -> str:
    project_name = select_local_demo_project(task)
    project_path = DEFAULT_TEST_PROJECTS_DIR / project_name
    if project_name == "construction-crm":
        return (
            f"Plan for approved local demo project: {task}\n\n"
            f"1. Create managed project folder `{project_path.relative_to(ROOT)}`.\n"
            "2. Add a small construction-store CRM with clients, products, stock, deals, orders, and statuses.\n"
            "3. Add unit tests for search, stock reservation, totals, low-stock warnings, and status validation.\n"
            "4. Run executor -> test/review iterations until checks pass or the iteration limit is reached.\n"
            "5. After a clean review, run the CRM smoke command as the application launch check.\n\n"
            "Approval needed: reply that you approve the plan, then run the approved local workflow."
        )
    if any("\u0400" <= char <= "\u04ff" for char in task):
        return (
            f"План для подтвержденного локального демо-проекта: {task}\n\n"
            f"1. Создать управляемую папку `{project_path.relative_to(ROOT)}`.\n"
            "2. Добавить маленький Python CLI калькулятор: сложение, вычитание, умножение и деление.\n"
            "3. Добавить unit-тесты для всех операций и деления на ноль.\n"
            "4. Запустить цикл executor -> test/review до чистых проверок или лимита итераций.\n"
            "5. После чистого review выполнить запуск/smoke приложения.\n\n"
            "Нужно подтверждение: ответь, что подтверждаешь план, после этого можно запускать approved workflow."
        )
    return (
        f"Plan for approved local demo project: {task}\n\n"
        f"1. Create managed project folder `{project_path.relative_to(ROOT)}`.\n"
        "2. Add a small Python CLI calculator with add, subtract, multiply, and divide.\n"
        "3. Add unit tests for all operations and division-by-zero handling.\n"
        "4. Run executor -> test/review iterations until checks pass or the iteration limit is reached.\n"
        "5. After a clean review, run the calculator as the application launch smoke check.\n\n"
        "Approval needed: reply that you approve the plan, then run the approved local workflow."
    )


def build_generic_chat_approval_plan(task: str) -> str:
    if has_cyrillic(task):
        ui_line = ""
        if task_requests_ui(task):
            ui_line = (
                "3. \u041e\u043f\u0438\u0441\u0430\u0442\u044c UI: \u0446\u0435\u043b\u0435\u0432\u043e\u0439 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c, "
                "\u043e\u0441\u043d\u043e\u0432\u043d\u043e\u0439 \u044d\u043a\u0440\u0430\u043d, \u043a\u043b\u044e\u0447\u0435\u0432\u044b\u0435 \u0431\u043b\u043e\u043a\u0438, \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u044f, \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f "
                "\u0438 \u0433\u0440\u0430\u043d\u0438\u0446\u044b MVP.\n"
            )
            next_number = 4
        else:
            next_number = 3
        return (
            f"\u041f\u043b\u0430\u043d \u0434\u043b\u044f \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f: {task}\n\n"
            "1. \u0423\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u0446\u0435\u043b\u044c, \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f, \u043e\u0441\u043d\u043e\u0432\u043d\u044b\u0435 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0438 \u0438 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u044f MVP.\n"
            "2. \u041e\u043f\u0438\u0441\u0430\u0442\u044c \u0430\u0440\u0445\u0438\u0442\u0435\u043a\u0442\u0443\u0440\u0443: \u0432\u0445\u043e\u0434\u044b, \u0432\u044b\u0445\u043e\u0434\u044b, \u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435 \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u044f, \u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u0438 \u0438 \u043e\u0448\u0438\u0431\u043a\u0438.\n"
            f"{ui_line}"
            f"{next_number}. \u0420\u0430\u0437\u0431\u0438\u0442\u044c \u0440\u0430\u0431\u043e\u0442\u0443 \u043d\u0430 bounded executor-\u0448\u0430\u0433\u0438 \u0441 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430\u043c\u0438 \u043f\u043e\u0441\u043b\u0435 \u043a\u0430\u0436\u0434\u043e\u0433\u043e \u0448\u0430\u0433\u0430.\n"
            f"{next_number + 1}. \u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c review/smoke \u0438 \u0432\u0435\u0440\u043d\u0443\u0442\u044c \u0438\u0442\u043e\u0433: \u0447\u0442\u043e \u0441\u0434\u0435\u043b\u0430\u043d\u043e, \u0447\u0442\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e, \u0447\u0442\u043e \u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c \u0440\u0438\u0441\u043a\u043e\u043c.\n\n"
            "\u041d\u0443\u0436\u043d\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435: \u043e\u0442\u0432\u0435\u0442\u044c, \u0447\u0442\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0435\u0448\u044c \u043f\u043b\u0430\u043d, \u0438 \u0442\u043e\u0433\u0434\u0430 \u043c\u043e\u0436\u043d\u043e \u0437\u0430\u043f\u0443\u0441\u043a\u0430\u0442\u044c approved workflow."
        )

    ui_line = ""
    if task_requests_ui(task):
        ui_line = (
            "3. Describe the UI: target user, primary screen, main regions, states, actions, and MVP boundaries.\n"
        )
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


def build_chat_approval_plan(task: str) -> str:
    if local_demo_project_name(task) and not task_requests_ui(task):
        return build_local_test_project_plan(task)
    return build_generic_chat_approval_plan(task)


def write_text_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except UnicodeDecodeError:
            pass
    path.write_text(content, encoding="utf-8")
    return True


def prepare_demo_project_dir(test_projects_root: Path, project_name: str) -> Path:
    project_path = (test_projects_root / project_name).resolve()
    if not path_is_inside(project_path, test_projects_root):
        raise ValueError(f"Demo project path escaped test projects root: {project_path}")

    marker_path = project_path / DEMO_MARKER_NAME
    if project_path.exists() and not marker_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing non-demo project directory: {project_path}"
        )

    project_path.mkdir(parents=True, exist_ok=True)
    if not marker_path.exists():
        marker = {
            "managedBy": "mini-orchestrator",
            "project": project_name,
            "generatedAt": utc_now(),
        }
        write_text_if_changed(marker_path, json.dumps(marker, ensure_ascii=False, indent=2) + "\n")
    return project_path


def calculator_project_files() -> dict[str, str]:
    return {
        "calculator.py": '''from __future__ import annotations

import argparse


def add(left: float, right: float) -> float:
    return left + right


def subtract(left: float, right: float) -> float:
    return left - right


def multiply(left: float, right: float) -> float:
    return left * right


def divide(left: float, right: float) -> float:
    if right == 0:
        raise ValueError("division by zero is not allowed")
    return left / right


OPERATIONS = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
}


def calculate(operation: str, left: float, right: float) -> float:
    try:
        handler = OPERATIONS[operation]
    except KeyError as exc:
        available = ", ".join(sorted(OPERATIONS))
        raise ValueError(f"unknown operation {operation!r}; choose one of: {available}") from exc
    return handler(left, right)


def format_number(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Small command-line calculator.")
    parser.add_argument("operation", choices=sorted(OPERATIONS))
    parser.add_argument("left", type=float)
    parser.add_argument("right", type=float)
    args = parser.parse_args(argv)

    try:
        result = calculate(args.operation, args.left, args.right)
    except ValueError as exc:
        parser.error(str(exc))
    print(format_number(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        "test_calculator.py": '''from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import calculator


class CalculatorTests(unittest.TestCase):
    def test_add(self) -> None:
        self.assertEqual(calculator.calculate("add", 2, 3), 5)

    def test_subtract(self) -> None:
        self.assertEqual(calculator.calculate("subtract", 10, 4), 6)

    def test_multiply(self) -> None:
        self.assertEqual(calculator.calculate("multiply", 6, 7), 42)

    def test_divide(self) -> None:
        self.assertEqual(calculator.calculate("divide", 8, 2), 4)

    def test_divide_by_zero_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "division by zero"):
            calculator.calculate("divide", 1, 0)


if __name__ == "__main__":
    unittest.main()
''',
        "README.md": """# Calculator

Generated by the mini-orchestrator local test project mode.

## Run

```powershell
python .\\calculator.py add 2 3
python .\\calculator.py subtract 10 4
python .\\calculator.py multiply 6 7
python .\\calculator.py divide 8 2
```

## Test

```powershell
python -m unittest discover -s . -p "test_*.py"
```
""",
    }


def write_calculator_project(project_path: Path) -> list[Path]:
    written: list[Path] = []
    for relative_path, content in calculator_project_files().items():
        target = project_path / relative_path
        write_text_if_changed(target, content)
        written.append(target)
    return written


def construction_crm_project_files() -> dict[str, str]:
    return {
        "crm.py": '''from __future__ import annotations

import argparse
from dataclasses import dataclass, field


VALID_ORDER_STATUSES = (
    "new",
    "in_progress",
    "awaiting_payment",
    "paid",
    "picking",
    "delivering",
    "closed",
)


@dataclass
class Client:
    id: str
    name: str
    phone: str
    segment: str


@dataclass
class Product:
    sku: str
    name: str
    category: str
    unit_price: float
    stock: int
    reorder_level: int


@dataclass
class Deal:
    id: str
    client_id: str
    title: str
    status: str
    manager: str
    expected_total: float


@dataclass
class OrderLine:
    sku: str
    quantity: int


@dataclass
class Order:
    id: str
    client_id: str
    deal_id: str
    lines: list[OrderLine]
    status: str = "new"
    discount_percent: float = 0
    comments: list[str] = field(default_factory=list)


class ConstructionCRM:
    def __init__(
        self,
        clients: list[Client],
        products: list[Product],
        deals: list[Deal],
    ) -> None:
        self.clients = {client.id: client for client in clients}
        self.products = {product.sku: product for product in products}
        self.deals = {deal.id: deal for deal in deals}
        self.orders: dict[str, Order] = {}
        self._next_order_number = 1001

    @classmethod
    def seed(cls) -> "ConstructionCRM":
        return cls(
            clients=[
                Client("C-001", "North Ridge Builders", "+1-555-0101", "contractor"),
                Client("C-002", "Mason Family", "+1-555-0199", "retail"),
                Client("C-003", "Lime Yard Design", "+1-555-0133", "designer"),
            ],
            products=[
                Product("CEM-M500", "Cement M500 50kg", "cement", 620.0, 120, 25),
                Product("MIX-PLASTER", "Dry plaster mix 30kg", "dry mixes", 410.0, 18, 20),
                Product("TILE-GRAPHITE", "Graphite floor tile 60x60", "tile", 1450.0, 64, 16),
                Product("FASTENER-BOX", "Universal fastener box", "fasteners", 480.0, 15, 18),
                Product("DRILL-PRO", "Professional hammer drill", "tools", 15800.0, 7, 3),
            ],
            deals=[
                Deal("D-100", "C-001", "Townhouse foundation materials", "in_progress", "Irina", 180000.0),
                Deal("D-101", "C-002", "Bathroom repair kit", "new", "Oleg", 62000.0),
                Deal("D-102", "C-003", "Tile showroom refresh", "awaiting_payment", "Irina", 130000.0),
            ],
        )

    def find_clients(self, query: str) -> list[Client]:
        normalized = query.casefold()
        return [
            client
            for client in self.clients.values()
            if normalized in client.name.casefold() or normalized in client.phone
        ]

    def low_stock_products(self) -> list[Product]:
        return [
            product
            for product in self.products.values()
            if product.stock <= product.reorder_level
        ]

    def create_order(
        self,
        client_id: str,
        deal_id: str,
        lines: list[OrderLine],
        discount_percent: float = 0,
        comment: str | None = None,
    ) -> Order:
        if client_id not in self.clients:
            raise ValueError(f"unknown client: {client_id}")
        if deal_id not in self.deals:
            raise ValueError(f"unknown deal: {deal_id}")
        if self.deals[deal_id].client_id != client_id:
            raise ValueError("deal does not belong to client")
        if not lines:
            raise ValueError("order must contain at least one line")
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("discount_percent must be between 0 and 100")

        for line in lines:
            if line.quantity <= 0:
                raise ValueError("line quantity must be positive")
            product = self.products.get(line.sku)
            if product is None:
                raise ValueError(f"unknown sku: {line.sku}")
            if product.stock < line.quantity:
                raise ValueError(
                    f"not enough stock for {line.sku}: requested {line.quantity}, available {product.stock}"
                )

        for line in lines:
            self.products[line.sku].stock -= line.quantity

        order = Order(
            id=f"ORD-{self._next_order_number}",
            client_id=client_id,
            deal_id=deal_id,
            lines=list(lines),
            status="picking",
            discount_percent=discount_percent,
        )
        self._next_order_number += 1
        if comment:
            order.comments.append(comment)
        self.orders[order.id] = order
        return order

    def order_total(self, order: Order) -> float:
        subtotal = sum(self.products[line.sku].unit_price * line.quantity for line in order.lines)
        discount = subtotal * (order.discount_percent / 100)
        return round(subtotal - discount, 2)

    def update_order_status(self, order_id: str, status: str) -> Order:
        if status not in VALID_ORDER_STATUSES:
            allowed = ", ".join(VALID_ORDER_STATUSES)
            raise ValueError(f"unknown order status {status!r}; choose one of: {allowed}")
        order = self.orders[order_id]
        order.status = status
        return order

    def dashboard(self) -> dict[str, int | float]:
        return {
            "clients": len(self.clients),
            "open_deals": sum(1 for deal in self.deals.values() if deal.status != "closed"),
            "orders": len(self.orders),
            "low_stock": len(self.low_stock_products()),
            "pipeline_total": sum(deal.expected_total for deal in self.deals.values()),
        }


def run_smoke() -> str:
    crm = ConstructionCRM.seed()
    order = crm.create_order(
        "C-001",
        "D-100",
        [OrderLine("CEM-M500", 10), OrderLine("FASTENER-BOX", 5)],
        discount_percent=5,
        comment="Reserved from approved CRM smoke scenario.",
    )
    total = crm.order_total(order)
    return f"smoke passed: {order.id} {order.status} total {total:.2f} low_stock {crm.dashboard()['low_stock']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construction-store CRM demo.")
    parser.add_argument("command", choices=("dashboard", "smoke"))
    args = parser.parse_args(argv)

    if args.command == "smoke":
        print(run_smoke())
        return 0

    crm = ConstructionCRM.seed()
    summary = crm.dashboard()
    print(
        "dashboard: "
        f"clients={summary['clients']} "
        f"open_deals={summary['open_deals']} "
        f"low_stock={summary['low_stock']} "
        f"pipeline_total={summary['pipeline_total']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        "test_crm.py": '''from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import crm


class ConstructionCRMTests(unittest.TestCase):
    def test_dashboard_starts_with_store_metrics(self) -> None:
        app = crm.ConstructionCRM.seed()
        self.assertEqual(app.dashboard()["clients"], 3)
        self.assertEqual(app.dashboard()["open_deals"], 3)
        self.assertEqual(app.dashboard()["low_stock"], 2)

    def test_client_search_uses_name_or_phone(self) -> None:
        app = crm.ConstructionCRM.seed()
        self.assertEqual(app.find_clients("ridge")[0].id, "C-001")
        self.assertEqual(app.find_clients("0199")[0].id, "C-002")

    def test_order_reserves_stock_and_applies_discount(self) -> None:
        app = crm.ConstructionCRM.seed()
        order = app.create_order(
            "C-001",
            "D-100",
            [crm.OrderLine("CEM-M500", 10), crm.OrderLine("FASTENER-BOX", 5)],
            discount_percent=5,
        )
        self.assertEqual(order.id, "ORD-1001")
        self.assertEqual(order.status, "picking")
        self.assertEqual(app.products["CEM-M500"].stock, 110)
        self.assertEqual(app.products["FASTENER-BOX"].stock, 10)
        self.assertEqual(app.order_total(order), 8170.0)

    def test_order_rejects_insufficient_stock(self) -> None:
        app = crm.ConstructionCRM.seed()
        with self.assertRaisesRegex(ValueError, "not enough stock"):
            app.create_order("C-001", "D-100", [crm.OrderLine("DRILL-PRO", 99)])

    def test_status_validation(self) -> None:
        app = crm.ConstructionCRM.seed()
        order = app.create_order("C-002", "D-101", [crm.OrderLine("TILE-GRAPHITE", 4)])
        app.update_order_status(order.id, "paid")
        self.assertEqual(order.status, "paid")
        with self.assertRaisesRegex(ValueError, "unknown order status"):
            app.update_order_status(order.id, "lost")

    def test_smoke_command_message(self) -> None:
        self.assertIn("smoke passed: ORD-1001 picking total 8170.00", crm.run_smoke())


if __name__ == "__main__":
    unittest.main()
''',
        "index.html": '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Construction Store CRM</title>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>
    <aside>
      <h1>BuildDesk CRM</h1>
      <nav>
        <button class="active" data-view="dashboard" aria-pressed="true">Dashboard</button>
        <button data-view="clients" aria-pressed="false">Clients</button>
        <button data-view="deals" aria-pressed="false">Deals</button>
        <button data-view="orders" aria-pressed="false">Orders</button>
        <button data-view="stock" aria-pressed="false">Stock</button>
      </nav>
    </aside>
    <main>
      <header>
        <div>
          <p>Construction store</p>
          <h2>Manager workspace</h2>
        </div>
        <div class="actions">
          <button data-action="new-client">New client</button>
          <button class="primary" data-action="new-order">New order</button>
        </div>
      </header>
      <section class="metrics">
        <article><span>Open deals</span><strong>3</strong></article>
        <article><span>Pipeline</span><strong>372k</strong></article>
        <article><span>Low stock</span><strong>2</strong></article>
        <article><span>Orders today</span><strong>1</strong></article>
      </section>
      <section class="workspace" data-view-panel="dashboard">
        <div class="panel wide">
          <h3>Deal pipeline</h3>
          <table>
            <thead><tr><th>Client</th><th>Need</th><th>Manager</th><th>Status</th><th>Total</th></tr></thead>
            <tbody>
              <tr><td>North Ridge Builders</td><td>Foundation materials</td><td>Irina</td><td><span class="tag blue">in progress</span></td><td>180,000</td></tr>
              <tr><td>Mason Family</td><td>Bathroom repair kit</td><td>Oleg</td><td><span class="tag gray">new</span></td><td>62,000</td></tr>
              <tr><td>Lime Yard Design</td><td>Tile showroom refresh</td><td>Irina</td><td><span class="tag amber">awaiting payment</span></td><td>130,000</td></tr>
            </tbody>
          </table>
        </div>
        <div class="panel">
          <h3>Stock warnings</h3>
          <ul>
            <li><strong>Dry plaster mix</strong><span>18 left</span></li>
            <li><strong>Universal fastener box</strong><span>15 left</span></li>
          </ul>
        </div>
      </section>
      <section class="workspace" data-view-panel="clients" hidden>
        <div class="panel wide">
          <h3>Clients</h3>
          <table>
            <thead><tr><th>Name</th><th>Phone</th><th>Debt</th><th>Last order</th></tr></thead>
            <tbody>
              <tr><td>North Ridge Builders</td><td>+1 555 0101</td><td>0</td><td>Foundation materials</td></tr>
              <tr><td>Mason Family</td><td>+1 555 0102</td><td>12,400</td><td>Bathroom repair kit</td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="workspace" data-view-panel="deals" hidden>
        <div class="panel wide">
          <h3>Deals</h3>
          <table>
            <thead><tr><th>Deal</th><th>Client</th><th>Status</th><th>Next step</th></tr></thead>
            <tbody>
              <tr><td>D-100</td><td>North Ridge Builders</td><td><span class="tag blue">in progress</span></td><td>Reserve stock</td></tr>
              <tr><td>D-101</td><td>Lime Yard Design</td><td><span class="tag amber">awaiting payment</span></td><td>Payment reminder</td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="workspace" data-view-panel="orders" hidden>
        <div class="panel wide">
          <h3>Orders</h3>
          <table>
            <thead><tr><th>Order</th><th>Client</th><th>Status</th><th>Total</th><th>Delivery</th></tr></thead>
            <tbody>
              <tr><td>ORD-1001</td><td>North Ridge Builders</td><td><span class="tag blue">picking</span></td><td>8,170</td><td>Tomorrow</td></tr>
              <tr><td>ORD-1002</td><td>Mason Family</td><td><span class="tag amber">partially paid</span></td><td>24,800</td><td>Pickup</td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="workspace" data-view-panel="stock" hidden>
        <div class="panel wide">
          <h3>Stock</h3>
          <table>
            <thead><tr><th>SKU</th><th>Product</th><th>Available</th><th>Reserved</th><th>Min</th></tr></thead>
            <tbody>
              <tr><td>CEM-M500</td><td>Cement M500</td><td>120 bags</td><td>10</td><td>40</td></tr>
              <tr><td>FASTENER-BOX</td><td>Universal fastener box</td><td>15 boxes</td><td>5</td><td>20</td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="action-panel" data-action-panel hidden>
        <h3 id="action-title">Action</h3>
        <p id="action-copy"></p>
      </section>
    </main>
    <script src="app.js"></script>
  </body>
</html>
''',
        "app.js": '''const viewButtons = Array.from(document.querySelectorAll("[data-view]"));
const viewPanels = Array.from(document.querySelectorAll("[data-view-panel]"));
const actionButtons = Array.from(document.querySelectorAll("[data-action]"));
const actionPanel = document.querySelector("[data-action-panel]");
const actionTitle = document.querySelector("#action-title");
const actionCopy = document.querySelector("#action-copy");

const actionText = {
  "new-client": ["New client", "Client form opened. Capture name, phone, need, and source."],
  "new-order": ["New order", "Order draft opened. Add products, reserve stock, and choose delivery."]
};

function activateView(viewName) {
  viewButtons.forEach((button) => {
    const selected = button.dataset.view === viewName;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  viewPanels.forEach((panel) => {
    panel.hidden = panel.dataset.viewPanel !== viewName;
  });
  if (actionPanel) {
    actionPanel.hidden = true;
  }
}

function openAction(actionName) {
  const [title, copy] = actionText[actionName] || ["Action", "Ready."];
  actionTitle.textContent = title;
  actionCopy.textContent = copy;
  actionPanel.hidden = false;
}

viewButtons.forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view));
});

actionButtons.forEach((button) => {
  button.addEventListener("click", () => openAction(button.dataset.action));
});
''',
        "ui_smoke.py": '''from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


EXPECTED_VIEWS = {"dashboard", "clients", "deals", "orders", "stock"}
EXPECTED_ACTIONS = {"new-client", "new-order"}


class UiContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.buttons: list[dict[str, str]] = []
        self.view_panels: set[str] = set()
        self.script_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        if tag == "button":
            self.buttons.append(attr_map)
        elif tag == "section" and "data-view-panel" in attr_map:
            self.view_panels.add(attr_map["data-view-panel"])
        elif tag == "script" and attr_map.get("src"):
            self.script_sources.append(attr_map["src"])


def main() -> None:
    root = Path(__file__).resolve().parent
    html_path = root / "index.html"
    html = html_path.read_text(encoding="utf-8")
    parser = UiContractParser()
    parser.feed(html)

    button_views = {button["data-view"] for button in parser.buttons if button.get("data-view")}
    button_actions = {button["data-action"] for button in parser.buttons if button.get("data-action")}
    inert_buttons = [
        button for button in parser.buttons
        if not button.get("data-view") and not button.get("data-action") and button.get("type") != "submit"
    ]

    missing_views = EXPECTED_VIEWS - button_views
    missing_panels = EXPECTED_VIEWS - parser.view_panels
    missing_actions = EXPECTED_ACTIONS - button_actions

    failures: list[str] = []
    if inert_buttons:
        failures.append(f"{len(inert_buttons)} button(s) have no data-view/data-action contract")
    if missing_views:
        failures.append(f"missing nav button views: {', '.join(sorted(missing_views))}")
    if missing_panels:
        failures.append(f"missing view panels: {', '.join(sorted(missing_panels))}")
    if missing_actions:
        failures.append(f"missing action buttons: {', '.join(sorted(missing_actions))}")
    if "app.js" not in parser.script_sources:
        failures.append("index.html must load app.js")

    js_path = root / "app.js"
    js = js_path.read_text(encoding="utf-8") if js_path.exists() else ""
    for required in ("addEventListener", "data-view", "data-action", "hidden"):
        if required not in js:
            failures.append(f"app.js does not contain {required}")

    if failures:
        raise SystemExit("ui smoke failed: " + "; ".join(failures))

    print(
        "ui smoke passed: "
        f"{len(parser.buttons)} buttons, {len(button_views)} views, {len(button_actions)} actions"
    )


if __name__ == "__main__":
    main()
''',
        "styles.css": '''* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 220px 1fr;
  font-family: Arial, Helvetica, sans-serif;
  color: #1f2933;
  background: #f3f6f4;
}

aside {
  background: #26352f;
  color: #f7faf8;
  padding: 24px 18px;
}

h1 {
  font-size: 22px;
  margin: 0 0 28px;
}

nav {
  display: grid;
  gap: 8px;
}

button {
  min-height: 38px;
  border: 1px solid #c8d0ca;
  border-radius: 6px;
  background: #ffffff;
  color: #223028;
  font: inherit;
  cursor: pointer;
}

nav button {
  width: 100%;
  text-align: left;
  padding: 0 12px;
  background: transparent;
  color: #dfe8e2;
  border-color: transparent;
}

nav button.active {
  background: #ffffff;
  color: #26352f;
}

main {
  padding: 24px;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
}

p,
h2,
h3 {
  margin: 0;
}

header p {
  color: #65736a;
  margin-bottom: 4px;
}

h2 {
  font-size: 28px;
}

.actions {
  display: flex;
  gap: 10px;
}

.primary {
  background: #2f6f5e;
  color: #ffffff;
  border-color: #2f6f5e;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(130px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

article,
.panel {
  background: #ffffff;
  border: 1px solid #d9e1dc;
  border-radius: 8px;
}

article {
  padding: 16px;
}

article span {
  display: block;
  color: #63716a;
  margin-bottom: 8px;
}

article strong {
  font-size: 26px;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
}

.panel {
  padding: 18px;
}

.action-panel {
  margin-top: 16px;
  background: #ffffff;
  border: 1px solid #d9e1dc;
  border-radius: 8px;
  padding: 16px 18px;
}

.action-panel[hidden],
.workspace[hidden] {
  display: none;
}

.panel h3 {
  font-size: 18px;
  margin-bottom: 14px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th,
td {
  text-align: left;
  padding: 12px 8px;
  border-bottom: 1px solid #edf1ee;
}

th {
  color: #58655f;
  font-weight: 600;
}

.tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
}

.blue {
  background: #e1eef7;
  color: #1d4e72;
}

.gray {
  background: #edf0ed;
  color: #4c5751;
}

.amber {
  background: #fff1d6;
  color: #735315;
}

ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}

li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf1ee;
}

li span {
  color: #8a3f1d;
}

@media (max-width: 820px) {
  body {
    grid-template-columns: 1fr;
  }

  aside {
    padding: 16px;
  }

  nav {
    grid-template-columns: repeat(5, minmax(80px, 1fr));
    overflow-x: auto;
  }

  header,
  .actions {
    align-items: stretch;
    flex-direction: column;
  }

  .metrics,
  .workspace {
    grid-template-columns: 1fr;
  }
}
''',
        "README.md": """# Construction Store CRM

Generated by the mini-orchestrator local test project mode.

This is a bounded MVP demo for a construction-store CRM. It includes clients,
deals, products, stock warnings, order creation, stock reservation, discounts,
statuses, an interactive manager workspace, and Python smoke tests.

## Run

```powershell
python .\\crm.py dashboard
python .\\crm.py smoke
```

Open `index.html` in a browser to view the static CRM workspace.
Run `python .\\ui_smoke.py` to verify the UI button contract.

## Test

```powershell
python -m unittest discover -s . -p "test_*.py"
python .\\ui_smoke.py
```
""",
    }


def write_construction_crm_project(project_path: Path) -> list[Path]:
    written: list[Path] = []
    for relative_path, content in construction_crm_project_files().items():
        target = project_path / relative_path
        write_text_if_changed(target, content)
        written.append(target)
    return written


def write_local_demo_project(project_name: str, project_path: Path) -> list[Path]:
    if project_name == "calculator":
        return write_calculator_project(project_path)
    if project_name == "construction-crm":
        return write_construction_crm_project(project_path)
    raise ValueError(f"Unsupported local demo project: {project_name}")


def local_demo_planner_output(project_name: str, project_path: Path) -> str:
    relative_path = project_path.relative_to(ROOT)
    if project_name == "calculator":
        return (
            f"Create a Python CLI calculator demo in {relative_path}. "
            "Include arithmetic operations, unit tests, and a CLI smoke check."
        )
    if project_name == "construction-crm":
        return (
            f"Create a construction-store CRM demo in {relative_path}. "
            "Include clients, deals, products, stock reservation, order statuses, "
            "unit tests, an interactive manager workspace, a CLI smoke check, "
            "and a UI smoke check."
        )
    raise ValueError(f"Unsupported local demo project: {project_name}")


def local_demo_smoke_command(project_name: str, project_path: Path) -> list[str]:
    if project_name == "calculator":
        return [sys.executable, str(project_path / "calculator.py"), "add", "2", "3"]
    if project_name == "construction-crm":
        return [sys.executable, str(project_path / "crm.py"), "smoke"]
    raise ValueError(f"Unsupported local demo project: {project_name}")


def local_demo_ui_smoke_command(project_name: str, project_path: Path) -> list[str] | None:
    if project_name == "calculator":
        return None
    if project_name == "construction-crm":
        return [sys.executable, str(project_path / "ui_smoke.py")]
    raise ValueError(f"Unsupported local demo project: {project_name}")


def skipped_command_result(message: str, cwd: Path) -> CommandResult:
    return CommandResult(command=["<skipped>"], cwd=cwd, exit_code=0, stdout=message, stderr="")


def local_demo_smoke_summary(
    project_name: str,
    project_path: Path,
    launch_result: CommandResult,
    ui_result: CommandResult,
) -> str:
    relative_path = project_path.relative_to(ROOT)
    if project_name == "calculator":
        return (
            f"Final passed. Project is at {relative_path}. "
            "Application launch smoke returned 5 for add 2 3."
        )
    if project_name == "construction-crm":
        return (
            f"Final passed. Project is at {relative_path}. "
            f"Application launch smoke returned: {launch_result.stdout}. "
            f"UI smoke returned: {ui_result.stdout}"
        )
    raise ValueError(f"Unsupported local demo project: {project_name}")


def run_command(command: list[str], cwd: Path, timeout_seconds: float = 15) -> CommandResult:
    return adapter_run_command(command, cwd, timeout_seconds=timeout_seconds)


def run_checked_command(command: list[str], cwd: Path, timeout_seconds: float = 15) -> CommandResult:
    result = run_command(command, cwd, timeout_seconds=timeout_seconds)
    if result.exit_code != 0:
        raise RuntimeError(render_command_result(result))
    return result


def render_command_result(result: CommandResult) -> str:
    return adapter_render_command_result(result)


def run_local_test_project_chain(
    task: str,
    log_path: Path,
    workers: list[Worker],
    test_projects_root: Path,
    max_review_iterations: int = 3,
) -> dict[str, str]:
    if max_review_iterations < 1:
        raise ValueError("max_review_iterations must be at least 1.")

    outputs: dict[str, str] = {}
    project_name = select_local_demo_project(task)
    project_path = prepare_demo_project_dir(test_projects_root, project_name)

    planner = find_worker(workers, "planner")
    planner_prompt = f"Plan a bounded local demo project for: {task}"
    write_event(log_path, "handoff", to=planner.name, prompt=planner_prompt, chain=True, localTestProject=True)
    write_event(log_path, "agent_started", agent=planner.name, model=planner.model, chain=True, localTestProject=True)
    outputs["planner"] = local_demo_planner_output(project_name, project_path)
    write_event(log_path, "agent_result", agent=planner.name, output=outputs["planner"], chain=True, localTestProject=True)

    executor = find_worker(workers, "executor")
    reviewer = find_worker(workers, "reviewer")
    executor_notes: list[str] = []
    reviewer_notes: list[str] = []
    previous_review = ""

    for iteration in range(1, max_review_iterations + 1):
        executor_prompt = (
            f"Executor iteration {iteration} for bounded local demo project: {task}\n\n"
            f"Prior context:\n{build_chain_prior(outputs)}\n\n"
            f"Previous review:\n{previous_review or 'none'}"
        )
        write_event(
            log_path,
            "handoff",
            to=executor.name,
            prompt=executor_prompt,
            chain=True,
            localTestProject=True,
            iteration=iteration,
        )
        write_event(
            log_path,
            "agent_started",
            agent=executor.name,
            model=executor.model,
            chain=True,
            localTestProject=True,
            iteration=iteration,
        )
        written_files = write_local_demo_project(project_name, project_path)
        relative_files = [str(path.relative_to(ROOT)) for path in written_files]
        executor_output = f"Iteration {iteration}: wrote files: {', '.join(relative_files)}"
        executor_notes.append(executor_output)
        outputs["executor"] = "\n".join(executor_notes)
        write_event(
            log_path,
            "agent_result",
            agent=executor.name,
            output=executor_output,
            chain=True,
            localTestProject=True,
            iteration=iteration,
        )

        reviewer_prompt = (
            f"Test/review iteration {iteration} for bounded local demo project: {task}\n\n"
            f"Prior context:\n{build_chain_prior(outputs)}"
        )
        write_event(
            log_path,
            "handoff",
            to=reviewer.name,
            prompt=reviewer_prompt,
            chain=True,
            localTestProject=True,
            iteration=iteration,
        )
        write_event(
            log_path,
            "agent_started",
            agent=reviewer.name,
            model=reviewer.model,
            chain=True,
            localTestProject=True,
            iteration=iteration,
        )
        test_result = run_command(
            [sys.executable, "-m", "unittest", "discover", "-s", str(project_path), "-p", "test_*.py"],
            cwd=ROOT,
        )
        if test_result.exit_code == 0:
            launch_result = run_command(
                local_demo_smoke_command(project_name, project_path),
                cwd=ROOT,
            )
        else:
            launch_result = CommandResult(
                command=local_demo_smoke_command(project_name, project_path),
                cwd=ROOT,
                exit_code=1,
                stdout="",
                stderr="Skipped launch smoke because unit tests failed.",
            )

        ui_command = local_demo_ui_smoke_command(project_name, project_path)
        if test_result.exit_code == 0 and launch_result.exit_code == 0 and ui_command is not None:
            ui_result = run_command(ui_command, cwd=ROOT)
        elif ui_command is None:
            ui_result = skipped_command_result("Skipped: no UI smoke declared for this demo project.", ROOT)
        else:
            ui_result = CommandResult(
                command=ui_command,
                cwd=ROOT,
                exit_code=1,
                stdout="",
                stderr="Skipped UI smoke because earlier checks failed.",
            )

        checks_passed = (
            test_result.exit_code == 0
            and launch_result.exit_code == 0
            and ui_result.exit_code == 0
        )
        review_status = "passed" if checks_passed else "failed"
        review_output = (
            f"Iteration {iteration} test/review {review_status}.\n\n"
            f"Unit tests:\n{render_command_result(test_result)}\n\n"
            f"Application launch smoke:\n{render_command_result(launch_result)}\n\n"
            f"UI smoke:\n{render_command_result(ui_result)}"
        )
        reviewer_notes.append(review_output)
        outputs["reviewer"] = "\n\n".join(reviewer_notes)
        write_event(
            log_path,
            "agent_result",
            agent=reviewer.name,
            output=review_output,
            chain=True,
            localTestProject=True,
            iteration=iteration,
            passed=checks_passed,
        )
        if checks_passed:
            outputs["reviewer"] = (
                f"{outputs['reviewer']}\n\n"
                f"{local_demo_smoke_summary(project_name, project_path, launch_result, ui_result)}"
            )
            return outputs

        previous_review = review_output

    raise RuntimeError(
        f"Local test project workflow did not pass after {max_review_iterations} iteration(s). "
        f"Last review:\n{previous_review}"
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
    chain: bool = False,
    local_test_project: bool = False,
    test_projects_dir: Path | None = None,
    plan_only: bool = False,
    max_review_iterations: int = 3,
) -> tuple[Path, dict[str, str], DispatchDecision]:
    if plan_only and local_test_project:
        raise ValueError("--plan-only cannot be combined with --local-test-project.")
    if local_test_project and dry:
        raise ValueError("--local-test-project cannot be combined with --dry-run.")
    if local_test_project and not chain:
        raise ValueError("--local-test-project requires chain mode.")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    log_path = RUNS_DIR / f"{run_id}.jsonl"
    write_event(
        log_path,
        "task_created",
        task=task,
        dryRun=dry,
        chain=chain,
        localTestProject=local_test_project,
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
        localTestProject=local_test_project,
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
            with CodexAppServer(
                log_path,
                codex_command=codex_command,
                request_timeout_seconds=request_timeout_seconds,
                turn_timeout_seconds=turn_timeout_seconds,
                use_worker_models=use_worker_models,
            ) as server:
                thread_id = server.start_thread(planner)
                output = server.run_turn(thread_id, planner, prompt)
        outputs = {"planner": output}
        write_event(log_path, "agent_result", agent=planner.name, output=output, planOnly=True)
        write_event(log_path, "final", outputs=outputs, planOnly=True)
        return log_path, outputs, decision

    if chain:
        if dry:
            outputs = dry_run_chain(decision.next_input, log_path, workers)
            write_event(log_path, "final", outputs=outputs, dryRun=True, chain=True)
            return log_path, outputs, decision

        if local_test_project:
            test_projects_root = resolve_test_projects_root(test_projects_dir)
            outputs = run_local_test_project_chain(
                decision.next_input,
                log_path,
                workers,
                test_projects_root,
                max_review_iterations=max_review_iterations,
            )
            write_event(log_path, "final", outputs=outputs, chain=True, localTestProject=True)
            return log_path, outputs, decision

        outputs: dict[str, str] = {}
        with CodexAppServer(
            log_path,
            codex_command=codex_command,
            request_timeout_seconds=request_timeout_seconds,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=use_worker_models,
        ) as server:
            for worker in ordered_chain_workers(workers):
                thread_id = server.start_thread(worker)
                prior = build_chain_prior(outputs)
                prompt = build_worker_prompt(worker, decision.next_input, prior=prior)
                write_event(log_path, "handoff", to=worker.name, prompt=prompt, chain=True)
                output = server.run_turn(thread_id, worker, prompt)
                outputs[worker.name] = output
                write_event(log_path, "agent_result", agent=worker.name, output=output, chain=True)

        write_event(log_path, "final", outputs=outputs, chain=True)
        return log_path, outputs, decision

    if dry:
        outputs = dry_run(decision.next_input, log_path, [selected_worker])
        write_event(log_path, "final", outputs=outputs, dryRun=True)
        return log_path, outputs, decision

    outputs: dict[str, str] = {}
    with CodexAppServer(
        log_path,
        codex_command=codex_command,
        request_timeout_seconds=request_timeout_seconds,
        turn_timeout_seconds=turn_timeout_seconds,
        use_worker_models=use_worker_models,
    ) as server:
        thread_id = server.start_thread(selected_worker)
        prompt = build_worker_prompt(selected_worker, decision.next_input)
        write_event(log_path, "handoff", to=selected_worker.name, prompt=prompt)
        output = server.run_turn(thread_id, selected_worker, prompt)
        outputs[selected_worker.name] = output
        write_event(log_path, "agent_result", agent=selected_worker.name, output=output)

    write_event(log_path, "final", outputs=outputs)
    return log_path, outputs, decision


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Codex-native dispatcher prototype.")
    parser.add_argument("--task", help="Task to classify and route to one dispatcher worker.")
    parser.add_argument("--task-file", help="UTF-8 text file containing the task to classify and route.")
    parser.add_argument("--dry-run", action="store_true", help="Write dispatcher events without starting Codex.")
    parser.add_argument("--chain", action="store_true", help="Run planner -> executor -> reviewer instead of one selected worker.")
    parser.add_argument("--plan-only", action="store_true", help="Return only a chat approval plan without writing project files.")
    parser.add_argument(
        "--local-test-project",
        action="store_true",
        help="Run the supported demo project flow locally inside test-projects/; implies --chain.",
    )
    parser.add_argument(
        "--test-projects-dir",
        default=str(DEFAULT_TEST_PROJECTS_DIR.relative_to(ROOT)),
        help="Repository-local directory for generated local test projects.",
    )
    parser.add_argument(
        "--max-review-iterations",
        type=int,
        default=3,
        help="Maximum executor -> test/review attempts for local test project mode.",
    )
    parser.add_argument("--from-worknest", action="store_true", help="Claim the next task from the configured WorkNest manager.")
    parser.add_argument("--project", default="mini-orchestrator", help="WorkNest project id for --from-worknest.")
    parser.add_argument("--config-service-url", help="Override GI config-service URL for manager discovery.")
    parser.add_argument("--codex-command", help="Path to the Codex CLI executable or command shim.")
    parser.add_argument("--model", help="Override worker model labels passed to app-server.")
    parser.add_argument(
        "--use-worker-models",
        dest="use_worker_models",
        action="store_true",
        default=True,
        help="Pass worker model names to app-server. This is the default.",
    )
    parser.add_argument(
        "--use-codex-default-models",
        dest="use_worker_models",
        action="store_false",
        help="Do not pass worker model names; let Codex config choose the model.",
    )
    parser.add_argument("--request-timeout-seconds", type=float, default=30, help="Timeout for app-server request responses.")
    parser.add_argument("--turn-timeout-seconds", type=float, default=90, help="Timeout for each agent turn.")
    args = parser.parse_args()

    started = time.time()
    task_text = args.task
    if args.task_file:
        task_path = Path(args.task_file)
        if not task_path.is_absolute():
            task_path = (ROOT / task_path).resolve()
        resolved_task_path = task_path.resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if not (path_is_inside(resolved_task_path, ROOT) or path_is_inside(resolved_task_path, temp_root)):
            raise ValueError(f"--task-file must stay inside {ROOT} or {temp_root}. Got: {resolved_task_path}")
        task_text = resolved_task_path.read_text(encoding="utf-8-sig")
    if args.from_worknest:
        worknest_task = load_worknest_task(args.project, args.config_service_url)
        task_text = f"{worknest_task.title}\n\nWhat to do:\n{worknest_task.what_to_do}\n\nDone when:\n{worknest_task.definition_of_done}"
    if not task_text:
        parser.error("--task is required unless --from-worknest is used.")

    workers = WORKERS
    if args.model:
        workers = [Worker(worker.name, args.model, worker.reasoning, worker.instructions_path) for worker in WORKERS]

    mode = "plan" if args.plan_only else "chain" if args.chain or args.local_test_project else "single"
    try:
        log_path, outputs, decision = run_pipeline(
            task_text,
            args.dry_run,
            workers,
            args.codex_command,
            args.request_timeout_seconds,
            args.turn_timeout_seconds,
            args.use_worker_models,
            chain=args.chain or args.local_test_project,
            local_test_project=args.local_test_project,
            test_projects_dir=Path(args.test_projects_dir),
            plan_only=args.plan_only,
            max_review_iterations=args.max_review_iterations,
        )
    except (RuntimeError, ValueError) as exc:
        print_json({
            "status": "error",
            "durationSeconds": round(time.time() - started, 2),
            "mode": mode,
            "localTestProject": args.local_test_project,
            "planOnly": args.plan_only,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        })
        return 1
    print_json({
        "status": "ok",
        "log": str(log_path.relative_to(ROOT)),
        "durationSeconds": round(time.time() - started, 2),
        "mode": mode,
        "localTestProject": args.local_test_project,
        "planOnly": args.plan_only,
        "dispatchDecision": asdict(decision),
        "agents": outputs,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
