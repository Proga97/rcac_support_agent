import re
from collections import Counter
from pathlib import Path

import yaml

from app.config import SITE_URL
from app.models import Page

FENCE_RE = re.compile(r"^\s*(```|~~~)")


def find_markdown_files(docs_root: Path, include: list[str]) -> list[Path]:
    """All .md files under docs_root whose relative path starts with one of `include`.

    Sorted, so every run processes files in the same order.
    """
    files: set[Path] = set()
    for prefix in include:
        base = docs_root / prefix
        if base.is_file():
            files.add(base)
        elif base.is_dir():
            files.update(base.rglob("*.md"))
        else:
            raise FileNotFoundError(f"Nothing at {base}. Check DOCS_ROOT and the include list.")
    return sorted(files)


def split_front_matter(text: str) -> tuple[dict, str]:
    """Return (front_matter, body). No front matter -> ({}, text)."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)  # search from 3 so empty front matter ("---\n---\n") works
    if end == -1:
        return {}, text
    data = yaml.safe_load(text[4:end])  # safe_load: plain data only, never runs code
    if not isinstance(data, dict):
        data = {}
    return data, text[end + len("\n---\n") :]


def path_to_url(source_path: str) -> str:
    """MkDocs' directory-URL rule, prefixed with config.SITE_URL.

    services/genai/api.md    -> https://docs.rcac.purdue.edu/services/genai/api/
    services/genai/index.md  -> https://docs.rcac.purdue.edu/services/genai/

    Check both cases against the live site before trusting this.
    """
    path = source_path.removesuffix(".md")
    if path == "index":
        return f"{SITE_URL}/"
    path = path.removesuffix("/index")
    return f"{SITE_URL}/{path}/"


def extract_title(front_matter: dict, body: str, source_path: str) -> str:
    """First '# ' heading outside code; else front_matter['title']; else the file name."""
    in_code = False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            in_code = not in_code
        elif not in_code and line.startswith("# "):
            return line[2:].strip()
    if front_matter.get("title"):
        return str(front_matter["title"])
    return Path(source_path).stem.replace("-", " ").replace("_", " ").title()


def load_page(docs_root: Path, file: Path) -> Page:
    """Read one file and build its Page."""
    front_matter, body = split_front_matter(file.read_text(encoding="utf-8"))
    source_path = file.relative_to(docs_root).as_posix()
    parts = source_path.split("/")

    # services/genai/api.md -> section "services", product "genai".
    # faqs.md or agentic-ai/index.md are not tied to one product -> "shared".
    section = parts[0] if len(parts) > 1 else "root"
    product = parts[1] if len(parts) > 2 else "shared"

    tags = front_matter.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    search = front_matter.get("search")
    boost = search.get("boost") if isinstance(search, dict) else None

    return Page(
        source_path=source_path,
        url=path_to_url(source_path),
        title=extract_title(front_matter, body, source_path),
        tags=[str(tag) for tag in tags],
        section=section,
        product=product,
        search_boost=boost,
        body=body,
    )


def load_pages(docs_root: Path, include: list[str]) -> list[Page]:
    """Load every page under the included folders."""
    return [load_page(docs_root, file) for file in find_markdown_files(docs_root, include)]


def tag_coverage(pages: list[Page]) -> None:
    """Print how many pages have tags, and every distinct tag with its count."""
    tagged = sum(1 for page in pages if page.tags)
    print(f"Pages: {len(pages)}, with tags: {tagged}, without: {len(pages) - tagged}")
    for tag, count in Counter(tag for page in pages for tag in page.tags).most_common():
        print(f"  {count:4d}  {tag}")
    for page in pages:
        if not page.tags:
            print(f"  (no tags) {page.source_path}")
