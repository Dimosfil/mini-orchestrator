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


class CodexAppServer:
    def __init__(
        self,
        log_path: Path,
        root: Path,
        codex_command: str | None = None,
        request_timeout_seconds: float = 30,
        turn_timeout_seconds: float = 90,
        use_worker_models: bool = False,
    ) -> None:
        self.log_path = log_path
        self.root = root
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
            cwd=str(self.root),
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
        result = self.request(
            "thread/start",
            {
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
            },
        )
        thread_id = result["thread"]["id"]
        write_event(
            self.log_path,
            "agent_thread_started",
            agent=worker.name,
            model=result.get("model", worker.model),
            threadId=thread_id,
        )
        return thread_id

    def run_turn(self, thread_id: str, worker: Worker, prompt: str) -> str:
        result = self.request(
            "turn/start",
            {
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
            },
        )
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
