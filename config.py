from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
BOOKS_DIR = BASE_DIR / "books"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# ChromaDB
COLLECTION_NAME = "ux_kb"

# Supported formats
SUPPORTED_FORMATS = {".pdf", ".epub", ".docx", ".txt", ".rtf"}
