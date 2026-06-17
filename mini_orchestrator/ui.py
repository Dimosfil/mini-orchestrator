from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict
import json
import os
import subprocess
import sys
import tempfile
import webbrowser
from urllib.parse import urlparse

from .orchestrator import Orchestrator


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "tools" / "codex-dispatcher" / "dispatcher.py"


@dataclass
class UiConfig:
    host: str
    port: int
    open_browser: bool
    service_id: str = "mini-orchestrator"
    base_url: str = ""


class _ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class _OrchestratorUIHandler(BaseHTTPRequestHandler):
    orchestrator: Orchestrator
    web_root: Path
    service_id: str = "mini-orchestrator"

    def _path(self) -> str:
        return urlparse(self.path).path

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request payload must be an object.")
        return payload

    def _json_response(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _http_error(self, status: int, message: str) -> None:
        self._json_response(status, {"error": message})

    def _run_dispatcher(self, args: list[str], timeout_seconds: int) -> Dict[str, Any]:
        if not DISPATCHER.exists():
            raise RuntimeError(f"Dispatcher script is missing: {DISPATCHER}")

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["MINI_ORCHESTRATOR_DISPATCHER_BEST_EFFORT_LOGS"] = "1"
        completed = subprocess.run(
            [sys.executable, str(DISPATCHER), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        try:
            payload = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Dispatcher returned non-JSON output: {stdout[:800]}") from exc

        if completed.returncode != 0:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise RuntimeError(message or stderr or f"Dispatcher failed with exit code {completed.returncode}.")

        if stderr and isinstance(payload, dict):
            payload.setdefault("stderr", stderr)
        return payload

    def _dispatcher_failure_detail(self, result: Dict[str, Any]) -> str:
        stderr = str(result.get("stderr") or "").strip()
        if stderr:
            return stderr[:800]

        log_value = str(result.get("log") or "").strip()
        if not log_value:
            return ""
        log_path = (ROOT / log_value).resolve()
        try:
            log_path.relative_to(ROOT)
        except ValueError:
            return ""
        if not log_path.exists():
            return ""

        detail = ""
        try:
            with log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event_type = event.get("type")
                    if event_type == "codex_notification":
                        message = event.get("message")
                        if isinstance(message, dict) and message.get("method") == "error":
                            params = message.get("params")
                            error = params.get("error") if isinstance(params, dict) else None
                            if isinstance(error, dict):
                                detail = str(error.get("message") or "").strip()
                    elif event_type in {"error", "agent_error"}:
                        detail = str(event.get("message") or event.get("error") or "").strip()
        except OSError:
            return ""
        return detail[:800]

    def _agent_role_for_dispatcher(self, role: str) -> str:
        normalized = role.strip().casefold()
        if "executor" in normalized or "исполн" in normalized:
            return "executor"
        if "review" in normalized or "рев" in normalized or "провер" in normalized:
            return "reviewer"
        return "planner"

    def _agent_chat_task(self, agent: Dict[str, Any], message: str, history: list[Any]) -> str:
        name = str(agent.get("name") or "Agent").strip()[:80]
        role = str(agent.get("role") or "Agent").strip()[:80]
        model = str(agent.get("llm") or "unknown").strip()[:80]
        speed = str(agent.get("speed") or "balanced").strip()[:40]
        reasoning = str(agent.get("reasoning") or "medium").strip()[:40]
        dispatcher_role = self._agent_role_for_dispatcher(role)

        history_lines: list[str] = []
        for raw_item in history[-8:]:
            if not isinstance(raw_item, dict):
                continue
            speaker = str(raw_item.get("speaker") or raw_item.get("role") or "").strip()[:20]
            text = str(raw_item.get("text") or raw_item.get("content") or "").strip()
            if speaker and text:
                history_lines.append(f"{speaker}: {text[:1000]}")
        history_text = "\n".join(history_lines) if history_lines else "No previous mini-chat messages."

        return (
            f"orchestrator {dispatcher_role} "
            "Answer as the selected visual agent in the mini-orchestrator UI.\n\n"
            f"Agent name: {name}\n"
            f"Agent role: {role}\n"
            f"Selected model: {model}\n"
            f"Preferred speed: {speed}\n"
            f"Reasoning level: {reasoning}\n\n"
            "Keep the answer concise and useful for checking this agent's style. "
            "If the user asks who you are or which model/settings are selected, answer from these agent settings. "
            "Do not edit files, run commands, or claim that the visual flow is executing.\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            f"User message:\n{message}"
        )

    def _task_from_payload(self, payload: Dict[str, Any]) -> str:
        task = str(payload.get("task") or payload.get("goal") or "").strip()
        if not task:
            raise ValueError("Field 'task' is required.")
        return task

    def do_POST(self) -> None:
        path = self._path()
        if path not in {"/api/run", "/api/dispatcher/plan", "/api/dispatcher/run", "/api/agents/chat"}:
            self._http_error(404, "Unknown endpoint.")
            return

        try:
            payload = self._read_json()
        except ValueError as exc:
            self._http_error(400, str(exc))
            return

        if path == "/api/run":
            goal = str(payload.get("goal", "")).strip()
            if not goal:
                self._http_error(400, "Field 'goal' is required.")
                return

            try:
                state = self.orchestrator.run(goal)
                self._json_response(200, self.orchestrator.to_dict(state))
            except Exception as exc:
                self._http_error(500, f"Core orchestrator failed: {exc}")
            return

        if path == "/api/dispatcher/plan":
            try:
                task = self._task_from_payload(payload)
                mode = str(
                    payload.get("mode")
                    or os.environ.get("MINI_ORCHESTRATOR_PLAN_PREVIEW_MODE")
                    or "demo"
                ).strip().casefold()
                if mode not in {"demo", "dry-run", "real"}:
                    self._http_error(400, "Field 'mode' must be 'demo' or 'real'.")
                    return
                dispatcher_args = ["--task", task, "--plan-only"]
                if mode in {"demo", "dry-run"}:
                    dispatcher_args.append("--dry-run")
                result = self._run_dispatcher(
                    dispatcher_args,
                    timeout_seconds=120 if mode == "real" else 30,
                )
                result.setdefault("previewMode", "real" if mode == "real" else "demo")
                self._json_response(200, result)
            except ValueError as exc:
                self._http_error(400, str(exc))
            except subprocess.TimeoutExpired:
                self._http_error(504, "Dispatcher plan preview timed out.")
            except Exception as exc:
                self._json_response(502, {"error": "Dispatcher plan preview failed.", "detail": str(exc)})
            return

        if path == "/api/dispatcher/run":
            try:
                task = self._task_from_payload(payload)
                if payload.get("approved") is not True:
                    self._http_error(400, "Field 'approved' must be true before running the workflow.")
                    return
                result = self._run_dispatcher(
                    ["--task", task, "--local-test-project"],
                    timeout_seconds=120,
                )
                self._json_response(200, result)
            except ValueError as exc:
                self._http_error(400, str(exc))
            except subprocess.TimeoutExpired:
                self._http_error(504, "Approved local workflow timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/chat":
            try:
                agent_value = payload.get("agent", {})
                if not isinstance(agent_value, dict):
                    self._http_error(400, "Field 'agent' must be an object.")
                    return
                message = str(payload.get("message", "")).strip()
                if not message:
                    self._http_error(400, "Field 'message' is required.")
                    return
                model = str(agent_value.get("llm") or "").strip()
                if not model:
                    self._http_error(400, "Agent field 'llm' is required.")
                    return
                if model.casefold() == "rules":
                    self._http_error(400, "This agent uses rules fallback, not a live LLM model.")
                    return
                history_value = payload.get("history", [])
                history = history_value if isinstance(history_value, list) else []
                task = self._agent_chat_task(agent_value, message[:4000], history)
                task_file_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        "w",
                        encoding="utf-8",
                        prefix="mini-orchestrator-agent-chat-",
                        suffix=".txt",
                        delete=False,
                    ) as task_file:
                        task_file.write(task)
                        task_file_path = Path(task_file.name)
                    result = self._run_dispatcher(
                        [
                            "--task-file",
                            str(task_file_path),
                            "--model",
                            model,
                            "--use-worker-models",
                            "--turn-timeout-seconds",
                            "120",
                        ],
                        timeout_seconds=150,
                    )
                finally:
                    if task_file_path:
                        try:
                            task_file_path.unlink()
                        except OSError:
                            pass
                agents = result.get("agents") if isinstance(result, dict) else {}
                if not isinstance(agents, dict) or not agents:
                    self._http_error(502, "Dispatcher did not return an agent response.")
                    return
                response_text = str(next(iter(agents.values()))).strip()
                if not response_text:
                    detail = self._dispatcher_failure_detail(result)
                    message_detail = f" Details: {detail}" if detail else ""
                    self._http_error(502, f"Dispatcher returned an empty agent response.{message_detail}")
                    return
                self._json_response(
                    200,
                    {
                        "agent": {
                            "name": str(agent_value.get("name") or "Agent"),
                            "role": str(agent_value.get("role") or "Agent"),
                            "llm": model,
                            "speed": str(agent_value.get("speed") or "balanced"),
                            "reasoning": str(agent_value.get("reasoning") or "medium"),
                        },
                        "message": response_text,
                        "dispatcher": {
                            "mode": result.get("mode"),
                            "log": result.get("log"),
                            "dispatchDecision": result.get("dispatchDecision"),
                        },
                    },
                )
            except subprocess.TimeoutExpired:
                self._http_error(504, "Agent mini chat timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

    def do_GET(self) -> None:
        path = self._path()
        static_pages = {
            "/": "index.html",
            "/index.html": "index.html",
            "/agents-builder": "agents-builder.html",
            "/agents-builder.html": "agents-builder.html",
        }
        if path in static_pages:
            file_path = self.web_root / static_pages[path]
            if not file_path.exists():
                self._http_error(500, "UI file missing.")
                return
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/health":
            self._json_response(200, {"status": "ok"})
            return
        if path == "/agent/guide":
            self._json_response(
                200,
                {
                    "service": self.service_id,
                    "name": "Mini Orchestrator",
                    "purpose": "Local web UI and API for mini-orchestrator experiments.",
                    "allowedActions": [
                        "Open the dashboard and agent builder UI.",
                        "Run dispatcher plan preview through /api/dispatcher/plan.",
                        "Run approved local demo workflows through /api/dispatcher/run.",
                        "Test one visual agent card through /api/agents/chat.",
                    ],
                    "forbiddenActions": [
                        "Do not guess or bind fallback ports when config-service has no service record.",
                        "Do not treat browser-local agent flows as executable backend workflows.",
                        "Do not store secrets in config-service records or UI payloads.",
                    ],
                    "startup": {
                        "requiresConfigService": True,
                        "serviceId": self.service_id,
                        "portSource": "config-service service record baseUrl",
                    },
                    "contract": "/agent/contract",
                },
            )
            return
        if path == "/agent/contract":
            self._json_response(
                200,
                {
                    "service": self.service_id,
                    "version": 1,
                    "endpoints": {
                        "health": {"method": "GET", "path": "/health"},
                        "dashboard": {"method": "GET", "path": "/"},
                        "agentBuilder": {"method": "GET", "path": "/agents-builder"},
                        "coreRun": {
                            "method": "POST",
                            "path": "/api/run",
                            "required": ["goal"],
                        },
                        "dispatcherPlan": {
                            "method": "POST",
                            "path": "/api/dispatcher/plan",
                            "required": ["task"],
                        },
                        "dispatcherRun": {
                            "method": "POST",
                            "path": "/api/dispatcher/run",
                            "required": ["task", "approved"],
                        },
                        "agentMiniChat": {
                            "method": "POST",
                            "path": "/api/agents/chat",
                            "required": ["agent", "message"],
                        },
                    },
                    "capabilities": [
                        "orchestrator-dashboard",
                        "dispatcher-plan-preview",
                        "approved-local-demo-workflow",
                        "agent-card-mini-chat",
                    ],
                },
            )
            return
        self._http_error(404, "Not found.")

    def log_message(self, format: str, *args) -> None:
        # keep CLI output clean for app usage
        return


def run_ui_server(orchestrator: Orchestrator, ui_config: UiConfig) -> int:
    web_root = Path(__file__).parent / "web"

    handler = _OrchestratorUIHandler
    handler.orchestrator = orchestrator
    handler.web_root = web_root
    handler.service_id = ui_config.service_id
    address = (ui_config.host, ui_config.port)
    httpd = _ThreadedHttpServer(address, handler)
    url = f"http://{ui_config.host}:{ui_config.port}/"
    if ui_config.open_browser:
        webbrowser.open(url)

    print(f"Mini Orchestrator UI: {url}")
    if ui_config.base_url:
        print(f"Config-service record: {ui_config.service_id} -> {ui_config.base_url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down UI.")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0
