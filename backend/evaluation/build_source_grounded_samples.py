"""Create 50 source-grounded Ragas question/reference samples from the FAISS index."""

from __future__ import annotations

import argparse
import json
import pickle
import re
from pathlib import Path
from typing import Any

SAMPLE_TITLES = (
    "Cancer", "Cerebral palsy", "Cystic fibrosis", "Coronary artery disease",
    "Diabetes mellitus", "Colon cancer", "Cervical cancer", "Childbirth",
    "Ehlers-Danlos syndrome", "Food poisoning", "Creutzfeldt-Jakob disease",
    "Coagulation disorders", "Endometrial cancer", "Fractures", "Detoxification",
    "Chickenpox", "Chiropractic", "Down syndrome", "Eye examination",
    "Familial Mediterranean fever", "Charcot Marie Tooth disease",
    "Fetal alcohol syndrome", "Fibrocystic condition of the breast",
    "Coronary artery bypass graft surgery", "Depressive disorders",
    "Cervical spondylosis", "Cholangitis", "Cushing’s syndrome",
    "Diverticulosis and diverticulitis", "Celiac disease", "Cognitive-behavioral therapy",
    "Common cold", "Crohn’s disease", "Dialysis, kidney", "Diarrhea",
    "Chronic fatigue syndrome", "Congenital heart disease", "Dementia",
    "Escherichia coli", "Fatigue", "Cardiopulmonary resuscitation (CPR)",
    "Cesarean section", "Chemotherapy", "Chronic obstructive lung disease",
    "Dizziness", "Emphysema", "Endocarditis", "Frostbite and frostnip",
    "Constipation", "Cystitis",
)


def _reference_answer(title: str, text: str) -> str:
    """Use the first source sentence as a concise, traceable reference answer."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"(?<=[a-z])- (?=[a-z])", "", cleaned)
    cleaned = re.sub(rf"^{re.escape(title)}\s+—\s+Definition\s+", "", cleaned)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    return sentences[0]


def build_samples(index_path: Path) -> list[dict[str, Any]]:
    with index_path.open("rb") as index_file:
        docstore, _ = pickle.load(index_file)
    documents = list(docstore._dict.values())
    samples: list[dict[str, Any]] = []
    for number, title in enumerate(SAMPLE_TITLES, start=1):
        matches = [document for document in documents if document.metadata.get("entry_title") == title]
        if not matches:
            raise ValueError(f"No indexed source entry found for {title!r}.")
        document = min(matches, key=lambda item: item.metadata.get("page_start", float("inf")))
        samples.append(
            {
                "id": f"medical-{number:02d}",
                "user_input": f"What is {title}?",
                "reference": _reference_answer(title, document.page_content),
                "source_entry_title": title,
                "source_page": document.metadata.get("page_start"),
            }
        )
    return samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("medical_ragas_samples_50.json"),
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path(__file__).parents[1] / "vectorstore" / "db_faiss" / "index.pkl",
    )
    arguments = parser.parse_args()
    samples = build_samples(arguments.index)
    arguments.output.write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(samples)} source-grounded samples to {arguments.output}")


if __name__ == "__main__":
    main()
