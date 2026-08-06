"""Grounded medical-answer generation with per-claim source citations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any
from urllib.parse import urlparse

from langchain_core.documents import Document

from ..common.custom_exception import CustomException
from ..common.logger import get_logger
from .llm import load_llm
from .vector_store import load_vector_store

logger = get_logger(__name__)
_RETRIEVAL_COUNT = 4
_ABSTENTION = (
    "I don't have enough cited information in the medical knowledge base to answer that safely."
)
_RESPONSE_SCHEMA = {
    "title": "CitedMedicalAnswer",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "citation_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "citation_ids"],
}


@dataclass(frozen=True)
class Citation:
    id: str
    title: str
    page: int | None

    def as_dict(self) -> dict[str, str | int | None]:
        return {"id": self.id, "title": self.title, "page": self.page}


def _data_source_name(metadata: Mapping[str, Any]) -> str:
    explicit_name = metadata.get("data_source_name")
    if isinstance(explicit_name, str) and explicit_name.strip():
        return explicit_name.strip()

    source = metadata.get("source")
    if not isinstance(source, str) or not source.strip():
        return "Medical knowledge base"
    source_path = urlparse(source).path if "://" in source else source
    filename_stem = PureWindowsPath(source_path).stem
    return filename_stem.replace("_", " ").replace("-", " ").strip().title()


def _source_page(metadata: Mapping[str, Any]) -> int | None:
    page_label = metadata.get("page_label")
    if isinstance(page_label, str) and page_label.isdigit():
        return int(page_label)
    page = metadata.get("page")
    return page + 1 if isinstance(page, int) and page >= 0 else None


def _retrieved_evidence(documents: list[Document]) -> tuple[list[Citation], str]:
    citations: list[Citation] = []
    context_blocks: list[str] = []
    for index, document in enumerate(documents, start=1):
        citation = Citation(
            f"source-{index}", _data_source_name(document.metadata), _source_page(document.metadata)
        )
        citations.append(citation)
        location = citation.title if citation.page is None else f"{citation.title}, page {citation.page}"
        context_blocks.append(f"[{citation.id} | {location}]\n{document.page_content}")
    return citations, "\n\n".join(context_blocks)


def _generation_prompt(question: str, context: str) -> str:
    return f"""You are a medical-reference assistant. Answer only from the supplied evidence.
Return one concise answer and cite it with one or more source IDs from the evidence.
Do not provide an answer when its evidence is missing, uncertain, or conflicting. Do not invent source IDs.
If the evidence cannot support an answer, return an empty answer and citation_ids array.

Evidence:
{context}

Question: {question}
"""


def _abstention_response() -> dict[str, Any]:
    return {"answer": _ABSTENTION, "citations": []}


def _validated_response(result: Any, citations: list[Citation]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        return _abstention_response()
    answer = result.get("answer")
    citation_ids = result.get("citation_ids")
    if not isinstance(answer, str) or not answer.strip() or not isinstance(citation_ids, list) or not citation_ids:
        return _abstention_response()
    citations_by_id = {citation.id: citation for citation in citations}
    if not all(
        isinstance(citation_id, str) and citation_id in citations_by_id
        for citation_id in citation_ids
    ):
        return _abstention_response()
    unique_citations: list[dict[str, str | int | None]] = []
    seen_citation_locations: set[tuple[str, int | None]] = set()
    for citation_id in citation_ids:
        citation = citations_by_id[citation_id].as_dict()
        location = (citation["title"], citation["page"])
        if location not in seen_citation_locations:
            seen_citation_locations.add(location)
            unique_citations.append(citation)
    return {"answer": answer.strip(), "citations": unique_citations}


def answer_question(question: str) -> dict[str, Any]:
    """Answer only when every displayed claim cites retrieved evidence."""
    try:
        vector_store = load_vector_store()
        if vector_store is None:
            raise CustomException("Vector store not found. Please run the data processing script first.")
        documents = vector_store.similarity_search(question, k=_RETRIEVAL_COUNT)
        if not documents:
            return _abstention_response()
        citations, context = _retrieved_evidence(documents)
        structured_llm = load_llm().with_structured_output(_RESPONSE_SCHEMA)
        result = structured_llm.invoke(_generation_prompt(question, context))
        return _validated_response(result, citations)
    except CustomException:
        raise
    except Exception as exc:
        error_message = CustomException(f"Error answering cited medical question: {exc}")
        logger.error(str(error_message))
        raise error_message from exc
