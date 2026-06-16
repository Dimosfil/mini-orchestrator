from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict
import json
import webbrowser

from .orchestrator import Orchestrator
from .llm import LlmRequestError, LlmUnavailable


@dataclass
class UiConfig:
    host: str
    port: int
    open_browser: bool


class _ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class _OrchestratorUIHandler(BaseHTTPRequestHandler):
    orchestrator: Orchestrator
    web_root: Path

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

    def do_POST(self) -> None:
        if self.path not in {"/api/run", "/api/campaign"}:
            self._http_error(404, "Unknown endpoint.")
            return

        try:
            payload = self._read_json()
        except ValueError as exc:
            self._http_error(400, str(exc))
            return

        if self.path == "/api/run":
            goal = str(payload.get("goal", "")).strip()
            if not goal:
                self._http_error(400, "Field 'goal' is required.")
                return

            state = self.orchestrator.run(goal)
            self._json_response(200, self.orchestrator.to_dict(state))
            return

        try:
            brief = str(payload.get("brief", "")).strip()
            target_audience = str(payload.get("target_audience", "")).strip()
            product_details = str(payload.get("product_details", "")).strip()
            tone = str(payload.get("tone", "")).strip()
            channels_value = payload.get("channels", [])
            if isinstance(channels_value, str):
                raw_channels = channels_value.split(",")
            elif isinstance(channels_value, list):
                raw_channels = channels_value
            else:
                raw_channels = []

            channels = [str(channel).strip() for channel in raw_channels if str(channel).strip()]

            if not brief or not target_audience or not product_details or not tone:
                self._http_error(400, "Fields 'brief', 'target_audience', 'product_details', and 'tone' are required.")
                return
            if not channels:
                self._http_error(400, "At least one channel is required.")
                return

            campaign = self.orchestrator.llm_client.generate_campaign(
                brief=brief,
                target_audience=target_audience,
                product_details=product_details,
                tone=tone,
                channels=channels,
            )
            self._json_response(200, campaign)
        except (LlmUnavailable, LlmRequestError) as exc:
            self._http_error(502, str(exc))
        except Exception as exc:
            self._http_error(500, f"Unexpected server error: {exc}")

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            file_path = self.web_root / "index.html"
            if not file_path.exists():
                self._http_error(500, "UI file missing.")
                return
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if self.path == "/health":
            self._json_response(200, {"status": "ok"})
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
    address = (ui_config.host, ui_config.port)
    httpd = _ThreadedHttpServer(address, handler)
    url = f"http://{ui_config.host}:{ui_config.port}/"
    if ui_config.open_browser:
        webbrowser.open(url)

    print(f"Mini Orchestrator UI: {url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down UI.")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0
