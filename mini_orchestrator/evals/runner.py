from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import re
import subprocess
import time
import uuid

from .. import runtime_store
from ..command_adapter import run_command_argv, split_command, validate_command


WorkflowRunner = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TIMEOUT_SECONDS = 600.0
DEFAULT_OUTPUT_LIMIT = 8000
ALLOWED_COMMANDS = {
    "node",
    "npm",
    "npx",
    "pnpm",
    "py",
    "pytest",
    "python",
    "python3",
    "yarn",
}


class EvalError(ValueError):
    pass


def upsert_eval_suite(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    suite = normalize_suite(payload)
    now = runtime_store.utc_now()
    current = runtime_store.get_json_document(root, "eval_suites", suite["id"])
    suite["createdAt"] = str((current or {}).get("createdAt") or suite.get("createdAt") or now)
    suite["updatedAt"] = now
    runtime_store.upsert_json_document(root, "eval_suites", suite["id"], suite)
    return suite


def read_eval_suite(root: Path, suite_id: str) -> dict[str, Any]:
    normalized_id = _validate_id(suite_id, "Eval suite id")
    suite = runtime_store.get_json_document(root, "eval_suites", normalized_id)
    if suite is None:
        raise EvalError("Eval suite was not found.")
    return normalize_suite(suite)


def list_eval_suites(root: Path) -> list[dict[str, Any]]:
    suites = []
    for suite in runtime_store.list_json_documents(root, "eval_suites"):
        try:
            normalized = normalize_suite(suite)
        except EvalError:
            continue
        suites.append(
            {
                "id": normalized["id"],
                "name": normalized["name"],
                "caseCount": len(normalized["cases"]),
                "createdAt": str(normalized.get("createdAt") or ""),
                "updatedAt": str(normalized.get("updatedAt") or ""),
            }
        )
    return suites


def run_eval_suite(
    root: Path,
    suite_payload: dict[str, Any],
    *,
    case_id: str | None = None,
    artifact_path: str | None = None,
    workflow_runner: WorkflowRunner | None = None,
) -> dict[str, Any]:
    suite = normalize_suite(suite_payload)
    root = root.resolve()
    selected_cases = _selected_cases(suite, case_id)
    now = runtime_store.utc_now()
    run_id = f"eval-{uuid.uuid4().hex[:12]}"
    run_payload: dict[str, Any] = {
        "runId": run_id,
        "suiteId": suite["id"],
        "suiteName": suite["name"],
        "caseId": str(case_id or ""),
        "status": "running",
        "createdAt": now,
        "updatedAt": now,
    }
    runtime_store.upsert_json_document(root, "eval_runs", run_id, run_payload)

    all_results: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []
    artifact_records: list[dict[str, Any]] = []

    for case in selected_cases:
        workflow_result: dict[str, Any] = {}
        if case.get("runWorkflow") is True:
            if workflow_runner is None:
                all_results.append(
                    _result(
                        str(case.get("id") or "workflow"),
                        "workflow",
                        "failed",
                        "Case requested workflow execution, but no existing orchestrator adapter was configured.",
                    )
                )
            else:
                started = time.perf_counter()
                try:
                    workflow_result = workflow_runner(suite, case)
                    all_results.append(
                        _result(
                            f"{case['id']}:workflow",
                            "workflow",
                            "passed",
                            "Existing orchestrator workflow completed.",
                            details={
                                "durationSeconds": round(time.perf_counter() - started, 3),
                                "workflow": _compact_json(workflow_result),
                            },
                        )
                    )
                except Exception as exc:
                    all_results.append(
                        _result(
                            f"{case['id']}:workflow",
                            "workflow",
                            "failed",
                            f"Existing orchestrator workflow failed: {exc}",
                            details={"durationSeconds": round(time.perf_counter() - started, 3)},
                        )
                    )

        artifact = locate_artifact(root, suite, case, workflow_result, artifact_path)
        artifact_records.append(
            {
                "artifactId": f"{run_id}-{case['id']}",
                "runId": run_id,
                "caseId": case["id"],
                "path": artifact.get("path") or "",
                "status": artifact["status"],
                "message": artifact["message"],
                "createdAt": now,
                "updatedAt": runtime_store.utc_now(),
            }
        )
        runtime_store.upsert_json_document(root, "eval_artifacts", artifact_records[-1]["artifactId"], artifact_records[-1])

        case_results: list[dict[str, Any]] = []
        if artifact["status"] != "found":
            case_results.append(
                _result(
                    f"{case['id']}:artifact",
                    "artifact_locator",
                    "failed",
                    artifact["message"],
                    details={"path": artifact.get("path") or ""},
                )
            )
        else:
            artifact_dir = Path(str(artifact["path"]))
            for index, check in enumerate(case["checks"], start=1):
                case_results.append(evaluate_check(root, artifact_dir, check, index))

        all_results.extend(case_results)
        failed = sum(1 for item in case_results if item["status"] != "passed")
        case_reports.append(
            {
                "caseId": case["id"],
                "status": "passed" if failed == 0 and case_results else "failed",
                "artifact": artifact,
                "checks": len(case_results),
                "failed": failed,
            }
        )

    failed_count = sum(1 for item in all_results if item["status"] != "passed")
    status = "passed" if failed_count == 0 and all_results else "failed"
    completed_at = runtime_store.utc_now()
    report = {
        "reportId": run_id,
        "runId": run_id,
        "suiteId": suite["id"],
        "suiteName": suite["name"],
        "caseId": str(case_id or ""),
        "status": status,
        "summary": {
            "cases": len(case_reports),
            "checks": len(all_results),
            "passed": sum(1 for item in all_results if item["status"] == "passed"),
            "failed": failed_count,
        },
        "cases": case_reports,
        "results": all_results,
        "artifacts": artifact_records,
        "createdAt": now,
        "updatedAt": completed_at,
    }
    run_payload.update(
        {
            "status": status,
            "updatedAt": completed_at,
            "summary": report["summary"],
            "reportId": run_id,
        }
    )
    runtime_store.upsert_json_document(root, "eval_runs", run_id, run_payload)
    runtime_store.replace_eval_results(root, run_id, all_results)
    runtime_store.upsert_json_document(root, "eval_reports", run_id, report)
    return report


def normalize_suite(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EvalError("Eval suite must be an object.")
    suite_id = _validate_id(payload.get("id") or _slug(str(payload.get("name") or "eval-suite")), "Eval suite id")
    cases_value = payload.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        raise EvalError("Eval suite field 'cases' must be a non-empty array.")
    cases = [_normalize_case(case, index) for index, case in enumerate(cases_value)]
    return {
        **payload,
        "id": suite_id,
        "name": _limited_text(payload.get("name"), "Eval suite", 120),
        "cases": cases,
        "createdAt": str(payload.get("createdAt") or ""),
        "updatedAt": str(payload.get("updatedAt") or ""),
    }


def locate_artifact(
    root: Path,
    suite: dict[str, Any],
    case: dict[str, Any],
    workflow_result: dict[str, Any] | None = None,
    override_path: str | None = None,
) -> dict[str, Any]:
    candidates = [
        override_path,
        case.get("artifactPath"),
        _nested_text(case.get("artifact"), "path"),
        _nested_text(case.get("expectedArtifacts"), "projectDir"),
        _nested_text(workflow_result, "artifactPath"),
        _nested_text(workflow_result, "projectDir"),
    ]
    fallback = root / ".mini_orchestrator" / "test-runs" / suite["id"] / case["id"]
    if fallback.exists():
        candidates.append(str(fallback))

    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        try:
            path = _resolve_inside(root, text)
        except EvalError as exc:
            return {"status": "failed", "path": text, "message": str(exc)}
        if not path.exists():
            return {
                "status": "missing",
                "path": str(path),
                "message": f"Artifact path does not exist: {path}",
            }
        if not path.is_dir():
            return {
                "status": "failed",
                "path": str(path),
                "message": f"Artifact path is not a directory: {path}",
            }
        return {"status": "found", "path": str(path), "message": "Artifact located."}

    return {"status": "missing", "path": "", "message": "No artifact path was provided or discovered."}


def evaluate_check(root: Path, artifact_dir: Path, check: dict[str, Any], index: int) -> dict[str, Any]:
    check_type = str(check.get("type") or "").strip().casefold()
    check_id = str(check.get("id") or f"{check_type or 'check'}-{index}").strip()
    started_at = runtime_store.utc_now()
    started = time.perf_counter()
    try:
        if check_type == "file_exists":
            result = _check_file_exists(artifact_dir, check, check_id)
        elif check_type == "directory_exists":
            result = _check_directory_exists(artifact_dir, check, check_id)
        elif check_type == "json_valid":
            result = _check_json_valid(artifact_dir, check, check_id)
        elif check_type == "file_contains":
            result = _check_file_contains(artifact_dir, check, check_id)
        elif check_type in {"command", "build_pass", "test_pass"}:
            result = _check_command(artifact_dir, check, check_id, check_type)
        elif check_type == "server_start":
            result = _check_server_start(artifact_dir, check, check_id)
        elif check_type == "http_check":
            result = _check_http(check, check_id)
        elif check_type == "log_scan":
            result = _check_log_scan(artifact_dir, check, check_id)
        elif check_type == "artifact_manifest_check":
            result = _check_artifact_manifest(artifact_dir, check, check_id)
        else:
            result = _result(check_id, check_type or "unknown", "failed", f"Unsupported evaluator type: {check_type or '<empty>'}")
    except Exception as exc:
        result = _result(check_id, check_type or "unknown", "failed", str(exc))

    result["startedAt"] = started_at
    result["completedAt"] = runtime_store.utc_now()
    result["durationSeconds"] = round(time.perf_counter() - started, 3)
    result["artifactRoot"] = str(artifact_dir)
    return result


def _normalize_case(case: Any, index: int) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise EvalError(f"Eval case at index {index} must be an object.")
    case_id = _validate_id(case.get("id") or f"case-{index + 1}", "Eval case id")
    checks = case.get("checks")
    if not isinstance(checks, list) or not checks:
        raise EvalError(f"Eval case '{case_id}' field 'checks' must be a non-empty array.")
    normalized_checks = []
    for check_index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise EvalError(f"Eval case '{case_id}' check at index {check_index} must be an object.")
        normalized_checks.append(check)
    return {**case, "id": case_id, "checks": normalized_checks}


def _selected_cases(suite: dict[str, Any], case_id: str | None) -> list[dict[str, Any]]:
    if not case_id:
        return list(suite["cases"])
    normalized_id = _validate_id(case_id, "Eval case id")
    selected = [case for case in suite["cases"] if case["id"] == normalized_id]
    if not selected:
        raise EvalError("Eval case was not found in the suite.")
    return selected


def _check_file_exists(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    path = _check_path(artifact_dir, check)
    if path.is_file():
        return _result(check_id, "file_exists", "passed", f"File exists: {_display_path(path, artifact_dir)}")
    return _result(check_id, "file_exists", "failed", f"Expected file is missing: {_display_path(path, artifact_dir)}")


def _check_directory_exists(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    path = _check_path(artifact_dir, check)
    if path.is_dir():
        return _result(check_id, "directory_exists", "passed", f"Directory exists: {_display_path(path, artifact_dir)}")
    return _result(check_id, "directory_exists", "failed", f"Expected directory is missing: {_display_path(path, artifact_dir)}")


def _check_json_valid(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    path = _check_path(artifact_dir, check)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return _result(
        check_id,
        "json_valid",
        "passed",
        f"JSON file is valid: {_display_path(path, artifact_dir)}",
        details={"rootType": type(data).__name__},
    )


def _check_file_contains(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    path = _check_path(artifact_dir, check)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    required = _string_list(check.get("contains"))
    forbidden = _string_list(check.get("notContains"))
    missing = [item for item in required if item not in text]
    present_forbidden = [item for item in forbidden if item in text]
    if missing or present_forbidden:
        return _result(
            check_id,
            "file_contains",
            "failed",
            "File content expectations failed.",
            details={"missing": missing, "forbiddenPresent": present_forbidden},
        )
    return _result(check_id, "file_contains", "passed", "File content expectations passed.")


def _check_command(artifact_dir: Path, check: dict[str, Any], check_id: str, check_type: str) -> dict[str, Any]:
    command = check.get("command")
    if not command:
        return _result(check_id, check_type, "failed", "Command check requires field 'command'.")
    cwd = _resolve_inside(artifact_dir, str(check.get("cwd") or "."))
    _ensure_allowed_command(command)
    timeout = _timeout(check)
    output_limit = _positive_int(check.get("outputLimit"), DEFAULT_OUTPUT_LIMIT)
    expected = _positive_or_zero_int(check.get("expectedExitCode"), 0)
    completed = run_command_argv(command, cwd, timeout, output_limit)
    details = {
        "command": completed.command,
        "cwd": str(cwd),
        "exitCode": completed.exit_code,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.exit_code == expected:
        return _result(check_id, check_type, "passed", f"Command exited with {completed.exit_code}.", details=details)
    return _result(
        check_id,
        check_type,
        "failed",
        f"Command exited with {completed.exit_code}; expected {expected}.",
        details=details,
    )


def _check_server_start(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    command = check.get("command")
    if not command:
        return _result(check_id, "server_start", "failed", "Server check requires field 'command'.")
    cwd = _resolve_inside(artifact_dir, str(check.get("cwd") or "."))
    _ensure_allowed_command(command)
    timeout = _timeout(check)
    output_limit = _positive_int(check.get("outputLimit"), DEFAULT_OUTPUT_LIMIT)
    wait_seconds = min(float(check.get("startupWaitSeconds") or 2), timeout)
    argv = _argv(command)
    process = subprocess.Popen(
        argv,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(wait_seconds)
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            return _result(
                check_id,
                "server_start",
                "failed",
                f"Server process exited early with {process.returncode}.",
                details={
                    "command": argv,
                    "exitCode": process.returncode,
                    "stdout": (stdout or "")[:output_limit],
                    "stderr": (stderr or "")[:output_limit],
                },
            )
        url = str(check.get("url") or "").strip()
        if url:
            http_result = _http_request(url, float(check.get("httpTimeoutSeconds") or 5))
            expected_status = _positive_int(check.get("expectedStatus"), 200)
            if http_result["status"] != expected_status:
                return _result(
                    check_id,
                    "server_start",
                    "failed",
                    f"Server HTTP status {http_result['status']}; expected {expected_status}.",
                    details={"command": argv, "http": http_result},
                )
        return _result(check_id, "server_start", "passed", "Server stayed running during startup check.", details={"command": argv})
    finally:
        _terminate_process(process)


def _check_http(check: dict[str, Any], check_id: str) -> dict[str, Any]:
    url = str(check.get("url") or "").strip()
    if not url:
        return _result(check_id, "http_check", "failed", "HTTP check requires field 'url'.")
    expected_status = _positive_int(check.get("expectedStatus"), 200)
    response = _http_request(url, float(check.get("timeoutSeconds") or 10))
    details = {"url": url, **response}
    contains = str(check.get("contains") or "")
    if response["status"] != expected_status:
        return _result(check_id, "http_check", "failed", f"HTTP status {response['status']}; expected {expected_status}.", details=details)
    if contains and contains not in str(response.get("body") or ""):
        return _result(check_id, "http_check", "failed", "HTTP body did not contain expected text.", details=details)
    return _result(check_id, "http_check", "passed", f"HTTP status {response['status']}.", details=details)


def _check_log_scan(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    path = _check_path(artifact_dir, check)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    fail_patterns = _string_list(check.get("failPatterns"))
    require_patterns = _string_list(check.get("requirePatterns"))
    matched_failures = [pattern for pattern in fail_patterns if re.search(pattern, text, flags=re.IGNORECASE)]
    missing_required = [pattern for pattern in require_patterns if not re.search(pattern, text, flags=re.IGNORECASE)]
    if matched_failures or missing_required:
        return _result(
            check_id,
            "log_scan",
            "failed",
            "Log scan expectations failed.",
            details={"matchedFailures": matched_failures, "missingRequired": missing_required},
        )
    return _result(check_id, "log_scan", "passed", "Log scan expectations passed.")


def _check_artifact_manifest(artifact_dir: Path, check: dict[str, Any], check_id: str) -> dict[str, Any]:
    manifest_path = _resolve_inside(artifact_dir, str(check.get("path") or "artifactManifest.json"))
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return _result(check_id, "artifact_manifest_check", "failed", "Artifact manifest must be a JSON object.")
    required = _string_list(check.get("requiredFields"))
    missing = [field for field in required if field not in payload]
    if missing:
        return _result(check_id, "artifact_manifest_check", "failed", "Artifact manifest is missing required fields.", details={"missing": missing})
    return _result(check_id, "artifact_manifest_check", "passed", "Artifact manifest passed.", details={"fields": sorted(payload)})


def _http_request(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "mini-orchestrator-eval/1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {"status": int(response.status), "body": body}
    except HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return {"status": int(exc.code), "body": body}
    except URLError as exc:
        return {"status": 0, "body": "", "error": str(exc.reason)}


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _check_path(artifact_dir: Path, check: dict[str, Any]) -> Path:
    raw_path = str(check.get("path") or "").strip()
    if not raw_path:
        raise EvalError("Check requires field 'path'.")
    return _resolve_inside(artifact_dir, raw_path)


def _resolve_inside(base: Path, value: str) -> Path:
    base = base.resolve()
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (base / path).resolve()
    if resolved != base and base not in resolved.parents:
        raise EvalError(f"Path escapes allowed root: {value}")
    return resolved


def _ensure_allowed_command(command: Any) -> None:
    if isinstance(command, str):
        blocker = validate_command(command)
        if blocker:
            raise EvalError(blocker)
        argv = split_command(command)
    elif isinstance(command, list):
        argv = [str(part) for part in command]
        blocker = validate_command(" ".join(argv))
        if blocker:
            raise EvalError(blocker)
    else:
        raise EvalError("Command must be a string or an array.")
    if not argv:
        raise EvalError("Command is empty.")
    executable = Path(argv[0]).name.casefold()
    stem = Path(executable).stem.casefold()
    if stem not in ALLOWED_COMMANDS:
        raise EvalError(f"Command executable is not allowed for eval checks: {argv[0]}")


def _argv(command: Any) -> list[str]:
    if isinstance(command, str):
        return split_command(command)
    return [str(part) for part in command]


def _timeout(check: dict[str, Any]) -> float:
    try:
        value = float(check.get("timeoutSeconds") or DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_SECONDS
    return max(0.1, min(value, MAX_TIMEOUT_SECONDS))


def _positive_int(value: Any, fallback: int) -> int:
    parsed = _positive_or_zero_int(value, fallback)
    return parsed if parsed > 0 else fallback


def _positive_or_zero_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None:
        return []
    text = str(value)
    return [text] if text else []


def _nested_text(value: Any, key: str) -> str:
    if isinstance(value, dict):
        return str(value.get(key) or "").strip()
    return ""


def _validate_id(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if not ID_PATTERN.match(text):
        raise EvalError(f"{label} must be a lowercase slug.")
    return text


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
    return slug[:100].strip("-") or "eval-suite"


def _limited_text(value: Any, fallback: str, limit: int) -> str:
    text = str(value or "").strip()
    return (text or fallback)[:limit]


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _compact_json(value: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= 4000:
        return value
    return {"truncated": True, "chars": len(text)}


def _result(
    check_id: str,
    check_type: str,
    status: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "checkId": check_id,
        "type": check_type,
        "status": status,
        "message": message,
        "details": details or {},
    }
