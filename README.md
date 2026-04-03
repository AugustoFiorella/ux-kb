# ux-kb

Knowledge Base personal de libros de UX, UI y CX convertida en RAG. Indexa PDFs, EPUBs y otros formatos en ChromaDB y los expone via API REST y MCP Server para que Claude Code consulte la base de conocimiento automáticamente al tomar decisiones de diseño.

> Repo privado — los libros no se incluyen en el repositorio.

---

## Qué hace

Lee libros de diseño en múltiples formatos, genera embeddings y los persiste en ChromaDB. Expone el conocimiento de dos formas:

- **API REST** — consultas manuales desde el browser o cualquier cliente HTTP
- **MCP Server** — Claude Code consulta la KB automáticamente antes de tomar decisiones de UX/UI

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Vector DB | ChromaDB (persistente en disco) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| PDF | PyMuPDF (fitz) |
| EPUB | ebooklib |
| DOCX | python-docx |
| RTF | striprtf |
| API | FastAPI + Uvicorn |
| MCP | Python MCP SDK |

---

## Estructura

```
ux-kb/
├── books/          # carpeta donde van los libros (no versionada)
├── chroma_db/      # base vectorial generada por ingest.py (no versionada)
├── ingest.py       # pipeline: libros → embeddings → ChromaDB
├── server.py       # FastAPI REST API (puerto 8001)
├── mcp_server.py   # MCP Server para Claude Code
└── config.py       # configuración centralizada
```

---

## Setup

### Requisitos

- Python 3.10+
- pip

### Instalación

```bash
git clone https://github.com/AugustoFiorella/ux-kb.git
cd ux-kb

python -m venv entorno-kb
entorno-kb\Scripts\activate   # Windows
# source entorno-kb/bin/activate  # Mac/Linux

pip install chromadb sentence-transformers pymupdf ebooklib python-docx striprtf fastapi uvicorn mcp
```

### Uso

**Paso 1 — Agregar libros**

Copiar los archivos a la carpeta `books/`. Formatos soportados: `.pdf`, `.epub`, `.docx`, `.txt`, `.rtf`

**Paso 2 — Indexar**

```bash
python ingest.py
```

Detecta el formato automáticamente, extrae texto, genera embeddings y persiste en ChromaDB. Es idempotente — podés correrlo cada vez que agregues libros nuevos sin duplicar los existentes.

**Paso 3 — Levantar el servidor REST**

```bash
python server.py
```

Corre en `http://localhost:8001`. Docs interactivas en `http://localhost:8001/docs`.

**Paso 4 — Registrar el MCP en Claude Code** (una sola vez)

```bash
claude mcp add ux-kb "C:\Python314\python.exe" "D:\ruta\al\repo\mcp_server.py" --scope user
```

Verificar:

```bash
claude mcp list
```

---

## API REST

### GET /health

```bash
curl http://localhost:8001/health
# {"status": "ok", "chunks": 3473}
```

### GET /query

```bash
curl "http://localhost:8001/query?q=usability+principles&n=5"
```

### POST /query

```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"q": "principles of good user experience", "n": 5}'
```

Respuesta:

```json
[
  {
    "text": "...",
    "filename": "The UX Book.pdf",
    "title": "The UX Book",
    "format": "pdf",
    "chunk_index": 6,
    "score": 0.67
  }
]
```

---

## MCP — uso en Claude Code

Una vez registrado y con `server.py` corriendo, Claude Code consulta la KB automáticamente. También podés forzar una consulta:

```
Usá query_ux_kb para buscar "navigation patterns mobile"
```

---

## Agregar libros nuevos

1. Copiar el archivo a `books/`
2. Correr `python ingest.py`
3. Los libros existentes no se re-procesan — solo el nuevo se agrega

---

## Notas

- Los libros y `chroma_db/` están en `.gitignore` — no se versionan
- El servidor REST debe estar corriendo para que el MCP funcione
- Los embeddings se calculan localmente, sin APIs externas
- Compatible con libros en español e inglés
