"""Chunker tests, building small Pages from strings."""

import pytest


from app.chunker import chunk_page, count_tokens, slugify, split_into_sections
from app.models import Page


def make_page(body: str) -> Page:
    return Page(
        source_path="services/genai/test.md",
        url="https://docs.rcac.purdue.edu/services/genai/test/",
        title="Test",
        tags=["Purdue GenAI Studio"],
        section="services",
        product="genai",
        body=body,
    )


def words(n: int) -> str:
    """Filler text with roughly n tokens."""
    return " ".join(f"word{i}" for i in range(n))


def test_heading_path_nests_and_resets():
    body = "# A\ntext\n## B\ntext\n### C\ntext\n## D\ntext\n"
    paths = [s.heading_path for s in split_into_sections(make_page(body))]
    assert paths == [["A"], ["A", "B"], ["A", "B", "C"], ["A", "D"]]


def test_hash_comment_in_code_block_is_not_a_heading():
    body = "# Setup\n\n```bash\n# load the module\nmodule load conda\n```\n"
    sections = split_into_sections(make_page(body))
    assert len(sections) == 1
    assert sections[0].heading_path == ["Setup"]


def test_code_block_is_never_split():
    code = "```python\n" + "\n\n".join(f"x{i} = {i}" for i in range(400)) + "\n```"
    body = f"# Big\n\n{words(50)}\n\n{code}\n"
    chunks = chunk_page(make_page(body), max_tokens=200)
    holding = [c for c in chunks if "```python" in c.text]
    assert len(holding) == 1
    assert holding[0].text.count("```") == 2  # opening and closing fence together


def test_long_section_is_split_under_max_tokens():
    body = "# Long\n\n" + "\n\n".join(words(100) for _ in range(10))
    chunks = chunk_page(make_page(body), max_tokens=300)
    assert len(chunks) > 1
    assert all(c.token_count <= 300 for c in chunks)


def test_tiny_section_is_merged_into_next():
    body = f"# Intro\nShort.\n## Details\n{words(120)}\n"
    chunks = chunk_page(make_page(body), min_tokens=50)
    assert len(chunks) == 1
    assert chunks[0].anchor == "intro"  # keeps the earlier section's anchor
    assert "Short." in chunks[0].text and "word5" in chunks[0].text


def test_chunk_ids_are_stable_across_runs():
    body = f"# A\n{words(80)}\n## B\n{words(80)}\n"
    first = [c.chunk_id for c in chunk_page(make_page(body))]
    second = [c.chunk_id for c in chunk_page(make_page(body))]
    assert first == second
    assert first[0] == "services/genai/test.md#a-0"


def test_slugify_matches_mkdocs():
    assert slugify("Rate Limits") == "rate-limits"
    assert slugify("Streaming vs Non-Streaming") == "streaming-vs-non-streaming"
    assert slugify("Speech-to-Text and Text-to-Speech") == "speech-to-text-and-text-to-speech"


def test_count_tokens_is_positive():
    assert count_tokens("hello world") > 0