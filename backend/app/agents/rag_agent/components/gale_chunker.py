"""Structure-aware extraction for *Gale Encyclopedia of Medicine* PDFs.

The encyclopedia's two-column article layout and ``KEY TERMS`` sidebars make
page-level or fixed-size PDF chunking unreliable.  This module emits semantic
LangChain documents (article section or glossary) and is also executable for
producing a portable JSONL export.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

TITLE_SIZE_MIN = 14.0
SECTION_SIZE = (10.5, 11.5)
KEY_TERMS_SIZE = (12.0, 13.0)
BODY_SIZE = (9.5, 10.5)
KNOWN_SECTIONS = {
    "definition", "description", "purpose", "precautions", "preparation",
    "causes and symptoms", "causes & symptoms", "diagnosis", "treatment",
    "alternative treatment", "aftercare", "risks", "normal results",
    "abnormal results", "prognosis", "prevention", "resources",
    "key terms", "demographics", "signs and symptoms", "complications",
}
RUNNING_HEADER_RE = re.compile(r"^GALE ENCYCLOPEDIA OF MEDICINE\s*2?$|^\d{1,4}$")


@dataclass(eq=False)
class Line:
    text: str
    size: float
    top: float
    bottom: float
    x0: float
    x1: float
    column: int
    page: int  # zero-based PDF page index


@dataclass
class Article:
    title: str
    start_page: int
    end_page: int
    sections: dict[str, list[str]] = field(default_factory=dict)
    key_terms: list[str] = field(default_factory=list)
    current_section: str = "Definition"


def extract_page_lines(page, page_number: int) -> list[Line]:
    """Return lines in print reading order: left column, then right column."""
    words = page.extract_words(extra_attrs=["size", "upright"], use_text_flow=False)
    if not words:
        return []

    mid_x = page.width / 2
    buckets: dict[tuple[int, int], list[dict]] = {}
    for word in words:
        if not word["upright"]:
            # Margin furniture is encoded as individually rotated glyphs.  It
            # shares y-coordinates with body text, so retaining it corrupts
            # both section headers and prose. Entry titles also occur in the
            # normal horizontal content stream.
            continue
        column = 0 if word["x0"] < mid_x else 1
        buckets.setdefault((column, round(word["top"] / 3)), []).append(word)

    lines: list[Line] = []
    for (column, _), line_words in buckets.items():
        line_words.sort(key=lambda word: word["x0"])
        lines.append(
            Line(
                text=" ".join(word["text"] for word in line_words),
                size=round(max(word["size"] for word in line_words), 1),
                top=min(word["top"] for word in line_words),
                bottom=max(word["bottom"] for word in line_words),
                x0=min(word["x0"] for word in line_words),
                x1=max(word["x1"] for word in line_words),
                column=column,
                page=page_number,
            )
        )
    return sorted(lines, key=lambda line: (line.column, line.top, line.x0))


def classify(line: Line) -> str:
    text = line.text.strip()
    if RUNNING_HEADER_RE.match(text):
        return "skip"
    if KEY_TERMS_SIZE[0] <= line.size <= KEY_TERMS_SIZE[1] and text.upper() == "KEY TERMS":
        return "key_terms_marker"
    if line.size >= TITLE_SIZE_MIN:
        return "title"
    if SECTION_SIZE[0] <= line.size <= SECTION_SIZE[1] and text.lower().rstrip(":") in KNOWN_SECTIONS:
        return "section_header"
    if BODY_SIZE[0] <= line.size <= BODY_SIZE[1]:
        return "body"
    return "other"


def _is_noise_fragment(line: Line) -> bool:
    return line.size < 9.0 and len(line.text.replace(" ", "")) <= 4


def _containing_sidebar_rect(page, marker: Line) -> tuple[float, float, float, float] | None:
    """Find the drawn box enclosing a KEY TERMS marker, if the PDF exposes it."""
    marker_x = (marker.x0 + marker.x1) / 2
    marker_y = (marker.top + marker.bottom) / 2
    candidates = []
    for rect in page.rects:
        if not (rect["x0"] <= marker_x <= rect["x1"] and rect["top"] <= marker_y <= rect["bottom"]):
            continue
        width, height = rect["x1"] - rect["x0"], rect["bottom"] - rect["top"]
        if width >= 40 and height >= 25:
            candidates.append((width * height, rect["x0"], rect["top"], rect["x1"], rect["bottom"]))
    if not candidates:
        return None
    _, x0, top, x1, bottom = min(candidates)
    return x0, top, x1, bottom


def _glossary_lines(page, lines: list[Line]) -> dict[Line, list[Line]]:
    """Map each marker to its sidebar lines without changing body-text routing.

    Prefer the actual drawn sidebar rectangle.  Some PDF conversions omit box
    geometry; for those, use only the immediately contiguous lines in the
    marker's column and never carry state into another page.
    """
    by_marker: dict[Line, list[Line]] = {}
    for marker in (line for line in lines if classify(line) == "key_terms_marker"):
        rect = _containing_sidebar_rect(page, marker)
        if rect:
            x0, top, x1, bottom = rect
            terms = [
                line for line in lines
                if line is not marker
                and x0 <= (line.x0 + line.x1) / 2 <= x1
                and top <= (line.top + line.bottom) / 2 <= bottom
            ]
        else:
            column_lines = sorted((line for line in lines if line.column == marker.column and line.top > marker.top), key=lambda line: line.top)
            terms = []
            previous_bottom = marker.bottom
            for line in column_lines:
                # A visible vertical break is the safest fallback boundary.
                if line.top - previous_bottom > 12:
                    break
                if classify(line) in {"title", "section_header", "key_terms_marker"}:
                    break
                terms.append(line)
                previous_bottom = line.bottom
        by_marker[marker] = terms
    return by_marker


def build_articles(pdf, page_range: range) -> Iterator[Article]:
    article: Article | None = None
    pending_title: list[str] = []
    pending_page: int | None = None

    def open_pending() -> Article | None:
        nonlocal article, pending_title, pending_page
        if not pending_title:
            return article
        if article and (article.sections or article.key_terms):
            completed.append(article)
        article = Article(" ".join(pending_title), pending_page or 0, pending_page or 0)
        pending_title, pending_page = [], None
        return article

    completed: list[Article] = []
    for page_number in page_range:
        page = pdf.pages[page_number]
        lines = extract_page_lines(page, page_number)
        glossary_by_marker = _glossary_lines(page, lines)
        glossary_lines = {line for terms in glossary_by_marker.values() for line in terms}

        for line in lines:
            if line in glossary_lines:
                continue
            kind = classify(line)
            text = line.text.strip()
            if not text or kind == "skip" or (kind == "other" and _is_noise_fragment(line)):
                continue
            if kind == "title":
                pending_title.append(text)
                pending_page = page_number if pending_page is None else pending_page
                continue

            open_pending()
            if article is None:
                continue
            article.end_page = page_number

            if kind == "key_terms_marker":
                article.key_terms.extend(term.text.strip() for term in glossary_by_marker[line] if term.text.strip())
            elif kind == "section_header":
                article.current_section = text.rstrip(":").title()
            else:
                article.sections.setdefault(article.current_section, []).append(text)

        # pdfplumber lazily caches PDFMiner layout objects.  The extracted
        # Lines above are plain values, so retaining the page cache would only
        # make a 759-page source consume memory as the iterator advances.
        flush_cache = getattr(page, "flush_cache", None)
        if flush_cache:
            flush_cache()
        while completed:
            yield completed.pop(0)

    open_pending()
    while completed:
        yield completed.pop(0)
    if article and (article.sections or article.key_terms):
        yield article


def articles_to_documents(articles: Iterable[Article], source: str, max_chars: int = 1200) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=max_chars, chunk_overlap=100, separators=["\n\n", ". ", " ", ""])
    documents: list[Document] = []
    for article in articles:
        base_metadata = {
            "source": source,
            "data_source_name": "Gale Encyclopedia of Medicine",
            "entry_title": article.title,
            "page_start": article.start_page + 1,
            "page_end": article.end_page + 1,
            "chunk_strategy": "gale_semantic",
        }
        for section, paragraphs in article.sections.items():
            text = "\n\n".join(paragraphs).strip()
            if not text:
                continue
            header = f"{article.title} — {section}\n\n"
            # Split the complete content so the header counts towards the limit.
            parts = splitter.split_text(header + text) if len(header) + len(text) > max_chars else [header + text]
            for part_number, part in enumerate(parts):
                documents.append(Document(page_content=part, metadata={**base_metadata, "section": section, "type": "section", "part": part_number}))
        if article.key_terms:
            text = f"{article.title} — Key Terms\n\n" + "\n".join(article.key_terms)
            for part_number, part in enumerate(splitter.split_text(text)):
                documents.append(Document(page_content=part, metadata={**base_metadata, "section": "Key Terms", "type": "glossary", "part": part_number}))
    return documents


def load_gale_pdf(path: str | Path, max_chars: int = 1200) -> list[Document]:
    pdf_path = Path(path)
    with pdfplumber.open(pdf_path) as pdf:
        articles = list(build_articles(pdf, range(len(pdf.pages))))
    return articles_to_documents(articles, str(pdf_path), max_chars=max_chars)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python -m app.agents.rag_agent.components.gale_chunker input.pdf output.jsonl [start_page] [end_page]")
    input_path, output_path = Path(sys.argv[1]), Path(sys.argv[2])
    with pdfplumber.open(input_path) as pdf:
        start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        end = int(sys.argv[4]) if len(sys.argv) > 4 else len(pdf.pages)
        documents = articles_to_documents(build_articles(pdf, range(start, end)), str(input_path))
    with output_path.open("w", encoding="utf-8") as output:
        for document in documents:
            output.write(json.dumps({"page_content": document.page_content, "metadata": document.metadata}, ensure_ascii=False) + "\n")
    print(f"Wrote {len(documents)} chunks to {output_path}")


if __name__ == "__main__":
    main()
