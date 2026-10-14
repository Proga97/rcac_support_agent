"""Chunk and tag statistics. Run with: uv run python scripts/stats.py

Print:
  - pages and chunks
  - min, max, mean and median tokens per chunk
  - a histogram in 100-token buckets (0-100, 100-200, ...)
  - the 5 smallest and 5 largest chunks with their heading paths
  - tag coverage (loader.tag_coverage)

Then read the smallest and largest chunks by eye. That's where chunking bugs show up.
"""

import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so "app" imports work

from app import config
from app.chunker import chunk_pages
from app.loader import load_pages, tag_coverage

INCLUDE = ["services/genai"]


def show(chunk) -> str:
    return f"{chunk.token_count:5d} tok  {chunk.chunk_id}  ({' > '.join(chunk.heading_path)})"


def main() -> None:
    pages = load_pages(config.DOCS_ROOT, INCLUDE)
    chunks = chunk_pages(pages)
    sizes = [chunk.token_count for chunk in chunks]

    print(f"Pages: {len(pages)}   Chunks: {len(chunks)}")
    print(
        f"Tokens per chunk: min {min(sizes)}, max {max(sizes)}, "
        f"mean {statistics.mean(sizes):.0f}, median {statistics.median(sizes):.0f}"
    )

    print("\nHistogram (100-token buckets):")
    buckets = Counter(size // 100 for size in sizes)
    for bucket in range(max(buckets) + 1):
        count = buckets.get(bucket, 0)
        print(f"  {bucket * 100:4d}-{bucket * 100 + 99:<4d} {'#' * count} {count}")

    ordered = sorted(chunks, key=lambda chunk: chunk.token_count)
    print("\n5 smallest:")
    for chunk in ordered[:5]:
        print("  " + show(chunk))
    print("\n5 largest:")
    for chunk in ordered[-5:]:
        print("  " + show(chunk))

    duplicates = [cid for cid, n in Counter(c.chunk_id for c in chunks).items() if n > 1]
    print(f"\nDuplicate chunk IDs: {duplicates or 'none'}")

    print("\nTag coverage:")
    tag_coverage(pages)


if __name__ == "__main__":
    main()
