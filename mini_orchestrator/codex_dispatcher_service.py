from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
import hashlib
import json
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER_TOOLS = ROOT / "tools" / "codex-dispatcher"
if str(DISPATCHER_TOOLS) not in sys.path:
    sys.path.insert(0, str(DISPATCHER_TOOLS))

from codex_app import CodexAppServer, normalize_access_mode  # type: ignore  # noqa: E402
from events import write_event  # type: ignore  # noqa: E402
from models import Worker  # type: ignore  # noqa: E402
from prompts import build_worker_prompt  # type: ignore  # noqa: E402
from routing import decide_dispatch, find_worker  # type: ignore  # noqa: E402
from worker_profiles import default_workers  # type: ignore  # noqa: E402


DEFAULT_WORKERS = default_workers(ROOT)

WORK_PACKAGE_FIELDS = [
    ("role/instructions", "instructions"),
    ("current objective", "currentObjective"),
    ("inputs/artifacts", "inputsArtifacts"),
    ("constraints", "constraints"),
    ("previous agent outputs", "previousOutputs"),
    ("allowed tools/actions", "allowedTools"),
    ("expected output format", "expectedOutput"),
]


class PersistentCodexDispatcher:
    def __init__(self, root: Path = ROOT, runs_dir: Path | None = None) -> None:
        self.root = root
        self.runs_dir = runs_dir or root / "tools" / "codex-dispatcher" / "runs"
        self._lock = RLock()
        self._server: CodexAppServer | None = None
        self._thread_cache: dict[str, str] = {}

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        if not self._server:
            return
        self._server.__exit__(None, None, None)
        self._server = None
        self._thread_cache = {}

    def _new_log_path(self) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        return self.runs_dir / f"{run_id}.jsonl"

    def _timing(self, log_path: Path, name: str, started: float, **payload: Any) -> None:
        write_event(
            log_path,
            "timing",
            name=name,
            elapsedSeconds=round(time.perf_counter() - started, 4),
            **payload,
        )

    def _routing_metadata(self, server: CodexAppServer) -> dict[str, Any]:
        return {
            "targetWorkspace": str(server.root),
            "workerChatRoot": str(server.worker_chat_root) if server.worker_chat_root else None,
            "processCwd": str(server.process_cwd),
        }

    def _ensure_server(
        self,
        log_path: Path,
        request_timeout_seconds: float,
        turn_timeout_seconds: float,
        use_worker_models: bool,
    ) -> CodexAppServer:
        if self._server and self._server.proc and self._server.proc.poll() is None:
            self._server.log_path = log_path
            self._server.request_timeout_seconds = request_timeout_seconds
            self._server.turn_timeout_seconds = turn_timeout_seconds
            self._server.use_worker_models = use_worker_models
            return self._server

        self._close_unlocked()
        started = time.perf_counter()
        server = CodexAppServer(
            log_path,
            root=self.root,
            request_timeout_seconds=request_timeout_seconds,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=use_worker_models,
        )
        self._server = server.__enter__()
        self._timing(log_path, "codex_app_server_initialized", started)
        return self._server

    def run_single(
        self,
        task: str,
        model: str | None = None,
        request_timeout_seconds: float = 30,
        turn_timeout_seconds: float = 120,
        use_worker_models: bool = True,
        reuse_thread: bool = False,
        compact_prompt: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                return self._run_single_locked(
                    task,
                    model,
                    request_timeout_seconds,
                    turn_timeout_seconds,
                    use_worker_models,
                    reuse_thread,
                    compact_prompt,
                )
            except RuntimeError as exc:
                if "app-server" not in str(exc) and "Codex" not in str(exc):
                    raise
                self._close_unlocked()
                return self._run_single_locked(
                    task,
                    model,
                    request_timeout_seconds,
                    turn_timeout_seconds,
                    use_worker_models,
                    reuse_thread,
                    compact_prompt,
                )

    def run_visual_agent_chat(
        self,
        agent: dict[str, Any],
        message: str,
        turn_timeout_seconds: float = 120,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                return self._run_visual_agent_chat_locked(agent, message, turn_timeout_seconds)
            except RuntimeError as exc:
                if "app-server" not in str(exc) and "Codex" not in str(exc):
                    raise
                self._close_unlocked()
                return self._run_visual_agent_chat_locked(agent, message, turn_timeout_seconds)

    def warm_visual_agent_chat(
        self,
        agent: dict[str, Any],
        turn_timeout_seconds: float = 120,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                return self._warm_visual_agent_chat_locked(agent, turn_timeout_seconds)
            except RuntimeError as exc:
                if "app-server" not in str(exc) and "Codex" not in str(exc):
                    raise
                self._close_unlocked()
                return self._warm_visual_agent_chat_locked(agent, turn_timeout_seconds)

    def run_visual_agent_task(
        self,
        agent: dict[str, Any],
        task: str,
        profile_snapshot_id: str = "",
        turn_timeout_seconds: float = 240,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                return self._run_visual_agent_task_locked(
                    agent,
                    task,
                    profile_snapshot_id,
                    turn_timeout_seconds,
                )
            except RuntimeError as exc:
                if "app-server" not in str(exc) and "Codex" not in str(exc):
                    raise
                self._close_unlocked()
                return self._run_visual_agent_task_locked(
                    agent,
                    task,
                    profile_snapshot_id,
                    turn_timeout_seconds,
                )

    def _warm_visual_agent_chat_locked(
        self,
        agent: dict[str, Any],
        turn_timeout_seconds: float,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        log_path = self._new_log_path()
        write_event(
            log_path,
            "task_created",
            task="visual-agent-mini-chat-warmup",
            dryRun=False,
            chain=False,
            planOnly=False,
        )

        model = _required_agent_model(agent)
        reasoning = _normalized_reasoning(str(agent.get("reasoning") or "medium"))
        name = str(agent.get("name") or "Agent").strip()[:80] or "Agent"
        worker = Worker("visual-agent", model, reasoning, ROOT / ".codex" / "agents" / "visual-agent.toml")

        server_started = time.perf_counter()
        server = self._ensure_server(
            log_path,
            request_timeout_seconds=30,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=True,
        )
        self._timing(log_path, "persistent_server_ready", server_started)

        profile = _visual_agent_profile(agent)
        access_mode = str(profile.get("accessMode") or "danger-full-access")
        profile_hash = hashlib.sha256(
            json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        agent_id = str(agent.get("id") or name).strip()[:80] or name
        thread_cache_key = f"visual-chat:{agent_id}:{profile_hash}"
        thread_id = self._thread_cache.get(thread_cache_key)
        thread_reused = False
        if thread_id:
            thread_reused = True
            write_event(
                log_path,
                "agent_thread_started",
                agent=name,
                model=model,
                threadId=thread_id,
                reused=True,
                **self._routing_metadata(server),
            )
            self._timing(log_path, "codex_thread_reused", time.perf_counter(), agent=name)
        else:
            thread_started = time.perf_counter()
            thread_id = server.start_thread(
                worker,
                developer_instructions=_visual_agent_developer_instructions(profile),
                access_mode=access_mode,
            )
            self._thread_cache[thread_cache_key] = thread_id
            self._timing(log_path, "codex_thread_started", thread_started, agent=name)

        write_event(log_path, "final", outputs={})
        duration = round(time.perf_counter() - started, 2)
        return {
            "status": "ok",
            "log": str(log_path.relative_to(self.root)),
            "durationSeconds": duration,
            "mode": "visual-agent-chat-warmup",
            "runtime": "persistent-codex-app-server",
            **self._routing_metadata(server),
            "threadReused": thread_reused,
            "profileHash": profile_hash,
            "accessMode": access_mode,
        }

    def _run_visual_agent_chat_locked(
        self,
        agent: dict[str, Any],
        message: str,
        turn_timeout_seconds: float,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        log_path = self._new_log_path()
        write_event(
            log_path,
            "task_created",
            task="visual-agent-mini-chat",
            dryRun=False,
            chain=False,
            planOnly=False,
        )

        model = _required_agent_model(agent)
        reasoning = _normalized_reasoning(str(agent.get("reasoning") or "medium"))
        name = str(agent.get("name") or "Agent").strip()[:80] or "Agent"
        worker = Worker("visual-agent", model, reasoning, ROOT / ".codex" / "agents" / "visual-agent.toml")

        server_started = time.perf_counter()
        server = self._ensure_server(
            log_path,
            request_timeout_seconds=30,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=True,
        )
        self._timing(log_path, "persistent_server_ready", server_started)

        profile = _visual_agent_profile(agent)
        access_mode = str(profile.get("accessMode") or "danger-full-access")
        profile_hash = hashlib.sha256(
            json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        agent_id = str(agent.get("id") or name).strip()[:80] or name
        thread_cache_key = f"visual-chat:{agent_id}:{profile_hash}"
        thread_id = self._thread_cache.get(thread_cache_key)
        thread_reused = False
        if thread_id:
            thread_reused = True
            write_event(
                log_path,
                "agent_thread_started",
                agent=name,
                model=model,
                threadId=thread_id,
                reused=True,
                **self._routing_metadata(server),
            )
            self._timing(log_path, "codex_thread_reused", time.perf_counter(), agent=name)
        else:
            thread_started = time.perf_counter()
            thread_id = server.start_thread(
                worker,
                developer_instructions=_visual_agent_developer_instructions(profile),
                access_mode=access_mode,
            )
            self._thread_cache[thread_cache_key] = thread_id
            self._timing(log_path, "codex_thread_started", thread_started, agent=name)

        write_event(
            log_path,
            "handoff",
            to=name,
            prompt=message,
            profileHash=profile_hash,
            accessMode=access_mode,
        )
        turn_started = time.perf_counter()
        output = server.run_turn(thread_id, worker, message, effort=reasoning, access_mode=access_mode)
        self._timing(log_path, "codex_turn_completed", turn_started, agent=name)

        outputs = {name: output}
        write_event(log_path, "agent_result", agent=name, output=output)
        write_event(log_path, "final", outputs=outputs)
        duration = round(time.perf_counter() - started, 2)
        return {
            "status": "ok",
            "log": str(log_path.relative_to(self.root)),
            "durationSeconds": duration,
            "mode": "visual-agent-chat",
            "agents": outputs,
            "runtime": "persistent-codex-app-server",
            **self._routing_metadata(server),
            "threadReused": thread_reused,
            "profileHash": profile_hash,
            "accessMode": access_mode,
        }

    def _run_visual_agent_task_locked(
        self,
        agent: dict[str, Any],
        task: str,
        profile_snapshot_id: str,
        turn_timeout_seconds: float,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        log_path = self._new_log_path()
        name = str(agent.get("name") or "Agent").strip()[:80] or "Agent"
        write_event(
            log_path,
            "task_created",
            task=task,
            dryRun=False,
            chain=False,
            planOnly=False,
            mode="visual-agent-task",
            profileSnapshotId=profile_snapshot_id,
            visualAgentName=name,
        )

        model = _required_agent_model(agent)
        reasoning = _normalized_reasoning(str(agent.get("reasoning") or "medium"))
        worker = Worker(name, model, reasoning, ROOT / ".codex" / "agents" / "visual-agent.toml")

        server_started = time.perf_counter()
        server = self._ensure_server(
            log_path,
            request_timeout_seconds=30,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=True,
        )
        self._timing(log_path, "persistent_server_ready", server_started)

        profile = _visual_agent_profile(agent)
        access_mode = str(profile.get("accessMode") or "danger-full-access")
        profile_hash = hashlib.sha256(
            json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        agent_id = str(agent.get("id") or name).strip()[:80] or name
        thread_cache_key = f"visual-task:{agent_id}:{profile_hash}"
        thread_id = self._thread_cache.get(thread_cache_key)
        thread_reused = False
        if thread_id:
            thread_reused = True
            write_event(
                log_path,
                "agent_thread_started",
                agent=name,
                model=model,
                threadId=thread_id,
                reused=True,
                profileSnapshotId=profile_snapshot_id,
                **self._routing_metadata(server),
            )
            self._timing(log_path, "codex_thread_reused", time.perf_counter(), agent=name)
        else:
            thread_started = time.perf_counter()
            thread_id = server.start_thread(
                worker,
                developer_instructions=_visual_agent_developer_instructions(profile),
                access_mode=access_mode,
            )
            self._thread_cache[thread_cache_key] = thread_id
            self._timing(log_path, "codex_thread_started", thread_started, agent=name)

        write_event(
            log_path,
            "handoff",
            to=name,
            prompt=task,
            profileHash=profile_hash,
            profileSnapshotId=profile_snapshot_id,
            accessMode=access_mode,
        )
        turn_started = time.perf_counter()
        output = server.run_turn(thread_id, worker, task, effort=reasoning, access_mode=access_mode)
        self._timing(log_path, "codex_turn_completed", turn_started, agent=name)

        outputs = {name: output}
        write_event(log_path, "agent_result", agent=name, output=output)
        write_event(log_path, "final", outputs=outputs)
        duration = round(time.perf_counter() - started, 2)
        return {
            "status": "ok",
            "log": str(log_path.relative_to(self.root)),
            "durationSeconds": duration,
            "mode": "visual-agent-task",
            "agents": outputs,
            "runtime": "persistent-codex-app-server",
            **self._routing_metadata(server),
            "threadReused": thread_reused,
            "profileHash": profile_hash,
            "profileSnapshotId": profile_snapshot_id,
            "accessMode": access_mode,
        }

    def _run_single_locked(
        self,
        task: str,
        model: str | None,
        request_timeout_seconds: float,
        turn_timeout_seconds: float,
        use_worker_models: bool,
        reuse_thread: bool,
        compact_prompt: bool,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        log_path = self._new_log_path()
        write_event(log_path, "task_created", task=task, dryRun=False, chain=False, planOnly=False)

        workers = DEFAULT_WORKERS
        if model:
            workers = [
                Worker(
                    worker.name,
                    model,
                    worker.reasoning,
                    worker.instructions_path,
                    access_mode=worker.access_mode,
                    source_agent_id=worker.source_agent_id,
                    instructions_text=worker.instructions_text,
                )
                for worker in workers
            ]

        decision = decide_dispatch(task, workers)
        selected_worker = find_worker(workers, decision.role)
        write_event(log_path, "dispatch_decision", **asdict(decision), dryRun=False, chain=False, planOnly=False)

        server_started = time.perf_counter()
        server = self._ensure_server(
            log_path,
            request_timeout_seconds=request_timeout_seconds,
            turn_timeout_seconds=turn_timeout_seconds,
            use_worker_models=use_worker_models,
        )
        self._timing(log_path, "persistent_server_ready", server_started)

        thread_cache_key = f"{selected_worker.name}:{selected_worker.model}:{'compact' if compact_prompt else 'worker'}"
        thread_id = self._thread_cache.get(thread_cache_key) if reuse_thread else None
        if thread_id:
            write_event(
                log_path,
                "agent_thread_started",
                agent=selected_worker.name,
                model=selected_worker.model,
                threadId=thread_id,
                reused=True,
                **self._routing_metadata(server),
            )
            self._timing(log_path, "codex_thread_reused", time.perf_counter(), agent=selected_worker.name)
        else:
            thread_started = time.perf_counter()
            thread_id = server.start_thread(selected_worker)
            if reuse_thread:
                self._thread_cache[thread_cache_key] = thread_id
            self._timing(log_path, "codex_thread_started", thread_started, agent=selected_worker.name)

        prompt = decision.next_input if compact_prompt else build_worker_prompt(selected_worker, decision.next_input)
        write_event(log_path, "handoff", to=selected_worker.name, prompt=prompt)
        turn_started = time.perf_counter()
        output = server.run_turn(thread_id, selected_worker, prompt)
        self._timing(log_path, "codex_turn_completed", turn_started, agent=selected_worker.name)

        outputs = {selected_worker.name: output}
        write_event(log_path, "agent_result", agent=selected_worker.name, output=output)
        write_event(log_path, "final", outputs=outputs)
        duration = round(time.perf_counter() - started, 2)
        return {
            "status": "ok",
            "log": str(log_path.relative_to(self.root)),
            "durationSeconds": duration,
            "mode": "single",
            "planOnly": False,
            "dispatchDecision": {
                "role": decision.role,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "nextInput": decision.next_input,
            },
            "agents": outputs,
            "runtime": "persistent-codex-app-server",
            **self._routing_metadata(server),
        }


def _normalized_reasoning(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"low", "medium", "high"}:
        return normalized
    if normalized in {"very_high", "very high"}:
        return "high"
    return "medium"


def _required_agent_model(agent: dict[str, Any]) -> str:
    model = str(agent.get("llm") or "").strip()
    if model:
        return model
    name = str(agent.get("name") or agent.get("id") or "Agent").strip() or "Agent"
    raise ValueError(f"Agent card {name!r} is missing an explicit llm setting.")


def _visual_agent_profile(agent: dict[str, Any]) -> dict[str, Any]:
    work_package_value = agent.get("workPackage", {})
    work_package = work_package_value if isinstance(work_package_value, dict) else {}
    access_mode = normalize_access_mode(str(agent.get("accessMode") or "danger-full-access"))
    return {
        "name": str(agent.get("name") or "Agent").strip()[:80],
        "role": str(agent.get("role") or "Agent").strip()[:80],
        "model": _required_agent_model(agent)[:80],
        "speed": str(agent.get("speed") or "balanced").strip()[:40],
        "reasoning": _normalized_reasoning(str(agent.get("reasoning") or "medium")),
        "accessMode": access_mode or "danger-full-access",
        "workPackage": {
            key: str(work_package.get(key) or "").strip()[:1200]
            for _, key in WORK_PACKAGE_FIELDS
            if str(work_package.get(key) or "").strip()
        },
    }


def _visual_agent_developer_instructions(profile: dict[str, Any]) -> str:
    work_package = profile.get("workPackage")
    package_lines: list[str] = []
    if isinstance(work_package, dict):
        for label, key in WORK_PACKAGE_FIELDS:
            value = str(work_package.get(key) or "").strip()
            if value:
                package_lines.append(f"{label}: {value}")
    package_text = "\n".join(package_lines) if package_lines else "No custom work package fields."
    return (
        "You are the selected visual agent in the mini-orchestrator UI.\n\n"
        f"Agent name: {profile['name']}\n"
        f"Agent role: {profile['role']}\n"
        f"Selected model: {profile['model']}\n"
        f"Preferred speed: {profile['speed']}\n"
        f"Reasoning level: {profile['reasoning']}\n\n"
        f"Access mode: {profile['accessMode']}\n\n"
        f"Agent work package:\n{package_text}\n\n"
        "Use this work package as your operating contract for the conversation. "
        "Answer as this configured agent, keep responses concise unless the user asks for detail, "
        "and use the available Codex runtime normally when the task requires it. "
        "If the user asks who you are or which model/settings are selected, answer from these settings."
    )
