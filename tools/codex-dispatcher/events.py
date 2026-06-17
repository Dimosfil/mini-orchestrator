from __future__ import annotations

import errno
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protocol import validate_event_type


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_event(log_path: Path, event_type: str, **payload: Any) -> None:
    validate_event_type(event_type)
    record = {
        "time": utc_now(),
        "type": event_type,
        **payload,
    }
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        if (
            exc.errno == errno.ENOSPC
            and os.environ.get("MINI_ORCHESTRATOR_DISPATCHER_BEST_EFFORT_LOGS") == "1"
        ):
            return
        raise
