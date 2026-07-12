"""
Law 6: every LLM call in the codebase goes through structured_call(). No
other module may construct an OpenAI client() or call the API directly.
Swapping models, adding retries, or changing providers means editing only
this file.
"""
from __future__ import annotations

import json
import os
from typing import Type, TypeVar

from pydantic import BaseModel

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = os.environ.get("SUPAGETTI_LLM_MODEL", "z-ai/glm-5.2")
MAX_TOKENS = 4096
MAX_RETRIES = 3

T = TypeVar("T", bound=BaseModel)


class LLMCallError(Exception):
    pass


def _client():
    from openai import OpenAI

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise LLMCallError(
            "NVIDIA_API_KEY is not set. Set it in the environment before "
            "running any command that calls the LLM (analyze, govern)."
        )
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def structured_call(prompt: str, schema: Type[T], system: str | None = None) -> T:
    """
    Call the LLM and force its output to conform to `schema`. Returns a
    validated instance of `schema`. Raises LLMCallError if the model cannot
    produce schema-conformant output after retries.
    """
    from openai import OpenAIError

    client = _client()
    tool_name = f"emit_{schema.__name__.lower()}"
    tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": f"Emit a {schema.__name__} object matching the required schema.",
            "parameters": schema.model_json_schema(),
        },
    }

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                max_tokens=MAX_TOKENS,
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                messages=messages,
            )

            message = response.choices[0].message
            for call in message.tool_calls or []:
                if call.function.name == tool_name:
                    return schema.model_validate(json.loads(call.function.arguments))

            raise LLMCallError("Model response contained no tool call.")
        except OpenAIError as exc:
            last_error = exc
        except Exception as exc:  # schema validation, malformed input, etc.
            last_error = exc

    raise LLMCallError(
        f"structured_call failed after {MAX_RETRIES} attempts: {last_error}"
    )
