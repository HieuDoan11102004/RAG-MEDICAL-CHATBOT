# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A medical-reference RAG chatbot with a React frontend and Flask backend. The backend retrieves passages from indexed PDFs using FAISS vector search and OpenAI to produce context-grounded, cited answers.

> This is an informational assistant, not a substitute for advice from a qualified healthcare professional.

## Running the Project

### Backend
```bash
cd backend
uv sync                          # Install dependencies
uv run python -m app.application # Start API on http://localhost:5000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                      # Start on http://localhost:5173
```

### Rebuilding the Vector Index
After changing PDFs, chunk settings, or embedding model:
```bash
cd backend
uv run python -m app.agents.rag_agent.components.data_loader
```

### Running Backend Tests
```bash
cd backend
uv run pytest
```

### Running Frontend Tests
```bash
cd frontend
npm run test                     # Run once
npm run test:watch               # Watch mode
```

### Docker
```bash
docker build -t rag-medical-backend ./backend
docker build --build-arg VITE_API_BASE_URL=https://api.example.com -t rag-medical-frontend ./frontend
```

## Architecture

### Monorepo Structure
The `frontend/` and `backend/` directories are intentionally independent:
- **frontend/**: React SPA built with Vite. Keeps active conversation in browser session.
- **backend/**: Flask JSON API containing the RAG pipeline, source PDFs, and FAISS index.

### Backend Architecture

```
backend/app/
├── application.py       # Flask app factory, CORS handling, API routes
├── api/
│   └── schemas.py      # Request validation for /api/messages
├── agents/
│   ├── orchestrator/   # LangGraph supervisor (Router + DirectResponder)
│   │   ├── agent.py
│   │   ├── router.py   # LLM-based route selection
│   │   └── responder.py
│   └── rag_agent/
│       ├── agent.py    # RAG agent node
│       └── components/
│           ├── retriever.py   # FAISS similarity search + answer generation
│           └── data_loader.py  # PDF chunking and indexing
├── domain/
│   └── models.py       # Pydantic dataclasses: MessageRequest, MessageResponse, RagResult
└── config.py           # YAML config loading
```

### Multi-Agent Flow (LangGraph)
1. **Router** receives user prompt → LLM selects route: `direct_response`, `rag`, `urgent_escalation`, or `clarification`
2. **DirectResponder** handles greetings, farewells, capability questions
3. **RAG Agent** retrieves 4 relevant passages from FAISS → generates cited answer
4. **Urgent Escalation** triggers for immediate-care scenarios
5. State is keyed by `conversation_id` using LangGraph's `MemorySaver` (in-memory, per-process)

### Frontend Architecture
```
frontend/src/
├── App.tsx             # Main component, conversation state
├── api/
│   └── chat.ts         # API client functions
└── components/
    ├── Sidebar.tsx     # Conversation history
    ├── MessageList.tsx # Chat messages with citations
    └── Composer.tsx    # Message input
```

## Configuration

### Backend (backend/.env)
```env
OPENAI_API_KEY=your_api_key
```
Additional optional settings in `backend/config.yaml`: `openai_model`, `openai_embedding_model`, `db_faiss_path`, `chunk_size`, `chunk_overlap`.

### Frontend
- `VITE_API_BASE_URL`: Set for production (defaults to Vite proxy in dev)

### CORS
Set `CORS_ALLOWED_ORIGINS` env var (comma-separated) on backend for cross-origin deployments.

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/application.py` | Flask app factory, API endpoints |
| `backend/app/agents/orchestrator/router.py` | LLM-based routing logic |
| `backend/app/agents/rag_agent/components/retriever.py` | FAISS retrieval + answer generation |
| `backend/app/api/schemas.py` | Request validation |
| `backend/app/domain/models.py` | Core data models |
| `frontend/src/App.tsx` | Frontend state management |
| `frontend/src/api/chat.ts` | Backend API calls |

## Important Notes

- **No authentication** is currently implemented. The API accepts optional `user_id` and `email` in requests but does not verify them. The README warns not to send real user identifiers until auth is in place.
- **Conversation state is in-memory only** - lost on backend restart.
- **PDF data source**: `backend/data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf` (759 pages)
- **FAISS index**: `backend/vectorstore/db_faiss/` - must be regenerated when PDFs change
