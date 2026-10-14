import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GENAI_BASE_URL = os.environ.get("GENAI_BASE_URL", "https://genai.rcac.purdue.edu/api")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-oss:120b")
DOCS_ROOT = Path(os.environ.get("DOCS_ROOT", "data/rcac-docs/docs"))
GENAI_API_KEY = os.environ.get("GENAI_API_KEY")

SITE_URL = "https://docs.rcac.purdue.edu"
LOG_DIR = Path("logs")
