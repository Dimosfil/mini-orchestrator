from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mini_orchestrator import runtime_store


def main() -> int:
    before = runtime_store.table_counts(ROOT)
    deleted = runtime_store.clear_temporary_task_state(ROOT)
    deleted_files = runtime_store.clear_dispatcher_run_logs(ROOT)
    deleted_runtime_files = runtime_store.clear_runtime_files(ROOT)
    after = runtime_store.table_counts(ROOT)
    print(
        json.dumps(
            {
                "status": "ok",
                "database": str(runtime_store.db_path(ROOT).relative_to(ROOT)),
                "deleted": deleted,
                "deletedFiles": deleted_files,
                "deletedRuntimeFiles": deleted_runtime_files,
                "preserved": {
                    "agent_chain_presets": after.get("agent_chain_presets", 0),
                    "runtime_meta": "schema_version",
                },
                "before": before,
                "after": after,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
