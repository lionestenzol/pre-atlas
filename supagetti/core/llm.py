"""
Law 6: every LLM call in the codebase goes through structured_call(). No
other module may construct an anthropic.Client() or call the API directly.
Swapping models, adding retries, or changing providers means editing only
this file.
"""
from __future__ import annotations

import os
from typing import Type, TypeVar

from pydantic import BaseModel

DEFAULT_MODEL = os.environ.get("SUPAGETTI_LLM_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS = 4096
MAX_RETRIES = 3

T = TypeVar("T", bound=BaseModel)


class LLMCallError(Exception):
    pass


def _client():
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMCallError(
            "ANTHROPIC_API_KEY is not set. Set it in the environment before "
            "running any command that calls the LLM (analyze, govern)."
        )
    return anthropic.Anthropic(api_key=api_key)


def structured_call(prompt: str, schema: Type[T], system: str | None = None) -> T:
    """
    Call the LLM and force its output to conform to `schema`. Returns a
    validated instance of `schema`. Raises LLMCallError if the model cannot
    produce schema-conformant output after retries.
    """
    import anthropic

    client = _client()
    tool_name = f"emit_{schema.__name__.lower()}"
    tool = {
        "name": tool_name,
        "description": f"Emit a {schema.__name__} object matching the required schema.",
        "input_schema": schema.model_json_schema(),
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs = dict(
                model=DEFAULT_MODEL,
                max_tokens=MAX_TOKENS,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )
            if system:
                kwargs["system"] = system
            response = client.messages.create(**kwargs)

            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return schema.model_validate(block.input)

            raise LLMCallError("Model response contained no tool_use block.")
        except anthropic.APIError as exc:
            last_error = exc
        except Exception as exc:  # schema validation, malformed input, etc.
            last_error = exc

    raise LLMCallError(
        f"structured_call failed after {MAX_RETRIES} attempts: {last_error}"
    )
