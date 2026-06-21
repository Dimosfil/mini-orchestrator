from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mini_orchestrator import runtime_store


RUNTIME_DIR = ".mini_orchestrator"
SKIP_TOP_LEVEL = {"test-runs"}
SKIP_FILE_NAMES = {
    "runtime.sqlite3",
    "runtime.sqlite3-shm",
    "runtime.sqlite3-wal",
}


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _theme_for(relative: Path) -> tuple[str, str]:
    top = relative.parts[1] if len(relative.parts) > 1 else ""
    if top in {
        "agent-cards",
        "worker-profiles",
        "agent-flows",
        "agent-flow-manifests",
        "daemon-runs",
        "dispatcher-tasks",
        "dispatcher-chain-presets",
        "dispatcher-chain-profiles",
        "dispatcher-processes",
        "logs",
        "runs",
        "symphony-process",
        "symphony-runs",
        "ui-process",
        "ui-processes",
        "ui-server",
    }:
        return top, top
    return "runtime", top or "root"


def _import_typed(root: Path, path: Path, relative: Path) -> bool:
    top = relative.parts[1] if len(relative.parts) > 1 else ""
    stem = path.stem
    source_path = _relative(path, root)

    if top == "agent-cards":
        payload = _load_json(path)
        if payload:
            card = payload.get("card") if isinstance(payload.get("card"), dict) else payload
            card_id = str(card.get("id") or stem).strip() if isinstance(card, dict) else stem
            runtime_store.upsert_json_document(root, "agent_cards", card_id, payload, source_path=source_path)
            return True
    if top == "worker-profiles":
        payload = _load_json(path)
        if payload:
            snapshot_id = str(payload.get("snapshotId") or stem).strip()
            runtime_store.upsert_json_document(root, "worker_profiles", snapshot_id, payload, source_path=source_path)
            return True
    if top == "agent-flows":
        payload = _load_json(path)
        if payload:
            flow_id = str(payload.get("id") or stem).strip()
            runtime_store.upsert_json_document(root, "agent_flows", flow_id, payload, source_path=source_path)
            return True
    if top == "agent-flow-manifests":
        payload = _load_json(path)
        if payload:
            manifest_id = str(payload.get("manifestId") or stem).strip()
            runtime_store.upsert_json_document(root, "agent_flow_manifests", manifest_id, payload, source_path=source_path)
            return True
    if top == "daemon-runs":
        if path.name.endswith(".state.json"):
            payload = _load_json(path)
            if payload:
                run_id = str(payload.get("runId") or path.name.removesuffix(".state.json")).strip()
                runtime_store.upsert_json_document(root, "daemon_runs", run_id, payload, source_path=source_path)
                return True
        if path.suffix == ".jsonl":
            run_id = path.stem
            events: list[dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
            runtime_store.replace_daemon_events(root, run_id, events)
            return True
    if top == "symphony-runs":
        payload = _load_json(path)
        if payload:
            run_id = str(payload.get("runId") or stem).strip()
            runtime_store.upsert_json_document(root, "symphony_runs", run_id, payload, source_path=source_path)
            return True
    if top == "dispatcher-tasks":
        runtime_store.store_dispatcher_task(root, path.stem, path.read_text(encoding="utf-8-sig", errors="replace"), source_path=source_path)
        return True
    if top == "dispatcher-chain-presets":
        payload = _load_json(path)
        if payload:
            runtime_store.store_dispatcher_chain_preset(root, path.stem, payload, source_path=source_path)
            return True
    if top == "dispatcher-processes":
        name = path.name
        stream = "stdout" if ".stdout." in name else "stderr" if ".stderr." in name else path.suffix.lstrip(".") or "output"
        run_id = name.split(".", 1)[0]
        runtime_store.store_dispatcher_process_output(
            root,
            run_id,
            stream,
            path.read_text(encoding="utf-8-sig", errors="replace"),
            source_path=source_path,
        )
        return True
    return False


def iter_runtime_files(root: Path) -> list[Path]:
    runtime_root = root / RUNTIME_DIR
    if not runtime_root.exists():
        return []
    files: list[Path] = []
    for path in runtime_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.resolve().relative_to(root.resolve())
        parts = relative.parts
        if len(parts) > 1 and parts[1] in SKIP_TOP_LEVEL:
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        files.append(path)
    return sorted(files)


def prune_imported_files(root: Path, files: list[Path]) -> None:
    runtime_root = (root / RUNTIME_DIR).resolve()
    for path in files:
        resolved = path.resolve()
        resolved.relative_to(runtime_root)
        if path.name in SKIP_FILE_NAMES:
            continue
        path.unlink(missing_ok=True)
    for path in sorted(runtime_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not path.is_dir() or path.name in SKIP_TOP_LEVEL:
            continue
        try:
            path.rmdir()
        except OSError:
            pass


def migrate(root: Path, *, prune_files: bool = False) -> dict[str, Any]:
    started_at = runtime_store.utc_now()
    files = iter_runtime_files(root)
    imported = 0
    skipped = 0
    for path in files:
        relative = path.resolve().relative_to(root.resolve())
        theme, topic = _theme_for(relative)
        try:
            runtime_store.import_runtime_file(root, path, theme=theme, topic=topic)
            _import_typed(root, path, relative)
            imported += 1
        except Exception:
            skipped += 1
    if prune_files:
        prune_imported_files(root, files)
    return {
        "startedAt": started_at,
        "completedAt": runtime_store.utc_now(),
        "database": _relative(runtime_store.db_path(root), root),
        "importedFiles": imported,
        "skippedFiles": skipped,
        "prunedFiles": imported if prune_files else 0,
        "tableCounts": runtime_store.table_counts(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import .mini_orchestrator runtime files into SQLite.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    parser.add_argument("--prune-files", action="store_true", help="Delete imported non-test-runs runtime files after import.")
    args = parser.parse_args()

    result = migrate(Path(args.root).resolve(), prune_files=args.prune_files)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
