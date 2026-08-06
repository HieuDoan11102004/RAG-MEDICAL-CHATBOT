# RAG Medical Chatbot

A Flask web application that answers medical questions using retrieval-augmented generation (RAG). It retrieves relevant passages from locally indexed PDF documents with FAISS, then uses an OpenAI chat model to generate a short, context-grounded answer.

> This project is an informational assistant, not a replacement for advice from a qualified medical professional.

## Project overview

The application provides a browser-based chat interface for questions about the medical reference material stored in this repository. Instead of asking a language model to answer from general knowledge alone, it first looks up the most relevant content from the local document index. That retrieved context is passed to the model with instructions to give a concise answer based only on the supplied material.

The workflow is:

1. Ingest the PDF documents in `data/`.
2. Split their text into overlapping chunks and create OpenAI embeddings.
3. Store the embeddings in a local FAISS vector index.
4. Retrieve the closest chunk for each question and generate a response from it.

## Data

The repository includes `data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf`, a 759-page medical reference PDF used as the initial knowledge source. Additional PDF documents can be placed in `data/`; the ingestion script processes every `*.pdf` file in that directory.

The generated FAISS files in `vectorstore/db_faiss/` are derived data, not source documents. Rebuild the index after adding, removing, or changing PDFs, or after changing the embedding model. The dataset may contain material that is incomplete, dated, or unsuitable for an individual medical decision, so users should consult qualified healthcare professionals for medical guidance.

## Requirements

- Python 3.12 or newer
- An OpenAI API key
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

1. Create a `.env` file in the project root:

   ```env
   OPENAI_API_KEY=your_api_key
   # Optional model overrides
   OPENAI_MODEL=gpt-4.1-mini
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   ```

2. Install the dependencies:

   ```bash
   uv sync
   ```

3. Add one or more PDF files to `data/`, then build the FAISS vector store:

   ```bash
   uv run app/components/data_loader.py
   ```

   This creates or replaces the index under `vectorstore/db_faiss/`. Rebuild it whenever the PDFs or embedding model change.

4. Start the application:

   ```bash
   uv run app/application.py
   ```

   Open <http://localhost:5000> in a browser.

## Docker

Build and run the container after adding `.env` and building the vector store:

```bash
docker build -t rag-medical-chatbot .
docker run --rm -p 5000:5000 --env-file .env rag-medical-chatbot
```

## How it works

1. PDF files in `data/` are split into overlapping text chunks.
2. OpenAI embeddings are stored in a local FAISS index.
3. Each question retrieves the closest matching chunk.
4. The configured OpenAI chat model answers from that retrieved context.

The default retrieval count is one chunk and responses are instructed to stay within two or three lines.

## Project layout

```text
app/
  application.py        Flask routes and chat UI
  components/           PDF ingestion, embeddings, FAISS, retrieval, and LLM setup
  config/               Runtime configuration
data/                   Source PDF documents
vectorstore/db_faiss/   Generated FAISS index
```
