from __future__ import annotations

import argparse
from collections import deque
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protocol import validate_event_type
from worknest import WorkNestClient, WorkNestTask


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = Path(__file__).resolve().parent / "runs"


@dataclass(frozen=True)
class Worker:
    name: str
    model: str
    reasoning: str
    instructions_path: Path


@dataclass(frozen=True)
class DispatchDecision:
    role: str
    reason: str
    confidence: float
    next_input: str


WORKERS = [
    Worker("planner", "gpt-5.5", "high", ROOT / ".codex" / "agents" / "planner.toml"),
    Worker("executor", "gpt-5.4", "medium", ROOT / ".codex" / "agents" / "executor.toml"),
    Worker("reviewer", "gpt-5.4-mini", "high", ROOT / ".codex" / "agents" / "reviewer.toml"),
]

PLANNER_TASK_MARKERS = (
    "plan",
    "planner",
    "proposed steps",
    "objective:",
    "next smallest improvement",
)

EXECUTOR_TASK_MARKERS = (
    "implement",
    "fix",
    "patch",
    "edit",
    "change the code",
    "update the code",
)

REVIEWER_TASK_MARKERS = (
    "review",
    "code review",
    "find bugs",
    "inspect the diff",
    "verify the implementation",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_event(log_path: Path, event_type: str, **payload: Any) -> None:
    validate_event_type(event_type)
    record = {
        "time": utc_now(),
        "type": event_type,
        **payload,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_instructions(worker: Worker) -> str:
    return worker.instructions_path.read_text(encoding="utf-8")


def find_worker(workers: list[Worker], role: str) -> Worker:
    for worker in workers:
        if worker.name == role:
            return worker
    available = ", ".join(worker.name for worker in workers)
    raise ValueError(f"Dispatch selected unknown role {role!r}. Available roles: {available}")


def decide_dispatch(task: str, workers: list[Worker]) -> DispatchDecision:
    find_worker(workers, "planner")
    find_worker(workers, "executor")
    find_worker(workers, "reviewer")
    normalized = task.casefold()
    next_input = task.strip()
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
                    return "".join(chunks).strip()


def build_worker_prompt(worker: Worker, task: str, prior: str = "") -> str:
    instructions = read_instructions(worker)
    return (
        f"Worker role: {worker.name}\n\n"
        f"Role configuration:\n{instructions}\n\n"
        f"Current task:\n{task}\n\n"
        f"Prior context:\n{prior or 'none'}\n\n"
        "Return only the result needed by the dispatcher."
    )


def dry_run(task: str, log_path: Path, workers: list[Worker]) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for worker in workers:
        write_event(log_path, "agent_started", agent=worker.name, model=worker.model, dryRun=True)
        output = f"[dry-run:{worker.name}] would process task with model {worker.model}."
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
) -> tuple[Path, dict[str, str], DispatchDecision]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    log_path = RUNS_DIR / f"{run_id}.jsonl"
    write_event(log_path, "task_created", task=task, dryRun=dry)
    decision = decide_dispatch(task, workers)
    selected_worker = find_worker(workers, decision.role)
    write_event(log_path, "dispatch_decision", **asdict(decision), dryRun=dry)

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
    parser = argparse.ArgumentParser(description="Run Codex-native dispatcher prototype with one selected worker.")
    parser.add_argument("--task", help="Task to classify and route to one dispatcher worker.")
    parser.add_argument("--dry-run", action="store_true", help="Write dispatcher events without starting Codex.")
    parser.add_argument("--from-worknest", action="store_true", help="Claim the next task from the configured WorkNest manager.")
    parser.add_argument("--project", default="mini-orchestrator", help="WorkNest project id for --from-worknest.")
    parser.add_argument("--config-service-url", help="Override GI config-service URL for manager discovery.")
    parser.add_argument("--codex-command", help="Path to the Codex CLI executable or command shim.")
    parser.add_argument("--model", help="Override worker model labels; use with --use-worker-models to pass them to app-server.")
    parser.add_argument("--use-worker-models", action="store_true", help="Pass worker model names to app-server instead of using Codex config defaults.")
    parser.add_argument("--request-timeout-seconds", type=float, default=30, help="Timeout for app-server request responses.")
    parser.add_argument("--turn-timeout-seconds", type=float, default=90, help="Timeout for each agent turn.")
    args = parser.parse_args()

    started = time.time()
    task_text = args.task
    if args.from_worknest:
        worknest_task = load_worknest_task(args.project, args.config_service_url)
        task_text = f"{worknest_task.title}\n\nWhat to do:\n{worknest_task.what_to_do}\n\nDone when:\n{worknest_task.definition_of_done}"
    if not task_text:
        parser.error("--task is required unless --from-worknest is used.")

    workers = WORKERS
    if args.model:
        workers = [Worker(worker.name, args.model, worker.reasoning, worker.instructions_path) for worker in WORKERS]

    log_path, outputs, decision = run_pipeline(
        task_text,
        args.dry_run,
        workers,
        args.codex_command,
        args.request_timeout_seconds,
        args.turn_timeout_seconds,
        args.use_worker_models,
    )
    print(json.dumps({
        "status": "ok",
        "log": str(log_path.relative_to(ROOT)),
        "durationSeconds": round(time.time() - started, 2),
        "dispatchDecision": asdict(decision),
        "agents": outputs,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
