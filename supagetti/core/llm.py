"""
Law 6: every LLM call in the codebase goes through structured_call(). No
other module may construct an OpenAI client(), an Instructor client, or
call the API directly. Swapping models, adding retries, or changing
providers means editing only this file.
"""
from __future__ import annotations

import os
from typing import Type, TypeVar

from pydantic import BaseModel

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = os.environ.get("SUPAGETTI_LLM_MODEL", "z-ai/glm-5.2")
MAX_TOKENS = 4096
MAX_RETRIES = 3
# Low-ish temperature for structured, audit-style calls (analyze/govern):
# these are meant to be careful and reproducible, not creative. Unset
# previously meant "whatever the provider defaults to" (NVIDIA's default is
# 1.0), which is the wrong end of the range for a findings/audit report.
TEMPERATURE = float(os.environ.get("SUPAGETTI_LLM_TEMPERATURE", "0.3"))

T = TypeVar("T", bound=BaseModel)


class LLMCallError(Exception):
    pass


def _client():
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise LLMCallError(
            "NVIDIA_API_KEY is not set. Set it in the environment before "
            "running any command that calls the LLM (analyze, govern)."
        )
    raw_client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)
    return instructor.from_openai(raw_client, mode=instructor.Mode.TOOLS)


def structured_call(prompt: str, schema: Type[T], system: str | None = None) -> T:
    """
    Call the LLM and force its output to conform to `schema`. Returns a
    validated instance of `schema`. Raises LLMCallError if the model cannot
    produce schema-conformant output after retries.

    Retries are handled by Instructor (github.com/jxnl/instructor): on a
    validation failure it feeds the Pydantic error back to the model as
    part of the retry request instead of blindly resending the same prompt,
    so later attempts see what was wrong with the last one.
    """
    from instructor.core.exceptions import InstructorError
    from openai import OpenAIError

    client = _client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        return client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            response_model=schema,
            max_retries=MAX_RETRIES,
            messages=messages,
        )
    except (InstructorError, OpenAIError) as exc:
        raise LLMCallError(
            f"structured_call failed after up to {MAX_RETRIES} attempts: {exc}"
        ) from exc
