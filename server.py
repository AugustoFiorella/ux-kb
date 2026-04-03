"""
FastAPI REST API for querying the UX/UI/CX Knowledge Base RAG.
"""

from contextlib import asynccontextmanager
from typing import Annotated

import chromadb
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

class State:
    model: SentenceTransformer
    collection: chromadb.Collection


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Loading embedding model '{EMBEDDING_MODEL}' ...")
    state.model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Connecting to ChromaDB at '{CHROMA_DIR}' ...")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    state.collection = client.get_collection(COLLECTION_NAME)
    print(f"Ready — {state.collection.count()} chunks in collection.")

    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="UX KB RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    q: str
    n: int = 5


class ChunkResult(BaseModel):
    text: str
    filename: str
    title: str
    format: str
    chunk_index: int
    score: float


# ---------------------------------------------------------------------------
# Query logic (shared by GET and POST)
# ---------------------------------------------------------------------------

def _query(q: str, n: int) -> list[ChunkResult]:
    embedding = state.model.encode([q]).tolist()
    results = state.collection.query(
        query_embeddings=embedding,
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[ChunkResult] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = round(1 - dist, 4)
        chunks.append(
            ChunkResult(
                text=doc,
                filename=meta.get("filename", ""),
                title=meta.get("title", ""),
                format=meta.get("format", ""),
                chunk_index=meta.get("chunk_index", 0),
                score=score,
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "chunks": state.collection.count()}


@app.post("/query", response_model=list[ChunkResult])
def query_post(body: QueryRequest):
    return _query(body.q, body.n)


@app.get("/query", response_model=list[ChunkResult])
def query_get(
    q: Annotated[str, Query(description="Search query")],
    n: Annotated[int, Query(description="Number of results")] = 5,
):
    return _query(q, n)


@app.get("/query_ux_kb", response_model=list[ChunkResult])
def query_ux_kb(
    q: Annotated[str, Query(description="Search query")],
    n: Annotated[int, Query(description="Number of results")] = 5,
):
    return _query(q, n)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
