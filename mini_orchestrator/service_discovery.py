from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG_PATH = ROOT / "tools" / "project-memory" / "service-runtime.json"


class ConfigServiceBlocker(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectServiceRuntimeConfig:
    service_id: str
    self_registration: str
    config_service_url: str | None


@dataclass(frozen=True)
class ResolvedUiRuntime:
    host: str
    port: int
    base_url: str
    service_id: str
    config_service_url: str
    endpoints: dict[str, str]


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigServiceBlocker(f"Project service runtime config is missing: {path}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigServiceBlocker(f"Project service runtime config is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ConfigServiceBlocker(f"Project service runtime config must be a JSON object: {path}")
    return payload


def load_project_service_runtime_config() -> ProjectServiceRuntimeConfig:
    payload = _load_json_file(RUNTIME_CONFIG_PATH)
    service_id = str(payload.get("service_id") or "").strip()
    if not service_id:
        raise ConfigServiceBlocker("Project service runtime config must define service_id.")
    self_registration = str(payload.get("self_registration") or "off").strip().lower()
    if self_registration not in {"on", "off"}:
        raise ConfigServiceBlocker("Project service runtime config self_registration must be 'on' or 'off'.")
    config_service_url = payload.get("configServiceUrl")
    if config_service_url is not None:
        config_service_url = str(config_service_url).strip() or None
    return ProjectServiceRuntimeConfig(
        service_id=service_id,
        self_registration=self_registration,
        config_service_url=config_service_url,
    )


def _validate_config_service_url(url: str, source: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigServiceBlocker(f"Config-service URL from {source} must be a full http:// or https:// URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigServiceBlocker(f"Config-service URL from {source} must not contain credentials, query, or fragment.")
    return url.rstrip("/")


def _gi_main_config_candidates() -> list[Path]:
    candidates: list[Path] = []
    home = os.environ.get("GENERAL_INSTRUCTIONS_HOME")
    if home:
        candidates.append(Path(home) / "config" / "gi-main.json")
    candidates.append(ROOT.parent / "general-instructions" / "config" / "gi-main.json")
    return candidates


def resolve_config_service_url(project_config: ProjectServiceRuntimeConfig) -> str:
    for env_name in ("MINI_ORCHESTRATOR_CONFIG_SERVICE_URL", "GI_CONFIG_SERVICE_URL"):
        value = os.environ.get(env_name)
        if value:
            return _validate_config_service_url(value.strip(), env_name)

    if project_config.config_service_url:
        return _validate_config_service_url(project_config.config_service_url, str(RUNTIME_CONFIG_PATH))

    for candidate in _gi_main_config_candidates():
        if not candidate.exists():
            continue
        payload = _load_json_file(candidate)
        value = str(payload.get("configServiceUrl") or "").strip()
        if value:
            return _validate_config_service_url(value, str(candidate))

    raise ConfigServiceBlocker(
        "Config-service URL is not configured. Set GENERAL_INSTRUCTIONS_HOME or "
        "MINI_ORCHESTRATOR_CONFIG_SERVICE_URL, or configure GI main config."
    )


def _get_json(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ConfigServiceBlocker(f"Config-service request failed with HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise ConfigServiceBlocker(f"Config-service is unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ConfigServiceBlocker("Config-service request timed out.") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ConfigServiceBlocker("Config-service response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ConfigServiceBlocker("Config-service response must be a JSON object.")
    return payload


def _resolve_base_url(record: dict[str, Any], service_id: str) -> tuple[str, str, int]:
    base_url = str(record.get("baseUrl") or "").strip().rstrip("/")
    if not base_url:
        raise ConfigServiceBlocker(f"Service record {service_id!r} has no baseUrl.")

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigServiceBlocker(f"Service record {service_id!r} baseUrl must be an HTTP URL.")
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return base_url, parsed.hostname, port


def _validate_service_record(record: dict[str, Any], service_id: str) -> tuple[str, str, int, dict[str, str]]:
    record_id = str(record.get("id") or record.get("service_id") or "").strip()
    if record_id != service_id:
        raise ConfigServiceBlocker(f"Config-service returned record {record_id!r}, expected {service_id!r}.")

    base_url, host, port = _resolve_base_url(record, service_id)
    endpoints_value = record.get("endpoints")
    if not isinstance(endpoints_value, dict):
        raise ConfigServiceBlocker(f"Service record {service_id!r} has no endpoints object.")
    endpoints = {str(key): str(value) for key, value in endpoints_value.items() if isinstance(value, str)}
    if not endpoints.get("availability"):
        raise ConfigServiceBlocker(f"Service record {service_id!r} has no endpoints.availability.")
    if not endpoints.get("api"):
        raise ConfigServiceBlocker(f"Service record {service_id!r} has no endpoints.api.")
    return base_url, host, port, endpoints


def resolve_ui_runtime(requested_host: str | None, requested_port: int | None) -> ResolvedUiRuntime:
    project_config = load_project_service_runtime_config()
    config_service_url = resolve_config_service_url(project_config)

    _get_json(f"{config_service_url}/health")
    service_url = f"{config_service_url}/services/{project_config.service_id}"
    try:
        record = _get_json(service_url)
    except ConfigServiceBlocker as exc:
        raise ConfigServiceBlocker(
            f"Cannot start UI: config-service has no usable record for "
            f"{project_config.service_id!r}. Details: {exc}"
        ) from exc

    base_url, host, port, endpoints = _validate_service_record(record, project_config.service_id)

    if requested_host and requested_host != host:
        raise ConfigServiceBlocker(
            f"Requested host {requested_host!r} does not match config-service host {host!r}."
        )
    if requested_port is not None and requested_port != port:
        raise ConfigServiceBlocker(
            f"Requested port {requested_port} does not match config-service port {port}."
        )

    if project_config.self_registration == "on":
        raise ConfigServiceBlocker(
            "self_registration is on, but config-service registration/refresh contract is not available. "
            "Set self_registration to off or add a documented registration endpoint."
        )

    return ResolvedUiRuntime(
        host=host,
        port=port,
        base_url=base_url,
        service_id=project_config.service_id,
        config_service_url=config_service_url,
        endpoints=endpoints,
    )
