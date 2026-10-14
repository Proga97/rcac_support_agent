"""Data models shared across the project."""

from pydantic import BaseModel


class Page(BaseModel):
    """One markdown file from the RCAC docs, with front matter parsed out."""

    source_path: str  # "services/genai/api.md", relative to docs/
    url: str  # "https://docs.rcac.purdue.edu/services/genai/api/"
    title: str  # "API"
    tags: list[str]  # ["Geddes", "Purdue GenAI Studio"]
    section: str  # "services"
    product: str  # "genai", or "shared" for pages that apply everywhere
    search_boost: float | None = None
    body: str  # markdown with front matter removed


class Chunk(BaseModel):
    """One retrievable piece of a Page."""

    chunk_id: str  # "services/genai/api.md#rate-limits-0"
    source_path: str
    url: str
    title: str
    tags: list[str]
    section: str
    product: str
    heading_path: list[str]  # ["API", "Rate Limits"]
    anchor: str  # "rate-limits"; empty for the top of the page
    text: str
    token_count: int

    @property
    def link(self) -> str:
        """The URL a citation should point to, including the section anchor."""
        return f"{self.url}#{self.anchor}" if self.anchor else self.url


class ChatResult(BaseModel):
    """The result of one LLM call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

class Section(BaseModel):
    """A run of lines under one heading. Internal to this module."""

    heading_path: list[str]
    level: int
    anchor: str
    lines: list[str]

