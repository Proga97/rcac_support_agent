"""Command-line chat loop. Run with: uv run python -m app.chat"""

import time

from app import config
from app.chunker import chunk_pages
from app.llm import RateLimited, chat
from app.loader import load_pages
from app.models import Chunk
from app.prompts import SYSTEM_PROMPT, build_user_message

INCLUDE = ["services/genai"]
KEEP_LAST_MESSAGES = 6  # after the system prompt
TRIM_HISTORY = True  # set False first, to watch input tokens grow every turn

# Hand-picked for today. Run scripts/stats.py and adjust if your IDs differ.
HAND_PICKED_IDS = [
    "services/genai/api.md#rate-limits-0",
    "services/genai/api.md#authentication-0",
    "services/genai/api.md#making-a-request-0",
]


def pick_chunks(all_chunks: list[Chunk]) -> list[Chunk]:
    """Today: the same hand-picked chunks for every question. Day 2 replaces this with search."""
    by_id = {chunk.chunk_id: chunk for chunk in all_chunks}
    missing = [chunk_id for chunk_id in HAND_PICKED_IDS if chunk_id not in by_id]
    if missing:
        raise SystemExit(f"These IDs don't exist: {missing}. Check scripts/stats.py output.")
    return [by_id[chunk_id] for chunk_id in HAND_PICKED_IDS]


def trim_history(messages: list[dict]) -> list[dict]:
    """Keep the system prompt plus the last KEEP_LAST_MESSAGES messages."""
    return messages[:1] + messages[1:][-KEEP_LAST_MESSAGES:]


def ask(messages: list[dict]):
    """Call the model, retrying once after a rate limit."""
    try:
        return chat(messages)
    except RateLimited:
        print("(rate limited, waiting 5 seconds...)")
        time.sleep(5)
        return chat(messages)


def main() -> None:
    chunks = pick_chunks(chunk_pages(load_pages(config.DOCS_ROOT, INCLUDE)))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Ask about GenAI Studio. /reset clears history, /quit exits.")

    while True:
        question = input("\nyou> ").strip()
        if question == "/quit":
            break
        if question == "/reset":
            messages = messages[:1]
            print("(history cleared)")
            continue
        if not question:
            continue

        messages.append({"role": "user", "content": build_user_message(question, chunks)})
        if TRIM_HISTORY:
            messages = trim_history(messages)
        result = ask(messages)
        messages.append({"role": "assistant", "content": result.text})

        print(f"\nassistant> {result.text}")
        print(
            f"\n[{len(messages)} messages | in {result.input_tokens} tok | "
            f"out {result.output_tokens} tok | {result.latency_ms} ms]"
        )


if __name__ == "__main__":
    main()
