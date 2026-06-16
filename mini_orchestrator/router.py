from __future__ import annotations

from dataclasses import dataclass


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
            return RouteDecision(model="gpt-5.5", reason="high-risk keyword matched")
        return RouteDecision(model="gpt-5.3-codex-spark", reason="lightweight technical step")
