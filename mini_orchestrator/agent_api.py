from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import tempfile


DispatcherRunner = Callable[[list[str], int], dict[str, Any]]
FailureDetailProvider = Callable[[dict[str, Any]], str]
DirectTranslator = Callable[[str, str, str], str]


@dataclass(frozen=True)
class AgentChatResponse:
    payload: dict[str, Any]


@dataclass(frozen=True)
class WorkPackageTranslationResponse:
    payload: dict[str, Any]


class AgentApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class VisualAgentApi:
    def __init__(
        self,
        run_dispatcher: DispatcherRunner,
        failure_detail: FailureDetailProvider,
        direct_translator: DirectTranslator | None = None,
    ) -> None:
        self._run_dispatcher = run_dispatcher
        self._failure_detail = failure_detail
        self._direct_translator = direct_translator

    def chat(self, payload: dict[str, Any]) -> AgentChatResponse:
        agent_value = payload.get("agent", {})
        if not isinstance(agent_value, dict):
            raise AgentApiError(400, "Field 'agent' must be an object.")

        message = str(payload.get("message", "")).strip()
        if not message:
            raise AgentApiError(400, "Field 'message' is required.")

        model = str(agent_value.get("llm") or "").strip()
        if not model:
            raise AgentApiError(400, "Agent field 'llm' is required.")
        if model.casefold() == "rules":
            raise AgentApiError(400, "This agent uses rules fallback, not a live LLM model.")

        history_value = payload.get("history", [])
        history = history_value if isinstance(history_value, list) else []
        task = self._agent_chat_task(agent_value, message[:4000], history)
        result = self._run_agent_task(task, model)
        agents = result.get("agents") if isinstance(result, dict) else {}
        if not isinstance(agents, dict) or not agents:
            raise AgentApiError(502, "Dispatcher did not return an agent response.")

        response_text = str(next(iter(agents.values()))).strip()
        if not response_text:
            detail = self._failure_detail(result)
            message_detail = f" Details: {detail}" if detail else ""
            raise AgentApiError(502, f"Dispatcher returned an empty agent response.{message_detail}")

        return AgentChatResponse(
            {
                "agent": {
                    "name": str(agent_value.get("name") or "Agent"),
                    "role": str(agent_value.get("role") or "Agent"),
                    "llm": model,
                    "speed": str(agent_value.get("speed") or "balanced"),
                    "reasoning": str(agent_value.get("reasoning") or "medium"),
                },
                "message": response_text,
                "dispatcher": {
                    "mode": result.get("mode"),
                    "log": result.get("log"),
                    "dispatchDecision": result.get("dispatchDecision"),
                },
            }
        )

    def translate_work_package(self, payload: dict[str, Any]) -> WorkPackageTranslationResponse:
        text = str(payload.get("text") or "").strip()
        if not text:
            raise AgentApiError(400, "Field 'text' is required.")

        language = str(payload.get("language") or "ru").strip().casefold()
        if language not in {"ru", "en"}:
            raise AgentApiError(400, "Field 'language' must be 'ru' or 'en'.")
        if language == "en":
            return WorkPackageTranslationResponse(
                {"text": text, "language": language, "source": "original"}
            )

        field_label = str(payload.get("field") or "work-package field").strip()[:80]
        if self._direct_translator:
            try:
                translated = self._direct_translator(text[:4000], language, field_label)
            except Exception:
                translated = ""
            if translated.strip():
                return WorkPackageTranslationResponse(
                    {
                        "text": self._clean_translation(translated),
                        "language": language,
                        "source": "openai-direct",
                    }
                )

        model = str(payload.get("model") or "").strip()
        if not model or model.casefold() == "rules":
            model = "gpt-5.4-mini"

        task = self._translation_task(text[:4000], language, field_label)
        result = self._run_agent_task(task, model)
        agents = result.get("agents") if isinstance(result, dict) else {}
        if not isinstance(agents, dict) or not agents:
            raise AgentApiError(502, "Dispatcher did not return a translation.")

        translated = str(next(iter(agents.values()))).strip()
        if not translated:
            detail = self._failure_detail(result)
            message_detail = f" Details: {detail}" if detail else ""
            raise AgentApiError(502, f"Dispatcher returned an empty translation.{message_detail}")

        return WorkPackageTranslationResponse(
            {
                "text": self._clean_translation(translated),
                "language": language,
                "source": "agent",
                "dispatcher": {
                    "mode": result.get("mode"),
                    "log": result.get("log"),
                    "dispatchDecision": result.get("dispatchDecision"),
                },
            }
        )

    def _run_agent_task(self, task: str, model: str) -> dict[str, Any]:
        task_file_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                prefix="mini-orchestrator-agent-chat-",
                suffix=".txt",
                delete=False,
            ) as task_file:
                task_file.write(task)
                task_file_path = Path(task_file.name)
            return self._run_dispatcher(
                [
                    "--task-file",
                    str(task_file_path),
                    "--model",
                    model,
                    "--use-worker-models",
                    "--turn-timeout-seconds",
                    "120",
                ],
                150,
            )
        finally:
            if task_file_path:
                try:
                    task_file_path.unlink()
                except OSError:
                    pass

    def _agent_role_for_dispatcher(self, role: str) -> str:
        normalized = role.strip().casefold()
        if "executor" in normalized or "исполн" in normalized:
            return "executor"
        if "review" in normalized or "рев" in normalized or "провер" in normalized:
            return "reviewer"
        return "planner"

    def _agent_chat_task(self, agent: dict[str, Any], message: str, history: list[Any]) -> str:
        name = str(agent.get("name") or "Agent").strip()[:80]
        role = str(agent.get("role") or "Agent").strip()[:80]
        model = str(agent.get("llm") or "unknown").strip()[:80]
        speed = str(agent.get("speed") or "balanced").strip()[:40]
        reasoning = str(agent.get("reasoning") or "medium").strip()[:40]
        dispatcher_role = self._agent_role_for_dispatcher(role)
        work_package_value = agent.get("workPackage", {})
        work_package = work_package_value if isinstance(work_package_value, dict) else {}
        package_fields = [
            ("role/instructions", "instructions"),
            ("current objective", "currentObjective"),
            ("inputs/artifacts", "inputsArtifacts"),
            ("constraints", "constraints"),
            ("previous agent outputs", "previousOutputs"),
            ("allowed tools/actions", "allowedTools"),
            ("expected output format", "expectedOutput"),
        ]
        package_lines = []
        for label, key in package_fields:
            value = str(work_package.get(key) or "").strip()
            if value:
                package_lines.append(f"{label}: {value[:1200]}")
        package_text = "\n".join(package_lines) if package_lines else "No custom work package fields."

        history_lines: list[str] = []
        for raw_item in history[-8:]:
            if not isinstance(raw_item, dict):
                continue
            speaker = str(raw_item.get("speaker") or raw_item.get("role") or "").strip()[:20]
            text = str(raw_item.get("text") or raw_item.get("content") or "").strip()
            if speaker and text:
                history_lines.append(f"{speaker}: {text[:1000]}")
        history_text = "\n".join(history_lines) if history_lines else "No previous mini-chat messages."

        return (
            f"orchestrator {dispatcher_role} "
            "Answer as the selected visual agent in the mini-orchestrator UI.\n\n"
            f"Agent name: {name}\n"
            f"Agent role: {role}\n"
            f"Selected model: {model}\n"
            f"Preferred speed: {speed}\n"
            f"Reasoning level: {reasoning}\n\n"
            f"Agent work package:\n{package_text}\n\n"
            "Keep the answer concise and useful for checking this agent's style. "
            "If the user asks who you are or which model/settings are selected, answer from these agent settings. "
            "Do not edit files, run commands, or claim that the visual flow is executing.\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            f"User message:\n{message}"
        )

    def _translation_task(self, text: str, language: str, field_label: str) -> str:
        language_name = "Russian" if language == "ru" else "English"
        return (
            "orchestrator planner "
            "Translate one mini-orchestrator work-package field for UI helper text.\n\n"
            f"Field: {field_label}\n"
            f"Target language: {language_name}\n\n"
            "Return only the translated text. Do not add Markdown, quotes, labels, notes, "
            "or explanations. Preserve technical terms such as prompt, workflow, branch, "
            "scope, JSON, API, and LLM when translating them would make the instruction less clear.\n\n"
            f"Text:\n{text}"
        )

    def _clean_translation(self, text: str) -> str:
        cleaned = text.strip()
        prefixes = [
            "translation:",
            "translated text:",
            "russian:",
            "ru:",
        ]
        lowered = cleaned.casefold()
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
                break
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1].strip()
        return cleaned
