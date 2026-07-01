from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mini_orchestrator import runtime_store
from mini_orchestrator.agent_flows import AgentFlowError, validate_agent_flow


def main() -> int:
    parser = argparse.ArgumentParser(description="Run gi test through the saved Mini Orchestrator run settings.")
    parser.add_argument("--task", help="Release/full-system test task text.")
    parser.add_argument("--task-file", type=Path, help="File containing release/full-system test task text.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Mini Orchestrator UI/API base URL.")
    parser.add_argument("--request-timeout-seconds", type=float, default=7200.0, help="HTTP wait timeout for full-chain runs.")
    parser.add_argument("--timeout-per-step-seconds", type=float, default=900.0, help="Soft timeout for each Symphony handoff.")
    parser.add_argument(
        "--late-completion-grace-seconds",
        type=float,
        default=900.0,
        help="Extra wait for still-running Symphony handoffs before cutting the chain.",
    )
    args = parser.parse_args()

    task = _task_text(args.task, args.task_file)
    if not task:
        raise SystemExit("gi test requires --task or --task-file.")

    cleanup = {
        "deleted": runtime_store.clear_temporary_task_state(ROOT),
        "deletedFiles": runtime_store.clear_dispatcher_run_logs(ROOT),
        "deletedRuntimeFiles": runtime_store.clear_runtime_files(ROOT),
    }

    base_url = str(args.base_url).rstrip("/")
    config_payload = _get_json(f"{base_url}/api/current-run-config")
    config = config_payload.get("config")
    if not isinstance(config, dict):
        raise SystemExit(
            "No saved current run config found. Select a chain and execution mode in the UI, "
            "then click 'Выбрать!' and 'Confirm mode' before gi test."
        )

    presets = _get_json(f"{base_url}/api/agent-chain-presets").get("presets")
    if not isinstance(presets, list):
        raise SystemExit("Mini Orchestrator did not return agent chain presets.")
    chain_preset = next((item for item in presets if item.get("id") == config.get("chainPresetId")), None)
    if not isinstance(chain_preset, dict):
        raise SystemExit(f"Saved chain preset was not found: {config.get('chainPresetId')}")
    _validate_chain_preset(chain_preset)

    execution = str(config.get("executionMode") or "dispatcher").strip().casefold()
    worker_mode = str(config.get("symphonyWorkerMode") or "debug-new-worker").strip()
    payload: dict[str, Any] = {
        "task": task,
        "approved": True,
        "mode": "real",
        "executionMode": execution,
        "chainPreset": chain_preset,
    }
    if execution == "symphony":
        endpoint = "/api/symphony/runs"
        payload.update(
            {
                "background": False,
                "submitToSymphony": True,
                "orchestrationMode": "mini-owned-chain",
                "waitForCompletion": True,
                "symphonyWorkerMode": worker_mode,
                "timeoutPerStepSeconds": args.timeout_per_step_seconds,
                "lateCompletionGraceSeconds": args.late_completion_grace_seconds,
            }
        )
    elif execution == "dispatcher":
        endpoint = "/api/dispatcher/run"
        payload["background"] = False
    else:
        raise SystemExit(f"Unsupported execution mode: {execution}")

    result = _post_json(f"{base_url}{endpoint}", payload, timeout=args.request_timeout_seconds)
    print(
        json.dumps(
            {
                "status": "ok",
                "baseUrl": base_url,
                "endpoint": endpoint,
                "cleanup": cleanup,
                "selected": {
                    "chainPresetId": chain_preset.get("id"),
                    "chainPresetName": chain_preset.get("name"),
                    "executionMode": execution,
                    "symphonyWorkerMode": worker_mode,
                },
                "result": result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _task_text(task: str | None, task_file: Path | None) -> str:
    if task is not None:
        return task.strip()
    if task_file is not None:
        return task_file.read_text(encoding="utf-8-sig").strip()
    return ""


def _validate_chain_preset(chain_preset: dict[str, Any]) -> None:
    flow = chain_preset.get("flow")
    if not isinstance(flow, dict):
        raise SystemExit("Saved chain preset is missing flow.")
    try:
        validation = validate_agent_flow(
            {
                **flow,
                "updatedAt": str(chain_preset.get("updatedAt") or flow.get("updatedAt") or runtime_store.utc_now()),
            }
        )
    except AgentFlowError as exc:
        raise SystemExit(f"Saved chain preset cannot be validated: {exc}") from exc
    if not validation["valid"]:
        messages = "; ".join(str(error.get("message") or error.get("code")) for error in validation["errors"])
        raise SystemExit(f"Saved chain preset is invalid and gi test is blocked: {messages}")


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    return _read_json(request)


def _post_json(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return _read_json(request, timeout=timeout)


def _read_json(request: urllib.request.Request, *, timeout: float = 1800.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {request.full_url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach Mini Orchestrator API at {request.full_url}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Non-JSON response from {request.full_url}: {raw[:500]}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Unexpected JSON response from {request.full_url}: {type(payload).__name__}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
