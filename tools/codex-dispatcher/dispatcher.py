from __future__ import annotations

from pathlib import Path

from cli import main as cli_main
from codex_app import CodexAppServer, repair_text_encoding, resolve_codex_command
from events import utc_now, write_event
from models import DispatchDecision, OrchestratorChatCommand, Worker
from pipeline import build_chat_approval_plan, dry_run, dry_run_chain
from pipeline import run_pipeline as pipeline_run_pipeline
from prompts import build_chain_prior, build_plan_only_prompt, build_worker_prompt, read_instructions
from routing import CHAIN_ROLES, decide_dispatch, find_worker, ordered_chain_workers, parse_orchestrator_chat_command
from worker_profiles import default_workers, workers_from_chain_preset_file


ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = Path(__file__).resolve().parent / "runs"

WORKERS = default_workers(ROOT)


def run_pipeline(
    task: str,
    dry: bool,
    workers: list[Worker],
    codex_command: str | None,
    request_timeout_seconds: float,
    turn_timeout_seconds: float,
    use_worker_models: bool,
    chain: bool = False,
    plan_only: bool = False,
) -> tuple[Path, dict[str, str], DispatchDecision]:
    return pipeline_run_pipeline(
        task,
        dry,
        workers,
        codex_command,
        request_timeout_seconds,
        turn_timeout_seconds,
        use_worker_models,
        root=ROOT,
        runs_dir=RUNS_DIR,
        chain=chain,
        plan_only=plan_only,
        codex_server_factory=CodexAppServer,
    )


def main() -> int:
    return cli_main(ROOT, RUNS_DIR, WORKERS)


if __name__ == "__main__":
    raise SystemExit(main())
