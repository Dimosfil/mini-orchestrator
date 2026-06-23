from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mini_orchestrator import runtime_store

from models import Worker
from pipeline import run_pipeline as pipeline_run_pipeline
from worker_profiles import workers_from_chain_preset, workers_from_chain_preset_file
from worknest_client import load_worknest_task


def print_json(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def main(root: Path, runs_dir: Path, workers: list[Worker]) -> int:
    parser = argparse.ArgumentParser(description="Run Codex-native dispatcher.")
    parser.add_argument("--task", help="Task to classify and route to one dispatcher worker.")
    parser.add_argument("--task-file", help="UTF-8 text file containing the task to classify and route.")
    parser.add_argument("--run-id", help="Stable run id used for the generated JSONL log filename.")
    parser.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--chain", action="store_true", help="Run planner -> executor -> reviewer instead of one selected worker.")
    parser.add_argument("--chain-preset-file", help="JSON file containing the selected dashboard agent chain preset.")
    parser.add_argument("--chain-preset-id", help="Run id whose selected dashboard chain preset is stored in runtime SQLite.")
    parser.add_argument("--plan-only", action="store_true", help="Return only a chat approval plan without writing project files.")
    parser.add_argument("--from-worknest", action="store_true", help="Claim the next task from the configured WorkNest manager.")
    parser.add_argument("--project", default="mini-orchestrator", help="WorkNest project id for --from-worknest.")
    parser.add_argument("--config-service-url", help="Override GI config-service URL for manager discovery.")
    parser.add_argument("--codex-command", help="Path to the Codex CLI executable or command shim.")
    parser.add_argument("--model", help="Override worker model labels passed to app-server.")
    parser.add_argument(
        "--use-worker-models",
        dest="use_worker_models",
        action="store_true",
        default=True,
        help="Pass worker model names to app-server. This is the default.",
    )
    parser.add_argument(
        "--use-codex-default-models",
        dest="use_worker_models",
        action="store_false",
        help="Do not pass worker model names; let Codex config choose the model.",
    )
    parser.add_argument("--request-timeout-seconds", type=float, default=30, help="Timeout for app-server request responses.")
    parser.add_argument("--turn-timeout-seconds", type=float, default=90, help="Timeout for each agent turn.")
    args = parser.parse_args()
    if args.dry_run and os.environ.get("MINI_ORCHESTRATOR_ENABLE_LEGACY_DRY_RUN") != "1":
        parser.error("--dry-run is retired for dispatcher CLI. Use real Codex/Symphony execution.")

    started = time.time()
    task_text = args.task
    if args.task_file:
        task_path = Path(args.task_file)
        if not task_path.is_absolute():
            task_path = (root / task_path).resolve()
        resolved_task_path = task_path.resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if not (path_is_inside(resolved_task_path, root) or path_is_inside(resolved_task_path, temp_root)):
            raise ValueError(f"--task-file must stay inside {root} or {temp_root}. Got: {resolved_task_path}")
        task_text = resolved_task_path.read_text(encoding="utf-8-sig")
    if args.from_worknest:
        worknest_task = load_worknest_task(args.project, args.config_service_url)
        task_text = f"{worknest_task.title}\n\nWhat to do:\n{worknest_task.what_to_do}\n\nDone when:\n{worknest_task.definition_of_done}"
    if not task_text:
        parser.error("--task is required unless --from-worknest is used.")

    selected_workers = workers
    if args.chain_preset_id:
        chain_preset = runtime_store.get_dispatcher_chain_preset(root, args.chain_preset_id)
        if chain_preset is None:
            raise ValueError(f"Stored chain preset was not found: {args.chain_preset_id}")
        selected_workers = workers_from_chain_preset(chain_preset, root)
    if args.chain_preset_file:
        preset_path = Path(args.chain_preset_file)
        if not preset_path.is_absolute():
            preset_path = (root / preset_path).resolve()
        resolved_preset_path = preset_path.resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if not (path_is_inside(resolved_preset_path, root) or path_is_inside(resolved_preset_path, temp_root)):
            raise ValueError(f"--chain-preset-file must stay inside {root} or {temp_root}. Got: {resolved_preset_path}")
        selected_workers = workers_from_chain_preset_file(resolved_preset_path, root)
    if args.model:
        selected_workers = [
            Worker(
                worker.name,
                args.model,
                worker.reasoning,
                worker.instructions_path,
                access_mode=worker.access_mode,
                source_agent_id=worker.source_agent_id,
                instructions_text=worker.instructions_text,
            )
            for worker in selected_workers
        ]

    mode = "plan" if args.plan_only else "chain" if args.chain else "single"
    try:
        log_path, outputs, decision = pipeline_run_pipeline(
            task_text,
            args.dry_run,
            selected_workers,
            args.codex_command,
            args.request_timeout_seconds,
            args.turn_timeout_seconds,
            args.use_worker_models,
            root=root,
            runs_dir=runs_dir,
            run_id=args.run_id,
            chain=args.chain,
            plan_only=args.plan_only,
        )
    except (RuntimeError, ValueError, TimeoutError) as exc:
        print_json(
            {
                "status": "error",
                "durationSeconds": round(time.time() - started, 2),
                "mode": mode,
                "planOnly": args.plan_only,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
        return 1
    print_json(
        {
            "status": "ok",
            "log": str(log_path.relative_to(root)),
            "durationSeconds": round(time.time() - started, 2),
            "mode": mode,
            "planOnly": args.plan_only,
            "dispatchDecision": {
                "role": decision.role,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "nextInput": decision.next_input,
            },
            "agents": outputs,
        }
    )
    return 0
