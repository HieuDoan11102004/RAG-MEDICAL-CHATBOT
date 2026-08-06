# RAG Medical Chatbot

A medical-reference chatbot built with retrieval-augmented generation (RAG). The React frontend provides the chat experience, while the Flask backend retrieves passages from locally indexed PDFs and uses OpenAI to produce concise, context-grounded answers.

> This is an informational assistant, not a substitute for advice from a qualified healthcare professional.

## Architecture

The applications are intentionally independent:

- `frontend/` is a Vite, React, and TypeScript single-page application. It keeps the active conversation for the current browser session and calls the backend JSON API.
- `backend/` is a Flask JSON API containing the RAG pipeline, configuration, source PDFs, and FAISS vector index. It does not serve the React application.

The RAG flow is: PDF documents are split into overlapping chunks, OpenAI embeddings are stored in a FAISS index, and each prompt retrieves relevant context before the configured chat model answers.

## Data

`backend/data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf` is the initial 759-page medical reference source. Place additional PDFs in `backend/data/`, then rebuild the index. `backend/vectorstore/db_faiss/` contains derived FAISS data and must be regenerated after changing PDFs, chunking settings, or the embedding model.

Reference material can be incomplete or outdated and must not be used as the sole basis for individual medical decisions.

## Run locally

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22+, npm, and an OpenAI API key.

Create `backend/.env` with your secret (do not commit it):

```env
OPENAI_API_KEY=your_api_key
```

Start the backend in one terminal:

```bash
cd backend
uv sync
uv run python -m app.application
```

The API listens on <http://localhost:5000>. To rebuild the document index after updating PDFs, run this from `backend/`:

```bash
uv run python -m app.components.data_loader
```

Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally <http://localhost:5173>). During local development, Vite proxies `/api` requests to the backend.

## Configuration

`backend/config.yaml` contains the six non-secret RAG defaults: `openai_model`, `openai_embedding_model`, `db_faiss_path`, `data_path`, `chunk_size`, and `chunk_overlap`. Settings are selected in this order: process environment, `backend/.env`, then YAML. Relative paths resolve from `backend/`.

The frontend uses `VITE_API_BASE_URL` to select its API origin. Leave it unset for the local Vite proxy; set it to the deployed backend URL when frontend and API are served from different origins:

```env
VITE_API_BASE_URL=https://api.example.com
```

For a cross-origin deployment, set the backend process environment's comma-separated `CORS_ALLOWED_ORIGINS` allowlist to the exact frontend origins (it is intentionally separate from `backend/.env`):

```env
CORS_ALLOWED_ORIGINS=https://chat.example.com,http://localhost:5173
```

## API

| Endpoint | Request | Success response |
| --- | --- | --- |
| `GET /api/health` | None | `{ "status": "ok" }` |
| `POST /api/chat` | `{ "prompt": "medical question" }` | `{ "answer": "..." }` |

`POST /api/chat` returns `400` with `{ "error": "..." }` for blank or invalid prompts and `500` with the same error shape when the RAG pipeline cannot complete a request. The browser retains chat history for its current session; the API is stateless.

## Docker

Build each application from its own directory context:

```bash
docker build -t rag-medical-backend ./backend
docker build --build-arg VITE_API_BASE_URL=https://api.example.com -t rag-medical-frontend ./frontend
```

Run the backend with its API key and a production CORS allowlist:

```bash
docker run --rm -p 5000:5000 \
  --env-file backend/.env \
  -e CORS_ALLOWED_ORIGINS=https://chat.example.com \
  rag-medical-backend
```

The frontend image serves the built static site on port 80:

```bash
docker run --rm -p 8080:80 rag-medical-frontend
```

`VITE_API_BASE_URL` is compiled into the frontend at build time, so rebuild the frontend image when the API URL changes.

## Project layout

```text
backend/
  app/                    Flask API and RAG pipeline
  config.yaml             Non-secret backend defaults
  data/                   Source PDF documents
  vectorstore/db_faiss/   Derived FAISS index
  tests/                  Backend tests
  Dockerfile              Backend image
frontend/
  src/                    React UI, components, and API client
  Dockerfile              Static frontend image
README.md                 Project documentation
```
