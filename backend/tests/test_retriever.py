"""Tests for cited medical-answer validation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.agents.rag_agent.components.retriever import Citation, _ABSTENTION, _validated_response, answer_question


class CitationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = [Document(page_content="Drink fluids.", metadata={"source": "/data/gale_medicine.pdf", "page": 2})]

    @patch("app.agents.rag_agent.components.retriever.load_llm")
    @patch("app.agents.rag_agent.components.retriever.load_vector_store")
    def test_answer_returns_retrieved_citations(self, load_store, load_llm) -> None:
        load_store.return_value.similarity_search.return_value = self.documents
        load_llm.return_value.with_structured_output.return_value.invoke.return_value = {
            "answer": "Drink fluids.", "citation_ids": ["source-1"]
        }

        response = answer_question("What should I do?")

        self.assertEqual(response["answer"], "Drink fluids.")
        self.assertEqual(response["citations"], [{"id": "source-1", "title": "Gale Medicine", "page": 3}])
        load_store.return_value.similarity_search.assert_called_once_with("What should I do?", k=4)

    @patch("app.agents.rag_agent.components.retriever.load_llm")
    @patch("app.agents.rag_agent.components.retriever.load_vector_store")
    def test_data_source_name_takes_priority_over_a_source_url(self, load_store, load_llm) -> None:
        load_store.return_value.similarity_search.return_value = [
            Document(
                page_content="This fallback sentence should not be used.",
                metadata={"source": "https://example.com/source.pdf", "page": 1, "data_source_name": "Medical Handbook"},
            )
        ]
        load_llm.return_value.with_structured_output.return_value.invoke.return_value = {
            "answer": "Drink fluids.", "citation_ids": ["source-1"]
        }

        response = answer_question("What should I do?")

        self.assertEqual(response["citations"][0]["title"], "Medical Handbook")

    @patch("app.agents.rag_agent.components.retriever.load_llm")
    @patch("app.agents.rag_agent.components.retriever.load_vector_store")
    def test_windows_source_path_is_reduced_to_its_filename(self, load_store, load_llm) -> None:
        load_store.return_value.similarity_search.return_value = [
            Document(
                page_content="Reference content.",
                metadata={"source": r"\Llmops\Rag Medical Chatbot\Data\The Gale Encyclopedia Of Medicine Second.pdf", "page": 19},
            )
        ]
        load_llm.return_value.with_structured_output.return_value.invoke.return_value = {
            "answer": "Supported claim.", "citation_ids": ["source-1"]
        }

        response = answer_question("Question")

        self.assertEqual(
            response["citations"],
            [{"id": "source-1", "title": "The Gale Encyclopedia Of Medicine Second", "page": 20}],
        )

    @patch("app.agents.rag_agent.components.retriever.load_llm")
    @patch("app.agents.rag_agent.components.retriever.load_vector_store")
    def test_gale_citation_uses_entry_title_and_start_page(self, load_store, load_llm) -> None:
        load_store.return_value.similarity_search.return_value = [
            Document(
                page_content="CPR supports breathing and circulation.",
                metadata={
                    "source": "/data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf",
                    "data_source_name": "Gale Encyclopedia of Medicine",
                    "entry_title": "Cardiopulmonary resuscitation (CPR)",
                    "page_start": 50,
                },
            )
        ]
        load_llm.return_value.with_structured_output.return_value.invoke.return_value = {
            "answer": "CPR supports breathing and circulation.",
            "citation_ids": ["source-1"],
        }

        response = answer_question("What is CPR?")

        self.assertEqual(
            response["citations"],
            [{
                "id": "source-1",
                "title": "Gale Encyclopedia of Medicine — Cardiopulmonary resuscitation (CPR)",
                "source_name": "Gale Encyclopedia of Medicine",
                "entry_title": "Cardiopulmonary resuscitation (CPR)",
                "page": 50,
            }],
        )

    def test_unknown_or_missing_citations_abstain(self) -> None:
        citations = []
        expected = {"answer": _ABSTENTION, "citations": []}
        self.assertEqual(_validated_response({"answer": "Advice", "citation_ids": ["source-1"]}, citations), expected)
        self.assertEqual(_validated_response({"answer": "Advice", "citation_ids": []}, citations), expected)

    def test_repeated_citations_are_returned_once_at_answer_end(self) -> None:
        citation = Citation("source-1", "The Gale Encyclopedia Of Medicine Second", None, 7)

        response = _validated_response(
            {"answer": "Supported answer.", "citation_ids": ["source-1", "source-1"]},
            [citation],
        )

        self.assertEqual(response["citations"], [{"id": "source-1", "title": "The Gale Encyclopedia Of Medicine Second", "page": 7}])

    @patch("app.agents.rag_agent.components.retriever.load_vector_store")
    def test_no_retrieved_evidence_abstains_without_loading_the_llm(self, load_store) -> None:
        load_store.return_value.similarity_search.return_value = []

        self.assertEqual(answer_question("Question"), {"answer": _ABSTENTION, "citations": []})
