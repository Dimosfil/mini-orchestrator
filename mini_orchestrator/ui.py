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
import webbrowser
from urllib.parse import urlparse

from .agent_api import AgentApiError, VisualAgentApi
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

    def _task_from_payload(self, payload: Dict[str, Any]) -> str:
        task = str(payload.get("task") or payload.get("goal") or "").strip()
        if not task:
            raise ValueError("Field 'task' is required.")
        return task

    def do_POST(self) -> None:
        path = self._path()
        if path not in {
            "/api/run",
            "/api/dispatcher/plan",
            "/api/dispatcher/run",
            "/api/agents/chat",
            "/api/agents/translate-work-package",
        }:
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
                    or "real"
                ).strip().casefold()
                if mode not in {"dry-run", "real"}:
                    self._http_error(400, "Field 'mode' must be 'dry-run' or 'real'.")
                    return
                dispatcher_args = ["--task", task, "--plan-only"]
                if mode == "dry-run":
                    dispatcher_args.append("--dry-run")
                result = self._run_dispatcher(
                    dispatcher_args,
                    timeout_seconds=120 if mode == "real" else 30,
                )
                result.setdefault("previewMode", mode)
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
                    ["--task", task, "--chain"],
                    timeout_seconds=300,
                )
                self._json_response(200, result)
            except ValueError as exc:
                self._http_error(400, str(exc))
            except subprocess.TimeoutExpired:
                self._http_error(504, "Approved dispatcher workflow timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/chat":
            try:
                response = VisualAgentApi(
                    self._run_dispatcher,
                    self._dispatcher_failure_detail,
                ).chat(payload)
                self._json_response(200, response.payload)
            except AgentApiError as exc:
                self._http_error(exc.status, exc.message)
            except subprocess.TimeoutExpired:
                self._http_error(504, "Agent mini chat timed out.")
            except Exception as exc:
                self._http_error(500, str(exc))
            return

        if path == "/api/agents/translate-work-package":
            try:
                response = VisualAgentApi(
                    self._run_dispatcher,
                    self._dispatcher_failure_detail,
                    self.orchestrator.llm_client.translate_work_package_field,
                ).translate_work_package(payload)
                self._json_response(200, response.payload)
            except AgentApiError as exc:
                self._http_error(exc.status, exc.message)
            except subprocess.TimeoutExpired:
                self._http_error(504, "Agent work-package translation timed out.")
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
                        "Run approved dispatcher workflows through /api/dispatcher/run.",
                        "Test one visual agent card through /api/agents/chat.",
                        "Translate edited work-package helper text through /api/agents/translate-work-package.",
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
                        "agentWorkPackageTranslation": {
                            "method": "POST",
                            "path": "/api/agents/translate-work-package",
                            "required": ["text", "language"],
                        },
                    },
                    "capabilities": [
                        "orchestrator-dashboard",
                        "dispatcher-plan-preview",
                        "approved-dispatcher-workflow",
                        "agent-card-mini-chat",
                        "agent-work-package-translation",
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
