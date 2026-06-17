from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import OrchestratorConfig


class LlmUnavailable(RuntimeError):
    pass


class LlmRequestError(RuntimeError):
    pass


def _to_text_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _to_variant_list(values: Any) -> List[Dict[str, str]]:
    if not isinstance(values, list):
        return []
    variants: List[Dict[str, str]] = []
    for raw_item in values:
        if not isinstance(raw_item, dict):
            continue
        headline = str(raw_item.get("headline", "")).strip()
        body = str(raw_item.get("body", "")).strip()
        if headline or body:
            variants.append({"headline": headline, "body": body})
    return variants


def _find_first_image_call(response: Dict[str, Any]) -> Dict[str, Any]:
    for item in response.get("output", []) or []:
        if isinstance(item, dict) and item.get("type") == "image_generation_call":
            return item
    raise LlmRequestError("OpenAI response did not include an image generation call.")


@dataclass(frozen=True)
class LlmJsonResult:
    raw_text: str
    payload: Dict[str, Any]


def _extract_output_text(response: Dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    for item in response.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return parsed

    start = cleaned.find("{")
    if start < 0:
        raise LlmRequestError("LLM response did not contain a JSON object.")

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(cleaned[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : index + 1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                break

    raise LlmRequestError("LLM response JSON was not an object.")


class OpenAiResponsesClient:
    def __init__(self, config: OrchestratorConfig):
        self.config = config

    @property
    def is_required(self) -> bool:
        return self.config.llm_provider == "openai"

    @property
    def is_enabled(self) -> bool:
        return self.config.llm_provider not in {"off", "rule", "rules", "rule-based", "none"}

    def is_configured(self) -> bool:
        return bool(os.environ.get(self.config.openai_api_key_env))

    def _api_key(self) -> str:
        api_key = os.environ.get(self.config.openai_api_key_env)
        if not api_key:
            raise LlmUnavailable(f"{self.config.openai_api_key_env} is not set.")
        return api_key

    def _responses_url(self) -> str:
        base = self.config.openai_base_url.rstrip("/")
        if base.endswith("/responses"):
            return base
        return f"{base}/responses"

    def _post_responses(self, body: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        request = Request(
            self._responses_url(),
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.llm_timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LlmRequestError(f"OpenAI request failed with HTTP {exc.code}: {detail[:800]}") from exc
        except URLError as exc:
            raise LlmRequestError(f"OpenAI request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LlmRequestError("OpenAI request timed out.") from exc

        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LlmRequestError("OpenAI response was not valid JSON.") from exc

    def create_json_plan(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        model: str | None = None,
    ) -> LlmJsonResult:
        if not self.is_enabled:
            raise LlmUnavailable("LLM provider is disabled.")
        if self.config.llm_provider == "auto" and not self.is_configured():
            raise LlmUnavailable(f"{self.config.openai_api_key_env} is not set.")

        api_key = self._api_key()
        model_name = model or self.config.coordinator_model
        body: Dict[str, Any] = {
            "model": model_name,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "orchestrator_plan",
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        try:
            return self._post_json(body, api_key)
        except LlmRequestError as exc:
            if "400" not in str(exc):
                raise

        fallback_body = dict(body)
        fallback_body.pop("text", None)
        fallback_body["input"] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{user_prompt}\n\nReturn only a single valid JSON object.",
            },
        ]
        return self._post_json(fallback_body, api_key)

    def _post_json(self, body: Dict[str, Any], api_key: str) -> LlmJsonResult:
        data = self._post_responses(body, api_key)
        text = _extract_output_text(data)
        if not text:
            raise LlmRequestError("OpenAI response did not include output text.")

        return LlmJsonResult(raw_text=text, payload=_extract_first_json_object(text))

    def translate_work_package_field(
        self,
        text: str,
        language: str,
        field_label: str,
        model: str | None = None,
    ) -> str:
        if not self.is_enabled:
            raise LlmUnavailable("LLM provider is disabled.")
        if self.config.llm_provider == "auto" and not self.is_configured():
            raise LlmUnavailable(f"{self.config.openai_api_key_env} is not set.")

        source = text.strip()
        if not source:
            raise LlmRequestError("Text is required.")

        language_name = "Russian" if language == "ru" else "English"
        api_key = self._api_key()
        body: Dict[str, Any] = {
            "model": model or self.config.translation_model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You translate short AI-agent work-package UI helper text. "
                        "Return only the translated text. Do not add labels, quotes, Markdown, or explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Field: {field_label}\n"
                        f"Target language: {language_name}\n\n"
                        "Preserve technical terms such as prompt, workflow, branch, scope, JSON, API, and LLM "
                        "when translating them would make the instruction less clear.\n\n"
                        f"Text:\n{source}"
                    ),
                },
            ],
        }
        data = self._post_responses(body, api_key)
        translated = _extract_output_text(data).strip()
        if not translated:
            raise LlmRequestError("OpenAI response did not include output text.")
        return translated

    def generate_campaign(self, brief: str, target_audience: str, product_details: str, tone: str, channels: List[str]) -> Dict[str, Any]:
        if not self.is_enabled:
            raise LlmUnavailable("LLM provider is disabled.")
        if not brief.strip():
            raise LlmRequestError("Campaign brief is required.")
        if not target_audience.strip():
            raise LlmRequestError("Target audience is required.")
        if not product_details.strip():
            raise LlmRequestError("Product details are required.")
        if not tone.strip():
            raise LlmRequestError("Tone is required.")
        if not channels:
            raise LlmRequestError("At least one channel is required.")

        system_prompt = (
            "You are a senior marketing strategist for fast, production-ready campaign briefs. "
            "Return strictly JSON that matches the provided schema."
        )
        user_prompt = (
            f"Brief: {brief}\n"
            f"Target audience: {target_audience}\n"
            f"Product details: {product_details}\n"
            f"Tone: {tone}\n"
            f"Channels: {', '.join(channels)}\n\n"
            "Create:\n"
            "- one concise campaign concept (2-3 short sentences)\n"
            "- exactly three headline/body copy variants suitable for quick experimentation\n"
            "- a practical launch checklist with 6-10 actionable items\n"
            "- three distinct image prompts aligned with the same creative direction"
        )
        schema: Dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "campaign_concept": {"type": "string"},
                "headline_body_variants": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "headline": {"type": "string"},
                            "body": {"type": "string"},
                        },
                        "required": ["headline", "body"],
                    },
                },
                "launch_checklist": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 6,
                },
                "image_prompts": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {"type": "string"},
                },
            },
            "required": [
                "campaign_concept",
                "headline_body_variants",
                "launch_checklist",
                "image_prompts",
            ],
        }

        plan = self.create_json_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            model=self.config.campaign_text_model,
        ).payload

        concept = str(plan.get("campaign_concept", "")).strip()
        variants = _to_variant_list(plan.get("headline_body_variants"))
        checklist = _to_text_list(plan.get("launch_checklist"))
        image_prompts = _to_text_list(plan.get("image_prompts"))

        if not concept:
            raise LlmRequestError("Campaign concept missing from model output.")
        if len(variants) < 3:
            raise LlmRequestError("Campaign text model did not return 3 headline/body variants.")
        if len(checklist) < 1:
            raise LlmRequestError("Campaign text model did not return checklist items.")
        if not image_prompts:
            raise LlmRequestError("Campaign text model did not return image prompts.")

        image_prompts = image_prompts[: self.config.campaign_image_count]
        while len(image_prompts) < self.config.campaign_image_count:
            image_prompts.append(f"{tone} campaign hero composition for {target_audience}")

        generated_images = self.generate_campaign_images(image_prompts)

        return {
            "campaign_concept": concept,
            "headline_body_variants": variants[:3],
            "launch_checklist": checklist,
            "image_prompts": image_prompts,
            "generated_images": generated_images,
            "meta": {
                "text_model": self.config.campaign_text_model,
                "image_model": self.config.campaign_image_model,
                "image_count": self.config.campaign_image_count,
                "image_size": self.config.campaign_image_size,
                "image_quality": self.config.campaign_image_quality,
            },
        }

    def generate_campaign_images(self, prompts: List[str]) -> List[Dict[str, str]]:
        if not self.is_enabled:
            raise LlmUnavailable("LLM provider is disabled.")
        if self.config.llm_provider == "auto" and not self.is_configured():
            raise LlmUnavailable(f"{self.config.openai_api_key_env} is not set.")

        api_key = self._api_key()
        images: List[Dict[str, str]] = []
        max_images = min(self.config.campaign_image_count, len(prompts))

        for index in range(max_images):
            prompt = prompts[index].strip()
            if not prompt:
                continue
            body: Dict[str, Any] = {
                "model": self.config.campaign_image_model,
                "input": [
                    {
                        "role": "user",
                        "content": (
                            "Create a marketing direction image from this prompt, "
                            "optimize it for brand-safe, social-first campaign use.\n"
                            f"Prompt: {prompt}"
                        ),
                    }
                ],
                "tools": [
                    {
                        "type": "image_generation",
                        "size": self.config.campaign_image_size,
                        "quality": self.config.campaign_image_quality,
                    }
                ],
                "tool_choice": {"type": "image_generation"},
            }
            raw = self._post_responses(body, api_key)
            image_call = _find_first_image_call(raw)
            image_result = image_call.get("result")
            if not isinstance(image_result, str) or not image_result.strip():
                raise LlmRequestError("Image generation returned an empty result.")
            images.append(
                {
                    "index": index + 1,
                    "prompt": prompt,
                    "revised_prompt": str(image_call.get("revised_prompt", "")).strip() or prompt,
                    "image_base64": image_result,
                },
            )

        return images
