import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.environ.get(
    "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
)
DB_FAISS_PATH = str(PROJECT_ROOT / "vectorstore" / "db_faiss")
DATA_PATH = str(PROJECT_ROOT / "data")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
