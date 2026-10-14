"""Loader tests. Use small strings, not real files.

Each test is skipped until you write it: delete the pytest.skip line, then fill in the body.
"""

import pytest



from app.loader import extract_title, path_to_url, split_front_matter

PAGE = """---
tags:
  - Geddes
  - Purdue GenAI Studio
search:
  boost: 1
---

# API

Use the GenAI Studio API when you need a repeatable script.
"""


def test_front_matter_is_parsed_and_removed():
    front_matter, body = split_front_matter(PAGE)
    print(front_matter, body)
    assert front_matter["tags"] == ["Geddes", "Purdue GenAI Studio"]
    assert front_matter["search"]["boost"] == 1
    assert "---" not in body
    assert body.lstrip().startswith("# API")


def test_no_front_matter_returns_empty_dict_and_full_text():
    text = "# Title\n\nJust text.\n"
    print(split_front_matter(text))
    assert split_front_matter(text) == ({}, text)


def test_path_to_url_for_normal_and_index_pages():
    base = "https://docs.rcac.purdue.edu"
    print(path_to_url("services/genai/api.md"))
    assert path_to_url("services/genai/api.md") == f"{base}/services/genai/api/"
    assert path_to_url("services/genai/index.md") == f"{base}/services/genai/"
    assert path_to_url("index.md") == f"{base}/"


def test_title_comes_from_first_heading_outside_code():
    body = "```bash\n# not a title\n```\n\n# Real Title\n\ntext"
    print(extract_title({}, body, "x/y.md"))
    assert extract_title({}, body, "x/y.md") == "Real Title"