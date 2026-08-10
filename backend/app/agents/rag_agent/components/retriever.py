"""Grounded medical-answer generation with per-claim source citations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any
from urllib.parse import urlparse

from langchain_core.documents import Document

from ....common.custom_exception import CustomException
from ....common.logger import get_logger
from ....common.tracing import trace_retrieval
from ..prompt import build_rag_prompt
from .llm import load_llm
from .vector_store import load_vector_store

logger = get_logger(__name__)
_RETRIEVAL_COUNT = 4
_MIN_RELEVANT_DOCS = 1  # At least 1 doc must match query keywords
_MIN_KEYWORD_MATCHES = 1  # At least 1 keyword must match per doc
_ENGLISH_ABSTENTION = "I don't have enough cited information in the medical knowledge base to answer that safely."
_VIETNAMESE_ABSTENTION = "Tôi không có đủ thông tin được trích dẫn trong cơ sở kiến thức y tế để trả lời câu hỏi này một cách an toàn."
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
    source_name: str
    entry_title: str | None
    page: int | None

    def as_dict(self) -> dict[str, str | int | None]:
        title = self.source_name
        if self.entry_title:
            title = f"{self.source_name} — {self.entry_title}"
        citation: dict[str, str | int | None] = {"id": self.id, "title": title, "page": self.page}
        if self.entry_title:
            citation["source_name"] = self.source_name
            citation["entry_title"] = self.entry_title
        return citation


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


def _entry_title(metadata: Mapping[str, Any]) -> str | None:
    value = metadata.get("entry_title")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _source_page(metadata: Mapping[str, Any]) -> int | None:
    page_start = metadata.get("page_start")
    if isinstance(page_start, int) and page_start >= 1:
        return page_start
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
            f"source-{index}",
            _data_source_name(document.metadata),
            _entry_title(document.metadata),
            _source_page(document.metadata),
        )
        citations.append(citation)
        citation_data = citation.as_dict()
        location = citation_data["title"] if citation.page is None else f"{citation_data['title']}, page {citation.page}"
        context_blocks.append(f"[{citation.id} | {location}]\n{document.page_content}")
    return citations, "\n\n".join(context_blocks)


def _has_vietnamese(text: str) -> bool:
    """Detect if text contains Vietnamese characters or common Vietnamese words."""
    vietnamese_chars = set("ạăắằẳẵặâấầẩẫậđêếềểễệơớờởỡợôốồổỗộưứừửữựảẳẩẫẻỉĩịủũụỉỏọổộứừửẳ")
    vietnamese_words = ["là", "của", "và", "có", "không", "tôi", "bạn", "nên", "thế", "nào", "gì", "tôi bị", "làm gì", "như thế"]
    text_lower = text.lower()
    if any(char in text_lower for char in vietnamese_chars):
        return True
    return any(f" {word} " in f" {text_lower} " for word in vietnamese_words)


def _translate_to_english(text: str) -> str:
    """Translate Vietnamese text to English for retrieval purposes."""
    from .llm import load_llm
    try:
        llm = load_llm(temperature=0, max_tokens=200)
        prompt = f"""Translate the following text to English. Provide ONLY the English translation, no explanations, no quotes.

Text: {text}

