"""
Ingest pipeline: reads books from ./books, chunks them,
generates embeddings, and upserts into ChromaDB.
"""

import sys
from pathlib import Path
from typing import Generator

import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    BOOKS_DIR,
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    SUPPORTED_FORMATS,
)


# ---------------------------------------------------------------------------
# Text extraction per format
# ---------------------------------------------------------------------------

def extract_pdf(path: Path) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def extract_epub(path: Path) -> str:
    import ebooklib
    from ebooklib import epub
    from html.parser import HTMLParser

    class _StripHTML(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self._parts.append(data)

        def get_text(self) -> str:
            return " ".join(self._parts)

    book = epub.read_epub(str(path))
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        parser = _StripHTML()
        parser.feed(item.get_content().decode("utf-8", errors="ignore"))
        parts.append(parser.get_text())
    return "\n".join(parts)


def extract_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_rtf(path: Path) -> str:
    from striprtf.striprtf import rtf_to_text
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return rtf_to_text(raw)


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".epub": extract_epub,
    ".docx": extract_docx,
    ".txt": extract_txt,
    ".rtf": extract_rtf,
}


def extract_text(path: Path) -> str:
    extractor = EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        raise ValueError(f"Unsupported format: {path.suffix}")
    return extractor(path)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> Generator[str, None, None]:
    """Yield fixed-size chunks with overlap."""
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + size, text_len)
        yield text[start:end]
        if end == text_len:
            break
        start += size - overlap


# ---------------------------------------------------------------------------
# Main ingest pipeline
# ---------------------------------------------------------------------------

def ingest_book(path: Path, collection: chromadb.Collection, model: SentenceTransformer) -> int:
    """Process a single book and upsert its chunks. Returns number of chunks."""
    fmt = path.suffix.lower()
    title = path.stem

    print(f"  Extracting text...", end=" ", flush=True)
    text = extract_text(path)
    print(f"{len(text):,} chars")

    chunks = list(chunk_text(text))
    print(f"  Chunking → {len(chunks)} chunks")

    print(f"  Generating embeddings...", end=" ", flush=True)
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()
    print("done")

    ids = [f"{path.stem}__chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"filename": path.name, "title": title, "format": fmt, "chunk_index": i}
        for i in range(len(chunks))
    ]

    print(f"  Upserting to ChromaDB...", end=" ", flush=True)
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print("done")
    return len(chunks)


def main() -> None:
    BOOKS_DIR.mkdir(exist_ok=True)
    CHROMA_DIR.mkdir(exist_ok=True)

    books = [p for p in BOOKS_DIR.iterdir() if p.suffix.lower() in SUPPORTED_FORMATS]
    if not books:
        print(f"No books found in {BOOKS_DIR}. Add .pdf/.epub/.docx/.txt/.rtf files and re-run.")
        sys.exit(0)

    print(f"Found {len(books)} book(s) to ingest.\n")

    print("Loading embedding model...", end=" ", flush=True)
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("ready\n")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    total_chunks = 0
    for i, book_path in enumerate(sorted(books), 1):
        print(f"[{i}/{len(books)}] {book_path.name}")
        try:
            n = ingest_book(book_path, collection, model)
            total_chunks += n
            print(f"  OK ({n} chunks)\n")
        except Exception as exc:
            print(f"  ERROR: {exc}\n", file=sys.stderr)

    print(f"Ingest complete. Total chunks in collection: {collection.count()} (added this run: {total_chunks})")


if __name__ == "__main__":
    main()
