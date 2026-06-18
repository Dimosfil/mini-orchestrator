from __future__ import annotations

import sys
from pathlib import Path


DISPATCHER_TOOLS = Path(__file__).resolve().parents[1] / "tools" / "codex-dispatcher"
if str(DISPATCHER_TOOLS) not in sys.path:
    sys.path.insert(0, str(DISPATCHER_TOOLS))

from codex_app import CodexAppServer, resolve_worker_chat_root  # type: ignore  # noqa: E402
from models import Worker  # type: ignore  # noqa: E402


class CapturingCodexAppServer(CodexAppServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests = []

    def request(self, method, params):
        self.requests.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}, "model": params["model"]}
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}
        return {}

    def collect_final_response(self, turn_id):
        return f"done:{turn_id}"


def test_resolve_worker_chat_root_reads_project_runtime_config(tmp_path):
    root = tmp_path / "project"
    worker_root = tmp_path / "worker-chats"
    config_dir = root / "tools" / "project-memory"
    config_dir.mkdir(parents=True)
    worker_root.mkdir()
    (config_dir / "service-runtime.json").write_text(
        f'{{"workerChatRoot": "{worker_root.as_posix()}"}}',
        encoding="utf-8",
    )

    assert resolve_worker_chat_root(root) == worker_root


def test_thread_uses_worker_chat_root_and_turn_uses_target_workspace(tmp_path):
    root = tmp_path / "project"
    worker_root = tmp_path / "worker-chats"
    root.mkdir()
    worker_root.mkdir()
    log_path = root / "run.jsonl"
    worker = Worker("planner", "gpt-5.5", "high", root / "planner.toml")

    server = CapturingCodexAppServer(log_path, root=root, worker_chat_root=worker_root)
    thread_id = server.start_thread(worker)
    output = server.run_turn(thread_id, worker, "hello")

    assert output == "done:turn-1"
    assert server.process_cwd == worker_root
    thread_params = server.requests[0][1]
    turn_params = server.requests[1][1]
    assert thread_params["cwd"] == str(worker_root)
    assert thread_params["runtimeWorkspaceRoots"] == [str(worker_root)]
    assert turn_params["cwd"] == str(root.resolve())
    assert turn_params["runtimeWorkspaceRoots"] == [str(root.resolve())]


def test_full_access_mode_maps_to_app_server_approval_and_sandbox(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    log_path = root / "run.jsonl"
    worker = Worker("executor", "gpt-5.4", "medium", root / "executor.toml")

    server = CapturingCodexAppServer(log_path, root=root)
    thread_id = server.start_thread(worker, access_mode="danger-full-access")
    output = server.run_turn(thread_id, worker, "write files", access_mode="danger-full-access")

    assert output == "done:turn-1"
    thread_params = server.requests[0][1]
    turn_params = server.requests[1][1]
    assert thread_params["approvalPolicy"] == "never"
    assert thread_params["approvalsReviewer"] == "user"
    assert thread_params["sandbox"] == "danger-full-access"
    assert turn_params["approvalPolicy"] == "never"
    assert turn_params["approvalsReviewer"] == "user"
    assert turn_params["sandboxPolicy"] == {"type": "dangerFullAccess"}
