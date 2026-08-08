"""Unit tests for the Qdrant vector-store adapter."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from qdrant_client import models

from app.agents.rag_agent.components.vector_store import load_vector_store, save_vector_store


class QdrantVectorStoreTests(unittest.TestCase):
    @patch("app.agents.rag_agent.components.vector_store.get_embedding_model")
    @patch("app.agents.rag_agent.components.vector_store._client")
    @patch("app.agents.rag_agent.components.vector_store.QdrantVectorStore")
    def test_load_uses_existing_collection(self, vector_store, client_factory, embeddings) -> None:
        embeddings.return_value.embed_query.return_value = [0.1, 0.2]
        client = client_factory.return_value
        client.collection_exists.return_value = True
        client.get_collection.return_value.config.params.vectors = models.VectorParams(
            size=2, distance=models.Distance.COSINE
        )

        load_vector_store()

        vector_store.from_existing_collection.assert_called_once()

    @patch("app.agents.rag_agent.components.vector_store.get_embedding_model")
    @patch("app.agents.rag_agent.components.vector_store._client")
    def test_missing_collection_returns_none(self, client_factory, embeddings) -> None:
        embeddings.return_value.embed_query.return_value = [0.1, 0.2]
        client_factory.return_value.collection_exists.return_value = False

        self.assertIsNone(load_vector_store())

    @patch("app.agents.rag_agent.components.vector_store.get_embedding_model")
    @patch("app.agents.rag_agent.components.vector_store._client")
    @patch("app.agents.rag_agent.components.vector_store.QdrantVectorStore")
    def test_save_recreates_collection_and_uploads_documents(self, vector_store, client_factory, embeddings) -> None:
        embeddings.return_value.embed_query.return_value = [0.1, 0.2]
        documents = [Document(page_content="Evidence", metadata={"page": 1, "entry_title": "Topic"})]

        save_vector_store(documents)

        client_factory.return_value.recreate_collection.assert_called_once()
        vector_store.from_documents.assert_called_once()
