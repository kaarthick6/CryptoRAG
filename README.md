# Cryptography-Anchored RAG Compliance System

This application indexes PDF documents, finds evidence with keyword and
semantic search, checks that every selected passage is intact, then asks
GroqCloud to answer from that verified evidence. It uses a local SHA-256 Merkle
tree and an HMAC-signed manifest. It does not use a blockchain.

## Why the system verifies evidence

A normal RAG system can return text that changed after indexing or belongs to an
old document version. Here each chunk hash is stored in SQLite and included in
a per-version Merkle tree. The expected root is also recorded in a separate
manifest signed with `MANIFEST_SIGNING_KEY`. Before generation, the app checks
the chunk's canonical hash, active version, signed root, and Merkle proof. If a
check fails, the API returns `Tampered or unverified context` and does not call
Groq.

The manifest and database are both local. This detects changes to the database
while the signing key and signed manifest remain protected. It does not protect
against an attacker who can read the signing key and replace or re-sign the
manifest. Keep the key outside source control and backups of the manifest in a
separate trusted location. Normal queries never update or re-sign the manifest.

## Architecture and request flow

1. PyMuPDF extracts text from each PDF page and retains its page number.
2. The chunker groups sentences up to the configured size and carries a small
   sentence overlap into the next chunk.
3. Sentence Transformers encodes chunks with `BAAI/bge-large-en`. The query
   embedding uses BGE's retrieval instruction.
4. Whoosh ranks text with BM25. Milvus ranks the embeddings by cosine similarity.
5. Reciprocal Rank Fusion adds `1 / (60 + rank)` for each search list and
   deduplicates stable chunk IDs. This combines rankings without mixing BM25 and
   vector score scales.
6. `BAAI/bge-reranker-base` scores question and passage pairs, then returns the
   top configured results.
7. SQLite supplies the stored expected hashes, active versions, roots, and
   inclusion proofs. The manifest HMAC authenticates each expected root.
8. Only `VerifiedChunk` objects can be formatted for the Groq LangChain client.
   Citations include the document, page number, and chunk ID.

SQLite stores document metadata, versions, chunks, expected hashes, Merkle
roots, and proofs. Whoosh and Milvus persist the two search indexes. Reingesting
the same PDF bytes is idempotent. Changed bytes create a new version and
deactivate old chunks from retrieval.

## Install

Use Python 3.11 or 3.12. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

The pinned requirements install the API, UI, PDF parser, local index clients,
and model libraries. The first embedding and reranker download their model
weights from Hugging Face and may take several minutes and several gigabytes of
disk space. Model load errors fail clearly; the app does not create placeholder
vectors.

## Configure Milvus

The app expects a reachable Milvus service. Set `MILVUS_URI` and, when needed,
`MILVUS_TOKEN`. The default URI is `http://localhost:19530`.

For local development, Milvus Lite stores data in a local file when `MILVUS_URI`
is set to a path such as `./storage/milvus.db`. Milvus documentation lists
Ubuntu and macOS as supported Milvus Lite environments; it is not supported on
Windows. On Windows, use WSL2 with Ubuntu and run the Python application in that
same WSL environment, or configure a separately managed Milvus endpoint. This
project does not use Docker. See the [Milvus Lite guide](https://milvus.io/docs/milvus_lite.md)
for the supported platforms and connection setup.

Example `.env` setting in Ubuntu/WSL:

```dotenv
MILVUS_URI=./storage/milvus.db
```

From Windows PowerShell, start Ubuntu with `wsl -d Ubuntu`, copy the project into
the Linux filesystem, then install and run it there:

```bash
mkdir -p ~/projects
cp -r /mnt/d/project/Information-Retreival ~/projects/verified-rag
cd ~/projects/verified-rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install "pymilvus[milvus-lite]==2.5.6"
test -f .env || cp .env.example .env
```

In that Linux copy, add your Groq API key and a strong `MANIFEST_SIGNING_KEY`
to `.env`, and set `MILVUS_URI=./storage/milvus.db`. The Milvus Lite client
creates and persists the local database file; there is no separate
Milvus process to start. Start FastAPI and Streamlit from WSL terminals. WSL2
forwards the local ports so the UI can be opened from the Windows browser.

The application creates its collection using the dimension reported by the
selected embedding model. An existing collection with a different dimension is
rejected.

## Configure Groq and the manifest key

Add a Groq API key to `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=llama-3.1-8b-instant
```

Generate a random 32-byte signing key in PowerShell and paste the printed value
into `.env` as `MANIFEST_SIGNING_KEY`:

```powershell
$bytes = New-Object byte[] 32
$randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$randomGenerator.GetBytes($bytes)
$randomGenerator.Dispose()
[Convert]::ToBase64String($bytes)
```

Do not commit `.env`, print the key in application logs, or expose it through the
frontend. A valid key is required for ingestion and integrity verification.
Verified evidence is transmitted to GroqCloud for inference. Review Groq's data
handling terms before uploading sensitive compliance documents.

## Add PDFs

Put PDFs in `data/compliance-documents/` or upload them from the Streamlit page.
Two sample Penal Code PDFs are included in the configured folder. Folder
ingestion can also be started in the UI or with:

```powershell
python -m scripts.ingest_documents
```

An unchanged PDF is reported as unchanged. A changed PDF creates a new version,
hashes, Merkle root, and signed manifest entry. Empty or corrupt PDFs produce a
clear error.

## Run the application

Start FastAPI from the project root:

```powershell
python -m scripts.run_backend
```

For Uvicorn's automatic reload during development, use
`uvicorn app.main:app --reload`; it uses Uvicorn's default host and port.

Start Streamlit in another terminal with the same virtual environment:

```powershell
streamlit run frontend/streamlit_app.py
```

The API is available at `http://127.0.0.1:8000`; the health endpoint is
`http://127.0.0.1:8000/health`. Main routes:

- `GET /health`
- `GET /documents`
- `POST /documents/upload`
- `POST /documents/ingest-folder`
- `GET /documents/{document_id}`
- `DELETE /documents/{document_id}`
- `POST /query`
- `GET /documents/{document_id}/integrity`
- `POST /documents/{document_id}/verify`

## Run tests and Ruff

```powershell
pytest -q
ruff check .
ruff format .
```

Tests use local temporary SQLite/Whoosh stores and mock generation. They do not
need a Groq API key or downloaded transformer models. API health tests do not
require a running Milvus service. Tests for a real Milvus server or real model
downloads should be run separately in the configured environment.

## Common problems

- **Manifest key missing/too short:** Set a random `MANIFEST_SIGNING_KEY` of at
  least 32 characters. The app fails closed if it is absent.
- **Manifest signature invalid:** Restore the separately trusted manifest and
  correct key. The query path will never automatically re-sign it.
- **Milvus unavailable:** Check `MILVUS_URI`, server status, and token. Health
  reports Milvus as unavailable and semantic search will fail rather than
  silently switch to a Python list.
- **Model download or load failed:** Check network access, disk space, and the
  configured model IDs. Search does not substitute fake embeddings.
- **Groq key missing or request failed:** Set `GROQ_API_KEY` and check provider
  access. Integrity verification still runs before any provider request.
- **PDF has no extracted text:** Scanned image-only PDFs need OCR before they
  can be indexed; OCR is not included in this project.
