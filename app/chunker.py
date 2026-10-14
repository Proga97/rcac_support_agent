import re
import unicodedata
from collections import Counter

import tiktoken
from pydantic import BaseModel

from app.models import Chunk, Page, Section

_ENCODING = tiktoken.get_encoding("o200k_base")  # loaded once, not on every call

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
ADMONITION_RE = re.compile(r'^(\s*)(?:!!!|\?\?\?\+?)\s+([\w-]+)(?:\s+"([^"]*)")?\s*$')
TAB_RE = re.compile(r'^(\s*)===\+?\s+"([^"]*)"\s*$')
HTML_IMG_RE = re.compile(r"<img\b[^>]*?\balt=\"([^\"]*)\"[^>]*>", re.IGNORECASE)
MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
HTML_P_RE = re.compile(r"</?p\b[^>]*>", re.IGNORECASE)
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
ATTR_ID_RE = re.compile(r"\{\s*#([\w-]+)[^}]*\}\s*$")



def count_tokens(text: str) -> int:
    """Token count with o200k_base. For sizing chunks, not billing."""
    return len(_ENCODING.encode(text))


def slugify(heading: str) -> str:
    """The anchor MkDocs' default toc extension generates for a heading.

    "Rate Limits" -> "rate-limits". Mirrors Python-Markdown's toc.slugify.
    """
    text = LINK_RE.sub(r"\1", heading)  # [text](url) -> text
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def clean_markdown(text: str) -> str:
    """Rewrite MkDocs-only syntax into plain text a model reads well. Code blocks are untouched.

    - Admonition `!!! warning "Protect API keys"` -> `**Warning: Protect API keys**`
    - Content tab `=== "Anvil"`                   -> `**Tab: Anvil**` (keeps per-cluster answers labeled)
    - `<img alt="...">` and `![alt](src)`         -> `[Image: alt]`
    - `<p ...>` wrappers                           -> removed
    """
    out, in_code = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue
        if m := ADMONITION_RE.match(line):
            indent, kind, title = m.group(1), m.group(2).capitalize(), m.group(3)
            out.append(f"{indent}**{kind}: {title}**" if title else f"{indent}**{kind}:**")
            continue
        if m := TAB_RE.match(line):
            out.append(f"{m.group(1)}**Tab: {m.group(2)}**")
            continue
        line = HTML_IMG_RE.sub(r"[Image: \1]", line)
        line = MD_IMG_RE.sub(r"[Image: \1]", line)
        line = HTML_P_RE.sub("", line)
        out.append(line)
    return "\n".join(out)


def _has_content(section: Section) -> bool:
    """True if the section has any non-blank line besides its heading."""
    return any(line.strip() and not HEADING_RE.match(line) for line in section.lines)


def split_into_sections(page: Page) -> list[Section]:
    """Walk the body line by line and start a new section at every heading outside code."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, title) of the current heading ancestors
    slug_counts: Counter[str] = Counter()
    current = Section(
        heading_path=[page.title], level=0, anchor="", lines=[]
    )  # text before any heading
    in_code = False

    for line in page.body.split("\n"):
        if FENCE_RE.match(line):
            in_code = not in_code
            current.lines.append(line)
            continue
        match = None if in_code else HEADING_RE.match(line)
        if not match:
            current.lines.append(line)
            continue

        if _has_content(current):
            sections.append(current)
        level, raw_title = len(match.group(1)), match.group(2)

        # MkDocs anchor: an explicit {#id} wins; otherwise slugify, with _1, _2 for repeats.
        if explicit := ATTR_ID_RE.search(raw_title):
            anchor = explicit.group(1)
            title = ATTR_ID_RE.sub("", raw_title).strip()
        else:
            title = raw_title
            slug = slugify(title)
            anchor = slug if slug_counts[slug] == 0 else f"{slug}_{slug_counts[slug]}"
            slug_counts[slug] += 1
        title = LINK_RE.sub(r"\1", title).replace("`", "")

        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        current = Section(
            heading_path=[t for _, t in stack], level=level, anchor=anchor, lines=[line]
        )

    if _has_content(current):
        sections.append(current)
    return sections


def _blocks(lines: list[str]) -> list[list[str]]:
    """Group lines into paragraphs, splitting at blank lines outside code blocks."""
    blocks, current, in_code = [], [], False
    for line in lines:
        if FENCE_RE.match(line):
            in_code = not in_code
        if not in_code and not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def split_large_section(section: Section, max_tokens: int) -> list[Section]:
    """Split an oversized section at paragraph boundaries. A single huge code block stays whole."""
    if count_tokens("\n".join(section.lines)) <= max_tokens:
        return [section]
    parts: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for block in _blocks(section.lines):
        block_tokens = count_tokens("\n".join(block))
        if current and current_tokens + block_tokens > max_tokens:
            parts.append(current)
            current, current_tokens = [], 0
        current.extend(block + [""])
        current_tokens += block_tokens
    if current:
        parts.append(current)
    return [section.model_copy(update={"lines": part}) for part in parts]


def merge_small_sections(sections: list[Section], min_tokens: int) -> list[Section]:
    """Merge each small section forward into the next one.

    The merged section keeps the EARLIER section's heading path and anchor, because that
    is where its text starts on the page, so a citation link still lands at the beginning.
    A small last section is appended to the previous one instead.
    """
    result: list[Section] = []
    pending: Section | None = None
    for section in sections:
        if pending is not None:
            section = pending.model_copy(update={"lines": pending.lines + [""] + section.lines})
            pending = None
        if count_tokens("\n".join(section.lines)) < min_tokens:
            pending = section
        else:
            result.append(section)
    if pending is not None:
        if result:
            last = result[-1]
            result[-1] = last.model_copy(update={"lines": last.lines + [""] + pending.lines})
        else:
            result.append(pending)
    return result


def chunk_page(page: Page, max_tokens: int = 800, min_tokens: int = 50) -> list[Chunk]:
    """Clean -> sections -> split large -> merge small -> Chunks with stable IDs."""
    cleaned = page.model_copy(update={"body": clean_markdown(page.body)})
    sections = [
        part
        for section in split_into_sections(cleaned)
        for part in split_large_section(section, max_tokens)
    ]
    sections = merge_small_sections(sections, min_tokens)

    chunks: list[Chunk] = []
    parts_per_anchor: Counter[str] = Counter()
    for section in sections:
        text = "\n".join(section.lines).strip()
        anchor_key = section.anchor or "top"
        chunk_id = f"{page.source_path}#{anchor_key}-{parts_per_anchor[anchor_key]}"
        parts_per_anchor[anchor_key] += 1
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                source_path=page.source_path,
                url=page.url,
                title=page.title,
                tags=page.tags,
                section=page.section,
                product=page.product,
                heading_path=section.heading_path,
                anchor=section.anchor,
                text=text,
                token_count=count_tokens(text),
            )
        )
    return chunks


def chunk_pages(pages: list[Page], max_tokens: int = 800, min_tokens: int = 50) -> list[Chunk]:
    """Chunk many pages."""
    return [chunk for page in pages for chunk in chunk_page(page, max_tokens, min_tokens)]