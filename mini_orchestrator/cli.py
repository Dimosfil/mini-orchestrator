from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json

from .config import parse_runtime_config
from .orchestrator import Orchestrator
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
    parser = ArgumentParser(description="Mini orchestrator: plan -> execute -> validate")
    parser.add_argument(
        "goal",
        nargs="?",
        help="Goal text for the orchestrator",
    )
    parser.add_argument("--chat", action="store_true", help="Start interactive chat mode")
    parser.add_argument("--ui", action="store_true", help="Start web UI mode")
    parser.add_argument("--host", default="127.0.0.1", help="Host for UI mode")
    parser.add_argument("--port", type=int, default=8765, help="Port for UI mode")
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
        return run_ui_server(
            orchestrator=orchestrator,
            ui_config=UiConfig(host=args.host, port=args.port, open_browser=args.open_browser),
        )

    if args.chat:
        return _run_interactive_chat(orchestrator)

    if not args.goal:
        parser.print_usage()
        return 1

    state = orchestrator.run(args.goal)
    _print_state(state, orchestrator)
    return 0 if state.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(run_from_args())
