from __future__ import annotations

from mini_orchestrator.symphony_daemon import build_symphony_handoff_payload
from mini_orchestrator.symphony_gateway import SymphonyDaemonError, SymphonyGateway, SymphonySubmitResult


def test_handoff_payload_contains_one_agent_and_previous_outputs():
    payload = {
        "approved": True,
        "project": "mini-orchestrator",
        "task": "Build CRM",
        "chainPreset": {
            "id": "chain-1",
            "flow": {
                "agents": [
                    {"id": "planner", "name": "Planner", "role": "planner"},
                    {"id": "executor", "name": "Executor", "role": "executor"},
                ]
            },
        },
    }

    handoff = build_symphony_handoff_payload(
        payload,
        agent_index=1,
        previous_outputs=[{"agentId": "planner", "summary": "Plan ready"}],
    )

    assert handoff["dispatchStrategy"] == "mini-owned-single-agent-handoff"
    assert handoff["chainControl"]["owner"] == "mini-orchestrator"
    assert handoff["chainControl"]["handoffIndex"] == 1
    assert handoff["chainControl"]["previousOutputsCount"] == 1
    assert [item["agent"]["id"] for item in handoff["agentTasks"]] == ["executor"]
    assert "Plan ready" in handoff["agentTasks"][0]["task"]["previousOutputs"]


def test_gateway_runs_mini_owned_chain_as_sequential_handoffs():
    submitted_agent_ids = []
    previous_output_counts = []

    def submit_func(payload):
        agent = payload["agentTasks"][0]["agent"]
        submitted_agent_ids.append(agent["id"])
        previous_output_counts.append(payload["chainControl"]["previousOutputsCount"])
        return {
            "response": {
                "request_id": f"request-{agent['id']}",
                "accepted": [{"issue_id": f"issue-{agent['id']}", "identifier": f"MO-{agent['id']}"}],
            }
        }

    gateway = SymphonyGateway(
        submit_func=submit_func,
        state_func=lambda _url: {"running": [], "retrying": [], "blocked": []},
        issue_func=lambda issue_id: {"issue_id": issue_id, "state": "Completed", "last_message": f"{issue_id} done"},
        sleeper=lambda _seconds: None,
    )

    result = gateway.run_mini_owned_chain(
        {
            "approved": True,
            "task": "Build CRM",
            "chainPreset": {
                "flow": {
                    "agents": [
                        {"id": "planner", "name": "Planner", "role": "planner"},
                        {"id": "executor", "name": "Executor", "role": "executor"},
                    ]
                }
            },
        },
        state_url="http://symphony.test/api/v1/state",
        timeout_per_step_seconds=30,
        poll_interval_seconds=0,
    )

    assert result.status == "done"
    assert submitted_agent_ids == ["planner", "executor"]
    assert previous_output_counts == [0, 1]
    assert result.checklist[0]["status"] == "done"
    assert [step["status"] for step in result.steps] == ["done", "done"]


def test_gateway_waits_until_accepted_issue_has_result():
    states = [
        {"running": [{"issue_id": "issue-1"}], "retrying": [], "blocked": []},
        {"running": [], "retrying": [], "blocked": []},
    ]
    issues = []

    gateway = SymphonyGateway(
        submit_func=lambda _payload: {
            "response": {
                "request_id": "request-1",
                "accepted": [{"issue_id": "issue-1", "identifier": "MO-1"}],
            }
        },
        state_func=lambda _url: states.pop(0),
        issue_func=lambda issue_id: issues.append(issue_id) or {"issue_id": issue_id, "state": "Completed"},
        sleeper=lambda _seconds: None,
    )

    result = gateway.run_and_wait(
        {"approved": True, "task": "Validate pipeline"},
        state_url="http://symphony.test/api/v1/state",
        timeout_seconds=30,
        poll_interval_seconds=0,
    )

    assert result.status == "done"
    assert result.request_id == "request-1"
    assert issues == ["MO-1"]


def test_gateway_returns_blocked_when_issue_enters_blocked_bucket():
    gateway = SymphonyGateway(
        state_func=lambda _url: {
            "running": [],
            "retrying": [],
            "blocked": [{"issue_id": "issue-1", "error": "needs approval"}],
        },
        issue_func=lambda _issue_id: {"state": "should not be fetched"},
    )

    result = gateway.wait_for_result(
        SymphonySubmitResult(
            request_id="request-1",
            accepted=[{"issue_id": "issue-1"}],
            blocked=[],
            raw={},
        ),
        state_url="http://symphony.test/api/v1/state",
        timeout_seconds=0,
        poll_interval_seconds=0,
    )

    assert result.status == "blocked"
    assert result.issues[0]["error"] == "needs approval"


def test_gateway_times_out_while_issue_remains_active():
    calls = {"clock": 0.0}

    def clock():
        calls["clock"] += 1.0
        return calls["clock"]

    gateway = SymphonyGateway(
        state_func=lambda _url: {
            "running": [{"issue_id": "issue-1", "last_event": "still working"}],
            "retrying": [],
            "blocked": [],
        },
        issue_func=lambda _issue_id: {"state": "should not be fetched"},
        sleeper=lambda _seconds: None,
        clock=clock,
    )

    result = gateway.wait_for_result(
        SymphonySubmitResult(
            request_id="request-1",
            accepted=[{"issue_id": "issue-1"}],
            blocked=[],
            raw={},
        ),
        state_url="http://symphony.test/api/v1/state",
        timeout_seconds=1,
        poll_interval_seconds=0,
    )

    assert result.status == "timeout"
    assert result.issues[0]["last_event"] == "still working"


def test_gateway_reports_completed_without_result_when_issue_endpoint_drops_terminal_issue():
    gateway = SymphonyGateway(
        state_func=lambda _url: {"running": [], "retrying": [], "blocked": []},
        issue_func=lambda _issue_id: (_ for _ in ()).throw(SymphonyDaemonError("Symphony daemon returned HTTP 404.")),
    )

    result = gateway.wait_for_result(
        SymphonySubmitResult(
            request_id="request-1",
            accepted=[{"issue_id": "issue-1", "identifier": "MO-1"}],
            blocked=[],
            raw={},
        ),
        state_url="http://symphony.test/api/v1/state",
        timeout_seconds=0,
        poll_interval_seconds=0,
    )

    assert result.status == "completed_without_result"
    assert result.issues == [
        {
            "issue_id": "issue-1",
            "issue_identifier": "MO-1",
            "error": "Symphony daemon returned HTTP 404.",
        }
    ]
