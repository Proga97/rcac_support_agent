import json
import time
from datetime import UTC, datetime

import httpx

from app import config
from app.models import ChatResult


class RateLimited(Exception):
    """GenAI Studio said 'slow down': an HTTP 429, or a body that decodes to null."""


# One client for the whole program, so connections are reused between calls.
_client = httpx.Client(timeout=120)  # the shared service can be slow under load


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.2) -> ChatResult:
    """Send one non-streaming chat completion and return the text, tokens and latency."""
    model = model or config.CHAT_MODEL
    body = {"model": model, "messages": messages, "temperature": temperature, "stream": False}
    headers = {"Authorization": f"Bearer {config.GENAI_API_KEY}"}

    start = time.perf_counter()
    response = _client.post(f"{config.GENAI_BASE_URL}/chat/completions", headers=headers, json=body)
    latency_ms = round((time.perf_counter() - start) * 1000)

    if response.status_code == 429:
        raise RateLimited("HTTP 429 from GenAI Studio")
    response.raise_for_status()
    data = response.json()
    if data is None:  # GenAI Studio's quiet way of saying you hit the rate limit
        raise RateLimited("GenAI Studio returned null")

    usage = data.get("usage") or {}
    result = ChatResult(
        text=data["choices"][0]["message"].get("content") or "",
        model=data.get("model", model),
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
    )
    _log_call(result, _question_preview(messages))
    return result


def _question_preview(messages: list[dict]) -> str:
    """The question part of the last user message, shortened for the log."""
    content = str(messages[-1].get("content", ""))
    return content.rsplit("Question:", 1)[-1].strip()[:120]


def _log_call(result: ChatResult, question_preview: str) -> None:
    """Append one JSON line per call to logs/llm_calls.jsonl. Never logs the API key."""
    config.LOG_DIR.mkdir(exist_ok=True)
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "question": question_preview,
    }
    with open(config.LOG_DIR / "llm_calls.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")