from __future__ import annotations

from collections import deque
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from events import write_event
from models import Worker


MOJIBAKE_MARKERS = (
    "Р С’",
    "Р Сџ",
    "Р РЋ",
    "Р Сњ",
    "Р С‘",
    "Р Вµ",
    "РЎРѓ",
    "РЎвЂљ",
    "РІР‚",
    "РІвЂћ",
    "Г‚",
)
ACCESS_MODES = {"danger-full-access", "workspace-write", "read-only"}
DEFAULT_TURN_TIMEOUT_SECONDS = 300.0


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


def resolve_codex_command() -> str:
    configured = os.environ.get("CODEX_COMMAND")
    if configured:
        return configured
    if os.name == "nt":
        cmd = shutil.which("codex.cmd")
        if cmd:
            return cmd
    return shutil.which("codex") or "codex"


def _load_worker_chat_root_from_config(root: Path) -> str:
    config_path = root / "tools" / "project-memory" / "service-runtime.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("workerChatRoot") or payload.get("worker_chat_root") or "").strip()


def resolve_worker_chat_root(root: Path, configured: str | Path | None = None) -> Path | None:
    value = str(configured or os.environ.get("MINI_ORCHESTRATOR_WORKER_CHAT_ROOT") or "").strip()
    if not value:
        value = _load_worker_chat_root_from_config(root)
    if not value:
        return None

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.exists():
        raise RuntimeError(f"Configured worker chat root does not exist: {candidate}")
    if not candidate.is_dir():
        raise RuntimeError(f"Configured worker chat root is not a directory: {candidate}")
    if candidate == root.resolve():
        return None
    return candidate


def normalize_access_mode(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold()
    return normalized if normalized in ACCESS_MODES else "danger-full-access"


def approval_policy_for_access(access_mode: str | None) -> str | None:
    normalized = normalize_access_mode(access_mode)
    if normalized == "danger-full-access":
        return "never"
    if normalized in {"workspace-write", "read-only"}:
        return "on-request"
    return None


def thread_sandbox_for_access(access_mode: str | None) -> str | None:
    return normalize_access_mode(access_mode)


def turn_sandbox_policy_for_access(access_mode: str | None) -> dict[str, Any] | None:
    normalized = normalize_access_mode(access_mode)
    if normalized == "danger-full-access":
        return {"type": "dangerFullAccess"}
    if normalized == "workspace-write":
        return {"type": "workspaceWrite", "networkAccess": False, "writableRoots": []}
    if normalized == "read-only":
        return {"type": "readOnly", "networkAccess": False}
    return None


class CodexAppServer:
    def __init__(
        self,
        log_path: Path,
        root: Path,
        codex_command: str | None = None,
        request_timeout_seconds: float = 30,
        turn_timeout_seconds: float = DEFAULT_TURN_TIMEOUT_SECONDS,
        use_worker_models: bool = False,
        worker_chat_root: str | Path | None = None,
    ) -> None:
        self.log_path = log_path
        self.root = root.resolve()
        self.worker_chat_root = resolve_worker_chat_root(self.root, worker_chat_root)
        self.process_cwd = self.worker_chat_root or self.root
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
        creationflags = 0
        startupinfo = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.proc = subprocess.Popen(
            [self.codex_command or resolve_codex_command(), "app-server"],
            cwd=str(self.process_cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        self.stdout_thread = threading.Thread(target=self.read_stdout, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
        self.stderr_thread.start()
        self.request(
            "initialize",
            {
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
            },
        )
        self.notify("initialized", {})
        write_event(
            self.log_path,
            "app_server_started",
            targetWorkspace=str(self.root),
            workerChatRoot=str(self.worker_chat_root) if self.worker_chat_root else None,
            processCwd=str(self.process_cwd),
        )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if not self.proc:
            return
        self._terminate_process_tree(self.proc)

    def _terminate_process_tree(self, proc: subprocess.Popen[str]) -> None:
        if os.name == "nt":
            if proc.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

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

    def start_thread(
        self,
        worker: Worker,
        developer_instructions: str | None = None,
        base_instructions: str | None = None,
        access_mode: str | None = None,
    ) -> str:
        thread_cwd = self.worker_chat_root or self.root
        effective_access_mode = access_mode or worker.access_mode or None
        approval_policy = approval_policy_for_access(effective_access_mode)
        approvals_reviewer = "user" if approval_policy else None
        sandbox = thread_sandbox_for_access(effective_access_mode)
        result = self.request(
            "thread/start",
            {
                "model": worker.model if self.use_worker_models else None,
                "modelProvider": None,
                "cwd": str(thread_cwd),
                "runtimeWorkspaceRoots": [str(thread_cwd)],
                "approvalPolicy": approval_policy,
                "approvalsReviewer": approvals_reviewer,
                "sandbox": sandbox,
                "permissions": None,
                "config": None,
                "serviceName": None,
                "baseInstructions": base_instructions,
                "developerInstructions": developer_instructions,
                "personality": None,
                "ephemeral": None,
                "sessionStartSource": None,
                "threadSource": None,
                "environments": None,
                "dynamicTools": None,
                "selectedCapabilityRoots": None,
                "mockExperimentalField": None,
            },
        )
        thread_id = result["thread"]["id"]
        write_event(
            self.log_path,
            "agent_thread_started",
            agent=worker.name,
            model=result.get("model", worker.model),
            threadId=thread_id,
            targetWorkspace=str(self.root),
            workerChatRoot=str(self.worker_chat_root) if self.worker_chat_root else None,
            accessMode=normalize_access_mode(effective_access_mode),
        )
        return thread_id

    def run_turn(
        self,
        thread_id: str,
        worker: Worker,
        prompt: str,
        effort: str | None = None,
        access_mode: str | None = None,
    ) -> str:
        effective_access_mode = access_mode or worker.access_mode or None
        approval_policy = approval_policy_for_access(effective_access_mode)
        approvals_reviewer = "user" if approval_policy else None
        sandbox_policy = turn_sandbox_policy_for_access(effective_access_mode)
        result = self.request(
            "turn/start",
            {
                "threadId": thread_id,
                "clientUserMessageId": None,
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
                "responsesapiClientMetadata": None,
                "additionalContext": None,
                "environments": None,
                "cwd": str(self.root),
                "runtimeWorkspaceRoots": [str(self.root)],
                "approvalPolicy": approval_policy,
                "approvalsReviewer": approvals_reviewer,
                "sandboxPolicy": sandbox_policy,
                "permissions": None,
                "model": None,
                "effort": effort or worker.reasoning,
                "summary": None,
                "personality": None,
                "outputSchema": None,
                "collaborationMode": None,
            },
        )
        turn_id = result.get("turn", {}).get("id")
        write_event(
            self.log_path,
            "agent_turn_started",
            agent=worker.name,
            threadId=thread_id,
            turnId=turn_id,
            accessMode=normalize_access_mode(effective_access_mode),
        )
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
