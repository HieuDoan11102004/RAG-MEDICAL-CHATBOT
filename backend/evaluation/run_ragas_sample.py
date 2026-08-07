"""Run five Ragas metrics against one real response from the medical chatbot."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerCorrectness,
    AnswerRelevancy,
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)

from app.agents.rag_agent.components.retriever import answer_question
from app.agents.rag_agent.components.vector_store import load_vector_store
from app.config.config import OPENAI_EMBEDDING_MODEL, get_openai_api_key

SAMPLES_PATH = Path(__file__).with_name("medical_ragas_samples_50.json")
RETRIEVAL_COUNT = 4
EVALUATOR_MODEL = os.getenv("RAGAS_EVALUATOR_MODEL", "gpt-4.1-mini")
METRIC_TIMEOUT_SECONDS = float(os.getenv("RAGAS_METRIC_TIMEOUT_SECONDS", "90"))
RELEVANCY_STRICTNESS = int(os.getenv("RAGAS_RELEVANCY_STRICTNESS", "1"))
def select_sample() -> dict[str, Any]:
    with SAMPLES_PATH.open(encoding="utf-8") as samples_file:
        samples = json.load(samples_file)
    if not isinstance(samples, list) or not samples:
        raise ValueError("The Ragas sample dataset must be a non-empty JSON array.")
    requested_id = os.getenv("RAGAS_SAMPLE_ID")
    sample = next((item for item in samples if item.get("id") == requested_id), None) if requested_id else secrets.choice(samples)
    if sample is None:
        raise ValueError(f"No Ragas sample exists with id {requested_id!r}.")
    if not all(isinstance(sample.get(field), str) and sample[field].strip() for field in ("user_input", "reference")):
        raise ValueError("The sample must contain non-empty user_input and reference fields.")
    return sample


def retrieved_contexts(question: str) -> list[str]:
    vector_store = load_vector_store()
    if vector_store is None:
        raise RuntimeError("Vector store not found. Build it before running the evaluation.")
    return [document.page_content for document in vector_store.similarity_search(question, k=RETRIEVAL_COUNT)]


async def score_metrics(
    question: str,
    response: str,
    contexts: list[str],
    reference: str,
    api_key: str,
) -> dict[str, float | str]:
    """Score metrics one at a time to avoid provider bursts and expose timeouts."""
    client = AsyncOpenAI(api_key=api_key, timeout=METRIC_TIMEOUT_SECONDS, max_retries=1)
    evaluator_llm = llm_factory(EVALUATOR_MODEL, client=client)
    evaluator_embeddings = embedding_factory(
        "openai", model=OPENAI_EMBEDDING_MODEL, client=client
    )
    metrics_and_inputs = [
        ("faithfulness", Faithfulness(llm=evaluator_llm), {
            "user_input": question, "response": response, "retrieved_contexts": contexts,
        }),
        ("answer_relevancy", AnswerRelevancy(
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            strictness=RELEVANCY_STRICTNESS,
        ), {"user_input": question, "response": response}),
        ("context_precision", ContextPrecisionWithReference(llm=evaluator_llm), {
            "user_input": question, "reference": reference, "retrieved_contexts": contexts,
        }),
        ("context_recall", ContextRecall(llm=evaluator_llm), {
            "user_input": question, "reference": reference, "retrieved_contexts": contexts,
        }),
        ("answer_correctness", AnswerCorrectness(
            llm=evaluator_llm, embeddings=evaluator_embeddings,
        ), {"user_input": question, "response": response, "reference": reference}),
    ]
    scores: dict[str, float | str] = {}
    for name, metric, inputs in metrics_and_inputs:
        print(f"Scoring {name}...", flush=True)
        try:
            result = await asyncio.wait_for(
                metric.ascore(**inputs), timeout=METRIC_TIMEOUT_SECONDS
            )
            scores[name] = result.value
        except TimeoutError:
            scores[name] = f"timed out after {METRIC_TIMEOUT_SECONDS:g}s"
        except Exception as exc:
            scores[name] = f"failed: {type(exc).__name__}: {exc}"
    return scores


def main() -> None:
    sample = select_sample()
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to run the chatbot and Ragas evaluator.")

    question = sample["user_input"]
    chatbot_response = answer_question(question)
    response = chatbot_response["answer"]
    contexts = retrieved_contexts(question)
    if not contexts:
        raise RuntimeError("The retriever returned no contexts, so Ragas cannot score this case.")

    scores = asyncio.run(
        score_metrics(question, response, contexts, sample["reference"], api_key)
    )

    print("Sample:", sample["id"])
    print("Question:", question)
    print("Chatbot answer:", response)
    print("Citations:", chatbot_response.get("citations", []))
    print("Scores (0 to 1; higher is better):")
    for name, score in scores.items():
        print(f"  {name}: {score}")


if __name__ == "__main__":
    main()