English translation:"""
        result = llm.invoke(prompt)
        translated = result.content if hasattr(result, "content") else str(result)
        return translated.strip()
    except Exception as exc:
        logger.warning("Translation failed, using original text: %s", exc)
        return text


def _extract_keywords(text: str) -> list[str]:
    """Extract important keywords from query for relevance checking."""
    # Medical/scientific terms to always check
    medical_terms = {
        "berberine", "goldenseal", "echinacea", "aspirin", "vitamin", "mineral",
        "herb", "herbal", "supplement", "medicine", "medication", "drug", "treatment",
        "therapy", "disease", "disorder", "syndrome", "symptom", "condition",
        "patient", "health", "medical", "diabetes", "cholesterol", "blood", "heart",
        "cancer", "infection", "bacteria", "virus", "fever", "pain", "headache",
        "nausea", "allergy", "allergic", "diarrhea", "constipation", "vomiting",
        "inflammation", "immune", "digestive", "stomach", "liver", "kidney", "lung",
        "brain", "mental", "anxiety", "depression", "sleep", "weight", "diet",
        "exercise", "nutrition", "protein", "fat", "sugar", "fiber", "enzyme",
        "hormone", "thyroid", "adrenal", "testosterone", "estrogen", "insulin",
        "antibiotic", "antioxidant", "anti-inflammatory", "immune", "vaccine",
        "thuốc", "bệnh", "chữa", "trị", "đau", "sức khỏe", "y tế", "dược",
    }
    
    # Remove common stop words
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "to", "of", "in", "for", "on", "with",
        "at", "by", "from", "as", "or", "and", "but", "if", "then", "what",
        "how", "why", "when", "where", "who", "which", "this", "that", "these",
        "those", "i", "you", "he", "she", "it", "we", "they", "my", "your",
        "his", "her", "its", "our", "their", "me", "him", "us", "them",
        "về", "của", "là", "có", "và", "không", "tôi", "bạn", "được", "trong",
        "nào", "gì", "thế", "nào", "làm", "sao", "vậy", "một", "để", "cho",
        "question", "answer", "help", "tell", "know", "think", "want", "need",
    }
    
    # Extract words (2+ chars)
    words = re.findall(r'\b[a-zA-ZÀ-ỹ]{2,}\b', text.lower())
    
    # Filter and prioritize
    keywords = []
    for word in words:
        if word not in stop_words:
            # Prefer medical/scientific terms
            if word in medical_terms:
                keywords.insert(0, word)  # Prioritize medical terms
            else:
                keywords.append(word)
    
    # Deduplicate while preserving priority order
    seen = set()
    prioritized = []
    for word in keywords:
        if word not in seen:
            seen.add(word)
            prioritized.append(word)
    
    return prioritized[:15]  # Limit to top 15 keywords


def _check_document_relevance(document: Document, keywords: list[str]) -> bool:
    """Check if document is relevant to query by checking keyword matches."""
    if not keywords:
        return True  # No keywords to check, trust FAISS
    
    content_lower = document.page_content.lower()
    metadata_str = str(document.metadata).lower()
    combined = content_lower + " " + metadata_str
    
    # Count how many keywords match
    matches = sum(1 for kw in keywords if kw in combined)
    
    # Document is relevant if:
    # - Any medical term matches, OR
    # - At least 2 generic keywords match
    medical_keywords = [kw for kw in keywords if len(kw) > 5]  # Longer words = more specific
    if any(kw in combined for kw in medical_keywords):
        return True
    
    return matches >= 2


def _filter_relevant_documents(
    documents: list[Document], 
    query: str,
    retrieval_query: str
) -> list[Document]:
    """
    Filter documents to only those relevant to the query.
    Uses keyword matching to ensure retrieved docs actually discuss the query topic.
    """
    # Extract keywords from both original and translated query
    original_keywords = _extract_keywords(query)
    translated_keywords = _extract_keywords(retrieval_query)
    all_keywords = list(set(original_keywords + translated_keywords))
    
    logger.info("Relevance check keywords: %s", all_keywords[:10])
    
    # If no useful keywords extracted, trust FAISS (don't filter)
    if not all_keywords:
        logger.info("No keywords extracted, trusting FAISS retrieval")
        return documents
    
    # Filter documents
    relevant_docs = []
    for doc in documents:
        if _check_document_relevance(doc, all_keywords):
            relevant_docs.append(doc)
    
    logger.info("Relevant docs: %d/%d", len(relevant_docs), len(documents))
    
    # If ALL docs were filtered out, check if we should trust FAISS anyway
    # (this handles cases where query is too generic)
    if not relevant_docs and len(documents) > 0:
        logger.warning("All documents filtered out. Extracting medical terms only...")
        # Try with just medical terms
        medical_terms = {
            "berberine", "goldenseal", "echinacea", "aspirin", "vitamin", "herb",
            "medicine", "treatment", "disease", "health", "medical", "diabetes",
            "thuốc", "bệnh", "chữa", "trị", "đau", "sức khỏe",
        }
        query_words = set(re.findall(r'\b[a-zA-ZÀ-ỹ]{2,}\b', query.lower()))
        query_words.update(set(re.findall(r'\b[a-zA-ZÀ-ỹ]{2,}\b', retrieval_query.lower())))
        
        if query_words & medical_terms:
            # Query contains medical terms but docs don't match
            # Still abstain (high confidence the docs are wrong)
            return []
        else:
            # Generic query like "what should I do" - trust FAISS
            return documents
    
    return relevant_docs


def _abstention_response(question: str = "") -> dict[str, Any]:
    """Return abstention message in the same language as the question."""
    if _has_vietnamese(question):
        return {"answer": _VIETNAMESE_ABSTENTION, "citations": []}
    return {"answer": _ENGLISH_ABSTENTION, "citations": []}


def _validated_response(result: Any, citations: list[Citation], question: str = "") -> dict[str, Any]:
    if not isinstance(result, Mapping):
        return _abstention_response(question)
    answer = result.get("answer")
    citation_ids = result.get("citation_ids")
    if not isinstance(answer, str) or not answer.strip() or not isinstance(citation_ids, list) or not citation_ids:
        return _abstention_response(question)
    citations_by_id = {citation.id: citation for citation in citations}
    if not all(
        isinstance(citation_id, str) and citation_id in citations_by_id
        for citation_id in citation_ids
    ):
        return _abstention_response(question)
    unique_citations: list[dict[str, str | int | None]] = []
    seen_citation_locations: set[tuple[str, str | None, int | None]] = set()
    for citation_id in citation_ids:
        citation = citations_by_id[citation_id].as_dict()
        location = (citation.get("source_name", citation["title"]), citation.get("entry_title"), citation["page"])
        if location not in seen_citation_locations:
            seen_citation_locations.add(location)
            unique_citations.append(citation)
    return {"answer": answer.strip(), "citations": unique_citations}


def _parse_conversation_context(question: str) -> tuple[str, str]:
    """
    Parse conversation context from question.
    Returns (actual_question, context_summary).
    """
    context_prefix = "Previous conversation:\n"
    current_prefix = "\n\nCurrent question: "
    
    if context_prefix in question and current_prefix in question:
        parts = question.split(current_prefix, 1)
        context_part = parts[0].replace(context_prefix, "")
        actual_question = parts[1] if len(parts) > 1 else question
        return actual_question, context_part
    return question, ""


def answer_question(question: str) -> dict[str, Any]:
    """Answer only when every displayed claim cites retrieved evidence."""
    try:
        vector_store = load_vector_store()
        if vector_store is None:
            raise CustomException("Vector store not found. Please run the data processing script first.")

        # Parse conversation context if present
        actual_question, conversation_context = _parse_conversation_context(question)
        
        # Translate Vietnamese queries to English for better retrieval
        # (PDF knowledge base is in English)
        retrieval_query = actual_question
        if _has_vietnamese(actual_question):
            logger.info("Vietnamese query detected, translating to English for retrieval")
            retrieval_query = _translate_to_english(actual_question)
            # Also translate context if present
            if conversation_context:
                conversation_context = _translate_to_english(conversation_context)
            logger.info("Translated query: %s", retrieval_query)
        
        # Prepend context to retrieval query for better embedding match
        if conversation_context:
            # Combine context with question for embedding
            retrieval_query = f"{conversation_context}. {retrieval_query}"
            logger.info("Retrieval with context: %s", retrieval_query[:100])

        with trace_retrieval(query=retrieval_query) as retrieval_observation:
            documents = vector_store.similarity_search(retrieval_query, k=_RETRIEVAL_COUNT)
            if retrieval_observation is not None:
                retrieval_observation.update(
                    output={"document_count": len(documents), "requested_count": _RETRIEVAL_COUNT}
                )
        
        if not documents:
            logger.warning("No documents retrieved for query: %s", retrieval_query)
            return _abstention_response(question)
        
        # Filter to only relevant documents
        relevant_docs = _filter_relevant_documents(documents, actual_question, retrieval_query)
        
        if len(relevant_docs) < _MIN_RELEVANT_DOCS:
            logger.warning(
                "Not enough relevant documents. Query: %s, Relevant: %d/%d",
                retrieval_query, len(relevant_docs), len(documents)
            )
            return _abstention_response(question)
        
        citations, context = _retrieved_evidence(relevant_docs)
        structured_llm = load_llm().with_structured_output(_RESPONSE_SCHEMA)
        # Pass original question (not translated) so LLM responds in original language
        result = structured_llm.invoke(build_rag_prompt(question, context))
        return _validated_response(result, citations, question)
    except CustomException:
        raise
    except Exception as exc:
        error_message = CustomException(f"Error answering cited medical question: %s" % exc)
        logger.error(str(error_message))
        raise error_message from exc
