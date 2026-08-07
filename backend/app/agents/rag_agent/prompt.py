"""Prompt owned by the citation-grounded RAG agent."""

RAG_SYSTEM_PROMPT = """You are a medical-reference assistant.
Answer only from the supplied evidence. Return one concise answer and cite it with
one or more source IDs from that evidence. Do not provide an answer when evidence
is missing, uncertain, or conflicting. Never invent source IDs. If the evidence
cannot support an answer, return an empty answer and an empty citation_ids array.
"""


def build_rag_prompt(question: str, evidence: str) -> str:
    """Render the RAG agent's complete, evidence-scoped generation prompt."""
    return f"""{RAG_SYSTEM_PROMPT}

Evidence:
{evidence}

Question: {question}
"""
