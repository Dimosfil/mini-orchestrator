from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
import hashlib
import json
import mimetypes
import sqlite3


DB_RELATIVE_PATH = Path(".mini_orchestrator") / "runtime.sqlite3"
TEMPORARY_TASK_STATE_TABLES = (
    "runtime_files",
    "agent_cards",
    "worker_profiles",
    "agent_flows",
    "agent_flow_manifests",
    "daemon_events",
    "daemon_runs",
    "symphony_runs",
    "dispatcher_tasks",
    "dispatcher_chain_presets",
    "dispatcher_process_outputs",
    "migration_runs",
)
PRESERVED_RUNTIME_TABLES = ("runtime_meta", "agent_chain_presets")
RUNTIME_FILE_KEEP_NAMES = {
    "runtime.sqlite3",
    "runtime.sqlite3-shm",
    "runtime.sqlite3-wal",
}

JSON_THEMES = {
    "agent_cards": ("agent_cards", "card_id"),
    "worker_profiles": ("worker_profiles", "snapshot_id"),
    "agent_flows": ("agent_flows", "flow_id"),
    "agent_flow_manifests": ("agent_flow_manifests", "manifest_id"),
    "agent_chain_presets": ("agent_chain_presets", "preset_id"),
    "daemon_runs": ("daemon_runs", "run_id"),
    "symphony_runs": ("symphony_runs", "run_id"),
    "dispatcher_chain_presets": ("dispatcher_chain_presets", "run_id"),
}

CURRENT_RUN_CONFIG_META_KEY = "current_run_config"


def db_path(root: Path) -> Path:
    return root / DB_RELATIVE_PATH


def runtime_uri(theme: str, key: str) -> str:
    return f"runtime-db://{theme}/{key}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@contextmanager
