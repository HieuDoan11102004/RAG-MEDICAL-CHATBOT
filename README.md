# RAG Medical Chatbot

A medical-reference chatbot built with retrieval-augmented generation (RAG). The React frontend provides the chat experience, while the Flask backend retrieves passages from locally indexed PDFs and uses OpenAI to produce concise, context-grounded answers.

> This is an informational assistant, not a substitute for advice from a qualified healthcare professional.

## Architecture

The applications are intentionally independent:

- `frontend/` is a Vite, React, and TypeScript single-page application. It keeps the active conversation for the current browser session and calls the backend JSON API.
- `backend/` is a Flask JSON API containing the RAG pipeline, configuration, and source PDFs. Qdrant stores the derived vector index. It does not serve the React application.

The RAG flow is: PDF documents are split into overlapping chunks, OpenAI embeddings are stored in a self-hosted Qdrant collection, and each prompt retrieves four relevant passages before the configured chat model returns an answer cited to those passages. Citations use the data-source name and its page number, never the source path or URL.

## Data

`backend/data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf` is the initial 759-page medical reference source. Place additional PDFs in `backend/data/`, then rebuild the Qdrant collection after changing PDFs, chunking settings, or the embedding model.

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
uv run python -m app.agents.rag_agent.components.data_loader
```

## Ragas evaluation

Ragas is an evaluation-only dependency and is not included in the deployed API bundle. Install the optional extra, then evaluate one randomly selected source-grounded sample from the 50-case dataset:

```bash
cd backend
uv sync --extra evaluation
uv run --extra evaluation python -m evaluation.run_ragas_sample
```

Set `RAGAS_SAMPLE_ID=medical-01` to run a specific sample. The 50 samples are generated from the indexed source entries with:

```bash
uv run --extra evaluation python -m evaluation.build_source_grounded_samples
```

Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally <http://localhost:5173>). During local development, Vite proxies `/api` requests to the backend.

## Configuration

`backend/config.yaml` contains the seven non-secret RAG defaults: `openai_model`, `openai_embedding_model`, `qdrant_url`, `qdrant_collection`, `data_path`, `chunk_size`, and `chunk_overlap`. Settings are selected in this order: process environment, `backend/.env`, then YAML. Relative paths resolve from `backend/`. Set `QDRANT_API_KEY` in `backend/.env`; it is intentionally not accepted in YAML.

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
| `POST /api/chat` | `{ "prompt": "medical question" }` | `{ "answer": "...", "citations": [{ "id": "source-1", "title": "...", "page": 12 }] }` |
| `POST /api/messages` | `{ "prompt": "medical question" }` | The cited answer plus `warnings` and `processing.route` from the orchestrator. |

`POST /api/chat` returns `400` with `{ "error": "..." }` for blank or invalid prompts and `500` with the same error shape when the RAG pipeline cannot complete a request. A claim is returned only when it has at least one citation to a retrieved passage; otherwise the assistant abstains. The top-level `citations` array is deduplicated and rendered once after the answer. The browser retains chat history for its current session; the API is stateless.

`POST /api/messages` is the versioned multi-agent entry point. In this initial text-only phase it validates prompts up to 4,000 characters, uses the structured LLM router to select immediate-care escalation when appropriate, and otherwise delegates to the citation-grounded RAG agent. It also accepts optional `conversation_id`, `user_id`, and `email` fields; invalid email addresses are rejected. `/api/chat` remains compatible with the original response shape.

### Multi-agent state

The orchestrator runs a LangGraph hierarchy with a shared `AgenticState`. It merges conversation messages by ID, maintains a `dialog_state` stack (`primary_assistant` → child agent → pop), and stores a separate latest execution status for each agent in `agent_states`. The current RAG agent is implemented; OCR and NER are reserved as future child-agent entries in the same state contract.

Simple greetings, farewells, and capability questions take the `direct_response` route and bypass retrieval. The structured LLM router can select the immediate-care safety route; other medical-information requests take the citation-grounded RAG route.

Every implemented agent owns its prompt in its package: `agents/orchestrator/prompt.py` and `agents/rag_agent/prompt.py`. The RAG agent's retrieval component imports its prompt from that agent package rather than owning prompt text itself.

Conversation state uses LangGraph's in-memory checkpointer and is keyed by `conversation_id`. It is therefore retained only while the backend process runs; it is not a durable medical-record store. Do not send real user identifiers or email addresses until authentication, access controls, encrypted persistence, retention limits, and privacy review are in place.

### Langfuse tracing

Langfuse tracing is opt-in. Add these values to `backend/.env` only after creating a Langfuse project:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENVIRONMENT=development
LANGFUSE_TRACE_CONTENT=false
```

Each chat turn is traced as `medical-chat-turn` and grouped by a hashed `conversation_id`; the RAG lookup is a nested `retrieve-medical-evidence` retriever observation. User and conversation identifiers are hashed before export. `LANGFUSE_TRACE_CONTENT=false` is the safe default: user prompts, model inputs, and outputs are redacted before export, while route, latency, citation count, and agent graph structure remain visible. Enable content tracing only after a privacy/compliance review.

## Docker

For the backend plus self-hosted Qdrant stack, add a strong `QDRANT_API_KEY` to `backend/.env`, then run from the repository root:

```bash
docker compose --env-file backend/.env up --build -d
docker compose --env-file backend/.env exec backend uv run python -m app.agents.rag_agent.components.data_loader
```

Qdrant is private to the Compose network and persists in the named `qdrant_storage` Docker volume. Rebuild the collection after updating source PDFs, chunk settings, or the embedding model. To intentionally discard the collection, stop the stack with `docker compose down -v` and rebuild it; this deletes all Qdrant data.

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
  tests/                  Backend tests
  Dockerfile              Backend image
frontend/
  src/                    React UI, components, and API client
  Dockerfile              Static frontend image
README.md                 Project documentation
```
