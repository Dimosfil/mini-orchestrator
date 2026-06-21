from __future__ import annotations

from dataclasses import dataclass

from .model_defaults import DEFAULT_COORDINATOR_MODEL, DEFAULT_EXECUTOR_MODEL


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str


class Router:
    """Simple route rule: risky work goes to GPT-5.5 coordinator first."""

    HIGH_RISK_MARKERS = (
        "delete",
        "remove",
        "deploy",
        "publish",
        "init",
        "install",
        "push",
        "rm ",
        "format",
    )

    def route_goal(self, goal: str) -> RouteDecision:
        text = goal.lower()
        if any(marker in text for marker in self.HIGH_RISK_MARKERS):
            return RouteDecision(model=DEFAULT_COORDINATOR_MODEL, reason="high-risk keyword matched")
        return RouteDecision(model=DEFAULT_EXECUTOR_MODEL, reason="lightweight technical step")
