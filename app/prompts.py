"""Prompt templates, kept out of the logic so you can change wording in one place."""

from app.models import Chunk


SYSTEM_PROMPT = (
    "You answer questions about Purdue RCAC services using only the documentation "
    "excerpts provided. Cite the excerpt IDs you used in square brackets. If the "
    "excerpts don't answer the question, say so plainly and suggest contacting "
    "rcac-help@purdue.edu. Do not use outside knowledge."
)


def format_excerpt(chunk: Chunk) -> str:
    """One labeled excerpt: its ID, its heading path, then its text."""
    return f"[{chunk.chunk_id}] {' > '.join(chunk.heading_path)}\n{chunk.text}"


def build_user_message(question: str, chunks: list[Chunk]) -> str:
    """Excerpts first, question last, so the question is the freshest thing the model reads."""
    excerpts = "\n\n".join(format_excerpt(chunk) for chunk in chunks)
    return f"Documentation excerpts:\n\n{excerpts}\n\nQuestion: {question}"