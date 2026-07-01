from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys

from .config import parse_runtime_config
from . import runtime_store
from .evals import EvalError, list_eval_suites, read_eval_suite, run_eval_suite, upsert_eval_suite
from .orchestrator import Orchestrator
from .service_discovery import ConfigServiceBlocker, resolve_ui_runtime
from .ui import UiConfig, run_ui_server


def _print_state(state, orchestrator: Orchestrator) -> None:
    payload = orchestrator.to_dict(state)
    print(json.dumps(payload, ensure_ascii=False))


def _run_interactive_chat(orchestrator: Orchestrator) -> int:
    print("Mini Orchestrator interactive mode. Type 'exit', 'quit', or '/help'.")
    last_state = None
    while True:
        try:
            goal = input("orch> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not goal:
            continue

        lowered = goal.lower()
        if lowered in {"exit", "quit", "q", "/exit", "/quit", "/q"}:
            return 0

        if lowered in {"/help", "help"}:
            print("Commands:")
            print("  read AGENTS.md")
            print("  search something")
            print("  run git status")
            print("  patch AGENTS.md \"old\" \"new\"")
            print("  /state  - print last JSON state")
            print("  exit / quit")
            continue

        if lowered == "/state":
            if last_state is None:
                print("{}")
            else:
                print(json.dumps(last_state, ensure_ascii=False))
            continue

        state = orchestrator.run(goal)
        last_state = orchestrator.to_dict(state)
        _print_state(state, orchestrator)

    return 0


def run_from_args(argv=None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv[:1] == ["eval"]:
        return _run_eval_args(raw_argv[1:])

    parser = ArgumentParser(description="Mini orchestrator: plan -> execute -> validate")
    parser.add_argument(
        "goal",
        nargs="?",
        help="Goal text for the orchestrator",
    )
    parser.add_argument("--chat", action="store_true", help="Start interactive chat mode")
    parser.add_argument("--ui", action="store_true", help="Start web UI mode")
    parser.add_argument("--host", default=None, help="Expected host for UI mode; must match config-service")
    parser.add_argument("--port", type=int, default=None, help="Expected port for UI mode; must match config-service")
    parser.add_argument("--open-browser", action="store_true", help="Open browser when UI starts")
    parser.add_argument("--workdir", default=".", help="Workspace root for operations")
    parser.add_argument("--max-iterations", type=int, default=None, help="Maximum loop iterations")
    parser.add_argument("--max-retries", type=int, default=None, help="Maximum retries per step")
    parser.add_argument(
        "--llm-provider",
        default=None,
        choices=("auto", "openai", "rules", "off"),
        help="Planner LLM provider. auto uses OpenAI when OPENAI_API_KEY is set.",
    )
    parser.add_argument("--coordinator-model", default=None, help="Model for the LLM coordinator planner")
    parser.add_argument("--executor-model", default=None, help="Model label for executor-planned tool actions")
    parser.add_argument("--openai-base-url", default=None, help="OpenAI-compatible API base URL")
    parser.add_argument(
        "--log",
        default=str(Path(".mini_orchestrator/runs/orchestrator.log.jsonl")),
        help="JSONL log path",
    )
    parser.add_argument("--no-log", action="store_true", help="Disable JSONL logging")
    args = parser.parse_args(argv)

    config = parse_runtime_config(
        args.workdir,
        args.max_iterations,
        args.max_retries,
        llm_provider=args.llm_provider,
        coordinator_model=args.coordinator_model,
        executor_model=args.executor_model,
        openai_base_url=args.openai_base_url,
    )
    orchestrator = Orchestrator(config=config, log_path=None if args.no_log else Path(args.log).resolve())

    if args.ui:
        try:
            runtime = resolve_ui_runtime(args.host, args.port)
        except ConfigServiceBlocker as exc:
            print(f"Config-service blocker: {exc}")
            return 2
        return run_ui_server(
            orchestrator=orchestrator,
            ui_config=UiConfig(
                host=runtime.host,
                port=runtime.port,
                open_browser=args.open_browser,
                service_id=runtime.service_id,
                base_url=runtime.base_url,
            ),
        )

    if args.chat:
        return _run_interactive_chat(orchestrator)

    if not args.goal:
        parser.print_usage()
        return 1

    state = orchestrator.run(args.goal)
    _print_state(state, orchestrator)
    return 0 if state.status == "done" else 1


def _run_eval_args(argv: list[str]) -> int:
    parser = ArgumentParser(description="Mini orchestrator software artifact evaluations")
    parser.add_argument("command", choices=("list", "run", "report"), help="Evaluation command")
    parser.add_argument("--workdir", default=".", help="Workspace root")
    parser.add_argument("--suite", help="Suite id or path to a suite JSON file")
    parser.add_argument("--case", dest="case_id", help="Run only one case id")
    parser.add_argument("--artifact", dest="artifact_path", help="Artifact path override for run checks")
    parser.add_argument("--run", dest="run_id", help="Eval run/report id")
    args = parser.parse_args(argv)

    root = Path(args.workdir).resolve()
    try:
        if args.command == "list":
            print(json.dumps({"suites": list_eval_suites(root)}, ensure_ascii=False))
            return 0

        if args.command == "run":
            if not args.suite:
                parser.error("--suite is required for eval run")
            suite = _load_eval_suite(root, str(args.suite))
            suite = upsert_eval_suite(root, suite)
            report = run_eval_suite(root, suite, case_id=args.case_id, artifact_path=args.artifact_path)
            print(json.dumps(report, ensure_ascii=False))
            return 0 if report["status"] == "passed" else 1

        if args.command == "report":
            if not args.run_id:
                parser.error("--run is required for eval report")
            report = runtime_store.get_json_document(root, "eval_reports", str(args.run_id))
            if report is None:
                raise EvalError("Eval report was not found.")
            print(json.dumps(report, ensure_ascii=False))
            return 0 if report.get("status") == "passed" else 1
    except EvalError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({"error": f"Eval command failed: {exc}"}, ensure_ascii=False))
        return 1

    return 1


def _load_eval_suite(root: Path, suite_ref: str) -> dict:
    path = Path(suite_ref)
    if not path.is_absolute():
        path = root / path
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise EvalError("Eval suite JSON must be an object.")
        return payload
    return read_eval_suite(root, suite_ref)


if __name__ == "__main__":
    raise SystemExit(run_from_args())