def connect(root: Path) -> Iterator[sqlite3.Connection]:
    path = db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    ensure_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runtime_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runtime_files (
            source_path TEXT PRIMARY KEY,
            theme TEXT NOT NULL,
            topic TEXT NOT NULL,
            name TEXT NOT NULL,
            content_type TEXT NOT NULL,
            encoding TEXT,
            is_binary INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            content_text TEXT,
            content_blob BLOB,
            imported_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_cards (
            card_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS worker_profiles (
            snapshot_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_flows (
            flow_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version INTEGER NOT NULL,
            validation_status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_flow_manifests (
            manifest_id TEXT PRIMARY KEY,
            flow_id TEXT,
            flow_version INTEGER,
            payload_json TEXT NOT NULL,
            compiled_at TEXT,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_chain_presets (
            preset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS daemon_runs (
            run_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS daemon_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            event_json TEXT NOT NULL,
            event_type TEXT,
            event_time TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_daemon_events_run_id ON daemon_events(run_id, id);

        CREATE TABLE IF NOT EXISTS symphony_runs (
            run_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS dispatcher_tasks (
            run_id TEXT PRIMARY KEY,
            task_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS dispatcher_chain_presets (
            run_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            source_path TEXT
        );

        CREATE TABLE IF NOT EXISTS dispatcher_process_outputs (
            run_id TEXT NOT NULL,
            stream TEXT NOT NULL,
            content_text TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source_path TEXT,
            PRIMARY KEY (run_id, stream)
        );

        CREATE TABLE IF NOT EXISTS migration_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            imported_files INTEGER NOT NULL DEFAULT 0,
            skipped_files INTEGER NOT NULL DEFAULT 0,
            notes TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO runtime_meta(key, value, updated_at)
        VALUES ('schema_version', '1', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (utc_now(),),
    )


def set_runtime_meta(root: Path, key: str, value: str) -> None:
    with connect(root) as conn:
        conn.execute(
            """
            INSERT INTO runtime_meta(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, utc_now()),
        )


def get_runtime_meta(root: Path, key: str) -> str | None:
    with connect(root) as conn:
        row = conn.execute("SELECT value FROM runtime_meta WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else None


def set_current_run_config(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    config = {
        "chainPresetId": str(payload.get("chainPresetId") or "").strip(),
        "executionMode": _normalized_execution_mode(payload.get("executionMode")),
        "symphonyWorkerMode": _normalized_symphony_worker_mode(payload.get("symphonyWorkerMode")),
        "updatedAt": utc_now(),
    }
    if not config["chainPresetId"]:
        raise ValueError("Current run config requires chainPresetId.")
    set_runtime_meta(root, CURRENT_RUN_CONFIG_META_KEY, json.dumps(config, ensure_ascii=False, sort_keys=True))
    return config


def get_current_run_config(root: Path) -> dict[str, Any] | None:
    raw = get_runtime_meta(root, CURRENT_RUN_CONFIG_META_KEY)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    chain_preset_id = str(value.get("chainPresetId") or "").strip()
    if not chain_preset_id:
        return None
    return {
        "chainPresetId": chain_preset_id,
        "executionMode": _normalized_execution_mode(value.get("executionMode")),
        "symphonyWorkerMode": _normalized_symphony_worker_mode(value.get("symphonyWorkerMode")),
        "updatedAt": str(value.get("updatedAt") or ""),
    }


def _normalized_execution_mode(value: Any) -> str:
    mode = str(value or "").strip().casefold()
    return mode if mode in {"dispatcher", "symphony"} else "dispatcher"


def _normalized_symphony_worker_mode(value: Any) -> str:
    mode = str(value or "").strip().casefold()
    return mode if mode in {"debug-new-worker", "optimal-reuse-idle"} else "debug-new-worker"


def upsert_json_document(
    root: Path,
    theme: str,
    key: str,
    payload: dict[str, Any],
    *,
    source_path: str | None = None,
) -> None:
    table_info = JSON_THEMES.get(theme)
    if not table_info:
        raise ValueError(f"Unsupported JSON runtime theme: {theme}")
    table, key_column = table_info
    now = utc_now()
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    with connect(root) as conn:
        if theme == "agent_flows":
            conn.execute(
                """
                INSERT INTO agent_flows(flow_id, name, version, validation_status, payload_json, created_at, updated_at, source_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(flow_id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    validation_status = excluded.validation_status,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (
                    key,
                    str(payload.get("name") or ""),
                    int(payload.get("version") or 0),
                    str(payload.get("validationStatus") or "unknown"),
                    payload_json,
                    str(payload.get("createdAt") or ""),
                    str(payload.get("updatedAt") or now),
                    source_path,
                ),
            )
        elif theme == "agent_flow_manifests":
            conn.execute(
                """
                INSERT INTO agent_flow_manifests(manifest_id, flow_id, flow_version, payload_json, compiled_at, updated_at, source_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(manifest_id) DO UPDATE SET
                    flow_id = excluded.flow_id,
                    flow_version = excluded.flow_version,
                    payload_json = excluded.payload_json,
                    compiled_at = excluded.compiled_at,
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (
                    key,
                    str(payload.get("flowId") or ""),
                    int(payload.get("flowVersion") or 0),
                    payload_json,
                    str(payload.get("compiledAt") or ""),
                    now,
                    source_path,
                ),
            )
        elif theme == "agent_chain_presets":
            conn.execute(
                """
                INSERT INTO agent_chain_presets(preset_id, name, payload_json, created_at, updated_at, source_path)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(preset_id) DO UPDATE SET
                    name = excluded.name,
                    payload_json = excluded.payload_json,
                    created_at = COALESCE(NULLIF(agent_chain_presets.created_at, ''), excluded.created_at),
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (
                    key,
                    str(payload.get("name") or ""),
                    payload_json,
                    str(payload.get("createdAt") or now),
                    str(payload.get("updatedAt") or now),
                    source_path,
                ),
            )
        elif theme == "daemon_runs":
            conn.execute(
                """
                INSERT INTO daemon_runs(run_id, status, payload_json, created_at, updated_at, source_path)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (
                    key,
                    str(payload.get("status") or ""),
                    payload_json,
                    str(payload.get("createdAt") or ""),
                    str(payload.get("updatedAt") or now),
                    source_path,
                ),
            )
        elif theme == "symphony_runs":
            conn.execute(
                """
                INSERT INTO symphony_runs(run_id, status, payload_json, created_at, updated_at, source_path)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (
                    key,
                    str(payload.get("status") or ""),
                    payload_json,
                    str(payload.get("createdAt") or ""),
                    str(payload.get("updatedAt") or now),
                    source_path,
                ),
            )
        elif theme == "agent_cards":
            conn.execute(
                f"""
                INSERT INTO {table}({key_column}, payload_json, updated_at, source_path)
                VALUES (?, ?, ?, ?)
                ON CONFLICT({key_column}) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (key, payload_json, str(payload.get("updatedAt") or now), source_path),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO {table}({key_column}, payload_json, updated_at, source_path)
                VALUES (?, ?, ?, ?)
                ON CONFLICT({key_column}) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at,
                    source_path = excluded.source_path
                """,
                (key, payload_json, now, source_path),
            )


def get_json_document(root: Path, theme: str, key: str) -> dict[str, Any] | None:
    table_info = JSON_THEMES.get(theme)
    if not table_info:
        raise ValueError(f"Unsupported JSON runtime theme: {theme}")
    table, key_column = table_info
    with connect(root) as conn:
        row = conn.execute(
            f"SELECT payload_json FROM {table} WHERE {key_column} = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    payload = json.loads(str(row["payload_json"]))
    return payload if isinstance(payload, dict) else None


def list_json_documents(root: Path, theme: str) -> list[dict[str, Any]]:
    table_info = JSON_THEMES.get(theme)
    if not table_info:
        raise ValueError(f"Unsupported JSON runtime theme: {theme}")
    table, _ = table_info
    order_column = "updated_at"
    with connect(root) as conn:
        rows = conn.execute(
            f"SELECT payload_json FROM {table} ORDER BY {order_column} DESC"
        ).fetchall()
    docs: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        if isinstance(payload, dict):
            docs.append(payload)
    return docs


def json_document_exists(root: Path, theme: str, key: str) -> bool:
    return get_json_document(root, theme, key) is not None


def delete_json_document(root: Path, theme: str, key: str) -> bool:
    table_info = JSON_THEMES.get(theme)
    if not table_info:
        raise ValueError(f"Unsupported JSON runtime theme: {theme}")
    table, key_column = table_info
    with connect(root) as conn:
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE {key_column} = ?",
            (key,),
        )
        return cursor.rowcount > 0


def insert_daemon_event(root: Path, run_id: str, event: dict[str, Any]) -> None:
    now = utc_now()
    with connect(root) as conn:
        conn.execute(
            """
            INSERT INTO daemon_events(run_id, event_json, event_type, event_time, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                json.dumps(event, ensure_ascii=False, sort_keys=True),
                str(event.get("type") or ""),
                str(event.get("time") or ""),
                now,
            ),
        )


def replace_daemon_events(root: Path, run_id: str, events: list[dict[str, Any]]) -> None:
    now = utc_now()
    with connect(root) as conn:
        conn.execute("DELETE FROM daemon_events WHERE run_id = ?", (run_id,))
        conn.executemany(
            """
            INSERT INTO daemon_events(run_id, event_json, event_type, event_time, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    json.dumps(event, ensure_ascii=False, sort_keys=True),
                    str(event.get("type") or ""),
                    str(event.get("time") or ""),
                    now,
                )
                for event in events
            ],
        )


def list_daemon_events(root: Path, run_id: str) -> list[dict[str, Any]]:
    with connect(root) as conn:
        rows = conn.execute(
            "SELECT event_json FROM daemon_events WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["event_json"]))
        if isinstance(payload, dict):
            events.append(payload)
    return events


def store_dispatcher_task(root: Path, run_id: str, task_text: str, *, source_path: str | None = None) -> None:
    with connect(root) as conn:
        conn.execute(
            """
            INSERT INTO dispatcher_tasks(run_id, task_text, created_at, source_path)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                task_text = excluded.task_text,
                source_path = excluded.source_path
            """,
            (run_id, task_text, utc_now(), source_path),
        )


def get_dispatcher_task(root: Path, run_id: str) -> str | None:
    with connect(root) as conn:
        row = conn.execute("SELECT task_text FROM dispatcher_tasks WHERE run_id = ?", (run_id,)).fetchone()
    return str(row["task_text"]) if row else None


def store_dispatcher_chain_preset(root: Path, run_id: str, preset: dict[str, Any], *, source_path: str | None = None) -> None:
    with connect(root) as conn:
        conn.execute(
            """
            INSERT INTO dispatcher_chain_presets(run_id, payload_json, created_at, source_path)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                source_path = excluded.source_path
            """,
            (run_id, json.dumps(preset, ensure_ascii=False, sort_keys=True), utc_now(), source_path),
        )


def get_dispatcher_chain_preset(root: Path, run_id: str) -> dict[str, Any] | None:
    with connect(root) as conn:
        row = conn.execute(
            "SELECT payload_json FROM dispatcher_chain_presets WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if not row:
        return None
    payload = json.loads(str(row["payload_json"]))
    return payload if isinstance(payload, dict) else None


def store_dispatcher_process_output(root: Path, run_id: str, stream: str, content: str, *, source_path: str | None = None) -> None:
    with connect(root) as conn:
        conn.execute(
            """
            INSERT INTO dispatcher_process_outputs(run_id, stream, content_text, updated_at, source_path)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, stream) DO UPDATE SET
                content_text = excluded.content_text,
                updated_at = excluded.updated_at,
                source_path = excluded.source_path
            """,
            (run_id, stream, content, utc_now(), source_path),
        )


def import_runtime_file(root: Path, path: Path, *, theme: str, topic: str) -> None:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    data = path.read_bytes()
    stat = path.stat()
    digest = hashlib.sha256(data).hexdigest()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    text: str | None = None
    blob: bytes | None = data
    encoding: str | None = None
    is_binary = 1
    try:
        text = data.decode("utf-8-sig")
        blob = None
        encoding = "utf-8-sig"
        is_binary = 0
    except UnicodeDecodeError:
        pass
    with connect(root) as conn:
        conn.execute(
            """
            INSERT INTO runtime_files(
                source_path, theme, topic, name, content_type, encoding, is_binary,
                size_bytes, mtime_ns, sha256, content_text, content_blob, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_path) DO UPDATE SET
                theme = excluded.theme,
                topic = excluded.topic,
                name = excluded.name,
                content_type = excluded.content_type,
                encoding = excluded.encoding,
                is_binary = excluded.is_binary,
                size_bytes = excluded.size_bytes,
                mtime_ns = excluded.mtime_ns,
                sha256 = excluded.sha256,
                content_text = excluded.content_text,
                content_blob = excluded.content_blob,
                imported_at = excluded.imported_at
            """,
            (
                relative,
                theme,
                topic,
                path.name,
                content_type,
                encoding,
                is_binary,
                stat.st_size,
                stat.st_mtime_ns,
                digest,
                text,
                blob,
                utc_now(),
            ),
        )


def table_counts(root: Path) -> dict[str, int]:
    tables = [
        "runtime_files",
        "agent_cards",
        "worker_profiles",
        "agent_flows",
        "agent_flow_manifests",
        "agent_chain_presets",
        "daemon_runs",
        "daemon_events",
        "symphony_runs",
        "dispatcher_tasks",
        "dispatcher_chain_presets",
        "dispatcher_process_outputs",
    ]
    with connect(root) as conn:
        return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}


def clear_temporary_task_state(root: Path) -> dict[str, int]:
    """Clear runtime state while preserving saved chain presets."""
    deleted: dict[str, int] = {}
    with connect(root) as conn:
        for table in TEMPORARY_TASK_STATE_TABLES:
            before = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            conn.execute(f"DELETE FROM {table}")
            deleted[table] = before
    return deleted


def clear_runtime_files(root: Path) -> dict[str, int]:
    runtime_dir = db_path(root).parent
    root_resolved = root.resolve()
    runtime_dir_resolved = runtime_dir.resolve()
    try:
        runtime_dir_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError(f"Runtime directory is outside project root: {runtime_dir_resolved}") from exc
    if not runtime_dir.exists():
        return {"files": 0, "directories": 0}

    deleted_files = 0
    deleted_dirs = 0
    for path in sorted(runtime_dir.iterdir(), key=lambda item: len(item.parts), reverse=True):
        if path.name in RUNTIME_FILE_KEEP_NAMES:
            continue
        path_resolved = path.resolve()
        path_resolved.relative_to(runtime_dir_resolved)
        if path.is_dir():
            _remove_directory_tree(path, runtime_dir_resolved)
            deleted_dirs += 1
        elif path.is_file():
            path.unlink()
            deleted_files += 1
    return {"files": deleted_files, "directories": deleted_dirs}


def _remove_directory_tree(path: Path, allowed_root: Path) -> None:
    path_resolved = path.resolve()
    path_resolved.relative_to(allowed_root)
    if not path.is_dir():
        raise RuntimeError(f"Refusing to remove non-directory as directory: {path_resolved}")
    for child in sorted(path.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        child.resolve().relative_to(path_resolved)
        if child.is_dir():
            child.rmdir()
        else:
            child.unlink()
    path.rmdir()


def clear_dispatcher_run_logs(root: Path) -> dict[str, int]:
    runs_dir = root / "tools" / "codex-dispatcher" / "runs"
    root_resolved = root.resolve()
    runs_dir_resolved = runs_dir.resolve()
    try:
        runs_dir_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError(f"Dispatcher runs directory is outside project root: {runs_dir_resolved}") from exc
    if not runs_dir.exists():
        return {"jsonl_files": 0}

    deleted = 0
    for path in runs_dir.glob("*.jsonl"):
        if not path.is_file():
            continue
        path.resolve().relative_to(runs_dir_resolved)
        path.unlink()
        deleted += 1
    return {"jsonl_files": deleted}
