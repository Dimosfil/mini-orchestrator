from __future__ import annotations

from pathlib import Path


def test_agent_builder_contains_approval_manifest_controls() -> None:
    html_path = Path("mini_orchestrator/web/agents-builder.html")
    html = html_path.read_text(encoding="utf-8")

    assert 'id="approval-task"' in html
    assert 'id="approval-confirm"' in html
    assert 'id="compile-manifest"' in html
    assert 'id="manifest-json"' in html
    assert "/api/agent-flows/" in html
    assert "/compile" in html


def test_agent_builder_agent_cards_are_vertically_bounded_and_resizable() -> None:
    html_path = Path("mini_orchestrator/web/agents-builder.html")
    html = html_path.read_text(encoding="utf-8")

    assert "max-height: min(720px, calc(100vh - 96px));" in html
    assert "resize: vertical;" in html
    assert "overflow-y: auto;" in html
    assert "const cardResizeObserver" in html
    assert "const cardHeight = cardRect?.height || 260;" in html
    assert "rect.height - cardHeight - 12" in html


def test_dashboard_maps_daemon_node_states_to_stage_artifacts() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert "run.nodeStates" in html
    assert "run.flowArtifacts" in html
    assert "stage-artifact" in html
    assert "artifactId" in html
    assert "verdict" in html


def test_dashboard_kanban_board_is_vertically_bounded_and_resizable() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert ".runs-board" in html
    assert "height: min(520px, calc(100vh - 190px));" in html
    assert "max-height: calc(100vh - 140px);" in html
    assert "resize: vertical;" in html
    assert 'id="runs-board-resize-handle"' in html
    assert "RUNS_BOARD_HEIGHT_STORAGE_KEY" in html
    assert "setupRunsBoardResize" in html
    assert "grid-template-rows: auto minmax(0, 1fr);" in html
    assert "flex-direction: column;" in html
    assert "flex: 0 0 auto;" in html
    assert "overflow-y: auto;" in html
    assert "overscroll-behavior: contain;" in html
    assert "grid-template-columns: repeat(5, minmax(260px, 1fr));" in html
    assert "min-width: 260px;" in html
    assert "min-height: 168px;" in html
    assert "grid-template-columns: minmax(0, 1fr) auto;" in html
    assert "overflow-wrap: anywhere;" in html
    assert "scrollbar-gutter: stable;" in html


def test_dashboard_kanban_cards_use_nested_object_frames() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert "kanban-card-frame" in html
    assert "kanban-card-body" in html
    assert "kanban-card-footer" in html
    assert ".kanban-card-frame {\n      display: flex;" in html
    assert "height: auto;" in html
    assert 'frame.className = "kanban-card-frame";' in html
    assert 'body.className = "kanban-card-body";' in html
    assert 'footer.className = "kanban-card-footer";' in html
    assert "frame.append(header, body);" in html
    assert "article.append(frame);" in html
    assert "article.append(header, current, stageRow, event);" not in html


def test_dashboard_kanban_cards_have_details_modal() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert 'id="run-details-backdrop"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert "kanban-details-button" in html
    assert 'detailsButton.textContent = "Details";' in html
    assert "detailsButton.addEventListener(\"click\", () => openRunDetails(run, profile));" in html
    assert "footer.append(detailsButton);" in html
    assert "function openRunDetails(run, profile)" in html
    assert "runDetailsJson(\"Full payload\", detailPayload)" in html
    assert "function closeRunDetails()" in html


def test_dashboard_kanban_refresh_preserves_column_scroll_positions() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert "captureKanbanScrollState" in html
    assert "restoreKanbanScrollState" in html
    assert "list.scrollTop" in html
    assert "liveRunsList.scrollLeft" in html
    assert "const kanbanScrollState = captureKanbanScrollState();" in html
    assert "restoreKanbanScrollState(kanbanScrollState);" in html
    assert "requestAnimationFrame(() => restoreKanbanScrollState(kanbanScrollState));" in html


def test_dashboard_live_runs_has_source_modes_and_badges() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert 'id="live-runs-source-mode"' in html
    assert '<option value="combined" selected>Combined</option>' in html
    assert '<option value="dispatcher">Dispatcher</option>' in html
    assert '<option value="symphony">Symphony</option>' in html
    assert "LIVE_RUNS_SOURCE_MODE_STORAGE_KEY" in html
    assert "/api/daemon/runs?source=" in html
    assert "run-source-badge" in html
    assert "runSourceLabel(run)" in html
    assert 'stale: "Stale"' in html
    assert 'status === "stale"' in html


def test_dashboard_rework_action_starts_background_workflow() -> None:
    html_path = Path("mini_orchestrator/web/index.html")
    html = html_path.read_text(encoding="utf-8")

    assert "async function startRunRework(run, profile)" in html
    assert 'postJson("/api/daemon/review", { runId: run.runId, decision })' in html
    assert "run.review?.decision" in html
    assert "function isLocalDaemonRun(run)" in html
    assert 'review: "Human Review"' in html
    assert 'status === "review"' in html
    assert 'postJson("/api/dispatcher/run"' in html
    assert "buildReworkTask(run, profile)" in html
    assert "approved: true" in html
    assert "background: true" in html
    assert 'mode: "real"' in html
    assert 'setMessage("Rework workflow started. Watch Live Runs for progress.", "ok")' in html
    assert 'setRunReviewDecision(run, "rework", profile)' in html


def test_approved_dispatcher_workflow_uses_extended_turn_timeout() -> None:
    source = Path("mini_orchestrator/ui.py").read_text(encoding="utf-8")

    assert "APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS = 300" in source
    assert '"--turn-timeout-seconds"' in source
    assert "str(APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS)" in source
    assert "timeout_seconds=APPROVED_WORKFLOW_TURN_TIMEOUT_SECONDS * 4" in source


def test_daemon_review_endpoint_is_documented_in_service_contract() -> None:
    source = Path("mini_orchestrator/ui.py").read_text(encoding="utf-8")

    assert '"/api/daemon/review"' in source
    assert '"daemonReview"' in source
    assert '"decisionValues": ["done", "rework"]' in source
    assert "set_run_review_decision" in source
